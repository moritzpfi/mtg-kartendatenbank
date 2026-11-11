# Workflow und Datenmodell

## Datenweg und Airflow

```text
MTG-API → HDFS raw → PySpark → HDFS final (Parquet) → MySQL → HTML-Suche
```

- `dags/mtg_cards.py`: täglich **05:00 UTC** bei laufender VM und aktivem DAG.
- Höchstens ein aktiver Lauf.

| Task | Skript / Zweck |
| --- | --- |
| `fetch_to_hdfs_raw` | `fetch_cards.py`: alle Karten abrufen, Original-JSON und Manifest in HDFS sichern |
| `transform_to_hdfs_final` | `process_cards.py transform`: Rohdaten prüfen, Karten aufbereiten und Parquet schreiben |
| `validate_final` | Geschriebenes Parquet erneut lesen und Mengen/Inhalte prüfen |
| `load_database` | Staging laden und prüfen, anschließend transaktional veröffentlichen |
| `validate_database` | Export mit Finalbestand vergleichen und Qualitätsbericht erzeugen |

## Quelle und Raw Layer

- API-Endpunkt: `https://api.magicthegathering.io/v1/cards`.
- `pageSize=100`, Weiterblättern per Next-Link. Prüfung auf fortlaufende Seiten und passende Gesamtzahl.
- Falls vorhanden, muss der Header `Total-Count` stabil bleiben und zur Endsumme passen. Ohne Header zählt das Ende der Next-Link-Kette. Fehlenden Header protokollieren.
- Die API kann sich zwischen einzelnen Seitenabrufen ändern.
- Originale Antwortbytes unter `/user/hadoop/mtg/raw/<lauf-id>/`.
- Manifest mit Zeitraum, Kartenzahl und SHA256 je Datei. Erneute Prüfung auf Prüfsumme, UTF-8 und gültiges JSON in der Transformation.
- Begrenzte Wiederholungen bei vorübergehenden HTTP-Fehlern, unter Berücksichtigung der Rate-Limits. Unvollständige Downloads entsprechend markiert.
- Wiederaufnahme aus der lokalen Arbeitsablage. Gleiche Run-ID verwendet einen abgeschlossenen Download erneut. Neue Run-ID startet einen neuen Abruf.

## Finalmodell

- Eine Zeile pro API-ID. Gleichnamige Editionen bleiben getrennt.
- Neun Exportspalten aus PySpark, einschließlich des vollständigen Originalobjekts.

| Spalte | Aufbereitung |
| --- | --- |
| `id` | Pflichtschlüssel, Rand-Leerraum entfernen, maximal 128 Zeichen |
| `multiverseid` | Optionale numerische ID zu BIGINT, fehlend oder unbrauchbar zu NULL |
| `name` | Pflichtname, Rand-Leerraum entfernen |
| `card_text` | API-`text`, fehlend zu leerem Suchtext |
| `artist` | Fehlend zu leerem Suchtext |
| `set_code` | API-`set`, fehlend zu leerem Text |
| `image_url` | Nur zulässige Wizards-Bildquelle, HTTP zu HTTPS, sonst NULL |
| `source_json` | Vollständiges ursprüngliches Objekt, einschließlich unbekannter und verschachtelter Felder |
| `details_json` | Vollständige bereinigte Kopie für die Detailanzeige |

- Datensätze ohne gültige ID oder Namen zählen und ausschließen.
- Exakte Dubletten entfernen. Bei unterschiedlichen Inhalten zur selben ID bricht die Transformation ab.
- Für jede Karte im neuen Finalbestand gültiges Original- und Detailobjekt.
- Parquet unter `/user/hadoop/mtg/final/<lauf-id>/`.
- `_summary.json`: Mengen, Regeln und kanonischer Inhalts-Hash über alle neun Spalten.
- Rohdatensätze = ungültige Datensätze + entfernte Dubletten + Finaldatensätze.

## Deterministische Textbereinigung

- `text_cleaning_v1`: Regeln aus der Tabelle auf die Detailkopie anwenden, mit der Python-Standardbibliothek.

| Feld | Regel |
| --- | --- |
| `foreignNames[].name`, `foreignNames[].text` | Nachgewiesene Zeichen U+0081/U+0090 entfernen |
| `foreignNames[].text` | Einfach kodiertes `&amp;` einmal zu `&` dekodieren |
| `rulings[].text` | ASCII-Leerzeichen am Anfang und Ende entfernen |
| `originalText` | Nachgewiesenes U+200B entfernen |

- Erhalten: Manasymbole, Zeilenumbrüche, Akzente, asiatische Schrift, geschützte Leerzeichen und bedeutungstragende spitze Klammern.
- Mehrfach kodierte oder unbekannte Entities als Prüfsignale. [Messwerte und Fundstellen](berichte/Textpruefung.md)

## Prüfung und Veröffentlichung

- Rohdaten-Audit: unabhängige Zählung der Feldwerte.
- Finalvalidierung und Datenbankvergleich: gleiche Zeilenzahl, Feldzähler und Inhaltsprüfsumme.
- Textprüfung: neun erwartete Exportwerte aus jedem Originalobjekt mit allen MySQL-Zeilen vergleichen.
- Eigene DDL für `cards_staging` und `cards`. Import in Paketen von 1.000 Zeilen.
- Staging prüfen, `cards` in einer Transaktion ersetzen, Menge und Inhalt vor dem Commit erneut prüfen.
- Rollback bei Fehlern erhält den bisherigen Suchbestand. Begrenzte Abrufe und absichtliche Exportfehler nur in `mtg_test`.
- Nach erfolgreichem Lauf im Arbeitsverzeichnis: `final_summary.json`, `database_summary.json` und `quality_report.md`.
- Messwerte aus einem konkreten Lauf. Neue Abrufe können abweichen. [Abnahme](berichte/Abnahme.md)

## Webanwendung

- Ein Suchfeld für Name, Kartentext und Künstler. Parametrisierte MySQL-Abfrage per `LIKE '%Suchtext%'`.
- Teiltextsuchen ohne Beachtung der Groß-/Kleinschreibung. SQL-Wildcards als wörtliche Zeichen behandeln.
- Maximal 50 Karten pro Ausgabe, mit Hinweis auf weitere Treffer.
- Backend liest aus MySQL. `GET /cards/<id>` lädt erst beim Aufklappen das vollständige `details_json` als `{"card": …}`.
- Unbekannte Felder und verschachtelte Listen sichtbar. HTML als Text, Zahlen wie 0 und boolesche Werte bleiben erhalten.
- HTTP 503 bei Datenbankfehlern, HTTP 400 bei überlangen Suchbegriffen.
- Suchfeld mittig auf der Startseite, oberhalb der Treffer in der Ergebnisansicht. Hell/Dunkel-Einstellung im Browser gespeichert.
- Kartenbilder per Klick vergrößern, mit Escape schließen. Lokale Kartenrückseite bei fehlendem oder defektem Bild. [Bildquellen](Bildquellen.md)

## Betriebsumfang

- Eine VM mit einem HDFS-DataNode, Replikationsfaktor 1.
- Spark `local[2]` mit 2 GB Treiberspeicher, Airflow SequentialExecutor, MySQL-Buffer-Pool mit 2 GB.
- Compose-Volumes für HDFS, MySQL, Airflow-Metadaten und Arbeitsdateien.
- Zugriff auf die Oberflächen über Loopback und SSH-Tunnel. [Betriebsanleitung](Betrieb.md)
