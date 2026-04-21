"""
Demo-Fixtures mit realistischen kommunalen Inhalten.

Drei Demo-Sammlungen:
- bauakte_schlossgarten: Bauakte mit Kostenueberschreitung + offenem Widerspruch
- digitalstrategie_2030: WissensDB mit Strategiepapieren
- haushalt_2026: Haushaltsplan-Sammlung mit Budget-Risiken
"""

DEMO_FIXTURES = {
    "bauakte_schlossgarten": {
        "name": "Bauakte Erschliessung Schlossgarten",
        "description": "Erschliessung des Neubaugebiets Schlossgarten, 14 Dokumente",
        "type": "akte",
        "documents": [
            {
                "title": "Bebauungsplan-Auszug Schlossgarten.pdf",
                "content": """Gemeinde Musterstadt — Bebauungsplan Nr. 47 "Schlossgarten"

Satzungsbeschluss vom 12.11.2025

Geltungsbereich: Gemarkung Musterstadt, Flur 3, Flurstuecke 124-142.

Art der baulichen Nutzung: Allgemeines Wohngebiet (WA) gemaess § 4 BauNVO.

Mass der baulichen Nutzung:
- GRZ: 0,4
- GFZ: 0,8
- Vollgeschosse: maximal II
- Hoehe baulicher Anlagen: Firsthoehe max. 10,50m

Erschliessung:
Die Erschliessung erfolgt ueber die Schlossallee (Bestandstrasse, Ausbau auf 7,00m)
sowie eine neu zu errichtende Planstrasse A (6,50m Breite inkl. Gehweg).

Gesamtkosten-Ansatz laut Haushaltsplan 2026: 2.300.000 € (Haushaltsansatz)

Baubeginn geplant: Juli 2026
Fertigstellung: Dezember 2026

Fristen:
- Ausschreibung bis zum 15.03.2026
- Vergabeverfahren bis 30.05.2026
- Baubeginn 15.07.2026
""",
            },
            {
                "title": "Kostenschaetzung Tiefbauamt 2026.pdf",
                "content": """Stadt Musterstadt — Tiefbauamt
Kostenschaetzung Erschliessung Schlossgarten (Stand 03/2026)

Gesamtkosten (aktualisierte Kostenschaetzung): 2.580.000 €

Gliederung:
- Erdbau und Baugrubensicherung: 420.000 €
- Strassenbau (inkl. Gehweg): 890.000 €
- Kanalisation (Schmutz- und Regenwasser): 680.000 €
- Strassenbeleuchtung: 85.000 €
- Gruenflaechen und Baumpflanzung: 140.000 €
- Telekommunikations-Leerrohre: 95.000 €
- Unvorhergesehenes (10%): 270.000 €

Die Kostenschaetzung liegt 280.000 € ueber dem Haushaltsansatz von 2.300.000 €.
Ein Nachtragshaushalt wird erforderlich.

Preisstand: Februar 2026. Preisanpassungen bei Vergabeverzoegerung moeglich.

Gez. Weber, Amtsleiter Tiefbauamt
""",
            },
            {
                "title": "TOeB-Stellungnahme Naturschutzbund.pdf",
                "content": """Naturschutzbund Deutschland e.V., Kreisverband Musterstadt
An die Stadtverwaltung Musterstadt

Stellungnahme zum Bebauungsplan Nr. 47 "Schlossgarten"

Wir erheben Widerspruch gegen den vorgelegten Bebauungsplan. Die vorgesehene
Erschliessungstrasse durchquert das Habitat einer geschuetzten Eidechsenpopulation
(Zauneidechse, FFH-Anhang IV).

Unsere Forderungen:
1. Einholung eines artenschutzrechtlichen Fachgutachtens vor Vergabeverfahren
2. Verlegung der Planstrasse A um mindestens 40m nach Osten
3. Anlage von Ausgleichsflaechen im Umfang von 1,5 ha

Die Antwort auf unsere Einwendung ist noch offen. Wir bitten um Stellungnahme
bis zum 22.04.2026.

Gez. Dr. Hoffmann, Vorsitzender
""",
            },
            {
                "title": "Protokoll Gemeinderat 14.03.2026.pdf",
                "content": """Protokoll der Gemeinderatssitzung vom 14.03.2026

TOP 4: Bebauungsplan Schlossgarten — Sachstand

Herr Buergermeister Mueller berichtet ueber den aktuellen Stand. Die Ausschreibung
ist vorbereitet, wird aber aufgrund der eingegangenen Stellungnahme des
Naturschutzbundes zurueckgestellt.

Frau Schmidt (Bauamt) informiert, dass die aktualisierte Kostenschaetzung
2.580.000 € betraegt und damit den Haushaltsansatz um 12% ueberschreitet.
Ein Nachtragshaushalt ist erforderlich.

Beschluss:
Der Gemeinderat beauftragt die Verwaltung,
1. bis zum 22.04.2026 eine Antwort auf die Einwendung des Naturschutzbundes
   zu erarbeiten
2. einen Nachtragshaushalt vorzubereiten und im Finanzausschuss am 07.05.2026
   einzubringen
3. das Vergabeverfahren erst nach Haushaltsfreigabe zu starten

Abstimmung: einstimmig

Gez. Lange, Protokollfuehrerin
""",
            },
            {
                "title": "Artenschutzrechtliches Fachgutachten.pdf",
                "content": """Gutachten zum Artenschutz — Flurstueck 124-142, Schlossgarten

Auftragnehmer: Dipl.-Biol. Richter
Datum: 08.04.2026

Kartierung vom 02.-05.04.2026 ergab Nachweise der Zauneidechse (Lacerta agilis)
auf den Flurstuecken 128 und 132. Schaetzung der Populationsgroesse: 40-60 Tiere.

Massnahmenvorschlag:
- Umsiedlung der Eidechsenpopulation auf eine Ausgleichsflaeche
- Erstellung von 15 Reptilienburgen (Steinhaufen, Sandlinsen)
- CEF-Massnahmen (continuous ecological functionality) vor Baubeginn

Kostenschaetzung der artenschutzrechtlichen Massnahmen: 85.000 €

Diese Kosten sind nicht im aktuellen Haushaltsansatz enthalten und kommen zu den
bereits bestehenden 280.000 € Mehrkosten hinzu.

Fazit: Eine Umsetzung der Erschliessung ist moeglich, erfordert aber CEF-Massnahmen
und Fristverschiebung. Baubeginn fruehestens September 2026.
""",
            },
            {
                "title": "Anwohner-Einwendung Strassenlaerm.pdf",
                "content": """Anwohnergemeinschaft Schlossallee
An die Stadt Musterstadt

Einwendung zum Bebauungsplan Schlossgarten

Die geplante Erschliessung wird zu einer erheblichen Verkehrsbelastung der
Schlossallee fuehren. Wir fordern:

1. Laermschutzgutachten vor Baubeginn
2. Temporeduzierung auf 30 km/h auf der Schlossallee
3. Errichtung einer Laermschutzwand entlang der Schlossallee

Die Stellungnahme der Verwaltung auf unsere Einwendung ist noch offen.
Klaerung erforderlich bis zum 30.04.2026.

52 Unterschriften beigefuegt.

Gez. Hoffmann, Sprecher Anwohnergemeinschaft
""",
            },
            {
                "title": "Finanzausschuss Tagesordnung 07.05.2026.pdf",
                "content": """Tagesordnung Finanzausschuss 07.05.2026

TOP 3: Nachtragshaushalt 2026 — Erschliessung Schlossgarten

Beschlussvorlage:
Die Mehrausgaben von 280.000 € (Kostensteigerung) plus voraussichtlich 85.000 €
(Artenschutzmassnahmen) sollen durch Nachtragshaushalt finanziert werden.

Gesamtvolumen Nachtrag: 365.000 €

Deckungsvorschlag:
- Ueberschuss aus laufendem Haushalt (Gewerbesteuer-Mehreinnahmen): 250.000 €
- Entnahme aus Ruecklage Infrastruktur: 115.000 €

Empfehlung des Kaemmerers:
Annahme des Nachtrags, jedoch Hinweis auf abschmelzende Infrastruktur-Ruecklage.
Weitere Kostensteigerungen muessten ueber Kreditaufnahme finanziert werden.
""",
            },
            {
                "title": "Vergabeunterlagen Entwurf Ausschreibung.pdf",
                "content": """Oeffentliche Ausschreibung (VOB/A)
Gegenstand: Erschliessungsarbeiten Schlossgarten

Auftragswert (geschaetzt): 2.580.000 € netto

Lose:
- Los 1: Erd- und Kanalarbeiten (ca. 1.100.000 €)
- Los 2: Strassenbau und Beleuchtung (ca. 975.000 €)
- Los 3: Gruenanlagen und CEF-Massnahmen (ca. 225.000 €)

Fristen:
- Veroeffentlichung geplant: 20.05.2026 (verschoben wegen Nachtragshaushalt)
- Angebotsfrist: 30.06.2026
- Zuschlag: 15.07.2026
- Baubeginn: 01.09.2026
- Fertigstellung: 15.12.2026

Eignungskriterien: Nachweis vergleichbarer Referenzprojekte ueber 1 Mio € der
letzten 3 Jahre.
""",
            },
        ],
    },

    "digitalstrategie_2030": {
        "name": "Digitalisierungsstrategie 2030",
        "description": "Strategiepapiere und Fachbereichs-Konzepte zur Digitalisierung der Verwaltung",
        "type": "wissensdb",
        "documents": [
            {
                "title": "Digitalisierungsstrategie Musterstadt 2030.pdf",
                "content": """Digitalisierungsstrategie der Stadt Musterstadt fuer den Zeitraum 2025-2030

Vision: Die Stadtverwaltung Musterstadt ist bis 2030 medienbruchfrei digital
arbeitsfaehig. Alle Fachverfahren werden digital gefuehrt, Buergerservices sind
online verfuegbar, und Mitarbeitende arbeiten ortsunabhaengig.

Handlungsfelder:
1. Digitale Buergerservices (OZG-Umsetzung)
2. Elektronische Akte (eAkte) in allen Fachbereichen
3. Agile Verwaltungskultur und Kompetenzentwicklung
4. IT-Infrastruktur und Cloud-Nutzung
5. Daten-getriebene Entscheidungsfindung

Zielsetzung bis 2027:
- 100% der OZG-Leistungen online verfuegbar
- eAkte in 8 von 12 Fachbereichen produktiv
- Nutzung einer souveraenen Cloud fuer sensible Daten

Das Gesamt-Investitionsvolumen wird auf 4,2 Mio € geschaetzt.

Die Strategie ist ein lebendes Dokument und wird jaehrlich fortgeschrieben.
""",
            },
            {
                "title": "Fachkonzept eAkte Bauamt.pdf",
                "content": """Fachkonzept eAkte im Bauamt

Das Bauamt fuehrt als erster Fachbereich die eAkte produktiv ein. Geplant ist die
Umstellung aller Neuakten ab 01.07.2026.

Bestandsakten werden rollierend digitalisiert: 500 Akten pro Quartal.

Anforderungen:
- DSGVO-konforme Speicherung
- Volltextsuche ueber alle Akten
- Signaturfaehigkeit (qualifizierte elektronische Signatur)
- Schnittstellen zum GIS und zum Meldewesen

Kosten (Einfuehrung + 3 Jahre Betrieb): 480.000 €
Frist fuer Produktivbetrieb: 01.07.2026

Hinweis: Die Kostenschaetzung beruht auf einem aelteren Angebot von 2024.
Eine Aktualisierung steht aus.
""",
            },
            {
                "title": "Bericht Cloud-Strategie Q1 2026.pdf",
                "content": """Bericht zur Cloud-Nutzung — Stand Q1 2026

In der Digitalisierungsstrategie 2030 wurde die Nutzung einer souveraenen Cloud
fuer sensible Daten festgelegt. Die Umsetzung erfolgt ueber die Deutsche
Verwaltungscloud-Strategie (DVC).

Stand:
- Vertrag mit kommunalem Rechenzentrum unterzeichnet
- 3 Pilotanwendungen migriert
- 8 weitere Anwendungen fuer 2026 geplant

Abweichung zur Strategie:
Die Strategie 2030 nennt ein Ziel von "souveraener Cloud fuer sensible Daten".
Das Bauamt-Fachkonzept verweist jedoch auf einen Cloud-Provider aus den USA.
Dieser Widerspruch muss geklaert werden.

Kostenstand:
- Bisherige Ausgaben: 320.000 €
- Prognose bis 2030: 1,8 Mio € (unter Strategie-Budget von 2,0 Mio €)
""",
            },
        ],
    },

    "haushalt_2026": {
        "name": "Jahreshaushalt 2026",
        "description": "Haushaltsplan, Erlaeuterungen, Fachplanungen",
        "type": "wissensdb",
        "documents": [
            {
                "title": "Haushaltsplan 2026 Vorlage.pdf",
                "content": """Haushaltsplan 2026 — Stadt Musterstadt

Gesamtvolumen:
- Einnahmen: 47,2 Mio €
- Ausgaben: 48,9 Mio €
- Defizit: 1,7 Mio € (ueber Ruecklage gedeckt)

Wesentliche Ausgaben:
- Personal: 18,4 Mio €
- Sachausgaben und Dienstleistungen: 12,1 Mio €
- Investitionen: 8,5 Mio € (Haushaltsansatz)
- Schuldendienst: 2,8 Mio €
- Zuweisungen und Umlagen: 7,1 Mio €

Groessere Investitionsprojekte:
- Sanierung Rathaus: Haushaltsansatz 1,8 Mio €
- Erschliessung Schlossgarten: Haushaltsansatz 2,3 Mio €
- Digitalisierung: Haushaltsansatz 0,9 Mio €
- Feuerwehr-Neubau: Haushaltsansatz 2,4 Mio €

Antrag auf Genehmigung durch den Gemeinderat bis 15.12.2025.
Frist fuer Verabschiedung: 31.01.2026.
""",
            },
            {
                "title": "Fortschreibung Investitionsplan Q1 2026.pdf",
                "content": """Fortschreibung Investitionsplan — Stand Ende Q1 2026

Uebersicht aktualisierte Kostenschaetzungen vs. Haushaltsansatz:

Rathaus-Sanierung:
- Ansatz: 1.800.000 €
- Kostenschaetzung aktuell: 1.950.000 € (+ 8%)

Erschliessung Schlossgarten:
- Ansatz: 2.300.000 €
- Kostenschaetzung aktuell: 2.580.000 € (+ 12%)

Digitalisierung:
- Ansatz: 900.000 €
- Kostenschaetzung aktuell: 870.000 € (unter Ansatz)

Feuerwehr-Neubau:
- Ansatz: 2.400.000 €
- Kostenschaetzung aktuell: 2.640.000 € (+ 10%)

Gesamtabweichung: + 640.000 € Mehrkosten
Nachtragshaushalt erforderlich bis 31.05.2026.
""",
            },
        ],
    },
}
