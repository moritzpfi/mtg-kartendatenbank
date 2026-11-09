# Projektvorstellung

Die neun Folien zeigen, wie die Kartendaten bereinigt und vor der Veröffentlichung geprüft werden. Erläuterungen und Quellen stehen in den Referentennotizen. [PowerPoint](../praesentation/MTG_Projektvorstellung.pptx)

## Ablauf

1. Den Airflow-Workflow starten. Einen begrenzten Lauf vorher mit dem Dozenten abstimmen und als Testlauf kennzeichnen.
2. Während der Ausführung die API-Quelle, die Verarbeitung und die Datenmodelle in Raw, Final und MySQL erklären.
3. Die Suche, die Kartendetails und den Bildersatz vorführen.

## Live-Demo vorbereiten

- VM und Dienste starten. Über den SSH-Tunnel Airflow, HDFS und die Suchseite öffnen. [Betriebsanleitung](Betrieb.md)
- Einen HDFS-Originaldatensatz, das Finalschema und die gemessenen Ergebnisse bereithalten. [Datenqualität](berichte/Datenqualitaet.md)
- `Manta`, `flying` und `Pete Venters` suchen, um Name, Text und Künstler zu zeigen.
- `Minsc & Boo, Timeless Heroes` von Bram Sels (CLB) öffnen. Unter „Alle Kartendaten“ und „Andere Sprachen“ zeigen, wie aus `Minsc &amp; Buh` im Original `Minsc & Buh` wird.
- `A-Minsc & Boo, Timeless Heroes` (HBG) als Beispiel für die Kartenrückseite öffnen.

Die Browseraufnahmen vom 09.11.2026 zeigen [Startseite](nachweise/bilder/startseite.jpg), [Suche](nachweise/bilder/suche.jpg), [deutschen Kartentext](nachweise/bilder/details.jpg) und [Kartenrückseite](nachweise/bilder/rueckseite.jpg).

Der dokumentierte vollständige Lauf hat einen gespeicherten Download verwendet. Bei der Demo angeben, ob der Lauf erneut abruft oder vorhandene Daten verarbeitet. [Abnahme](berichte/Abnahme.md)

Für Rückfragen die Trennung von Raw und Final, den Umgang mit Druckvarianten und fehlenden Werten sowie den Schutz des Suchbestands durch Staging und Transaktion erläutern. [Workflow](Workflow.md)
