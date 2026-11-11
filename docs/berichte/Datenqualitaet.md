# Datenqualität und Exportnachweis

- Quellenstand **03.11.2026**, Prüfung **04.11.2026, 17:12 UTC**.
- Lauf `airflow_ad6095f4d0fe289c92ad2548`, Wiederverarbeitung von **937 HDFS-Seiten**.
- Alle SHA256-Prüfsummen entsprechen dem Manifest. Alle Seiten als striktes UTF-8 und JSON lesbar. [Manifest und Vollvergleich](../nachweise/daten/live_verification.json)

## Bestand und Änderungen

- Basis: **93.643 Rohdatensätze**, gerundet auf drei Nachkommastellen.
- Mehrere Maßnahmen pro Karte möglich.

| Prüfung oder Maßnahme | Anzahl | Anteil am Rohbestand |
| --- | ---: | ---: |
| Rohdatensätze | 93.643 | 100,000 % |
| Wegen ungültiger Pflichtfelder verworfen | 0 | 0,000 % |
| Exakte Dubletten entfernt | 0 | 0,000 % |
| Finaldatensätze und MySQL-Zeilen | 93.643 | 100,000 % |
| Fehlenden Kartentext als leeren Suchwert exportiert | 1.095 | 1,169 % |
| Fehlenden Künstler als leeren Suchwert exportiert | 9 | 0,010 % |
| Verschiedene Karten mit vereinheitlichten Suchwerten | 1.104 | 1,179 % |
| Numerische ID von Zeichenkette zu BIGINT konvertiert | 63.808 | 68,140 % |
| Fehlende numerische ID als NULL beibehalten | 29.835 | 31,860 % |
| Zulässige Bild-URL von HTTP auf HTTPS umgestellt | 63.808 | 68,140 % |
| Fehlende Bild-URL als NULL exportiert | 29.835 | 31,860 % |

- 0 Namen oder IDs mit Rand-Leerraum, 0 unbrauchbare numerische IDs, 0 unzulässige Bild-URLs.
- In sieben Quellfeldern je 0 explizite JSON-NULLs, leere Zeichenketten, reine Leerraumwerte, Unicode-Ersatzzeichen und unerwartete C0-Steuerzeichen.
- Fehlende Schlüssel separat erfasst. [Feldstatistik im Finalnachweis](../nachweise/daten/final_summary.json)
- 93.643 eindeutige IDs, 29.049 verschiedene Namen.
- 82.104 Datensätze zu 17.510 mehrfach vorkommenden Namen. Editionen und Druckvarianten anhand der API-ID getrennt.

## Vergleich von Finalbestand und MySQL

- Übereinstimmende Zeilenzahl, Feldzähler und Inhalts-Hash.
- Hash über alle neun Exportspalten: `6fd429ff102969109804ca9bf55b0f2e95012cb3841a0cdfcf29b0ea8a51f286`
- `source_json` enthält das Originalobjekt, `details_json` die bereinigte Kopie. Beide fließen in den Hash ein.
- Detailtextkorrekturen bei **166 Karten (0,177 %)**, getrennt von der Vereinheitlichung der Suchfelder erfasst. [Datenbanknachweis](../nachweise/daten/database_summary.json) · [Textprüfung](Textpruefung.md)
- Bildstatistik zählt die API-URLs. Die Erreichbarkeit zeigt sich beim Bildabruf im Browser. [Bildquellen](../Bildquellen.md)
- Konsistenzprüfung gegen die API-Quelle, aus der auch Spielregeln und Künstlerangaben stammen.
- [Befehle zur Wiederholung](../Betrieb.md)
