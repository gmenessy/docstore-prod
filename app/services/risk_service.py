"""
Risk-Service — Erkennung konkreter Verwaltungs-Risiken.

Analysiert Dokumente, Wiki-Seiten und NER-Ergebnisse um konkrete Risiken
fuer Entscheider abzuleiten:
- Kostenabweichungen (Zahlen-Vergleich)
- Faellige Fristen (Datum-Extraktion + Deadline-Matching)
- Widersprueche (aus Wiki-Lint uebernommen)
- Unbeantwortete Einwendungen (Pattern-Matching)
"""
import re
import logging
from datetime import datetime, date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Document, WikiPage, PlanTask

logger = logging.getLogger(__name__)


# Schweregrad-Mapping
SEVERITY_ROT = "rot"      # Faellige Frist, ungeloeste Widersprueche, Budget > 10% ueber
SEVERITY_AMBER = "amber"  # Frist in < 14 Tagen, Budget 5-10% ueber
SEVERITY_GELB = "gelb"    # Geringer Abweichungen, Hinweise

# Regex-Patterns fuer Risiko-Erkennung
PATTERN_KOSTEN = re.compile(
    r"(?P<type>ansatz|kosten(?:schaetzung|voranschlag)?|budget|haushaltsansatz|gesamtkosten)\s*[:\s]\s*"
    r"(?P<amount>[\d\.,]+)\s*(?P<unit>mio|mrd|euro|eur|€|tausend|t€)",
    re.IGNORECASE
)
PATTERN_FRIST = re.compile(
    r"(?:bis\s+(?:zum\s+)?|spaetestens\s+|fristgerecht\s+(?:bis\s+)?|frist[:\s]+)"
    r"(?P<date>\d{1,2}\.\s*\d{1,2}\.\s*\d{4})",
    re.IGNORECASE
)
PATTERN_EINWENDUNG = re.compile(
    r"(einwendung|widerspruch|stellungnahme|einspruch)\s+"
    r"(?:von|durch|des|der)\s+(?P<quelle>[A-ZÄÖÜ][\w\-\s]{3,40})",
    re.IGNORECASE
)
PATTERN_AKTION_OFFEN = re.compile(
    r"(?P<verb>antwort(?:en)?|bearbeit(?:en|ung)|pruef(?:en|ung)|stellungnahme|klaer(?:en|ung))\s+"
    r"(?:ist\s+)?(?:noch\s+)?(?:offen|erforderlich|ausstehend|unbeantwortet)",
    re.IGNORECASE
)


def _parse_german_date(s: str) -> date | None:
    """Parse '15.04.2026' oder '15. 04. 2026' → date-Objekt."""
    try:
        cleaned = re.sub(r"\s+", "", s)
        return datetime.strptime(cleaned, "%d.%m.%Y").date()
    except (ValueError, AttributeError):
        return None


def _parse_amount(amount: str, unit: str) -> float | None:
    """'2,3' + 'Mio' → 2300000.0"""
    try:
        val = float(amount.replace(".", "").replace(",", "."))
        unit_lower = unit.lower()
        if unit_lower in ("mio",):
            return val * 1_000_000
        if unit_lower in ("mrd",):
            return val * 1_000_000_000
        if unit_lower in ("tausend", "t€"):
            return val * 1000
        return val
    except (ValueError, AttributeError):
        return None


def _extract_kosten(text: str) -> list[dict]:
    """Findet alle Kostenangaben im Text."""
    results = []
    for m in PATTERN_KOSTEN.finditer(text):
        amount = _parse_amount(m.group("amount"), m.group("unit"))
        if amount:
            results.append({
                "type": m.group("type").lower(),
                "amount": amount,
                "text": m.group(0),
                "pos": m.start(),
            })
    return results


def _extract_fristen(text: str) -> list[dict]:
    """Findet faellige Fristen im Text."""
    results = []
    today = date.today()
    for m in PATTERN_FRIST.finditer(text):
        due = _parse_german_date(m.group("date"))
        if not due:
            continue
        days_until = (due - today).days
        context_start = max(0, m.start() - 100)
        context = text[context_start:m.end() + 50].strip()
        results.append({
            "due_date": due.isoformat(),
            "days_until": days_until,
            "context": context[:200],
            "overdue": days_until < 0,
        })
    return results


def _extract_offene_aktionen(text: str) -> list[dict]:
    """Findet offene Aktionen (Antwort ausstehend, Klaerung erforderlich)."""
    results = []
    for m in PATTERN_AKTION_OFFEN.finditer(text):
        context_start = max(0, m.start() - 150)
        context = text[context_start:m.end() + 50].strip()
        einwendung_match = PATTERN_EINWENDUNG.search(context)
        quelle = einwendung_match.group("quelle").strip() if einwendung_match else None
        results.append({
            "verb": m.group("verb").lower(),
            "quelle": quelle,
            "context": context[:200],
        })
    return results


async def analyze_store_risks(db: AsyncSession, store_id: str) -> dict:
    """
    Hauptanalyse: Aggregiert Risiken ueber alle Dokumente einer Sammlung.

    Returns:
        {
          "total": int,
          "by_severity": {"rot": N, "amber": N, "gelb": N},
          "risks": [{severity, type, title, description, source, due_date?, ...}],
          "generated_at": ISO-timestamp
        }
    """
    docs_result = await db.execute(
        select(Document).where(Document.store_id == store_id)
    )
    documents = docs_result.scalars().all()

    if not documents:
        return {
            "total": 0,
            "by_severity": {"rot": 0, "amber": 0, "gelb": 0},
            "risks": [],
            "generated_at": datetime.utcnow().isoformat(),
        }

    all_risks = []
    all_kosten = []

    for doc in documents:
        if not doc.content_text:
            continue

        text = doc.content_text
        doc_label = doc.title or doc.id[:8]

        # 1. Fristen
        for frist in _extract_fristen(text):
            if frist["overdue"]:
                severity = SEVERITY_ROT
                title = f"Ueberfaellige Frist: {frist['due_date']}"
            elif frist["days_until"] <= 14:
                severity = SEVERITY_AMBER
                title = f"Frist in {frist['days_until']} Tagen: {frist['due_date']}"
            else:
                continue  # nur nahe/ueberfaellige Fristen als Risiko

            all_risks.append({
                "severity": severity,
                "type": "frist",
                "title": title,
                "description": frist["context"],
                "source": doc_label,
                "source_doc_id": doc.id,
                "due_date": frist["due_date"],
                "days_until": frist["days_until"],
            })

        # 2. Offene Aktionen
        for aktion in _extract_offene_aktionen(text):
            quelle_text = f" von {aktion['quelle']}" if aktion["quelle"] else ""
            all_risks.append({
                "severity": SEVERITY_AMBER,
                "type": "offene_aktion",
                "title": f"Offene {aktion['verb'].title()}{quelle_text}",
                "description": aktion["context"],
                "source": doc_label,
                "source_doc_id": doc.id,
            })

        # 3. Kosten sammeln (Vergleich am Ende)
        for kosten in _extract_kosten(text):
            all_kosten.append({
                **kosten,
                "source": doc_label,
                "source_doc_id": doc.id,
            })

    # 4. Kosten-Abweichungs-Analyse
    # Finde "Ansatz" und "Kostenschaetzung" im gleichen Umfeld
    ansatz_values = [k for k in all_kosten if "ansatz" in k["type"] or "haushalt" in k["type"] or "budget" in k["type"]]
    schaetzung_values = [k for k in all_kosten if "schaetzung" in k["type"] or "gesamt" in k["type"]]

    if ansatz_values and schaetzung_values:
        ansatz_amount = max(k["amount"] for k in ansatz_values)
        schaetzung_amount = max(k["amount"] for k in schaetzung_values)

        if schaetzung_amount > ansatz_amount:
            abweichung_pct = ((schaetzung_amount - ansatz_amount) / ansatz_amount) * 100

            if abweichung_pct >= 10:
                severity = SEVERITY_ROT
            elif abweichung_pct >= 5:
                severity = SEVERITY_AMBER
            else:
                severity = SEVERITY_GELB

            all_risks.append({
                "severity": severity,
                "type": "kostenabweichung",
                "title": f"Kostenschaetzung ueberschreitet Ansatz um {abweichung_pct:.0f}%",
                "description": f"Ansatz: {ansatz_amount:,.0f} € · Schaetzung: {schaetzung_amount:,.0f} €",
                "source": "Kostenvergleich",
                "amount_delta": schaetzung_amount - ansatz_amount,
                "amount_pct": abweichung_pct,
            })

    # 5. Wiki-Widersprueche uebernehmen (falls vorhanden)
    wiki_result = await db.execute(
        select(WikiPage).where(WikiPage.store_id == store_id)
    )
    wiki_pages = wiki_result.scalars().all()

    for page in wiki_pages:
        flags = page.contradiction_flags or []
        for flag in flags:
            if isinstance(flag, dict):
                desc = flag.get("description", "") or flag.get("text", "")
                source = flag.get("source_document", page.title)
            else:
                desc = str(flag)
                source = page.title

            all_risks.append({
                "severity": SEVERITY_AMBER,
                "type": "widerspruch",
                "title": f"Widerspruch in '{page.title}'",
                "description": desc[:200],
                "source": source,
                "wiki_slug": page.slug,
            })

    # Dedup nach (type, source_doc_id, title)
    seen = set()
    deduped = []
    for r in all_risks:
        key = (r["type"], r.get("source_doc_id"), r["title"][:50])
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    # Sortieren: rot → amber → gelb, dann nach Typ
    severity_order = {SEVERITY_ROT: 0, SEVERITY_AMBER: 1, SEVERITY_GELB: 2}
    deduped.sort(key=lambda r: (severity_order.get(r["severity"], 3), r["type"]))

    # Top 10 nehmen
    top_risks = deduped[:10]

    return {
        "total": len(deduped),
        "by_severity": {
            SEVERITY_ROT: sum(1 for r in deduped if r["severity"] == SEVERITY_ROT),
            SEVERITY_AMBER: sum(1 for r in deduped if r["severity"] == SEVERITY_AMBER),
            SEVERITY_GELB: sum(1 for r in deduped if r["severity"] == SEVERITY_GELB),
        },
        "risks": top_risks,
        "generated_at": datetime.utcnow().isoformat(),
    }
