"""Audit every original HDFS page without downloading card images or guessing missing values."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import logging
import re
from urllib.parse import urlsplit

from scripts.common import Hdfs, normalize_image_url, run_directory, save_json
from scripts.text_cleaning import add_audit, audit_summary, report_lines

FIELDS = ("id", "multiverseid", "name", "text", "artist", "set", "imageUrl")
LOG = logging.getLogger(__name__)


def inspect_card(card, fields, changes, ids, names, image_hosts, examples):
    for field in FIELDS:
        value = card.get(field)
        metric = fields[field]
        if field not in card:
            metric["missing_key"] += 1
        elif value is None:
            metric["explicit_null"] += 1
        elif isinstance(value, str):
            metric["strings"] += 1
            metric["empty_string"] += value == ""
            metric["whitespace_only"] += bool(value) and not value.strip()
            metric["edge_whitespace"] += value != value.strip()
            metric["replacement_character"] += "\ufffd" in value
            metric["unexpected_control_characters"] += any(ord(c) < 32 and c not in "\n\r\t" for c in value)
            metric["max_characters"] = max(metric["max_characters"], len(value))
            metric["max_utf8_bytes"] = max(metric["max_utf8_bytes"], len(value.encode("utf-8")))
        else:
            metric["non_string"] += 1
            metric["integer_values"] += isinstance(value, int) and not isinstance(value, bool)
    identifier, name = card.get("id"), card.get("name")
    valid = isinstance(identifier, str) and bool(identifier.strip()) and isinstance(name, str) and bool(name.strip())
    changes["invalid_required_fields"] += not valid
    if not valid:
        return
    ids[identifier.strip()] += 1
    names[name.strip()] += 1
    row_changed = False
    for field, key in (("id", "id_trimmed"), ("name", "name_trimmed")):
        changed = card[field] != card[field].strip()
        changes[key] += changed
        row_changed |= changed
    for field, key in (("text", "missing_text_to_empty"), ("artist", "missing_artist_to_empty"),
                       ("set", "missing_set_to_empty")):
        changed = card.get(field) is None
        changes[key] += changed
        row_changed |= changed
    number = card.get("multiverseid")
    number_missing = number is None or (isinstance(number, str) and not number.strip())
    number_valid = (isinstance(number, (str, int)) and not isinstance(number, bool)
                    and re.fullmatch(r"[0-9]+", str(number)) is not None
                    and int(number) <= 9223372036854775807)
    changes["multiverseid_missing"] += number_missing
    changes["multiverseid_parsed_to_bigint"] += number_valid
    changes["multiverseid_string_to_integer"] += number_valid and isinstance(number, str)
    changes["multiverseid_invalid_to_null"] += not number_missing and not number_valid
    row_changed |= not number_missing and not number_valid
    changes["rows_with_value_cleaning"] += row_changed
    image = card.get("imageUrl")
    normalized = normalize_image_url(image)
    changes["image_url_available"] += normalized is not None
    changes["image_url_missing"] += image is None or image == ""
    changes["image_url_unusable"] += image is not None and image != "" and normalized is None
    changes["image_url_normalized"] += normalized is not None and image != normalized
    row_changed |= normalized is not None and image != normalized
    if normalized:
        image_hosts[urlsplit(normalized).hostname] += 1
        if len(examples["image_examples"]) < 3:
            examples["image_examples"].append({"id": identifier, "name": name, "source_url": image, "display_url": normalized})
    changes["rows_with_content_changes"] += row_changed


def audit_raw(hdfs, manifest):
    run_id = manifest["run_id"]
    if not manifest.get("download_complete") or not manifest.get("hdfs_complete"):
        raise ValueError("Audit requires a completed HDFS raw snapshot")
    fields = {name: Counter() for name in FIELDS}
    changes, ids, names, hosts = Counter(), Counter(), Counter(), Counter()
    examples = {"image_examples": []}
    text_metrics, text_warnings, text_examples = {}, {}, {}
    count = 0
    for index, page in enumerate(manifest["pages"], 1):
        body = hdfs.read(f"{hdfs.root}/raw/{run_id}/{page['file']}")
        if hashlib.sha256(body).hexdigest() != page["sha256"]:
            raise ValueError("HDFS raw checksum mismatch: " + page["file"])
        payload = json.loads(body.decode("utf-8", errors="strict"))
        cards = payload["cards"]
        if len(cards) != page["count"]:
            raise ValueError("Raw page count differs from manifest")
        for card in cards:
            inspect_card(card, fields, changes, ids, names, hosts, examples)
            add_audit(card, text_metrics, text_warnings, text_examples)
        count += len(cards)
        if index % 100 == 0:
            LOG.info("Audited %s raw pages / %s records", index, count)
    if count != manifest["raw_count"]:
        raise ValueError("Audit count differs from raw manifest")
    report = {
        "run_id": run_id, "audited_at": datetime.now(timezone.utc).isoformat(),
        "raw_count": count, "verified_sha256_pages": len(manifest["pages"]),
        "strict_utf8_pages": len(manifest["pages"]),
        "fields": {name: dict(values) for name, values in fields.items()},
        "changes": dict(changes), "distinct_ids": len(ids),
        "duplicate_id_groups": sum(n > 1 for n in ids.values()),
        "distinct_names": len(names), "repeated_name_groups": sum(n > 1 for n in names.values()),
        "records_in_repeated_name_groups": sum(n for n in names.values() if n > 1),
        "image_hosts": dict(hosts), **examples,
        "text_cleaning": audit_summary(text_metrics, text_warnings, text_examples, count),
        "scope": "All original HDFS pages and selected export fields; image URL availability is not a check of every remote image.",
    }
    save_json(run_directory(run_id) / "data_quality.json", report)
    hdfs.put(f"{hdfs.root}/raw/{run_id}/_quality.json", json.dumps(report, ensure_ascii=False).encode())
    LOG.info("Quality audit: %s records, changes=%s", count, dict(changes))
    return report


def write_quality_report(summary, database):
    quality = summary["data_quality"]
    changes = quality["changes"]
    rows = [
        ("Originalseiten mit geprüfter SHA256 und striktem UTF-8", quality["verified_sha256_pages"]),
        ("Rohdatensätze", summary["raw_count"]),
        ("Wegen Pflichtfeldern verworfen", summary["invalid_count"]),
        ("Exakte Dubletten entfernt", summary["duplicate_count"]),
        ("Finaldatensätze / MySQL-Karten", database["count"]),
        ("ID / Name am Rand getrimmt", f"{changes['id_trimmed']} / {changes['name_trimmed']}"),
        ("Fehlender Kartentext zu leerem Suchtext", changes["missing_text_to_empty"]),
        ("Fehlender Künstler zu leerem Suchtext", changes["missing_artist_to_empty"]),
        ("Fehlende multiverseid als NULL beibehalten", changes["multiverseid_missing"]),
        ("multiverseid von Zeichenkette zu BIGINT", changes["multiverseid_string_to_integer"]),
        ("Unbrauchbare multiverseid zu NULL", changes["multiverseid_invalid_to_null"]),
        ("Verschiedene Zeilen mit Wertbereinigung (ohne Typ-/Bild-URL-Umstellung)", changes["rows_with_value_cleaning"]),
        ("Mitgelieferte zulässige Bild-URLs (Schema-/Hostprüfung)", changes["image_url_available"]),
        ("Fehlende Bild-URLs", changes["image_url_missing"]),
        ("Unbrauchbare / nicht erlaubte Bild-URLs", changes["image_url_unusable"]),
        ("Bild-URLs auf HTTPS normalisiert", changes["image_url_normalized"]),
    ]
    lines = ["# Datenqualität und Exportnachweis", "", f"Lauf: `{summary['run_id']}`",
             f"Prüfung: {quality['audited_at']} (UTC).", "",
             "Alle ursprünglichen HDFS-Seiten wurden gelesen, mit ihren gespeicherten SHA256 verglichen, strikt als UTF-8 dekodiert und als JSON eingelesen.",
             "Die folgenden Zahlen sind gemessen, keine geschätzten Bereinigungsmengen.", "",
             "| Prüfung / Maßnahme | Anzahl |", "| --- | ---: |"]
    lines.extend(f"| {name} | {value} |" for name, value in rows)
    total = summary["raw_count"]
    percentage_rows = [
        ("Finaldatensätze", database["count"]),
        ("Wegen Pflichtfeldern verworfen", summary["invalid_count"]),
        ("Exakte Dubletten entfernt", summary["duplicate_count"]),
        ("Verschiedene Zeilen mit Wertbereinigung (ohne Typ-/Bild-URL-Umstellung)", changes["rows_with_value_cleaning"]),
        ("Fehlender Kartentext zu leerem Suchtext", changes["missing_text_to_empty"]),
        ("Fehlender Künstler zu leerem Suchtext", changes["missing_artist_to_empty"]),
        ("multiverseid von Zeichenkette zu BIGINT", changes["multiverseid_string_to_integer"]),
        ("Fehlende multiverseid als NULL beibehalten", changes["multiverseid_missing"]),
        ("Zulässige Bild-URL vorhanden", changes["image_url_available"]),
        ("Fehlende Bild-URL", changes["image_url_missing"]),
    ]
    lines += ["", "## Prozentanteile je Lauf", "",
              f"Bezugsgröße für jede Zeile: alle {total} Rohdatensätze dieses Laufs. Anteile sind auf drei Nachkommastellen gerundet.",
              "Die Maßnahmen überlappen sich. Diese Anteile sind kein pauschaler Qualitätswert und keine Prüfungsbewertung.", "",
              "| Prüfung / Maßnahme | Anzahl | Anteil am Rohbestand |", "| --- | ---: | ---: |"]
    for name, count in percentage_rows:
        percentage = f"{100 * count / total:.3f} %".replace(".", ",") if total else "nicht berechenbar"
        lines.append(f"| {name} | {count} | {percentage} |")
    lines += ["", "## Fehlende Felder und Zeichenprüfung", "",
              "`Fehlt` bedeutet fehlender JSON-Schlüssel; ein explizites JSON-NULL wird separat gezählt.",
              "Steuerzeichenprüfung: U+0000 bis U+001F außer Tab, LF und CR. Formatierende Zeilenumbrüche bleiben erhalten.", "",
              "| Quellfeld | Fehlt | JSON-NULL | Leere Zeichenkette | Nur Leerraum | U+FFFD | Unerwartete Steuerzeichen | Max. UTF-8-Bytes |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for field, counts in quality["fields"].items():
        values = [counts.get(key, 0) for key in ("missing_key", "explicit_null", "empty_string", "whitespace_only",
                                               "replacement_character", "unexpected_control_characters", "max_utf8_bytes")]
        lines.append(f"| {field} | " + " | ".join(map(str, values)) + " |")
    lines += ["", "## Gleiche Namen sind nicht automatisch Dubletten", "",
              f"Es gibt {quality['distinct_ids']} eindeutige Karten-IDs und {quality['distinct_names']} verschiedene Namen nach exakter Schreibweise. "
              f"{quality['records_in_repeated_name_groups']} Datensätze gehören zu {quality['repeated_name_groups']} mehrfach vorkommenden Namen. "
              "Verschiedene Editionen oder Druckvarianten werden wegen ihrer verschiedenen IDs bewusst erhalten.", "",
              "## Gegenprüfung im Export", "",
              "Die Feldzahlen werden aus dem Rohbestand unabhängig ermittelt und bei einem vollständig gültigen, eindeutigen Bestand mit PySpark verglichen. "
              "Die Datenbank muss anschließend dieselben Feldzahlen, dieselbe Zeilenzahl und denselben Inhalts-Hash wie der Finalbestand haben.", "",
              "```json", json.dumps(database["field_counts"], ensure_ascii=False, indent=2), "```", "",
              f"Kanonischer Inhalts-Hash über die Exportspalten des Finalnachweises: `{summary['sha256']}`.", "",
              "Der aktuelle Export enthält sieben Such-/Anzeigefelder, `source_json` mit dem vollständigen ursprünglichen Kartenobjekt "
              "und `details_json` mit dem vollständigen regelbasiert bereinigten Objekt. Der Inhalts-Hash umfasst alle Exportspalten. "
              "Die bisherigen Feldzähler beziehen sich auf die sieben ausgewählten Quellfelder. Die zusätzlichen Textkorrekturen werden getrennt ausgewiesen.", "",
              "## Aussagegrenzen und Bilder", "",
              "Die Prüfung belegt Konsistenz und die beschriebenen Bereinigungsregeln. Sie beweist nicht die inhaltliche Richtigkeit jeder Spielregel oder Künstlerangabe des Anbieters. "
              "Fehlende optionale Werte werden ausgewiesen und nicht erfunden. Die Zahl der vorhandenen Bild-URLs ist keine Verfügbarkeitsprüfung aller entfernten Bilder.", "",
              "Es gibt keinen Massen-Download der Kartenbilder. Gespeichert werden URL-Zeichenketten. Die Suchseite lädt Bilder erst bei Bedarf im Browser und zeigt bei fehlenden oder nicht erreichbaren Bildern einen Platzhalter.", "",
              "Maßnahmenzahlen können sich überlappen; sie dürfen nicht zu einer Anzahl verschiedener bereinigter Karten addiert werden.", ""]
    if "text_cleaning" in summary:
        lines += report_lines(summary["text_cleaning"])
    path = run_directory(summary["run_id"]) / "quality_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    options = parser.parse_args()
    run_directory(options.run_id)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    hdfs = Hdfs()
    manifest = json.loads(hdfs.read(f"{hdfs.root}/raw/{options.run_id}/_manifest.json"))
    audit_raw(hdfs, manifest)
