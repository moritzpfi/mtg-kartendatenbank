# Vorstellung der MTG-Kartendatenbank

## 1. Start in Airflow

- Airflow, HDFS und Kartensuche im Browser. [VM und SSH-Tunnel](../docs/Betrieb.md#vorhandene-vm-öffnen)
- DAG `mtg_cards` starten, Grid-Ansicht öffnen.
- Ziel: Kartenbestand der MTG-API nach Name, Kartentext und Künstler durchsuchen.
- Zeitplan: täglich 05:00 UTC bei laufender VM und aktivem DAG.
- Lauf für die Demo: neuer Vollabruf oder Wiederverarbeitung gespeicherter API-Antworten. [Vollabruf](../docs/Betrieb.md#airflow-lauf) · [Wiederverarbeitung](../docs/Betrieb.md#gespeicherte-daten-erneut-verarbeiten)
- Falls abgestimmter Testlauf: eine API-Seite, Ziel `mtg_test`. Die Websuche zeigt den bisherigen Vollbestand.

## 2. Datenweg während des Laufs

[UML-Aktivitätsdiagramm](ETL_Aktivitaet.svg)

- `fetch_to_hdfs_raw`: `fetch_cards.py` folgt den Seitenlinks der API. Original-JSON und Manifest mit Prüfsumme je Seite in HDFS Raw.
- JSON-Beispiel: Kartenliste mit verschachtelten Übersetzungen und Regelhinweisen.
- `transform_to_hdfs_final`: `process_cards.py` prüft die Rohdaten und schreibt mit PySpark den Parquet-Bestand.
- Finalmodell: eine Zeile pro API-ID, getrennte Druckvarianten. Suchfelder, `source_json` als Original und `details_json` als bereinigte Kopie.
- Bereinigung: fehlender Kartentext oder Künstler als leerer Suchwert. `Minsc &amp; Buh` im Original wird zu `Minsc & Buh` in der Detailkopie.
- `validate_final`: Parquet erneut lesen, Zeilenzahl und Inhalt prüfen.
- `load_database`: `cards_staging` laden und prüfen, dann `cards` in einer Transaktion ersetzen. Rollback bei Ladefehler.
- `validate_database`: MySQL mit Parquet vergleichen.
- Lauf vom 04.11.2026 mit gespeichertem Vollabruf: 93.643 übereinstimmende Zeilen, 166 Karten mit bereinigten Detailtexten.

[Datenmodell](../docs/Workflow.md) · [Messwerte](../docs/berichte/Abnahme.md)

## 3. Websuche nach dem Lauf

[UML-Sequenzdiagramm](Websuche_Sequenz.svg)

- Browser → Flask → MySQL-Tabelle `cards` → HTML-Trefferliste.
- Kartendetails beim Aufklappen über die API-ID laden.
- Suche nacheinander: `Manta` (Name), `flying` (Kartentext), `Pete Venters` (Künstler).
- **Minsc & Boo, Timeless Heroes** von Bram Sels (CLB) öffnen. Unter **Alle Kartendaten → Andere Sprachen** den deutschen Text mit `Minsc & Buh` zeigen. [Textprüfung](../docs/berichte/Textpruefung.md)
