# MTG-Kartendatenbank

Prüfungsprojekt Big Data, Wintersemester 2026/27. Karten aus der Magic-the-Gathering-API werden mit PySpark aufbereitet und in MySQL gespeichert. Die Websuche findet Karten nach Name, Kartentext oder Künstler.

Der Datenweg: **MTG-API → HDFS Raw (JSON) → PySpark → HDFS Final (Parquet) → MySQL → Websuche**.

## Starten

Die folgenden Befehle starten das Projekt auf dem eigenen Rechner. Dabei entstehen eigene Container, Datenbanken und Zugangsdaten. Ein Zugang zu meiner VM ist dafür nicht nötig.

Auf einer eigenen Linux-VM dieselben Befehle nach der SSH-Anmeldung ausführen. Falls Docker dort Administratorrechte benötigt, den Docker-Befehlen `sudo` voranstellen.

Benötigt werden Docker mit Compose v2 und Internetzugriff. Die Container laufen unter Linux auf x86-64. Unter Windows muss Docker Desktop deshalb im Linux-Modus laufen. Python, Java, Airflow, HDFS und MySQL sind in den Containern enthalten.

ZIP entpacken, Docker starten und ein Terminal im Ordner mit `compose.yaml` öffnen.

**Einmalig die Konfiguration anlegen.** Die passende Variante ausführen:

Windows, PowerShell:

```powershell
docker run --rm --mount "type=bind,source=${PWD},target=/project" --workdir /project python:3.11-slim python scripts/configure.py
```

Linux, Bash:

```bash
docker run --rm --user "$(id -u):$(id -g)" --mount "type=bind,source=${PWD},target=/project" --workdir /project python:3.11-slim python scripts/configure.py
```

Der Befehl erstellt eine `.env` mit zufälligen Passwörtern. Falls sie schon existiert, wird sie beibehalten. Unter Linux gehört die Datei anschließend dem eigenen Benutzer.

**Danach die Container starten.** Diese Befehle gelten für beide Systeme:

```bash
docker compose build airflow-init
docker compose up -d
docker compose ps -a
```

Beim ersten Start warten, bis `hdfs`, `mysql`, `airflow` und `web` als `healthy` angezeigt werden. `airflow-init` richtet Benutzer und Tabellen ein und beendet sich danach mit Exit-Code 0. Das ist normal.

## Workflow starten

Wenn die Dienste bereit sind, den gesamten Ablauf mit einem Befehl starten. Dafür ist kein Login in der Airflow-Oberfläche nötig:

```bash
docker compose exec -T airflow airflow dags trigger mtg_cards
```

Der DAG hat keinen Zeitplan. Nach dem Start laufen alle fünf Schritte nacheinander durch. Der vollständige API-Abruf kann dauern. Für einen weiteren Durchlauf denselben Befehl erneut verwenden, sobald der vorherige abgeschlossen ist.

Den Fortschritt im Terminal prüfen:

```bash
docker compose exec -T airflow airflow dags list-runs -d mtg_cards
```

Falls der DAG direkt nach dem Containerstart noch nicht gefunden wird, kurz warten und den Befehl wiederholen. Bei `running` läuft die Verarbeitung, bei `success` sind die Karten für die Suche verfügbar. Bei `failed` die Task-Protokolle in Airflow ansehen.

Danach die Kartensuche öffnen. Beispiele: `Manta`, `flying` oder `Pete Venters`. Eine Karte aufklappen, um die Details zu sehen. Die Datenregeln stehen im [Workflow](docs/Workflow.md).

| Oberfläche | Adresse im eigenen Browser |
| --- | --- |
| Kartensuche | [localhost:15000](http://127.0.0.1:15000) |
| Airflow | [localhost:18080](http://127.0.0.1:18080) |
| HDFS | [localhost:19870](http://127.0.0.1:19870) |

Für die Kartensuche ist keine Anmeldung nötig. Die Airflow-Oberfläche dient bei Bedarf zur Anzeige der fünf Tasks und ihrer Protokolle. Benutzer: **admin**. Das lokal erzeugte Passwort lässt sich so anzeigen:

```bash
docker compose exec airflow printenv AIRFLOW_ADMIN_PASSWORD
```

MySQL-Zugang und Tabellen sind bereits eingerichtet; die Anwendung verwendet sie automatisch.

## Browserzugriff bei einer eigenen VM

Nur wenn Docker auf einer entfernten VM läuft: Für den Browserzugriff vom eigenen PC einen SSH-Tunnel öffnen. `benutzer@server` durch den eigenen Zugang ersetzen und das Terminal offen lassen:

```bash
ssh -L 15000:127.0.0.1:15000 -L 18080:127.0.0.1:18080 -L 19870:127.0.0.1:19870 benutzer@server
```

Dann gelten die Browseradressen aus der Tabelle auch auf dem eigenen PC. Bei lokalem Docker entfällt dieser Schritt.

Zum Stoppen reicht `docker compose stop`. Die gespeicherten Daten bleiben dabei erhalten. Falls ein Dienst nicht startet, zeigt `docker compose logs --tail=50` die letzten Meldungen.
