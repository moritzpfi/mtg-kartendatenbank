# MTG-Kartendatenbank

- Prüfungsprojekt Big Data, Wintersemester 2026/27.
- Airflow-Workflow: MTG-API → HDFS Raw → PySpark → HDFS Final → MySQL.
- Websuche nach Name, Kartentext und Künstler, mit vollständigen Kartendetails.

## Dokumentation

- [Auftrag und Abgabe](docs/Auftrag.md)
- [Workflow, Datenmodell und Bereinigungsregeln](docs/Workflow.md)
- [Betrieb auf der Google-Cloud-VM und Airflow-Start](docs/Betrieb.md)
- [Datenqualität und Exportzahlen](docs/berichte/Datenqualitaet.md)
- [Textprüfung vor und nach der Bereinigung](docs/berichte/Textpruefung.md)
- [Abnahme und Prüfnachweise](docs/berichte/Abnahme.md)
- [Vortragsnotizen, UML und Live-Demo](praesentation/Sprechleitfaden.md)

## Abgabepaket

```bash
python3 scripts/package_project.py
```

- Ausgabe: `abgabe/MTG_API_Abgabe.zip`
- Inhalt: Code, Dokumentation, Prüfnachweise und Vortragsunterlagen.
- Ausgeschlossen: Zugangsdaten und Arbeitsdaten.
