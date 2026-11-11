# Prüfungsauftrag und Abgabe

- Wintersemester 2026/27.
- Projektentscheidungen: MySQL, Parquet und Bereinigungsregeln.

## Fachlicher Auftrag

- Alle über die vorgegebene MTG-API verfügbaren Karten abrufen und die Originaldaten als JSON in HDFS speichern.
- Die Daten bereinigen, für Abfragen aufbereiten und in eine Nutzerdatenbank exportieren.
- Eine HTML-Suche nach Name, Kartentext oder Künstler bereitstellen.
- Den gesamten Ablauf automatisieren.

- Vollständiger Bestand für die Abgabe, Teilmengen für Entwicklungstests.
- Bereinigung nach Befund. Fehler und Änderungen dokumentieren. Bereinigungsquote offen.
- Gleichnamige Druckvarianten anhand der API-ID unterscheiden.
- [Workflow](Workflow.md) · [Abnahme](berichte/Abnahme.md)

## Abzugebende Dateien

- Kurze Beschreibung des gesamten ETL-Workflows mit Zweck der Schritte und fachlichen Regeln.
- Alle DAGs, Tasks, Skripte und benötigten Konfigurationen.
- Eine gleichnamige DDL-Datei pro Fachtabelle (`cards.sql` und `cards_staging.sql`).
- Vollständiger Code der Webanwendung.

## Präsentation und Termine

- Abgabe bis **20.11.2026, 23:59 Uhr** an **contact@marcel-mittelstaedt.com**, z. B. per Dropbox- oder Google-Drive-Link.
- Präsentationen am **23. oder 30.11.2026**, jeweils **13:00–15:45 Uhr**. Persönlichen Termin klären.
- Themenliste auf Seite 75 der Prüfungsfolien.
- Live-Demo: Workflow starten, Quelle, Tasks und Datenmodelle (Raw, Final, Frontend) erklären, Suche vorführen.
- Vortragsdauer, Folienzahl und Punktegewichtung laut Prüfungsfolien offen.
- Voraussetzungen laut Einführung: Vorlesungsteilnahme und abgeschlossene Übungen.

## Originalquellen

- [MTG-Aufgabenblatt](../../BigData/exercises/winter_semester_2026-2027/exam_create_mtg_trading_card_database_by_api/Create_MTG_Trading_Card_Database_By_API.pdf), Seiten 2–7.
- [Prüfungsfolien](<../../BigData/slides/winter_semester_2026-2027/5_Practical Exam.pdf>), Seiten 5–7, 47–53 und 75.
- [Einführung](../../BigData/slides/winter_semester_2026-2027/0_Intoduction.pdf), Seite 17.

- Original-PDFs im benachbarten Vorlesungsrepository, außerhalb des Abgabepakets.
