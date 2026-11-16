"""Card fields, transformation rules and measured data quality in one place."""

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import logging
import re
from urllib.parse import urlsplit, urlunsplit

from scripts.common import Hdfs, run_directory, save_json


WEB_CARD_FIELDS = ("name", "subtypes", "text", "flavor", "artist")
COLUMNS = ("id", "name", "subtypes", "card_text", "flavor", "artist", "image_url")
SCHEMA_VERSION = 2
FIELDS = ("id", "name", "subtypes", "text", "flavor", "artist", "imageUrl")
VERSION = "text_cleaning_v1"
RULES = {
    "control_characters": ("U+0081 / U+0090 entfernt", "entfernte Zeichen"),
    "amp_entity": ("&amp; zu & dekodiert", "ersetzte Entities"),
    "edge_spaces": ("ASCII-Leerzeichen am Rand entfernt", "entfernte Leerzeichen"),
    "zero_width_space": ("U+200B entfernt", "entfernte Zeichen"),
}
ENTITY = re.compile(r"&(?:#[0-9]+|#x[0-9A-Fa-f]+|[A-Za-z][A-Za-z0-9]*);")
MULTIPLE_ENCODING = re.compile(r"&amp;(?:#[0-9]+|#x[0-9A-Fa-f]+|[A-Za-z][A-Za-z0-9]*);")
LOG = logging.getLogger(__name__)


def reduced_card(original):
    """Select the export fields and normalize their values."""
    for field in ("id", "name", "text", "flavor", "artist", "imageUrl"):
        if original.get(field) is not None and not isinstance(original[field], str):
            raise ValueError("Expected a string for " + field)
    subtypes = original.get("subtypes")
    if subtypes is not None and (not isinstance(subtypes, list) or not all(isinstance(item, str) for item in subtypes)):
        raise ValueError("Expected a list of strings for subtypes")
    return {
        "id": original["id"].strip() if original.get("id") is not None else None,
        "name": original["name"].strip() if original.get("name") is not None else None,
        "subtypes": json.dumps(subtypes or [], ensure_ascii=False, separators=(",", ":")),
        "card_text": original.get("text") or "", "flavor": original.get("flavor") or "",
        "artist": original.get("artist") or "", "image_url": normalize_image_url(original.get("imageUrl")),
    }


def canonical_cards(page_bytes):
    """Project source cards before they enter the persisted Final data model."""
    page = json.loads(bytes(page_bytes).decode("utf-8"))
    return [json.dumps(reduced_card(card), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            for card in page["cards"]]


def clean_card(original):
    """Return a complete copy, change events and review signals; never edit original."""
    card = deepcopy(original)
    changes, warnings = [], []

    def update(container, key, field):
        value = container.get(key)
        if not isinstance(value, str):
            return
        before = value

        def record(rule, count):
            if count:
                changes.append({"rule": rule, "field": field, "operations": count})

        if field in ("foreignNames[].name", "foreignNames[].text"):
            record("control_characters", value.count("\u0081") + value.count("\u0090"))
            value = value.translate({0x81: None, 0x90: None})
        if field == "foreignNames[].text":
            if MULTIPLE_ENCODING.search(value):
                warnings.append({"field": field, "reason": "multiple_entity_encoding"})
            else:
                record("amp_entity", value.count("&amp;"))
                value = value.replace("&amp;", "&")
            if ENTITY.search(value):
                warnings.append({"field": field, "reason": "unresolved_entity"})
        if field == "rulings[].text":
            stripped = value.strip(" ")
            record("edge_spaces", len(value) - len(stripped))
            value = stripped
        if field == "originalText":
            record("zero_width_space", value.count("\u200b"))
            value = value.replace("\u200b", "")
        if value != before:
            container[key] = value

    update(card, "originalText", "originalText")
    for collection, keys in (("foreignNames", ("name", "text")), ("rulings", ("text",))):
        items = card.get(collection)
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    for key in keys:
                        update(item, key, f"{collection}[].{key}")
    return card, changes, warnings


def normalize_image_url(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = urlsplit(value.strip())
        if (parsed.scheme not in ("http", "https")
                or parsed.hostname not in ("gatherer.wizards.com", "gatherer-static.wizards.com")
                or parsed.username or parsed.password or parsed.port not in (None, 80, 443)):
            return None
        return urlunsplit(("https", parsed.hostname, parsed.path, parsed.query, ""))
    except ValueError:
        return None


def inspect_card(card, fields, changes, ids, names, image_hosts, examples):
    for field in FIELDS:
        value = card.get(field)
        metric = fields[field]
        if field not in card:
            metric["missing_key"] += 1
        elif value is None:
            metric["explicit_null"] += 1
        elif field == "subtypes":
            if isinstance(value, list) and all(isinstance(item, str) for item in value):
                metric["arrays"] += 1
                metric["empty_array"] += not value
            else:
                metric["non_string"] += 1
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
                       ("flavor", "missing_flavor_to_empty"), ("subtypes", "missing_subtypes_to_empty")):
        changed = card.get(field) is None
        changes[key] += changed
        row_changed |= changed
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
    raw_page_bytes = 0
    for index, page in enumerate(manifest["pages"], 1):
        body = hdfs.read(f"{hdfs.root}/raw/{run_id}/{page['file']}")
        raw_page_bytes += len(body)
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
        "raw_count": count, "raw_page_bytes": raw_page_bytes, "verified_sha256_pages": len(manifest["pages"]),
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


def add_audit(card, metrics, warnings, examples):
    """Accumulate raw text occurrences and distinct API IDs, without double counting cards."""
    cleaned, changes, signals = clean_card(card)
    identifier = card.get("id")
    identifier = identifier.strip() if isinstance(identifier, str) else None
    for event in changes:
        key = (event["rule"], event["field"])
        metric = metrics.setdefault(key, {"changed_values": 0, "operations": 0, "ids": set()})
        metric["changed_values"] += 1
        metric["operations"] += event["operations"]
        if identifier:
            metric["ids"].add(identifier)
        sample = examples.setdefault(event["rule"], [])
        if len(sample) < 3 and not any(item["id"] == identifier for item in sample):
            sample.append({"id": identifier, "name": card.get("name"), "field": event["field"]})
    for signal in signals:
        key = signal["field"] + ":" + signal["reason"]
        warnings[key] = warnings.get(key, 0) + 1
    return cleaned


def audit_summary(metrics, warnings, examples, raw_count):
    groups, all_ids = [], set()
    for (rule, field), metric in sorted(metrics.items()):
        all_ids.update(metric["ids"])
        groups.append({"rule": rule, "field": field, "changed_values": metric["changed_values"],
                       "operations": metric["operations"], "operation_unit": RULES[rule][1],
                       "cards": len(metric["ids"]),
                       "percent_of_raw_cards": round(100 * len(metric["ids"]) / raw_count, 6) if raw_count else 0})
    return {"version": VERSION, "raw_count": raw_count, "groups": groups,
            "changed_cards": len(all_ids),
            "percent_of_raw_cards": round(100 * len(all_ids) / raw_count, 6) if raw_count else 0,
            "review_signals": dict(warnings), "examples": dict(examples),
            "scope": "Changed text occurrences in raw cards and distinct API IDs; groups can overlap. Originals are preserved."}


def report_lines(summary):
    total = summary["raw_count"]
    percentage = lambda count: f"{100 * count / total:.3f} %".replace(".", ",") if total else "nicht berechenbar"
    lines = ["## Deterministische Bereinigung der Detailtexte", "",
             f"Regelversion: `{summary['version']}`. Bezugsgröße der Kartenanteile: {total} Rohdatensätze.",
             "Textwerte zählen einzelne Vorkommen in der Quelle; Karten zählen verschiedene API-IDs. Gruppen können sich überschneiden.", "",
             "| Regel | Quellfeld | Geänderte Textwerte | Operationen | Einheit | Verschiedene Karten | Anteil |",
             "| --- | --- | ---: | ---: | --- | ---: | ---: |"]
    for group in summary["groups"]:
        lines.append(f"| {RULES[group['rule']][0]} | {group['field']} | {group['changed_values']} | "
                     f"{group['operations']} | {group['operation_unit']} | {group['cards']} | {percentage(group['cards'])} |")
    lines += ["", f"Insgesamt verschiedene Karten mit Detailtextkorrekturen: **{summary['changed_cards']}** "
              f"(**{percentage(summary['changed_cards'])}**). Die Gruppenzahlen werden dafür nicht addiert.", "",
              "Die Originalobjekte bleiben unverändert in HDFS Raw. Die Bereinigung läuft vor der Projektion auf die sieben Finalspalten. "
              "Änderungen an verworfenen Übersetzungen und Regelhistorien zählen nur zur Quellenprüfung und werden nicht als Finaltextkorrekturen ausgegeben. "
              "Es werden keine Spielregeln umformuliert oder fehlenden Inhalte ergänzt.",
              "Mehrfach kodierte und unbekannte Entities bleiben unverändert und erzeugen Prüfsignale.", "",
              "Prüfsignale: `" + str(summary["review_signals"]) + "`.", ""]
    return lines


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
        ("Fehlender Flavourtext zu leerem Text", changes.get("missing_flavor_to_empty", 0)),
        ("Fehlende Untertypen zu leerer Liste", changes.get("missing_subtypes_to_empty", 0)),
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
        ("Fehlender Flavourtext zu leerem Text", changes.get("missing_flavor_to_empty", 0)),
        ("Fehlende Untertypen zu leerer Liste", changes.get("missing_subtypes_to_empty", 0)),
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
              "Der reduzierte Export enthält genau sieben Spalten: `id`, `name`, `subtypes`, `card_text`, `flavor`, `artist`, `image_url`. "
              "Untertypen werden als kompakte JSON-Liste gespeichert. Vollständige Kartenobjekte, Übersetzungen, Regelhistorien und Editionen "
              "bleiben ausschließlich in HDFS Raw. Der Inhalts-Hash umfasst alle sieben Exportspalten.", "",
              "Textkorrekturen an später verworfenen Feldern werden im Rohdaten-Audit separat gezählt; sie sind keine Änderungen gespeicherter Finalfelder.", "",
              "## Aussagegrenzen und Bilder", "",
              "Die Prüfung belegt Konsistenz und die beschriebenen Bereinigungsregeln. Sie beweist nicht die inhaltliche Richtigkeit jeder Spielregel oder Künstlerangabe des Anbieters. "
              "Fehlende optionale Werte werden ausgewiesen und nicht erfunden. Die Zahl der vorhandenen Bild-URLs ist keine Verfügbarkeitsprüfung aller entfernten Bilder.", "",
              "Es gibt keinen Massen-Download der Kartenbilder. Gespeichert werden URL-Zeichenketten. Die Suchseite lädt Bilder erst bei Bedarf im Browser und zeigt bei fehlenden oder nicht erreichbaren Bildern einen Platzhalter.", "",
              "Maßnahmenzahlen können sich überlappen; sie dürfen nicht zu einer Anzahl verschiedener bereinigter Karten addiert werden.", ""]
    if "text_cleaning" in summary:
        lines += report_lines(summary["text_cleaning"])
    if "reduction" in summary:
        lines += ["## Gemessene Speicherung", "", "```json",
                  json.dumps(summary["reduction"], ensure_ascii=False, indent=2), "```", "",
                  "Raw-JSON und Final-Parquet unterscheiden sich sowohl in der Feldauswahl als auch im Speicherformat. "
                  "Die Byte-Differenz misst deshalb den Gesamteffekt beider Maßnahmen.", ""]
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
