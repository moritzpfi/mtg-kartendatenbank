# Textprüfung des vollständigen API-Bestands

- Quellenstand **03.11.2026**, Prüfung **04.11.2026, 17:31 UTC**.
- Lauf `airflow_ad6095f4d0fe289c92ad2548`.
- **93.643 Karten** aus **937 Originalseiten**, **7.886.028 Zeichenketten** einschließlich verschachtelter Übersetzungen und Regelhinweise.
- Je Seite SHA256-Prüfsumme mit Manifest abgeglichen, striktes UTF-8 und JSON geprüft. [Maschinenlesbarer Textaudit](../nachweise/daten/text_audit.json)

## Original und bereinigte Kopie

- Basis: **93.643 Rohdatensätze**, mehrere Signale pro Karte möglich.
- Textwerte zählen einzelne Zeichenketten. Kartenspalten zählen unterschiedliche API-IDs.

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

- Je 0 Funde in Original und Kopie: U+FFFD, verdächtige Mojibake-Muster, Abweichungen von Unicode-NFC, reine Leerraumwerte, CR und Tab.
- **279.825 Zeichenketten** in Name, Kartentext und Künstlerangabe. Als einziges Signal beabsichtigte Zeilenumbrüche auf 51.935 Karten.
- Leere Suchwerte für 1.095 fehlende Kartentexte und neun fehlende Künstlerangaben. [Datenqualität](Datenqualitaet.md)

## Gemessene Korrekturen

- Regeln aus `text_cleaning_v1` für die aufgeführten Felder.
- Eine Operation pro entferntem Zeichen oder ersetzter Entity. Mehrere Operationen pro Textwert möglich.

| Quellfeld | Regel | Geänderte Textwerte | Operationen | Karten | Anteil |
| --- | --- | ---: | ---: | ---: | ---: |
| `foreignNames[].name` | U+0081/U+0090 entfernt | 1 | 1 | 1 | 0,001 % |
| `foreignNames[].text` | U+0081/U+0090 entfernt | 15 | 15 | 15 | 0,016 % |
| `foreignNames[].text` | `&amp;` einmal zu `&` dekodiert | 5 | 13 | 3 | 0,003 % |
| `rulings[].text` | ASCII-Leerzeichen am Rand entfernt | 439 | 439 | 146 | 0,156 % |
| `originalText` | U+200B entfernt | 1 | 1 | 1 | 0,001 % |

- Bereinigte Detailtexte bei **166 Karten (0,177 %)**, einmal pro API-ID gezählt.
- Originale in HDFS und `source_json`. `details_json` enthält alle Felder mit den aufgeführten Korrekturen.
- Feldnamen, IDs, URLs und verschachtelte Strukturen bleiben erhalten.
- **Minsc & Boo, Timeless Heroes**, deutscher Text: `Minsc &amp; Buh` → `Minsc & Buh`.
- **Aetherspouts**, italienischer Name: U+0090 aus `Vortici d\u0090'Etere` entfernt. [Textaudit mit Originalausschnitten](../nachweise/daten/text_audit.json)

## Verbleibende Prüfsignale

- **Courser of Kruphix**: drei Übersetzungen mit kodiertem `&lt;I&gt;`, gemeldet und unverändert.
- **Case of the Burning Masks**: U+00A0 am Ende eines Regelhinweises. Die Regel entfernt nur ASCII-Leerzeichen. [Fundstellen](../nachweise/daten/review_signals.json)
- Spitze Klammern als Text, z. B. `<sad trombone noises>` im Regelhinweis. Detailwerte erscheinen im Frontend als Text.
- Erhalten: Manasymbole mit historischen Schreibweisen, Zeilenumbrüche, Akzente, nichtlateinische Schrift und leere optionale Hinweise.

## Vergleich mit MySQL

- Erwartete Exportwerte aus Originalobjekten mit **93.643 MySQL-Zeilen in allen neun Spalten** verglichen.
- **0 Abweichungen, 0 fehlende IDs**, einschließlich Originalobjekt und bereinigter Kopie. [Vollvergleich](../nachweise/daten/live_verification.json)
- Geprüft: dokumentierte technische Muster und korrekte Übernahme. Spielregeln und Übersetzungen stammen aus der API.
- Wiederholung mit demselben HDFS-Snapshot und MySQL-Bestand. [Betriebsanleitung](../Betrieb.md)
