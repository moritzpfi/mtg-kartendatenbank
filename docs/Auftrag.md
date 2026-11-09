# Prüfungsauftrag und Abgabe

Prüfungsprojekt im Wintersemester 2026/27. MySQL, Parquet und die Bereinigungsregeln sind Entscheidungen des Projekts.

## Fachlicher Auftrag

- Alle über die vorgegebene MTG-API verfügbaren Karten abrufen und die Originaldaten als JSON in HDFS speichern.
- Die Daten bereinigen, für Abfragen aufbereiten und in eine Nutzerdatenbank exportieren.
- Eine HTML-Suche nach Name, Kartentext oder Künstler bereitstellen.
- Den gesamten Ablauf automatisieren.

Teilmengen dienen Entwicklungstests. Die fertige Datenkette muss den vollständigen Bestand verarbeiten. Die Bereinigung dokumentiert gefundene Fehler und Änderungen. Eine feste Bereinigungsquote ist nicht vorgegeben. Gleiche Namen verschiedener Druckvarianten sind keine Dubletten.

Die technische Umsetzung steht im [Workflow](Workflow.md), die Nachweise in der [Abnahme](berichte/Abnahme.md).

## Abzugebende Dateien

- Kurze Beschreibung des gesamten ETL-Workflows mit Zweck der Schritte und fachlichen Regeln.
- Alle DAGs, Tasks, Skripte und benötigten Konfigurationen.
- Eine gleichnamige DDL-Datei pro Fachtabelle (`cards.sql` und `cards_staging.sql`).
- Vollständiger Code der Webanwendung.

## Präsentation und Termine

Zum Vortrag den Workflow starten, während der Ausführung Quelle, Schritte und Datenmodelle in Raw, Final und Frontend erklären und anschließend die Suche demonstrieren. Die Prüfungsfolien nennen keine feste Vortragsdauer, Folienzahl oder Punktegewichtung.

- Abgabe bis **20.11.2026, 23:59 Uhr** an **contact@marcel-mittelstaedt.com**. Die Folien nennen Dropbox oder Google Drive als Bereitstellungsmöglichkeiten.
- Präsentationen am **23. oder 30.11.2026** von **13:00 bis 15:45 Uhr**. Den persönlichen Slot klären.
- Den Eintrag in der auf Seite 75 der Prüfungsfolien verlinkten Themenliste prüfen.
- Die Einführungsfolien nennen Vorlesungsteilnahme und abgeschlossene Übungen als persönliche Prüfungsvoraussetzungen.

## Originalquellen

- [MTG-Aufgabenblatt](../../BigData/exercises/winter_semester_2026-2027/exam_create_mtg_trading_card_database_by_api/Create_MTG_Trading_Card_Database_By_API.pdf), Seiten 2–7.
- [Prüfungsfolien](<../../BigData/slides/winter_semester_2026-2027/5_Practical Exam.pdf>), Seiten 5–7, 47–53 und 75.
- [Einführung](../../BigData/slides/winter_semester_2026-2027/0_Intoduction.pdf), Seite 17.

Die Quellenverweise setzen die vorhandene lokale Ordnerstruktur mit dem Vorlesungsrepository neben dem Projekt voraus. Die Original-PDFs gehören nicht zum eigenen Quellcodepaket.
