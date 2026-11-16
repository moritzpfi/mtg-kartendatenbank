# Workflow mit Docker

## Was läuft wo?

Zum Starten die [Anleitung in der README](../README.md#starten) verwenden. Alle Dienste laufen auf dem eigenen Docker-Rechner. Die Zugangsdaten werden dort erzeugt. Eine Verbindung zur Entwicklungs-VM ist nicht nötig.

| Container | Aufgabe |
| --- | --- |
| `hdfs` | Speichert Raw-JSON und Final-Parquet |
| `mysql` | Speichert die Karten für die Websuche |
| `airflow-init` | Legt den Airflow-Benutzer und die Datenbanktabellen an und beendet sich danach |
| `airflow` | Führt Scheduler, Airflow-Oberfläche und die Python-/PySpark-Schritte aus |
| `web` | Stellt die Flask-Kartensuche bereit |

Beim Start werden der Airflow-Benutzer `admin` sowie die MySQL-Datenbanken `mtg` und `mtg_test` mit dem Benutzer `mtg` angelegt. Die Passwörter stehen in der `.env`. Die Tabellen entstehen aus den mitgelieferten SQL-Dateien.

Der DAG `mtg_cards` wird im Terminal gestartet. Anschließend laufen alle Schritte automatisch durch. Er hat keinen Zeitplan und startet keinen täglichen Abruf. Start und Statusprüfung sind ohne Browser-Anmeldung möglich; die Befehle stehen in der [README](../README.md#workflow-starten). Airflows interner Scheduler führt die gestarteten Tasks aus.

Die Airflow-Oberfläche unter [localhost:18080](http://127.0.0.1:18080) ist optional. Nach der Anmeldung erscheinen die fünf Tasks und ihre Protokolle in der Grid-Ansicht. Wenn alle erfolgreich sind, kann die [Kartensuche](http://127.0.0.1:15000) den neuen Bestand anzeigen. Beim ersten Start ist die Kartendatenbank bis zum erfolgreichen Import leer. Beim Zugriff auf eine VM die Portweiterleitung aus der README verwenden.

## Datenweg innerhalb der Container

Die Quelle ist die [Magic-the-Gathering-API](https://api.magicthegathering.io/v1/cards). Python ruft die Karten mit bis zu 100 Einträgen pro Seite ab und folgt den Links zur nächsten Seite. Die Originalantworten bleiben unverändert als JSON in HDFS Raw.

```text
MTG-API → HDFS Raw → PySpark → HDFS Final → MySQL → Websuche
```

Airflow führt diese fünf Schritte nach dem manuellen Start nacheinander aus. Es läuft höchstens ein Durchlauf gleichzeitig.

| Airflow-Task | Was passiert? |
| --- | --- |
| `fetch_to_hdfs_raw` | Alle API-Seiten abrufen und die Originalantworten in HDFS sichern |
| `transform_to_hdfs_final` | Karten mit PySpark aufbereiten und als Parquet in HDFS Final speichern |
| `validate_final` | Gespeicherte Finaldaten erneut lesen und Anzahl sowie Inhalt prüfen |
| `load_database` | Daten über eine Staging-Tabelle nach MySQL laden |
| `validate_database` | MySQL mit den Finaldaten vergleichen und den Qualitätsbericht schreiben |

## Welche Daten bleiben übrig?

Eine Zeile steht für eine API-ID. Für die Anzeige werden fünf Felder übernommen, dazu kommen ID und Bild-URL.

| Finalspalte | Inhalt und Aufbereitung |
| --- | --- |
| `id` | API-ID als Schlüssel, Rand-Leerzeichen entfernen |
| `name` | Kartenname, Rand-Leerzeichen entfernen |
| `subtypes` | Untertypenliste als JSON-Zeichenkette, fehlend als `[]` |
| `card_text` | API-Feld `text`, fehlend als `""` |
| `flavor` | Flavourtext, fehlend als `""` |
| `artist` | Künstler, fehlend als `""` |
| `image_url` | Zulässige Wizards-Bildadresse auf HTTPS umstellen, sonst `NULL` |

Diese sieben Felder werden für Suche und Anzeige verwendet. Die übrigen Angaben, etwa Edition, Manakosten und Übersetzungen, bleiben nur in Raw erhalten.

Datensätze ohne gültige ID oder Namen werden gezählt und aussortiert. Exakte Dubletten über alle sieben Exportfelder werden entfernt. Verschiedene IDs bleiben auch bei gleichem Namen erhalten. Gibt es widersprüchliche Inhalte zur selben ID, bricht die Verarbeitung ab.

Die Regeln stehen in [cards.py](../scripts/cards.py), die Ausführung mit Spark, HDFS und MySQL in [process_cards.py](../scripts/process_cards.py). Die gemessenen Anteile stehen unter [Datenqualität](Datenqualitaet.md).

## Speicherung und Suche

Raw und Final liegen in HDFS. Die Daten werden in Docker-Volumes gespeichert; die Ordner legt der Workflow selbst an.

- Raw: `/user/hadoop/mtg/raw/<lauf-id>/`, Original-JSON mit Manifest und Prüfsummen.
- Final: `/user/hadoop/mtg/final/<lauf-id>/`, sieben Spalten als Parquet.
- MySQL: [cards_staging.sql](../sql/cards_staging.sql) für den Import und [cards.sql](../sql/cards.sql) für die Suche. Erst nach erfolgreicher Prüfung ersetzt eine Transaktion den bisherigen Suchbestand. Bei einem Fehler erfolgt ein Rollback.
- Flask sucht in Name, Kartentext und Künstler. Die Trefferliste zeigt höchstens 50 Karten. Beim Aufklappen lädt sie die fünf Anzeigefelder aus MySQL. Die Suche läuft ohne neuen API-Abruf.

Falls schon eine ältere Projektdatenbank vorhanden ist, zuerst die Daten sichern und die Tabellen mit den beiden DDL-Dateien abgleichen. Der Workflow baut bestehende Tabellen nicht automatisch um.

## MySQL bei Bedarf direkt ansehen

Der Datenbankserver heißt innerhalb des Docker-Netzes `mysql` und hört auf Port 3306. Ein SQL-Client ist bereits im Container vorhanden:

```bash
docker compose exec mysql mysql -u mtg -p mtg
```

Beim Passwort-Prompt den Wert von `MYSQL_PASSWORD` aus der `.env` eingeben. Nach einem erfolgreichen Workflow-Lauf lässt sich zum Beispiel die Kartenzahl abfragen:

```sql
SELECT COUNT(*) FROM cards;
```

Der normale Docker-Lauf verwendet echte API-Daten, HDFS und MySQL. Nur die lokalen Tests verwenden teilweise Mocks oder eine SQLite-Testdatenbank. Airflows eigene Laufverwaltung nutzt ebenfalls SQLite; die Kartendaten liegen in MySQL.

## Tests bei Bedarf

Bei laufenden Containern können alle Tests so gestartet werden. Die Integrationstests schreiben nur in die separate Datenbank `mtg_test`:

```bash
docker compose exec -T -e RUN_INTEGRATION=1 airflow python -m unittest discover -v
```

## Bildquellen

DHBW-Logo aus dem Vorlesungsrepository, Magic-Symbol aus der bereitgestellten Grafik, Kartenbilder aus der MTG-API. Die [Kartenrückseite](https://backs.scryfall.io/normal/0/a/0aeebaf5-8c7d-4636-9e82-8c27447861f7.jpg) stammt von Scryfall. Das Kartenbeispiel in der Präsentation stammt aus den Aufgabenfolien.
