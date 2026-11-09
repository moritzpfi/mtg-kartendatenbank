"""Small, deterministic corrections of text defects observed in the MTG source."""

from copy import deepcopy
import re

VERSION = "text_cleaning_v1"
RULES = {
    "control_characters": ("U+0081 / U+0090 entfernt", "entfernte Zeichen"),
    "amp_entity": ("&amp; zu & dekodiert", "ersetzte Entities"),
    "edge_spaces": ("ASCII-Leerzeichen am Rand entfernt", "entfernte Leerzeichen"),
    "zero_width_space": ("U+200B entfernt", "entfernte Zeichen"),
}
ENTITY = re.compile(r"&(?:#[0-9]+|#x[0-9A-Fa-f]+|[A-Za-z][A-Za-z0-9]*);")
MULTIPLE_ENCODING = re.compile(r"&amp;(?:#[0-9]+|#x[0-9A-Fa-f]+|[A-Za-z][A-Za-z0-9]*);")


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
              "`source_json` bleibt unverändert; `details_json` enthält das vollständige bereinigte Objekt. "
              "IDs, URLs, Feldnamen und Strukturen bleiben erhalten. Es werden keine Spielregeln umformuliert oder fehlenden Inhalte ergänzt.",
              "Mehrfach kodierte und unbekannte Entities bleiben unverändert und erzeugen Prüfsignale.", "",
              "Prüfsignale: `" + str(summary["review_signals"]) + "`.", ""]
    return lines
