# Kurzvorstellung während des Airflow-Laufs

[Aktuelle PowerPoint](MTG_Airflow_Kurzvortrag.pptx): fünf Vortragsfolien für etwa zwei Minuten. Raw- und Final-Ausschnitt zeigen dieselbe Karte. Die Sprechtexte stehen auch in den PowerPoint-Notizen. Die Messwerte für Rückfragen stehen unten in diesem Leitfaden.

Vorher den DAG `mtg_cards` starten und die Grid-Ansicht öffnen. Während des Laufs die Folien zeigen. [Startanleitung](../README.md#workflow-starten)

## 1. Datenquelle, etwa 20 Sekunden

„Die Daten kommen von der Magic-the-Gathering-API. Links ist ein Ausschnitt der JSON-Antwort, rechts die Karte dazu. Die API liefert mehr Angaben, als die Suche braucht, zum Beispiel Manakosten, Farben und Edition.“

## 2. Abruf und HDFS Raw, etwa 20 Sekunden

„Das Python-Skript lädt bis zu 100 Karten pro Seite und folgt jeweils dem nächsten Seitenlink. Die Antworten bleiben unverändert als JSON in HDFS Raw. Airflow führt die Schritte nacheinander aus.“

## 3. Transformationen, etwa 30 Sekunden

„Mit PySpark behalte ich fünf Anzeigefelder plus ID und Bild-URL. Fehlende Texte setze ich auf einen leeren Text, fehlende Untertypen auf eine leere Liste. Dazu kommen die Prüfung auf Pflichtfelder und Dubletten sowie die Umstellung der Bild-URLs auf HTTPS. Das Ergebnis liegt als Parquet in HDFS Final.“

## 4. Aufgeräumter JSON-Ausschnitt, etwa 15 Sekunden

„Hier ist dieselbe Karte nach der Aufbereitung. Die zusätzlichen Angaben sind weg. Diese fünf Felder zeigt die Suche an, ID und Bild-URL bleiben im Hintergrund erhalten. Auf der Folie ist das als JSON dargestellt, gespeichert wird es als Parquet.“

Der Ausschnitt zeigt die fünf Anzeigefelder. `subtypes` ist im gespeicherten Finalmodell eine JSON-Zeichenkette. `text` heißt dort `card_text`. Das vollständige Modell enthält zusätzlich `id` und `image_url`.

## 5. Export und Suche, etwa 20 Sekunden

„Zum Schluss kommen die Karten nach MySQL. Daraus liest die Flask-Anwendung für die Suche. Wenn Airflow fertig ist, suche ich nach einer Karte und öffne die Details.“

## Danach live

- Zu Airflow zurückwechseln und den Laufstatus zeigen.
- Nach erfolgreichem Lauf die Websuche öffnen, `Manta` suchen und `Manta Riders` aufklappen.
- Bei Bedarf `flying` für Kartentext und `Pete Venters` für Künstler zeigen.

Den Lauf korrekt benennen: Ein neuer Vollabruf lädt die API erneut. Eine Wiederverarbeitung nutzt gespeicherte Antworten. Ein begrenzter Lauf nach `mtg_test` aktualisiert den produktiven Suchbestand nicht.

## Für Rückfragen

### Welche Transformationen konkret, und bei wie viel Prozent?

„Bei rund 72,2 Prozent der Karten vereinheitliche ich fehlende Angaben. Am häufigsten fehlen der Flavourtext oder die Untertypen. Zusätzlich stelle ich Bild-URLs auf HTTPS um. Dubletten oder ungültige Pflichtdatensätze gab es im gemessenen Bestand nicht.“

Alle Kartenanteile beziehen sich auf **93.643 Raw-Datensätze**, Snapshot vom **03.11.2026**, am **16.11.2026** wiederverarbeitet.

| Konkrete Transformation | Betroffene Karten | Anteil am Raw-Bestand |
| --- | ---: | ---: |
| Projektion auf fünf Anzeigefelder plus ID und Bild-URL | 93.643 | 100,000 % |
| Mindestens einen fehlenden optionalen Wert vereinheitlicht, ohne Bild-URL-/Typumstellung | 67.625 | 72,216 % |
| Fehlender Kartentext zu `""` | 1.095 | 1,169 % |
| Fehlender Künstler zu `""` | 9 | 0,010 % |
| Fehlender Flavourtext zu `""` | 46.891 | 50,074 % |
| Fehlende Untertypen zu `[]`, danach als JSON-Zeichenkette speichern | 36.024 | 38,470 % |
| Vorhandene Bild-URL von HTTP zu HTTPS normalisiert | 63.808 | 68,140 % |
| ID bzw. Name am Rand getrimmt | 0 / 0 | 0,000 % |
| Exakte Dubletten entfernt | 0 | 0,000 % |
| Ungültige Pflichtdatensätze verworfen | 0 | 0,000 % |

- Die Anteile können sich überschneiden und dürfen nicht addiert werden. Einschließlich der Bild-URL-Normalisierung betreffen Wertänderungen insgesamt 87.296 verschiedene Karten, also **93,222 %**.
- Die Prozente zählen bearbeitete Karten. Fehlender optionaler Text ist nicht automatisch ein Fehler. Die Umwandlung der Untertypenliste in eine JSON-Zeichenkette ändert nur die Darstellung.
- **Speicherreduktion: 96,19 %**, von 365.975.259 Bytes Raw-JSON auf 13.960.216 Bytes Final-Parquet. Das misst Feldauswahl, Format und Kompression gemeinsam. Der Raw-Bestand bleibt erhalten.
- Wie viele Felder entfallen, hängt von der jeweiligen Karte ab. Die API-Objekte haben nicht alle denselben Aufbau.

Die Messwerte stehen zusammengefasst unter [Datenqualität](../docs/Datenqualitaet.md).

### Weitere fachliche Rückfragen

- Die fünf Anzeigefelder sind Name, Untertypen, Regeltext, Flavourtext und Künstler. ID und Bild-URL kommen für Zuordnung und Vorschau hinzu.
- Für Suche und Anzeige werden nur die ausgewählten Felder gebraucht. Alle Originalfelder bleiben in HDFS Raw erhalten.
- Die Dublettenregel ist implementiert. Im dokumentierten vollständigen Snapshot musste sie keine Zeilen entfernen.
- Einzelheiten zu den fünf Airflow-Tasks und Bereinigungsregeln stehen im [Workflow](../docs/Workflow.md).

Bild und JSON-Ausschnitt: MTG-Aufgabenblatt „Create MTG Trading Card Database By API“, Seite 2, bzw. Prüfungsfolien, Seite 48. Das eingebettete Kartenbild stammt direkt aus dem Aufgabenblatt.
