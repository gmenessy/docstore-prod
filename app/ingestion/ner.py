"""
NER v2 – Erweiterte Entitaeten-Extraktion.

Zwei Modi:
  1. Regex-basiert (Standard, On-Premise, kein LLM noetig)
  2. LLM-gestuetzt (optional, via OpenAI-kompatible API)

Extrahiert:
  - Personen (inkl. Titel, Doppelnamen)
  - Daten (alle deutschen Formate)
  - Fachbegriffe (120+ kommunale Verwaltungs-/Recht-/IT-Terme)
  - Orte (Stadt, Gemeinde, Kreis, Adressen)
  - Organisationen (Aemter, Behoerden, Unternehmen)
  - PII (E-Mail, Telefon, IBAN, IP, Geburtsdatum, Aktenzeichen)
  - Geldbetraege (Euro, Mio, Mrd)
  - Gesetze & Paragraphen
"""
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExtractedEntities:
    """Alle extrahierten Entitaeten eines Dokuments."""
    personen: list[dict] = field(default_factory=list)
    daten: list[dict] = field(default_factory=list)
    fachbegriffe: list[dict] = field(default_factory=list)
    orte: list[dict] = field(default_factory=list)
    organisationen: list[dict] = field(default_factory=list)
    pii: list[dict] = field(default_factory=list)
    geldbetraege: list[dict] = field(default_factory=list)
    gesetze: list[dict] = field(default_factory=list)

    def all_flat(self) -> list[dict]:
        return (self.personen + self.daten + self.fachbegriffe + self.orte +
                self.organisationen + self.pii + self.geldbetraege + self.gesetze)

    def to_dict(self) -> dict:
        return {
            "personen": self.personen,
            "daten": self.daten,
            "fachbegriffe": self.fachbegriffe,
            "orte": self.orte,
            "organisationen": self.organisationen,
            "pii": self.pii,
            "geldbetraege": self.geldbetraege,
            "gesetze": self.gesetze,
        }

    @property
    def total_count(self) -> int:
        return len(self.all_flat())


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Fachbegriffe (120+ kommunale Verwaltungsterme)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FACHBEGRIFFE = [
    # Verwaltungsrecht
    "Verordnung", "Beschluss", "Antrag", "Genehmigung", "Satzung",
    "Haushalt", "Verwaltung", "Foerderung", "Massnahme", "Infrastruktur",
    "Bebauungsplan", "Flaechennutzungsplan", "Gemeindeordnung", "Kommunalrecht",
    "Vergaberecht", "Ausschreibung", "Zuschlag", "Leistungsverzeichnis",
    "Planfeststellung", "Baugenehmigung", "Denkmalschutz", "Umweltschutz",
    "Laermschutz", "Immissionsschutz", "Naturschutz", "Wasserschutz",
    "Foerdermittel", "Kofinanzierung", "Eigenanteil", "Zuwendung",
    "Rechnungspruefung", "Haushaltsplan", "Doppik", "Ergebnishaushalt",
    # Gremien & Dokumente
    "Protokoll", "Niederschrift", "Drucksache", "Vorlage", "Stellungnahme",
    "Gutachten", "Expertise", "Machbarkeitsstudie", "Konzept", "Strategie",
    "Leitfaden", "Richtlinie", "Handlungsempfehlung", "Rahmenvertrag",
    "Dienstanweisung", "Geschaeftsordnung", "Organisationsverfuegung",
    "Personalrat", "Gleichstellung", "Inklusion", "Nachhaltigkeit",
    # Digitalisierung
    "Digitalisierung", "Datenschutz", "DSGVO", "Compliance", "Barrierefreiheit",
    "OZG", "E-Government", "Smart City", "Open Data", "KI-Verordnung",
    "BSI-Grundschutz", "IT-Sicherheit", "Verschluesselung", "Authentifizierung",
    "Schnittstelle", "API", "Microservice", "Container", "Kubernetes",
    "E-Akte", "DMS", "Fachverfahren", "Registermodernisierung", "XOeV",
    "FIM", "DVDV", "VZD", "Serviceportal", "Buergerportal",
    # Finanzen
    "Kassenkredit", "Investitionskredit", "Tilgung", "Abschreibung",
    "Gewerbesteuer", "Grundsteuer", "Einkommensteuer", "Finanzzuweisung",
    "Schluesselzuweisung", "Kreisumlage", "Finanzausgleich",
    # Bau & Planung
    "Erschliessung", "Bautraeger", "Bauleitplanung", "Stadtentwicklung",
    "Verkehrsentwicklungsplan", "Radverkehrskonzept", "OEPNV",
    "Klimaschutzkonzept", "Energiekonzept", "Waermeplanung",
    # Personal
    "Stellenplan", "Besoldung", "Entgeltgruppe", "TVoeD", "Beamtenrecht",
    "Personalentwicklung", "Fortbildung", "Telearbeit", "Homeoffice",
]
# Auch mit Umlauten matchen
FACHBEGRIFFE_EXTRA = [
    "Foerderung", "Massnahme", "Flaechennutzungsplan",
    "Laermschutz", "Foerdermittel", "Rechnungspruefung",
    "Geschaeftsordnung", "Organisationsverfuegung",
    "Verschluesselung", "Schluesselzuweisung",
    # Original-Schreibweise
    "Förderung", "Maßnahme", "Flächennutzungsplan",
    "Lärmschutz", "Fördermittel", "Rechnungsprüfung",
    "Geschäftsordnung", "Organisationsverfügung",
    "Verschlüsselung", "Schlüsselzuweisung",
]
ALL_FACHBEGRIFFE = list(set(FACHBEGRIFFE + FACHBEGRIFFE_EXTRA))

MONATE = "Januar|Februar|Maerz|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Regex-basierte Extraktion (Standard)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def extract_entities(text: str) -> ExtractedEntities:
    """Entitaeten aus deutschem Text extrahieren (Regex-basiert)."""
    if not text:
        return ExtractedEntities()

    result = ExtractedEntities()

    # ── Personen (erweitert: Doppelnamen, Adelstitel) ──
    person_patterns = [
        r"(?:Herr|Frau)\s+(?:(?:Dr|Prof|Dipl|Ing)\.\s*)*[A-ZÄÖÜ][a-zäöüß]+(?:[\-\s][A-ZÄÖÜ][a-zäöüß]+){0,2}",
        r"(?:Dr|Prof)\.\s+(?:med\.\s+|jur\.\s+|rer\.\s+nat\.\s+|ing\.\s+)?[A-ZÄÖÜ][a-zäöüß]+\s+[A-ZÄÖÜ][a-zäöüß]+(?:\-[A-ZÄÖÜ][a-zäöüß]+)?",
        r"(?:Buergermeister(?:in)?|Bürgermeister(?:in)?|Oberbuergermeister(?:in)?|Oberbürgermeister(?:in)?|Landrat|Landrätin|Minister(?:in)?)\s+[A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)?",
    ]
    for pattern in person_patterns:
        for match in re.finditer(pattern, text):
            name = match.group().strip()
            ctx = _context(text, match, 60)
            result.personen.append({"value": name, "count": 1, "context": ctx})
    result.personen = _deduplicate(result.personen)

    # ── Daten (alle deutschen Formate) ──
    datum_patterns = [
        rf"\d{{1,2}}\.\s*(?:{MONATE})\s+\d{{4}}",
        r"\d{1,2}\.\d{1,2}\.\d{2,4}",
        r"\d{4}-\d{2}-\d{2}",
        r"(?:Quartal|Q)[1-4]\s*[/\s]\s*\d{4}",
        r"(?:Anfang|Mitte|Ende)\s+\d{4}",
        r"(?:Frueh|Früh)jahr|(?:Sommer|Herbst|Winter)\s+\d{4}",
    ]
    for pattern in datum_patterns:
        for match in re.finditer(pattern, text):
            result.daten.append({"value": match.group().strip(), "count": 1, "context": _context(text, match, 40)})
    result.daten = _deduplicate(result.daten)

    # ── Fachbegriffe ──
    fach_counter = Counter()
    for term in ALL_FACHBEGRIFFE:
        count = len(re.findall(re.escape(term), text, re.IGNORECASE))
        if count > 0:
            fach_counter[term] = count
    for term, count in fach_counter.most_common():
        match = re.search(re.escape(term), text, re.IGNORECASE)
        ctx = _context(text, match, 40) if match else ""
        result.fachbegriffe.append({"value": term, "count": count, "context": ctx})

    # ── Orte (erweitert: Stadtteile, PLZ) ──
    ort_patterns = [
        r"(?:Stadt|Gemeinde|Kreis|Landkreis|Land|Bezirk|Stadtkreis|Ortsteil|Stadtteil)\s+[A-ZÄÖÜ][a-zäöüß\-]+(?:\s+[A-ZÄÖÜ][a-zäöüß\-]+)?",
        r"\b\d{5}\s+[A-ZÄÖÜ][a-zäöüß]+(?:\s+[a-zäöüß]+)*",  # PLZ + Ort
        r"(?:[A-ZÄÖÜ][a-zäöüß]+(?:strasse|straße|str\.|weg|platz|allee|gasse|ring))\s*\d+\w?",  # Straßenadressen
    ]
    for pattern in ort_patterns:
        for match in re.finditer(pattern, text):
            value = match.group().strip()
            if len(value) > 4:
                result.orte.append({"value": value, "count": 1, "context": _context(text, match, 30)})
    result.orte = _deduplicate(result.orte)

    # ── Organisationen (erweitert) ──
    org_patterns = [
        r"[A-ZÄÖÜ][a-zäöüß]+(?:amt|behoerde|behörde|ministerium|verwaltung|kammer|verband|agentur|institut|anstalt)",
        r"(?:Amt|Behoerde|Behörde|Ministerium|Referat|Abteilung|Dezernat|Fachbereich|Stabsstelle)\s+(?:fuer\s+|für\s+)?[A-ZÄÖÜ][a-zäöüß]+(?:\s+(?:und\s+)?[a-zäöüß]+)*",
        r"(?:Komm\.ONE|SAP|Microsoft|Oracle|IBM|Telekom|Dataport|ITEOS|ekom21|Civitec|regio\s*iT)",
        r"[A-ZÄÖÜ]{2,}(?:\s+[A-ZÄÖÜ]{2,})+\b(?!\s*[:=])",  # Akronyme: BW, BW IT
    ]
    for pattern in org_patterns:
        for match in re.finditer(pattern, text):
            value = match.group().strip()
            if len(value) > 3:
                result.organisationen.append({"value": value, "count": 1, "context": _context(text, match, 30)})
    result.organisationen = _deduplicate(result.organisationen)

    # ── PII (personenbezogene Daten) ──
    pii_patterns = [
        (r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", "email"),
        (r"(?:\+49|0049|0)\s*[\d\s/\-()]{8,16}", "telefon"),
        (r"[A-Z]{2}\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{0,4}", "iban"),
        (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "ip_adresse"),
        (r"(?:geb(?:oren)?\.?\s*(?:am\s*)?\d{1,2}\.\d{1,2}\.\d{2,4})", "geburtsdatum"),
        (r"Az\.?\s*[:.]?\s*[\w\-/]+\d+", "aktenzeichen"),
        (r"(?:Steuer(?:nummer|ID|identifikation)|StNr|IdNr)[\s.:]*[\d\s/]{8,15}", "steuernummer"),
        (r"Personalausweis(?:nummer)?[\s.:]*[A-Z0-9]{9,}", "ausweisnummer"),
    ]
    for pattern, pii_type in pii_patterns:
        for match in re.finditer(pattern, text):
            result.pii.append({"value": match.group().strip(), "type": pii_type, "count": 1, "context": _context(text, match, 30)})
    result.pii = _deduplicate(result.pii, key_field="value")

    # ── Geldbetraege ──
    geld_patterns = [
        r"\d[\d.,]*\s*(?:Euro|EUR|€)",
        r"\d[\d.,]*\s*(?:Mio|Mrd|Tsd)\.?\s*(?:Euro|EUR|€)?",
        r"(?:Betrag|Budget|Kosten|Foerderung|Förderung|Investition|Volumen)\s*(?:von\s+|:\s*)?\d[\d.,]*\s*(?:Euro|EUR|€|Mio|Mrd)",
    ]
    for pattern in geld_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            result.geldbetraege.append({"value": match.group().strip(), "count": 1, "context": _context(text, match, 40)})
    result.geldbetraege = _deduplicate(result.geldbetraege)

    # ── Gesetze & Paragraphen ──
    gesetz_patterns = [
        r"§\s*\d+[a-z]?\s*(?:Abs\.\s*\d+)?\s*(?:S\.\s*\d+)?\s*(?:[A-ZÄÖÜ][A-Za-zÄÖÜäöüß]+(?:G|O|V|B)\b)?",
        r"(?:Artikel|Art\.)\s*\d+\s*(?:Abs\.\s*\d+)?(?:\s+(?:GG|DSGVO|EUV|AEUV|BayVwVfG|VwVfG|BauGB|BGB|StGB))?",
        r"(?:GG|BGB|StGB|VwVfG|VwGO|BauGB|BImSchG|WHG|BNatSchG|GemO|KomHVO|LHO|BHO|TVoeD|TVöD|BeamtStG|DSGVO|BDSG|LDSG|OZG|EGovG)\b",
    ]
    for pattern in gesetz_patterns:
        for match in re.finditer(pattern, text):
            value = match.group().strip()
            if len(value) > 1:
                result.gesetze.append({"value": value, "count": 1, "context": _context(text, match, 40)})
    result.gesetze = _deduplicate(result.gesetze)

    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LLM-gestuetzte Extraktion (optional)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NER_SYSTEM_PROMPT = """Du bist ein NER-Extraktor fuer deutsche Verwaltungsdokumente.
Extrahiere ALLE Entitaeten aus dem folgenden Text und gib sie als JSON zurueck.

Kategorien:
- personen: Namen von Personen (mit Titel)
- daten: Datumsangaben und Fristen
- orte: Orte, Adressen, Regionen
- organisationen: Aemter, Behoerden, Firmen
- fachbegriffe: Verwaltungs- und Fachterminologie
- geldbetraege: Betraege in Euro
- gesetze: Gesetze, Paragraphen, Vorschriften

Antwort NUR als JSON, kein anderer Text:
{"personen": [...], "daten": [...], "orte": [...], "organisationen": [...], "fachbegriffe": [...], "geldbetraege": [...], "gesetze": [...]}
Jeder Eintrag: {"value": "...", "context": "kurzer Kontext-Satz"}
"""


async def extract_entities_llm(
    text: str,
    provider_id: str = "ollama",
    model: str = None,
) -> ExtractedEntities:
    """
    LLM-gestuetzte NER-Extraktion (optional).
    Faellt auf Regex-Extraktion zurueck bei Fehler.

    API-Keys werden nur noch über Umgebungsvariablen konfiguriert (DOCSTORE_*_API_KEY).
    """
    import json as json_module
    from app.core.llm_client import llm_client

    # Nur ersten 3000 Zeichen an LLM senden (Kosten/Latenz)
    truncated = text[:3000]

    try:
        result = await llm_client.chat_completion(
            messages=[
                {"role": "system", "content": NER_SYSTEM_PROMPT},
                {"role": "user", "content": truncated},
            ],
            provider_id=provider_id,
            model=model,
            temperature=0.1,
            max_tokens=2000,
        )

        content = result.get("content", "")
        # JSON parsen (robust: suche nach erstem { ... })
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if not json_match:
            raise ValueError("Kein JSON in LLM-Antwort")

        data = json_module.loads(json_match.group())
        entities = ExtractedEntities()

        for cat in ["personen", "daten", "orte", "organisationen", "fachbegriffe", "geldbetraege", "gesetze"]:
            items = data.get(cat, [])
            target = getattr(entities, cat)
            for item in items:
                if isinstance(item, str):
                    target.append({"value": item, "count": 1, "context": ""})
                elif isinstance(item, dict):
                    target.append({"value": item.get("value", str(item)), "count": 1, "context": item.get("context", "")})

        # Mit Regex-Ergebnissen mergen (fuer Vollstaendigkeit)
        regex_result = extract_entities(text)
        entities = _merge_results(entities, regex_result)
        return entities

    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"LLM-NER fehlgeschlagen, Fallback auf Regex: {e}")
        return extract_entities(text)


def _merge_results(llm: ExtractedEntities, regex: ExtractedEntities) -> ExtractedEntities:
    """LLM- und Regex-Ergebnisse zusammenfuehren (dedupliziert)."""
    merged = ExtractedEntities()
    for cat in ["personen", "daten", "fachbegriffe", "orte", "organisationen", "pii", "geldbetraege", "gesetze"]:
        llm_items = getattr(llm, cat, [])
        regex_items = getattr(regex, cat, [])
        combined = llm_items + regex_items
        setattr(merged, cat, _deduplicate(combined))
    return merged


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Hilfsfunktionen
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _context(text: str, match, radius: int = 50) -> str:
    """Kontext um einen Match extrahieren."""
    if not match:
        return ""
    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    return text[start:end].strip()


def _deduplicate(entities: list[dict], key_field: str = "value") -> list[dict]:
    """Entitaeten deduplizieren und Haeufigkeiten zusammenfassen."""
    seen = {}
    for e in entities:
        key = e.get(key_field, "").lower()
        if not key:
            continue
        if key in seen:
            seen[key]["count"] = seen[key].get("count", 1) + 1
        else:
            seen[key] = {**e}
    return sorted(seen.values(), key=lambda x: x.get("count", 0), reverse=True)
