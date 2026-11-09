# Textprüfung des vollständigen API-Bestands

Quellenstand **03.11.2026**, geprüft am **04.11.2026 um 17:31 UTC**. Lauf `airflow_ad6095f4d0fe289c92ad2548`.

Geprüft wurden **93.643 Karten** aus **937 Originalseiten** mit insgesamt **7.886.028 Zeichenketten**, einschließlich verschachtelter Übersetzungen und Regelhinweise. Jede Seite wurde anhand ihrer SHA256-Prüfsumme im Manifest geprüft und strikt als UTF-8 und JSON gelesen. [Maschinenlesbarer Textaudit](../nachweise/daten/text_audit.json)

## Original und bereinigte Kopie

Die Anteile beziehen sich auf alle **93.643 Rohdatensätze**. Eine Karte kann mehrere Signale liefern. Die Spalte „Originale Textwerte“ zählt einzelne Zeichenketten, die beiden Kartenspalten zählen verschiedene API-IDs.

| Prüfsignal | Karten im Original | Anteil am Rohbestand | Originale Textwerte | Karten nach Bereinigung |
| --- | ---: | ---: | ---: | ---: |
| Unerwartete Steuerzeichen (C0/C1 außer LF, CR und Tab) | 16 | 0,017 % | 16 | 0 |
| Dekodierbare HTML-Entities | 4 | 0,004 % | 8 | 1 |
| Unicode-Formatzeichen | 1 | 0,001 % | 1 | 0 |
| Leerraum am Anfang oder Ende | 146 | 0,156 % | 440 | 1 |
| Geschützte Leerzeichen | 10 | 0,011 % | 10 | 10 |
| Leere Zeichenketten | 8 | 0,009 % | 8 | 8 |
| Spitze Klammern mit tagähnlichem Inhalt | 11 | 0,012 % | 15 | 11 |
| Zeilenumbruch LF | 61.932 | 66,136 % | 298.199 | 61.932 |

U+FFFD, verdächtige Mojibake-Muster, Abweichungen von Unicode-NFC, ausschließlich aus Leerraum bestehende Texte, CR und Tab wurden weder in den Originalen noch in der bereinigten Kopie gefunden.

In Name, Kartentext und Künstlerangabe waren **279.825 Zeichenketten** vorhanden. Dort fand die Prüfung nur beabsichtigte Zeilenumbrüche auf 51.935 Karten. Für die 1.095 fehlenden Kartentexte und neun fehlenden Künstlerangaben verwendet der Export leere Suchwerte. [Datenqualität](Datenqualitaet.md)

## Gemessene Korrekturen

Die Regelversion `text_cleaning_v1` korrigiert in den angegebenen Feldern konkrete technische Fehler. „Operationen“ zählt einzelne entfernte Zeichen oder ersetzte Entities. Ein Textwert kann mehrere Operationen enthalten.

| Quellfeld | Regel | Geänderte Textwerte | Operationen | Karten | Anteil |
| --- | --- | ---: | ---: | ---: | ---: |
| `foreignNames[].name` | U+0081/U+0090 entfernt | 1 | 1 | 1 | 0,001 % |
| `foreignNames[].text` | U+0081/U+0090 entfernt | 15 | 15 | 15 | 0,016 % |
| `foreignNames[].text` | `&amp;` einmal zu `&` dekodiert | 5 | 13 | 3 | 0,003 % |
| `rulings[].text` | ASCII-Leerzeichen am Rand entfernt | 439 | 439 | 146 | 0,156 % |
| `originalText` | U+200B entfernt | 1 | 1 | 1 | 0,001 % |

Insgesamt wurden die Detailtexte von **166 verschiedenen Karten (0,177 %)** korrigiert. Jede betroffene API-ID zählt einmal, auch wenn mehrere Regeln zutreffen. Die HDFS-Originale und `source_json` bleiben erhalten. `details_json` enthält alle Felder des Originals mit den genannten Korrekturen. Feldnamen, IDs, URLs und verschachtelte Strukturen bleiben erhalten.

Im deutschen Text von **Minsc & Boo, Timeless Heroes** wird aus `Minsc &amp; Buh` der Text `Minsc & Buh`. Bei **Aetherspouts** wird das Steuerzeichen U+0090 aus dem italienischen Namen `Vortici d\u0090'Etere` entfernt. Die ursprünglichen Ausschnitte stehen im [Textaudit](../nachweise/daten/text_audit.json).

## Verbleibende Prüfsignale

Drei Übersetzungen von **Courser of Kruphix** enthalten die kodierte Markupform `&lt;I&gt;`. Die Bereinigung meldet diese drei Texte und lässt sie unverändert. Der Regelhinweis von **Case of the Burning Masks** endet mit einem geschützten Leerzeichen U+00A0, das die Regel für ASCII-Leerzeichen ausnimmt. [Fundstellen](../nachweise/daten/review_signals.json)

Spitze Klammern können zum Kartentext gehören, etwa `<sad trombone noises>` in einem Regelhinweis. Das Frontend zeigt die Detailwerte als Text an. Auch Manasymbole einschließlich historischer Schreibweisen, Zeilenumbrüche, Akzente und nichtlateinische Schrift bleiben erhalten. Leere optionale Hinweise bleiben leer.

## Vergleich mit MySQL

Der Audit hat die erwarteten Exportwerte aus den Originalobjekten berechnet und mit **93.643 MySQL-Zeilen in allen neun Spalten** verglichen. Der Vergleich ergab **0 Abweichungen und 0 fehlende IDs**. Er umfasst das Originalobjekt und die bereinigte Kopie. Die Prüfung erfasst die dokumentierten technischen Muster und die korrekte Übernahme. Spielregeln und Übersetzungen stammen aus der API. [Vollvergleich](../nachweise/daten/live_verification.json)

Befehle für eine Wiederholung mit demselben HDFS-Snapshot und dem zugehörigen MySQL-Bestand stehen in der [Betriebsanleitung](../Betrieb.md).
