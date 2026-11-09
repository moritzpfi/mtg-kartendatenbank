# Datenqualität und Exportnachweis

Quellenstand **03.11.2026**, geprüft am **04.11.2026 um 17:12 UTC**. Lauf `airflow_ad6095f4d0fe289c92ad2548`.

Bei der Wiederverarbeitung wurden **937 gespeicherte HDFS-Seiten** geprüft. Die SHA256-Prüfsummen stimmten mit dem Manifest überein. Alle Seiten ließen sich strikt als UTF-8 dekodieren und als JSON lesen. [Manifest und Vollvergleich](../nachweise/daten/live_verification.json)

## Bestand und Änderungen

Die Anteile beziehen sich auf **93.643 Rohdatensätze** und sind auf drei Nachkommastellen gerundet. Maßnahmen können dieselben Karten betreffen.

| Prüfung oder Maßnahme | Anzahl | Anteil am Rohbestand |
| --- | ---: | ---: |
| Rohdatensätze | 93.643 | 100,000 % |
| Wegen ungültiger Pflichtfelder verworfen | 0 | 0,000 % |
| Exakte Dubletten entfernt | 0 | 0,000 % |
| Finaldatensätze und MySQL-Zeilen | 93.643 | 100,000 % |
| Fehlenden Kartentext als leeren Suchwert exportiert | 1.095 | 1,169 % |
| Fehlenden Künstler als leeren Suchwert exportiert | 9 | 0,010 % |
| Verschiedene Karten mit vereinheitlichten Suchwerten | 1.104 | 1,179 % |
| Numerische ID von Zeichenkette zu BIGINT konvertiert | 63.808 | 68,140 % |
| Fehlende numerische ID als NULL beibehalten | 29.835 | 31,860 % |
| Zulässige Bild-URL von HTTP auf HTTPS umgestellt | 63.808 | 68,140 % |
| Fehlende Bild-URL als NULL exportiert | 29.835 | 31,860 % |

Bei Namen und IDs fiel kein Rand-Leerraum zum Entfernen an. Die Prüfung fand weder unbrauchbare numerische IDs noch nicht erlaubte Bild-URLs. In den sieben untersuchten Quellfeldern gab es keine expliziten JSON-NULLs, leeren oder ausschließlich aus Leerraum bestehenden Zeichenketten, Unicode-Ersatzzeichen oder unerwarteten C0-Steuerzeichen. Fehlende Schlüssel wurden separat erfasst. [Feldstatistik im Finalnachweis](../nachweise/daten/final_summary.json)

Die 93.643 eindeutigen IDs verteilen sich auf 29.049 verschiedene Namen. Auf 17.510 mehrfach vorkommende Namen entfallen 82.104 Datensätze. Editionen und Druckvarianten bleiben anhand ihrer API-IDs getrennt.

## Vergleich von Finalbestand und MySQL

Zeilenzahl, Feldzähler und der Inhalts-Hash stimmen überein. Der Hash umfasst alle neun Exportspalten einschließlich `source_json` und `details_json`.

`6fd429ff102969109804ca9bf55b0f2e95012cb3841a0cdfcf29b0ea8a51f286`

`source_json` bewahrt das vollständige Originalobjekt. `details_json` enthält die bereinigte Kopie. Die Detailtextkorrekturen betreffen **166 verschiedene Karten (0,177 %)** und werden getrennt von der Vereinheitlichung der Suchfelder ausgewiesen. [Datenbanknachweis](../nachweise/daten/database_summary.json) · [Textprüfung](Textpruefung.md)

Die Bildstatistik erfasst die von der API gelieferten URLs. Ob ein Bild erreichbar ist, zeigt sich beim Abruf im Browser. Die Konsistenzprüfung vergleicht die Exportwerte mit der Quelle, aus der auch die Spielregeln und Künstlerangaben stammen. [Bildquellen](../Bildquellen.md)

Befehle zur Wiederholung stehen in der [Betriebsanleitung](../Betrieb.md).
