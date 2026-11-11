# Abnahme des Projekts

- Vollständiger API-Download vom **03.11.2026**.
- Wiederverarbeitung und Prüfung am **04.11.2026** in Lauf `airflow_ad6095f4d0fe289c92ad2548`.

## Prüfungsauftrag

| Anforderung | Nachweis |
| --- | --- |
| Vollständiger API-Bestand, Originale in HDFS | 93.643 Karten, Originalseiten anhand ihrer Prüfsummen geprüft. [Vollvergleich](../nachweise/daten/live_verification.json) |
| PySpark-Aufbereitung, Finaldaten in HDFS | Neun Exportspalten, bereinigte Kopie, Mengen- und Inhaltsprüfung. [Finalnachweis](../nachweise/daten/final_summary.json) |
| Export in Nutzerdatenbank | 93.643 MySQL-Zeilen, Menge und Hash entsprechen Final. [Datenbanknachweis](../nachweise/daten/database_summary.json) |
| Suche nach Name, Text und Künstler | HTTP-Prüfungen und Browseraufnahmen von der VM. [Prüfung](../nachweise/daten/live_verification.json), [Suche](../nachweise/bilder/suche.jpg) |
| Automatisierter Gesamtworkflow | Alle fünf Tasks im vollständigen Wiederverarbeitungslauf erfolgreich. [Lauf](../nachweise/airflow/lauf.json), [Protokoll](../nachweise/airflow/lauf.log) |
| Dokumentation, Skripte, DAG, DDLs und Webcode | Im Abgabepaket enthalten. Eigene DDL je Fachtabelle (`sql/cards.sql`, `sql/cards_staging.sql`). |

## Bereinigung

- **93.643 Karten** im Bestand erhalten.
- **166 Karten (0,177 %)** mit bereinigten Detailtexten.
- **1.104 Karten (1,179 %)** mit vereinheitlichten fehlenden Suchwerten. Überschneidungen mit der Detailtextbereinigung möglich.
- [Datenqualität](Datenqualitaet.md) · [Textprüfung](Textpruefung.md)

## Tests und Ergebnis

- **34 Tests**: 29 Kern-, Web- und Texttests, fünf Integrationstests mit HDFS, PySpark und MySQL. [Protokoll](../nachweise/tests/tests.log)
- Testfälle für wiederholten Export und Rollback nach Teilschreibvorgang. Entwicklungstests nur in `mtg_test`.
- Unabhängiger Vergleich aller neun Spalten in 93.643 Zeilen: **0 Abweichungen, 0 fehlende IDs**.
- Originale und bereinigte Kopien separat geprüft. [Textaudit](../nachweise/daten/text_audit.json)
- Browserprüfung vom **09.11.2026**: Startseite, `Manta`-Suche, `Minsc & Buh` und Ersatzbild. [Befunde](../nachweise/bilder/browser.json) · [Startseite](../nachweise/bilder/startseite.jpg) · [Details](../nachweise/bilder/details.jpg) · [Rückseite](../nachweise/bilder/rueckseite.jpg)

## Laufzeit und Betrieb

- **23 Minuten 43 Sekunden** einschließlich fehlgeschlagener Transformation und Wartezeit bis zum Wiederanlauf. [Taskzeiten](../nachweise/airflow/lauf.json) · [Fehlversuch](../nachweise/airflow/spark_fehlversuch.log)
- Zweiter Versuch erfolgreich mit 2 GB Spark-Treiberspeicher und früh freigegebenem Final-Cache.
- HDFS einschließlich Metadateien: Raw **366.094.837 Bytes**, Final **310.500.824 Bytes**, Replikation 1.
- MySQL-Tabellen zusammen **3.456.909.312 Bytes**. Kartendatenarchiv ohne Bilddateien. [Messungen](../nachweise/daten/measurements.json)
- Betriebsstand bei Abnahme. [Sicherung](../nachweise/betrieb/sicherung.json) · [Zeitplan](../nachweise/airflow/zeitplan.json) · [Abschluss](../nachweise/betrieb/abschluss.json) · [Dienste](../nachweise/betrieb/dienste.log)
