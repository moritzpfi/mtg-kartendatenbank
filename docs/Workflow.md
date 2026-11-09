# Workflow und Datenmodell

## Datenweg und Airflow

```text
MTG-API → HDFS raw → PySpark → HDFS final (Parquet) → MySQL → HTML-Suche
```

`dags/mtg_cards.py` führt täglich um **05:00 UTC** höchstens einen Lauf gleichzeitig aus:

| Task | Skript / Zweck |
| --- | --- |
| `fetch_to_hdfs_raw` | `fetch_cards.py`: alle Karten abrufen, Original-JSON und Manifest in HDFS sichern |
| `transform_to_hdfs_final` | `process_cards.py transform`: Rohdaten prüfen, Karten aufbereiten und Parquet schreiben |
| `validate_final` | Geschriebenes Parquet erneut lesen und Mengen/Inhalte prüfen |
| `load_database` | Staging laden und prüfen, anschließend transaktional veröffentlichen |
| `validate_database` | Export mit Finalbestand vergleichen und Qualitätsbericht erzeugen |

## Quelle und Raw Layer

Quelle: `https://api.magicthegathering.io/v1/cards`. Der Abruf nutzt `pageSize=100`, folgt den Next-Links und prüft fortlaufende Seiten sowie die gemeldete Gesamtzahl. Ändert sich `Total-Count` während des Abrufs oder weicht die Endsumme ab, wird kein Bestand veröffentlicht. Fehlt dieser Header, wird dies dokumentiert und das Ende über die Next-Links bestimmt. Eine veränderliche externe API bietet keinen transaktionalen Snapshot über alle Abrufzeitpunkte.

Originale Antwortbytes liegen unter `/user/hadoop/mtg/raw/<lauf-id>/`. Das Manifest protokolliert Zeitraum, Kartenzahl und SHA256 je Datei. Die Transformation prüft alle Seiten erneut auf Prüfsumme, UTF-8 und gültiges JSON. Vorübergehende HTTP-Fehler werden begrenzt wiederholt, Rate-Limits berücksichtigt. Unvollständige Downloads bleiben unvollständig markiert.

Die lokale Arbeitsablage erlaubt die Wiederaufnahme. Eine neue Run-ID startet einen neuen Abruf. Bei derselben Run-ID verwendet der Workflow einen abgeschlossenen Download erneut.

## Finalmodell

Eine Zeile entspricht einer API-ID. Verschiedene Editionen können denselben Namen haben und bleiben getrennt. PySpark bewahrt jedes vollständige Objekt und erzeugt neun Exportspalten:

| Spalte | Aufbereitung |
| --- | --- |
| `id` | Pflichtschlüssel, Rand-Leerraum entfernen, maximal 128 Zeichen |
| `multiverseid` | Optionale numerische ID zu BIGINT, fehlend oder unbrauchbar zu NULL |
| `name` | Pflichtname, Rand-Leerraum entfernen |
| `card_text` | API-`text`, fehlend zu leerem Suchtext |
| `artist` | Fehlend zu leerem Suchtext |
| `set_code` | API-`set`, fehlend zu leerem Text |
| `image_url` | Nur zulässige Wizards-Bildquelle, HTTP zu HTTPS, sonst NULL |
| `source_json` | Vollständiges ursprüngliches Objekt, einschließlich unbekannter und verschachtelter Felder |
| `details_json` | Vollständige bereinigte Kopie für die Detailanzeige |

Datensätze ohne gültige ID oder Namen werden gezählt und ausgeschlossen. Exakt identische Datensätze werden dedupliziert. Unterschiedliche Inhalte mit derselben ID stoppen die Transformation. Neue Finalbestände benötigen für jede Karte gültige Original- und Detailobjekte.

Parquet liegt unter `/user/hadoop/mtg/final/<lauf-id>/`. `_summary.json` enthält Mengen, Regeln und den kanonischen Inhalts-Hash über alle neun Spalten. Die Bilanz lautet: Rohdatensätze = ungültige Datensätze + entfernte Dubletten + Finaldatensätze.

## Deterministische Textbereinigung

`text_cleaning_v1` wendet diese Regeln mit der Python-Standardbibliothek auf eine Kopie an.

| Feld | Regel |
| --- | --- |
| `foreignNames[].name`, `foreignNames[].text` | Nachgewiesene Zeichen U+0081/U+0090 entfernen |
| `foreignNames[].text` | Einfach kodiertes `&amp;` einmal zu `&` dekodieren |
| `rulings[].text` | ASCII-Leerzeichen am Anfang und Ende entfernen |
| `originalText` | Nachgewiesenes U+200B entfernen |

Manasymbole, Zeilenumbrüche, Akzente, asiatische Schrift, geschützte Leerzeichen und bedeutungstragende spitze Klammern bleiben erhalten. Mehrfach kodierte oder unbekannte Entities bleiben als Prüfsignale stehen. [Messwerte und Fundstellen](berichte/Textpruefung.md)

## Prüfung und Veröffentlichung

Der Rohdaten-Audit zählt Feldwerte unabhängig. Finalvalidierung und Datenbankvergleich verlangen gleiche Zeilenzahl, Feldzahlen und Inhaltsprüfsumme. Die zusätzliche Textprüfung berechnet die erwarteten neun Exportwerte aus jedem Originalobjekt und vergleicht alle Datenbankzeilen.

MySQL verwendet `cards_staging` und `cards`, jeweils mit eigener DDL. Der Loader verarbeitet Pakete von 1.000 Zeilen, prüft Staging und ersetzt `cards` anschließend innerhalb einer Transaktion. Vor dem Commit werden Menge und Inhalt nochmals geprüft. Fehler lösen ein Rollback aus; der bisherige Suchbestand bleibt erhalten. Begrenzte Abrufe und absichtliche Exportfehler sind ausschließlich in `mtg_test` erlaubt.

Jeder erfolgreiche Lauf erzeugt `final_summary.json`, `database_summary.json` und `quality_report.md` im Arbeitsverzeichnis. Die [Abnahme](berichte/Abnahme.md) dokumentiert einen konkreten geprüften Lauf. Neue Abrufe können andere Zahlen ergeben.

## Webanwendung

Ein Suchfeld durchsucht Name, Text und Künstler gemeinsam mit parametrisierter SQL-Suche. `LIKE '%Suchtext%'` findet zusammenhängende Teiltexte mitten im Satz. SQL-Wildcards werden wörtlich maskiert. Die Suche ignoriert Groß-/Kleinschreibung, begrenzt die Ausgabe auf 50 Karten und weist auf weitere Treffer hin.

Das Backend liest ausschließlich MySQL. Erst beim Aufklappen lädt `GET /cards/<id>` das vollständige `details_json` als `{"card": …}`. Unbekannte Felder und verschachtelte Listen bleiben sichtbar. HTML erscheint als Text; Zahlen wie 0 und boolesche Werte bleiben erhalten. Datenbankfehler ergeben HTTP 503, überlange Suchbegriffe HTTP 400.

Auf der Startseite steht die Suche mittig, bei Treffern steht sie oben. Der Umschalter für Hell und Dunkel speichert die Einstellung im Browser. Kartenbilder lassen sich per Klick vergrößern und mit Escape schließen. Bei fehlenden oder defekten Bildern erscheint die lokale Kartenrückseite. [Bildquellen](Bildquellen.md)

## Betriebsumfang

Eine VM betreibt einen HDFS-DataNode mit Replikationsfaktor 1, Spark `local[2]` mit 2 GB Treiberspeicher und den Airflow SequentialExecutor. MySQL nutzt einen 2-GB-Buffer-Pool. Compose-Volumes speichern HDFS, MySQL, Airflow-Metadaten und Arbeitsdateien. Die Oberflächen sind über Loopback und SSH-Tunnel erreichbar. [Betriebsanleitung](Betrieb.md)
