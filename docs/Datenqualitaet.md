# Datenqualität

Die Zahlen stammen aus dem vollständigen Snapshot vom **03.11.2026**, erneut verarbeitet am **16.11.2026**. Neue API-Abrufe können andere Werte liefern.

- **93.643 Karten** auf 937 API-Seiten, gleich viele Karten in Raw, Final und MySQL.
- Alle Originalseiten anhand ihrer SHA256 geprüft und als UTF-8/JSON gelesen.
- **0 entfernte Dubletten**, **0 ungültige Pflichtdatensätze** und keine Abweichungen beim Vergleich des Exports mit der Quelle.

## Was wurde verändert?

Alle Prozentwerte beziehen sich auf die 93.643 Raw-Datensätze.

| Maßnahme | Karten | Anteil |
| --- | ---: | ---: |
| Fehlende Texte oder Untertypen vereinheitlicht | 67.625 | 72,216 % |
| Fehlender Kartentext zu `""` | 1.095 | 1,169 % |
| Fehlender Künstler zu `""` | 9 | 0,010 % |
| Fehlender Flavourtext zu `""` | 46.891 | 50,074 % |
| Fehlende Untertypen zu `[]` | 36.024 | 38,470 % |
| Bild-URL von HTTP auf HTTPS umgestellt | 63.808 | 68,140 % |
| ID bzw. Name am Rand getrimmt | 0 / 0 | 0,000 % |
| Exakte Dubletten entfernt | 0 | 0,000 % |
| Ungültige Pflichtdatensätze verworfen | 0 | 0,000 % |

Eine Karte kann in mehreren Zeilen der Tabelle vorkommen. Die Anteile werden deshalb nicht addiert. Zählt man die Bild-URL-Umstellung dazu, ändern sich Werte bei 87.296 verschiedenen Karten, also **93,222 %**. Auf sieben Spalten reduziert wird der gesamte Bestand.

Die Werte zeigen, wie viele Karten bearbeitet wurden. Ein fehlender optionaler Text ist nicht automatisch ein Fehler der Quelle. Bei 29.835 Karten fehlt eine Bild-URL. Die Oberfläche zeigt dann eine Kartenrückseite.

## Speichergröße

| Bestand | Größe |
| --- | ---: |
| Original-JSON | 365.975.259 Bytes |
| Final-Parquet | 13.960.216 Bytes |

Das sind **96,19 % weniger Speicher** für den Finalbestand. Gemessen wurde der gemeinsame Effekt von Feldauswahl, Speicherformat und Kompression. Der Raw-Bestand bleibt zusätzlich erhalten.

Nach einem erfolgreichen Durchlauf stehen `final_summary.json`, `database_summary.json` und `quality_report.md` unter `/opt/mtg/work/<lauf-id>/` im Airflow-Container. Das Arbeitsverzeichnis liegt im Docker-Volume `work`. Feldauswahl, Bereinigung und Qualitätszähler stehen in [cards.py](../scripts/cards.py).
