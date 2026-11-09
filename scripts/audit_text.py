"""Read-only text audit of a complete HDFS snapshot and its MySQL export."""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import html
import json
import logging
import re
import unicodedata

import pymysql

from scripts.common import Hdfs, connect_database, normalize_image_url, run_directory, save_json
from scripts.process_cards import COLUMNS
from scripts.text_cleaning import add_audit, audit_summary, report_lines

LOG = logging.getLogger(__name__)
PRIMARY = {"name", "text", "artist"}
TAG = re.compile(r"</?[A-Za-z][^<>]*>")
ENTITY = re.compile(r"&(?:#[0-9]{1,8}|#x[0-9A-Fa-f]{1,8}|[A-Za-z][A-Za-z0-9]{1,31});")
MOJIBAKE = re.compile(r"(?:[\u00c3\u00c2][\u0080-\u00bf]|\u00e2[\u0080-\u00bf]|\u00f0\u0178|\u00ef\u00bf\u00bd)")


def write_report(report, path):
    total = report["counts"]["raw_cards"]
    fields, cards = report["fields"], report["cards_with_flags"]
    labels = {
        "unexpected_control": "Unerwartete Steuerzeichen (C0/C1 außer LF, CR, Tab)",
        "html_entity": "Dekodierbare HTML-Entities",
        "format_character": "Unicode-Formatzeichen, z. B. unsichtbarer Abstand",
        "edge_whitespace": "Leerraum am Anfang / Ende",
        "nonbreaking_space": "Geschützte Leerzeichen (nicht automatisch fehlerhaft)",
        "empty": "Leere Zeichenketten",
        "html_tag": "Spitze Klammern mit tagähnlichem Inhalt (Prüfsignal)",
        "replacement_character": "Unicode-Ersatzzeichen U+FFFD",
        "possible_mojibake": "Verdächtige Mojibake-Muster (Heuristik)",
        "not_nfc": "Nicht in Unicode-NFC vorliegende Texte",
        "whitespace_only": "Nur Leerraum",
        "cr": "Wagenrücklauf CR", "tab": "Tabulator", "lf": "Zeilenumbruch LF (erhalten)",
    }
    number = lambda value: f"{value:,}".replace(",", ".")
    lines = ["# Textprüfung des vollständigen API-Bestands", "",
             f"Lauf: `{report['run_id']}`. Prüfung: {report['audited_at']} (UTC).", "",
             f"Geprüft wurden **{number(total)} Karten**, **{report['verified_sha256_utf8_pages']} Originalseiten** "
             f"und **{number(report['counts']['all_strings'])} Zeichenketten** einschließlich verschachtelter Übersetzungen und Regelhinweise.",
             "Jede Seite wurde anhand der Manifest-SHA256 geprüft, strikt als UTF-8 dekodiert und als JSON gelesen.", "",
             "## Hauptfelder für die Suche", "",
             f"Name, Kartentext und Künstler enthalten zusammen {number(report['counts']['primary_strings'])} vorhandene Zeichenketten. "
             f"Der Quellschlüssel `text` fehlt bei {report['missing_primary_keys'].get('text', 0)} Karten, `artist` bei "
             f"{report['missing_primary_keys'].get('artist', 0)}. Der Export verwendet dafür leere Suchtexte. Die Inhalte werden nicht erfunden.", "",
             "## Messergebnisse", "",
             f"Die Prozentanteile beziehen sich jeweils auf alle {total} Karten, nicht auf die Anzahl der Zeichenketten. "
             "Die Kategorien können sich überschneiden und dürfen nicht addiert werden. Ein Prüfsignal ist nicht automatisch ein Datenfehler.", "",
             "| Prüfung | Hauptfelder: Karten | Originalobjekte: Karten | Anteil am Rohbestand | Originale: Textwerte | Bereinigte Details: Karten |",
             "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for check, label in labels.items():
        count = cards.get("all:" + check, 0)
        percentage = f"{100 * count / total:.3f} %".replace(".", ",")
        string_count = sum(counts.get(check, 0) for counts in fields.values())
        after = report["cleaned_cards_with_flags"].get("all:" + check, 0)
        lines.append(f"| {label} | {cards.get('primary:' + check, 0)} | {count} | {percentage} | {string_count} | {after} |")
    primary_flags = sum(cards.get("primary:" + check, 0) for check in labels if check != "lf")
    lines += ["", "## Einordnung der Fundstellen", "",
              ("Die Hauptfelder `name`, `text` und `artist` zeigen außer beabsichtigten Zeilenumbrüchen keine der geprüften Auffälligkeiten."
               if primary_flags == 0 else "Die Hauptfelder enthalten Prüfsignale. Die gemessenen Feldzähler und Beispiele müssen einzeln bewertet werden."),
              "Die Tabelle unterscheidet diese Hauptfelder vom vollständigen ursprünglichen Kartenobjekt.", "",
              "- C0-/C1-Steuerzeichen außer Zeilenumbrüchen und Tabulatoren sind technische Auffälligkeiten.",
              "- Ein ausgeschriebenes `&amp;` kann in einem gelieferten Text ein noch nicht dekodiertes `&` sein.",
              "- Unicode-Formatzeichen und Rand-Leerraum brauchen eine Bewertung im jeweiligen Feld.",
              "- Ein leerer optionaler Regelhinweis wird nicht durch erfundenen Text ergänzt.",
              "- Geschützte Leerzeichen können typografisch korrekt sein, etwa vor einem französischen Doppelpunkt.",
              "- Spitze Klammern sind teilweise echter Inhalt: beispielsweise `<Token.Name=Faction>` im Anekdotentext von "
              "`Steel Overseer` oder `<sad trombone noises>` in einem Regelhinweis. Ein pauschales Entfernen vermeintlicher HTML-Tags würde Inhalt löschen.", "",
              "Die Originalfelder bleiben in Raw und `source_json` unverändert. `details_json` enthält die während der PySpark-Verarbeitung bereinigte Kopie. "
              "Die Tabelle vergleicht die Originalauffälligkeiten mit dem bereinigten Zustand. Diese lesende Prüfung selbst verändert keine Kartendaten. "
              "Das Frontend zeigt die bereinigten Detailwerte als Text an und führt sie nicht als HTML aus.", "",
              "## Gemessene Beispiele", "",
              "Die folgenden Ausschnitte stammen aus diesem Lauf. Nicht-ASCII-Zeichen erscheinen als Python-Escapes, damit unsichtbare Zeichen erkennbar sind. "
              "Die vollständigen Beispieltexte und Feldzähler stehen im JSON-Nachweis.", ""]
    for key, examples in sorted(report["examples"].items()):
        if key.endswith(":lf"):
            continue
        example = examples[0]
        snippet = ascii(example["value"][:260])
        lines += [f"- `{key}`: {example['name']} (`{example['id']}`).", "", "```text", snippet, "```", ""]
    lines += ["## Vergleich mit dem Datenbankexport", "",
              f"Verglichen wurden {report['database']['count']} MySQL-Zeilen in allen neun Spalten einschließlich `source_json` und `details_json`. "
              f"Abweichungen: **{report['database']['mismatches']}**. Fehlende erwartete IDs: **{report['database']['missing_expected_ids']}**. "
              "Die erwarteten Werte wurden direkt aus den Originalobjekten nach den dokumentierten Exportregeln berechnet. "
              "Dieser Vergleich belegt die korrekte Übernahme, nicht die Fehlerfreiheit der Quelle.", "",
              "## Wiederholen", "",
              "Die Befehle für die Prüfung des gespeicherten HDFS-Snapshots und des zugehörigen MySQL-Bestands stehen in `docs/Betrieb.md`.", "",
              "## Aussagegrenzen", "",
              "Die Prüfung erkennt die dokumentierten technischen Muster. Sie prüft nicht jede Übersetzung auf Rechtschreibung oder jede Spielregel auf fachliche Richtigkeit. "
              "Auch `originalText` kann historische Schreibweisen für Manasymbole enthalten. Umlaute, nichtlateinische Schrift, "
              "Spielzeichen wie `{U}`, `{T}` und echte Zeilenumbrüche bleiben erhalten. Null Treffer bei einem Suchmuster beweisen keine allgemeine Fehlerfreiheit.", "",
              "Maschinenlesbare Feldzähler, Zeichen-Codes und begrenzte Beispieltexte: `docs/nachweise/daten/text_audit.json`.", ""]
    lines += report_lines(report["text_cleaning"])
    path.write_text("\n".join(lines), encoding="utf-8")


def strings(value, path=""):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from strings(item, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item, path + "[]")


def flags(value):
    categories = {unicodedata.category(character) for character in value}
    return {
        "empty": value == "",
        "whitespace_only": bool(value) and not value.strip(),
        "edge_whitespace": value != value.strip(),
        "replacement_character": "\ufffd" in value,
        "unexpected_control": "Cc" in categories and any(
            unicodedata.category(character) == "Cc" and character not in "\n\r\t" for character in value),
        "format_character": "Cf" in categories,
        "html_tag": bool(TAG.search(value)),
        "html_entity": any(html.unescape(match.group()) != match.group() for match in ENTITY.finditer(value)),
        "possible_mojibake": bool(MOJIBAKE.search(value)),
        "not_nfc": not unicodedata.is_normalized("NFC", value),
        "nonbreaking_space": "\u00a0" in value or "\u202f" in value,
        "cr": "\r" in value, "tab": "\t" in value, "lf": "\n" in value,
    }


def row_hash(values):
    return hashlib.sha256(json.dumps(list(values), ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def audit(run_id):
    hdfs = Hdfs()
    manifest = json.loads(hdfs.read(f"{hdfs.root}/raw/{run_id}/_manifest.json"))
    if not manifest.get("download_complete") or not manifest.get("hdfs_complete"):
        raise ValueError("A completed raw snapshot is required")
    if manifest.get("development"):
        raise ValueError("This audit compares a complete snapshot with the published production database")
    fields, totals = defaultdict(Counter), Counter()
    after_fields, after_cards = defaultdict(Counter), Counter()
    cleaning_metrics, cleaning_warnings, cleaning_examples = {}, {}, {}
    examples, characters = defaultdict(list), defaultdict(Counter)
    expected, observed_cards = {}, Counter()
    missing = Counter()
    for index, page in enumerate(manifest["pages"], 1):
        body = hdfs.read(f"{hdfs.root}/raw/{run_id}/{page['file']}")
        if hashlib.sha256(body).hexdigest() != page["sha256"]:
            raise ValueError("Raw checksum mismatch: " + page["file"])
        cards = json.loads(body.decode("utf-8", errors="strict"))["cards"]
        if len(cards) != page["count"]:
            raise ValueError("Raw page count mismatch")
        totals["raw_cards"] += len(cards)
        for card in cards:
            cleaned = add_audit(card, cleaning_metrics, cleaning_warnings, cleaning_examples)
            after_seen = set()
            for field, value in strings(cleaned):
                after_fields[field]["strings"] += 1
                for check, found in flags(value).items():
                    if found:
                        after_fields[field][check] += 1
                        after_seen.add("all:" + check)
            after_cards.update(after_seen)
            seen = set()
            for field in PRIMARY:
                missing[field] += field not in card
            for field, value in strings(card):
                fields[field]["strings"] += 1
                totals["all_strings"] += 1
                if field in PRIMARY:
                    totals["primary_strings"] += 1
                for check, found in flags(value).items():
                    if not found:
                        continue
                    fields[field][check] += 1
                    seen.add(("all", check))
                    if field in PRIMARY:
                        seen.add(("primary", check))
                    key = field + ":" + check
                    if len(examples[key]) < 3:
                        examples[key].append({"id": card.get("id"), "name": card.get("name"), "value": value[:900]})
                for character in set(value):
                    if unicodedata.category(character) in ("Cc", "Cf", "Zs") and character not in " \n":
                        label = f"U+{ord(character):04X} {unicodedata.name(character, 'UNNAMED')}"
                        characters[field][label] += 1
            for scope, check in seen:
                observed_cards[scope + ":" + check] += 1
            identifier, name = card.get("id"), card.get("name")
            if not isinstance(identifier, str) or not identifier.strip() or not isinstance(name, str) or not name.strip():
                totals["invalid_required"] += 1
                continue
            number = card.get("multiverseid")
            number = int(number) if isinstance(number, (str, int)) and not isinstance(number, bool) and re.fullmatch(r"[0-9]+", str(number)) and int(number) <= 9223372036854775807 else None
            values = [identifier.strip(), number, name.strip(), card.get("text") or "", card.get("artist") or "",
                      card.get("set") or "", normalize_image_url(card.get("imageUrl")),
                      json.dumps(card, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                      json.dumps(cleaned, ensure_ascii=False, sort_keys=True, separators=(",", ":"))]
            digest = row_hash(values)
            if values[0] in expected:
                totals["duplicate_ids"] += 1
                if expected[values[0]] != digest:
                    raise ValueError("Conflicting raw ID: " + values[0])
            expected[values[0]] = digest
        if index % 100 == 0:
            LOG.info("Text audit: %s pages / %s cards", index, totals["raw_cards"])
    if totals["raw_cards"] != manifest["raw_count"]:
        raise ValueError("Total raw count mismatch")
    mismatches = []
    database_count = 0
    connection = connect_database()
    try:
        with connection.cursor(pymysql.cursors.SSCursor) as cursor:
            cursor.execute(f"SELECT {','.join(COLUMNS)} FROM cards ORDER BY id")
            for row in cursor:
                database_count += 1
                if expected.pop(row[0], None) != row_hash(row):
                    totals["database_mismatches"] += 1
                    if len(mismatches) < 10:
                        mismatches.append(row[0])
    finally:
        connection.close()
    report = {
        "run_id": run_id, "audited_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Every string in original and cleaned cards, including nested values. MySQL comparison covers all nine export columns; originals and cleaned details are compared separately through their expected canonical values.",
        "source": manifest["source"], "verified_sha256_utf8_pages": len(manifest["pages"]),
        "counts": dict(totals), "missing_primary_keys": dict(missing),
        "cards_with_flags": dict(observed_cards),
        "fields": {field: dict(counts) for field, counts in sorted(fields.items())},
        "cleaned_fields": {field: dict(counts) for field, counts in sorted(after_fields.items())},
        "cleaned_cards_with_flags": dict(after_cards),
        "special_characters": {field: dict(counts) for field, counts in sorted(characters.items())},
        "examples": dict(examples),
        "database": {"count": database_count, "mismatches": totals["database_mismatches"],
                     "missing_expected_ids": len(expected), "example_mismatch_ids": mismatches},
        "interpretation": "Flags are review signals, not automatic errors. Line breaks, accents, symbols and multilingual spelling can be legitimate. No source or database values were changed.",
    }
    final = json.loads(hdfs.read(f"{hdfs.root}/final/{run_id}/_summary.json"))
    report["text_cleaning"] = audit_summary(cleaning_metrics, cleaning_warnings, cleaning_examples, totals["raw_cards"])
    if report["text_cleaning"] != final["text_cleaning"]:
        raise ValueError("Independently recounted text corrections differ from the final summary")
    output = run_directory(run_id) / "text_audit.json"
    save_json(output, report)
    write_report(report, output.with_suffix(".md"))
    LOG.info("Text audit saved: %s; %s", output, report["database"])
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    options = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = audit(options.run_id)
    print(json.dumps({key: result[key] for key in ("counts", "cards_with_flags", "database")}, ensure_ascii=False, indent=2))
    if result["database"]["mismatches"] or result["database"]["missing_expected_ids"]:
        raise SystemExit("MySQL differs from the audited source snapshot")
