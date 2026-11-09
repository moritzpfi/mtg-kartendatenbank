# Einrichtung und Betrieb

## Neue Umgebung

Voraussetzungen: Linux x86-64, Docker Engine mit Compose v2, Python 3 und Internetzugriff beim Bauen und API-Abruf.

```bash
python3 scripts/configure.py
sudo docker compose build airflow-init
sudo docker compose up -d
sudo docker compose ps -a
```

`configure.py` legt die private `.env` mit zufälligen Zugangsdaten an, falls sie fehlt. Für Airflow mit `admin` und dem Wert von `AIRFLOW_ADMIN_PASSWORD` aus `.env` anmelden. Die Datei bleibt außerhalb des Abgabepakets.

## Vorhandene VM öffnen

Das Projekt liegt auf der VM unter `/home/moritz/mtg-api`. Eine ausgeschaltete VM zuerst starten.

```powershell
gcloud compute instances start big-data --project=big-data-511408 --zone=europe-west3-b
```

Den SSH-Tunnel unter Windows öffnen und das Terminal offen lassen.

```powershell
gcloud compute ssh big-data --project=big-data-511408 --zone=europe-west3-b --quiet --command="sleep 3600" --ssh-flag=-L --ssh-flag=15000:127.0.0.1:15000 --ssh-flag=-L --ssh-flag=18080:127.0.0.1:18080 --ssh-flag=-L --ssh-flag=19870:127.0.0.1:19870
```

| Oberfläche | Lokale Adresse |
| --- | --- |
| Kartensuche | http://127.0.0.1:15000 |
| Airflow | http://127.0.0.1:18080 |
| HDFS | http://127.0.0.1:19870 |

Bei belegten Ports die lokalen Tunnelports ändern. Dienste mit `sudo docker compose up -d` starten und mit `sudo docker compose stop` stoppen. Dabei bleiben die Daten in den Volumes erhalten. `sudo docker compose down -v` löscht die Volumes.

Nach der Vorführung lässt sich die VM mit `gcloud compute instances stop big-data --project=big-data-511408 --zone=europe-west3-b` herunterfahren.

## Airflow-Lauf

Neue Installationen beginnen mit pausiertem DAG. Nach Prüfung der Umgebung:

```bash
sudo docker compose exec -T airflow airflow dags list-import-errors
sudo docker compose exec -T airflow airflow dags unpause mtg_cards
sudo docker compose exec -T airflow airflow dags list-runs -d mtg_cards
```

Auf der VM ist der tägliche DAG für **05:00 UTC** eingerichtet. Ein manueller Lauf mit leerer Konfiguration ruft alle Karten neu ab. `{"max_pages": 1}` begrenzt den Entwicklungslauf auf eine API-Seite und veröffentlicht nur in `mtg_test`. Vor einem weiteren Lauf den laufenden Vollabruf abwarten. Der Abruf berücksichtigt die Rate-Limit-Header und wartet standardmäßig eine Sekunde zwischen erfolgreichen Anfragen.

## Gespeicherte Daten erneut verarbeiten

Die folgenden Befehle verarbeiten den gespeicherten vollständigen Abruf erneut. Erst starten, wenn kein anderer DAG-Lauf aktiv ist.

```bash
run_id=airflow_ad6095f4d0fe289c92ad2548
sudo docker compose exec -T airflow python -m scripts.process_cards transform --run-id "$run_id"
sudo docker compose exec -T airflow python -m scripts.process_cards validate-final --run-id "$run_id"
sudo docker compose exec -T airflow python -m scripts.process_cards load --run-id "$run_id"
sudo docker compose exec -T airflow python -m scripts.process_cards validate-database --run-id "$run_id"
```

Für eine Wiederholung über Airflow zuerst den Finalstand sichern und im gespeicherten Lauf `scheduled__2026-11-02T05:00:00+00:00` alle fünf Tasks zurücksetzen. Der abgeschlossene Download muss in der Arbeitsablage liegen. Im Abrufprotokoll prüfen, ob Airflow ihn wiederverwendet hat. Eine neue Run-ID startet einen neuen Abruf.

## Berichte neu erzeugen

Die Verarbeitung schreibt Zähler und Qualitätsbericht für jeden Lauf. Auf der VM im Projektverzeichnis den vollständigen HDFS-Snapshot und den dazugehörigen veröffentlichten MySQL-Bestand prüfen. `verify_live` prüft auch die HTTP-Suche. `audit_text` liest die gespeicherten Daten und startet keinen API-Abruf.

```bash
run_id=airflow_ad6095f4d0fe289c92ad2548
sudo docker compose exec -T airflow python -m scripts.verify_live --run-id "$run_id"
sudo docker compose exec -T airflow python -m scripts.audit_text --run-id "$run_id"
sudo docker compose cp "airflow:/opt/mtg/work/$run_id/text_audit.json" docs/nachweise/daten/text_audit.json
```

Die vollständigen Berichte stehen im Container unter `/opt/mtg/work/$run_id/quality_report.md` und `/opt/mtg/work/$run_id/text_audit.md`. Für eine neue Abgabe die Final- und Datenbanknachweise übernehmen und die Kurzberichte, die Abnahme und die PowerPoint anhand der neuen Messwerte aktualisieren.

## Tests und Paket

```bash
sudo docker compose exec -T airflow python -m unittest tests.test_core tests.test_web tests.test_text_audit tests.test_text_cleaning -v
sudo docker compose exec -T -e RUN_INTEGRATION=1 airflow python -m unittest tests.test_integration -v
python3 scripts/package_project.py
```

Die fünf Integrationstests laufen nur mit `RUN_INTEGRATION=1` und verwenden HDFS, Spark und MySQL. In MySQL schreiben sie ausschließlich in `mtg_test`.
