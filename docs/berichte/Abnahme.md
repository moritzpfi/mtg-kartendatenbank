# Abnahme des Projekts

Der Lauf `airflow_ad6095f4d0fe289c92ad2548` verarbeitete am **04.11.2026** den gespeicherten API-Download vom **03.11.2026** erneut und prüfte den vollständigen Bestand.

## Prüfungsauftrag

| Anforderung | Nachweis |
| --- | --- |
| Vollständiger API-Bestand, Originale in HDFS | 93.643 Karten, Originalseiten anhand ihrer Prüfsummen geprüft. [Vollvergleich](../nachweise/daten/live_verification.json) |
| PySpark-Aufbereitung, Finaldaten in HDFS | Neun Exportspalten, bereinigte Kopie, Mengen- und Inhaltsprüfung. [Finalnachweis](../nachweise/daten/final_summary.json) |
| Export in Nutzerdatenbank | 93.643 MySQL-Zeilen, Menge und Hash entsprechen Final. [Datenbanknachweis](../nachweise/daten/database_summary.json) |
| Suche nach Name, Text und Künstler | HTTP-Prüfungen und echte VM-Aufnahmen. [Prüfung](../nachweise/daten/live_verification.json), [Suche](../nachweise/bilder/suche.jpg) |
| Automatisierter Gesamtworkflow | Alle fünf Tasks im vollständigen Wiederverarbeitungslauf erfolgreich. [Lauf](../nachweise/airflow/lauf.json), [Protokoll](../nachweise/airflow/lauf.log) |
| Dokumentation, Skripte, DAG, DDLs und Webcode | Im Abgabepaket enthalten; `sql/cards.sql` und `sql/cards_staging.sql` entsprechen den Fachtabellen |

## Bereinigung

Alle **93.643 Karten** blieben erhalten. Bei **166 Karten (0,177 %)** wurden Detailtexte korrigiert. Bei **1.104 Karten (1,179 %)** wurden fehlende Suchwerte vereinheitlicht. Die Gruppen können sich überschneiden. [Datenqualität](Datenqualitaet.md) · [Textprüfung](Textpruefung.md)

## Tests und Ergebnis

- **34 Tests:** 29 Kern-/Web-/Texttests und fünf echte HDFS-/PySpark-/MySQL-Integrationstests. Enthalten sind wiederholter Export und Rollback nach teilweise geschriebenen Daten. Entwicklungstests verwenden ausschließlich `mtg_test`. [Protokoll](../nachweise/tests/tests.log).
- **Vollständiger unabhängiger Vergleich:** 93.643 Zeilen in allen neun Spalten, **0 Abweichungen und 0 fehlende IDs**. Originale und bereinigte Kopien separat geprüft. [Textaudit](../nachweise/daten/text_audit.json).
- **Browseraufnahmen vom 09.11.2026:** Startseite, Suche nach `Manta`, bereinigtes `Minsc & Buh` und Bildersatz geprüft. [Befunde](../nachweise/bilder/browser.json), [Startseite](../nachweise/bilder/startseite.jpg), [Details](../nachweise/bilder/details.jpg), [Rückseite](../nachweise/bilder/rueckseite.jpg).

## Laufzeit und Betrieb

Die Wiederverarbeitung dauerte **23 Minuten 43 Sekunden** einschließlich des ersten fehlgeschlagenen Transformationsversuchs und der Wartezeit bis zum Wiederanlauf. Der zweite Versuch lief mit 2 GB Spark-Treiberspeicher und frühzeitig freigegebenem Final-Cache durch. [Taskzeiten](../nachweise/airflow/lauf.json) · [Fehlversuch](../nachweise/airflow/spark_fehlversuch.log)

Speicher einschließlich Metadateien: Raw **366.094.837 Bytes**, Final **310.500.824 Bytes**, Replikation 1. Die beiden MySQL-Tabellen belegen laut Speicherstatistik zusammen **3.456.909.312 Bytes**. Bilddateien sind nicht Teil des Kartenarchivs. [Messungen](../nachweise/daten/measurements.json).

Die Betriebsnachweise dokumentieren den gesicherten Finalstand, den aktiven Zeitplan und die geprüften Dienste zum Zeitpunkt der Abnahme. [Sicherung](../nachweise/betrieb/sicherung.json) · [Zeitplan](../nachweise/airflow/zeitplan.json) · [Abschluss](../nachweise/betrieb/abschluss.json) · [Dienste](../nachweise/betrieb/dienste.log)
