# Einrichtung und Betrieb

## Neue Umgebung

- Linux x86-64, Docker Engine mit Compose v2 und Python 3.
- Internetzugriff für Image-Build und API-Abruf.

```bash
python3 scripts/configure.py
sudo docker compose build airflow-init
sudo docker compose up -d
sudo docker compose ps -a
```

- `configure.py` erzeugt bei Bedarf eine private `.env` mit zufälligen Zugangsdaten.
- `.env` außerhalb des Abgabepakets.

## Vorhandene VM öffnen

- Google-Cloud-VM `big-data`, Projektverzeichnis `/home/moritz/mtg-api`.
- Airflow läuft in Docker. `restart: unless-stopped` startet vorhandene Container mit Docker, sofern sie vorher nicht manuell gestoppt wurden. [Docker-Neustartregeln](https://docs.docker.com/engine/containers/start-containers-automatically/)

**VM-Status in PowerShell**

```powershell
gcloud compute instances describe big-data --project=big-data-511408 --zone=europe-west3-b --format="value(status)"
```

**VM starten bei `TERMINATED`**

```powershell
gcloud compute instances start big-data --project=big-data-511408 --zone=europe-west3-b
```

**Dienste starten, Status anzeigen und SSH-Tunnel öffnen**

```powershell
gcloud compute ssh big-data --project=big-data-511408 --zone=europe-west3-b --command="cd /home/moritz/mtg-api && sudo docker compose up -d && sudo docker compose ps && sleep 3600" --ssh-flag=-L --ssh-flag=15000:127.0.0.1:15000 --ssh-flag=-L --ssh-flag=18080:127.0.0.1:18080 --ssh-flag=-L --ssh-flag=19870:127.0.0.1:19870
```

- PowerShell-Fenster offen lassen. Der Tunnel endet nach einer Stunde oder beim Schließen der SSH-Verbindung.
- Falls Airflow noch startet, kurz warten und die Seite neu laden.

| Oberfläche | Lokale Adresse |
| --- | --- |
| Kartensuche | http://127.0.0.1:15000 |
| Airflow | http://127.0.0.1:18080 |
| HDFS | http://127.0.0.1:19870 |

- Airflow-Login: `admin`, Passwort aus `AIRFLOW_ADMIN_PASSWORD` in der `.env` auf der VM.
- Bei Portkonflikten den ersten Port der jeweiligen Weiterleitung und die Browseradresse ändern.
- Dienste im Projektverzeichnis stoppen: `sudo docker compose stop`. Die Daten bleiben in den Volumes.
- `sudo docker compose down -v` löscht die Volumes.
- VM nach der Demo stoppen: `gcloud compute instances stop big-data --project=big-data-511408 --zone=europe-west3-b`.

## Airflow-Lauf

- Bei einer Neuinstallation ist der DAG zunächst pausiert.
- In der SSH-Shell Importfehler prüfen, DAG aktivieren und Läufe anzeigen.

```bash
sudo docker compose exec -T airflow airflow dags list-import-errors
sudo docker compose exec -T airflow airflow dags unpause mtg_cards
sudo docker compose exec -T airflow airflow dags list-runs -d mtg_cards
```

- Zeitplan: täglich **05:00 UTC** (**06:00 MEZ**, **07:00 MESZ**) bei laufender VM und aktivem DAG.
- Vollabruf: **DAGs → mtg_cards → Trigger DAG**. Der Lauf und seine fünf Tasks stehen in **Grid**. [Airflow-Dokumentation zum manuellen Start](https://airflow.apache.org/docs/apache-airflow/2.10.5/core-concepts/dag-run.html#external-triggers)
- Laufenden Abruf vor einem weiteren Lauf abwarten. Standardpause zwischen erfolgreichen API-Anfragen: eine Sekunde. Rate-Limit-Header werden berücksichtigt.
- Abgestimmter Testlauf: eine API-Seite, Ziel `mtg_test`. Start per SSH, da die Oberfläche das Formular für Laufparameter überspringt. [Airflow-Einstellung für das Startformular](https://airflow.apache.org/docs/apache-airflow/2.10.5/configurations-ref.html#show-trigger-form-if-no-params)

**SSH in einem zweiten PowerShell-Fenster**

```powershell
gcloud compute ssh big-data --project=big-data-511408 --zone=europe-west3-b
```

**Testlauf auf der VM**

```bash
cd /home/moritz/mtg-api
sudo docker compose exec -T airflow airflow dags trigger --conf '{"max_pages": 1}' mtg_cards
```

## Gespeicherte Daten erneut verarbeiten

- Gespeicherter Vollabruf. Vor dem Start andere DAG-Läufe abwarten.

```bash
run_id=airflow_ad6095f4d0fe289c92ad2548
sudo docker compose exec -T airflow python -m scripts.process_cards transform --run-id "$run_id"
sudo docker compose exec -T airflow python -m scripts.process_cards validate-final --run-id "$run_id"
sudo docker compose exec -T airflow python -m scripts.process_cards load --run-id "$run_id"
sudo docker compose exec -T airflow python -m scripts.process_cards validate-database --run-id "$run_id"
```

- Wiederholung über Airflow: Finalstand sichern und alle fünf Tasks des Laufs `scheduled__2026-11-02T05:00:00+00:00` zurücksetzen.
- Voraussetzung: abgeschlossener Download in der Arbeitsablage.
- Wiederverwendung im Abrufprotokoll prüfen. Eine neue Run-ID startet einen neuen Abruf.

## Berichte neu erzeugen

- Zähler und Qualitätsbericht je Lauf.
- Prüfung im Projektverzeichnis der VM mit zusammengehörigem HDFS-Snapshot und MySQL-Bestand.
- `verify_live` prüft auch die HTTP-Suche. `audit_text` arbeitet mit den gespeicherten Daten.

```bash
run_id=airflow_ad6095f4d0fe289c92ad2548
sudo docker compose exec -T airflow python -m scripts.verify_live --run-id "$run_id"
sudo docker compose exec -T airflow python -m scripts.audit_text --run-id "$run_id"
sudo docker compose cp "airflow:/opt/mtg/work/$run_id/text_audit.json" docs/nachweise/daten/text_audit.json
```

- Berichte im Container: `/opt/mtg/work/$run_id/quality_report.md` und `/opt/mtg/work/$run_id/text_audit.md`.
- Bei neuer Abgabe Final- und Datenbanknachweise übernehmen. Messwerte in Kurzberichten, Abnahme und [Sprechleitfaden](../praesentation/Sprechleitfaden.md) aktualisieren.

## Tests und Paket

```bash
sudo docker compose exec -T airflow python -m unittest tests.test_core tests.test_web tests.test_text_audit tests.test_text_cleaning -v
sudo docker compose exec -T -e RUN_INTEGRATION=1 airflow python -m unittest tests.test_integration -v
python3 scripts/package_project.py
```

- Fünf Integrationstests mit `RUN_INTEGRATION=1`.
- Dienste: HDFS, Spark und MySQL. Schreibzugriffe in MySQL nur auf `mtg_test`.
