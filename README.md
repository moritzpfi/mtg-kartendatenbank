# MTG-Kartendatenbank

Prüfungsprojekt Big Data, Wintersemester 2026/27. Airflow übernimmt Karten aus der MTG-API, sichert die Originale in HDFS, bereitet sie mit PySpark auf und veröffentlicht sie in MySQL. Die Webseite durchsucht Name, Kartentext und Künstler und zeigt alle gelieferten Kartendetails.

## Dokumentation

| Inhalt | Datei |
| --- | --- |
| Prüfungsauftrag und Abgabevorgaben | [Auftrag](docs/Auftrag.md) |
| Datenweg, Datenmodell und Bereinigungsregeln | [Workflow](docs/Workflow.md) |
| Einrichtung, VM-Zugriff und wiederholte Ausführung | [Betrieb](docs/Betrieb.md) |
| Gemessene Bereinigung und Exportzahlen | [Datenqualität](docs/berichte/Datenqualitaet.md) |
| Textprüfung vor und nach der Bereinigung | [Textprüfung](docs/berichte/Textpruefung.md) |
| Abnahme mit Prüfnachweisen | [Abnahme](docs/berichte/Abnahme.md) |
| PowerPoint und Vorführung | [Präsentation](praesentation/MTG_Projektvorstellung.pptx), [Leitfaden](docs/Praesentation.md) |

## Abgabepaket

```bash
python3 scripts/package_project.py
```

Das Skript schreibt `abgabe/MTG_API_Abgabe.zip` mit Code, Dokumentation, Prüfnachweisen und PowerPoint. Zugangsdaten und Arbeitsdaten bleiben außerhalb des Pakets.
