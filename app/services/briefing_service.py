"""
Briefing-Service — Entscheider-Briefing in einer Pipeline.

Aggregiert in einem Call:
- Sachstand (aus Live-View oder neu generiert)
- Risiken (aus risk_service)
- Naechste Schritte (Top-Tasks nach Prioritaet+Frist)
- KI-Loesungsvorschlag (LLM-Call ueber alle Daten zusammen)

Alles mit Transparenz: Quellen-Anzahl, Modell, Confidence.
"""
import logging
from datetime import datetime, date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Store, Document, PlanTask, TaskStatus, TaskPriority
from app.services.risk_service import analyze_store_risks
from app.services.intelligence import generate_summary_llm, generate_summary

logger = logging.getLogger(__name__)


async def _top_next_steps(db: AsyncSession, store_id: str, limit: int = 5) -> list[dict]:
    """
    Liefert Top-Tasks sortiert nach:
    1. Prioritaet (hoch > mittel > niedrig)
    2. Faelligkeit (ueberfaellig > dringend > regulaer)
    3. Status (active > planning > backlog)
    """
    result = await db.execute(
        select(PlanTask)
        .where(PlanTask.store_id == store_id)
        .where(PlanTask.status != TaskStatus.DONE)
    )
    tasks = result.scalars().all()

    priority_order = {TaskPriority.HIGH: 0, TaskPriority.MEDIUM: 1, TaskPriority.LOW: 2}
    status_order = {TaskStatus.ACTIVE: 0, TaskStatus.PLANNING: 1, TaskStatus.BACKLOG: 2}

    def sort_key(t):
        due_urgency = 999
        if t.due_date:
            try:
                due = datetime.fromisoformat(t.due_date.split("T")[0]).date() if "T" in (t.due_date or "") \
                    else datetime.strptime(t.due_date, "%Y-%m-%d").date() if t.due_date else None
                if due:
                    due_urgency = (due - date.today()).days
            except (ValueError, AttributeError):
                pass
        return (
            priority_order.get(t.priority, 3),
            due_urgency,
            status_order.get(t.status, 3),
        )

    tasks_sorted = sorted(tasks, key=sort_key)[:limit]

    result_list = []
    for t in tasks_sorted:
        is_wiki_maintenance = (t.source_document or "").startswith("wiki-lint:")
        result_list.append({
            "id": t.id,
            "title": t.title,
            "description": t.description[:150] if t.description else "",
            "assignee": t.assignee or "",
            "due_date": t.due_date or "",
            "priority": t.priority.value if t.priority else "mittel",
            "status": t.status.value if t.status else "backlog",
            "is_wiki_maintenance": is_wiki_maintenance,
        })
    return result_list


async def _generate_solution_proposal(
    store_name: str,
    sachstand: str,
    risks: list[dict],
    next_steps: list[dict],
) -> dict:
    """
    LLM-Call: Synthese aus Sachstand + Risiken + Schritten → Loesungsvorschlag.
    Fallback-Modus wenn kein LLM verfuegbar.
    """
    if not risks and not next_steps:
        return {
            "text": "Die Akte scheint aktuell ohne akute Entscheidungsbedarfe. Routine-Bearbeitung empfohlen.",
            "model": "regel-basiert",
            "sources": 0,
            "confidence": 0.5,
        }

    try:
        from app.core.llm_client import llm_client

        risks_text = "\n".join(
            f"- [{r['severity'].upper()}] {r['title']}: {r.get('description', '')[:150]}"
            for r in risks[:5]
        )
        steps_text = "\n".join(
            f"- {s['title']} ({s['priority']}, Frist: {s.get('due_date', 'offen')})"
            for s in next_steps[:5]
        )

        prompt_user = f"""Sachstand der Akte '{store_name}':
{sachstand}

Identifizierte Risiken:
{risks_text or '(keine)'}

Geplante naechste Schritte:
{steps_text or '(keine)'}

Formuliere in 2-3 Saetzen eine konkrete Handlungsempfehlung fuer einen Entscheider.
Beziehe dich auf die Risiken und schlage einen Weg vor wie die naechsten Schritte
zeitlich und inhaltlich sinnvoll verknuepft werden koennten. Schreibe klar und knapp
in Verwaltungsdeutsch. Keine Aufzaehlungen, nur Fliesstext."""

        result = await llm_client.chat_completion(
            messages=[
                {"role": "system", "content": "Du bist ein erfahrener Verwaltungsberater. "
                 "Du synthetisierst Entscheidungsempfehlungen aus Lageinformationen."},
                {"role": "user", "content": prompt_user},
            ],
            provider_id="ollama",
            max_tokens=300,
        )

        if result and result.get("content"):
            return {
                "text": result["content"].strip(),
                "model": result.get("model", "ollama"),
                "provider": result.get("provider", "ollama"),
                "sources": len(risks) + len(next_steps),
                "confidence": 0.85,
            }
    except Exception as e:
        logger.warning(f"Loesungsvorschlag LLM-Fehler: {e}, Fallback")

    # Fallback: Regel-basierte Empfehlung
    rot_count = sum(1 for r in risks if r["severity"] == "rot")
    high_prio_count = sum(1 for s in next_steps if s["priority"] == "hoch")

    if rot_count > 0:
        text = (f"Es bestehen {rot_count} akute Risiken die vorrangig zu adressieren sind. "
                f"Parallel sollten die {high_prio_count} hochprioritaere Massnahmen eingetaktet werden. "
                "Eine Priorisierung in der naechsten Sitzung wird empfohlen.")
    elif high_prio_count > 0:
        text = (f"Die Akte ist in geordneter Bearbeitung. {high_prio_count} prioritaere Schritte "
                "koennen zeitnah umgesetzt werden. Keine akuten Eskalationen erforderlich.")
    else:
        text = "Routinebearbeitung empfohlen. Keine akuten Entscheidungsbedarfe erkennbar."

    return {
        "text": text,
        "model": "regel-basiert",
        "sources": len(risks) + len(next_steps),
        "confidence": 0.6,
    }


async def generate_briefing(db: AsyncSession, store_id: str) -> dict:
    """
    Hauptfunktion: Erzeugt komplettes Decision-Briefing in einem Aufruf.
    """
    # Store laden
    store_result = await db.execute(select(Store).where(Store.id == store_id))
    store = store_result.scalar_one_or_none()
    if not store:
        return {"error": "Store nicht gefunden"}

    # Dokumente zaehlen & Summary
    docs_result = await db.execute(
        select(Document).where(Document.store_id == store_id)
    )
    documents = docs_result.scalars().all()

    doc_count = len(documents)
    total_pages = sum(d.page_count or 0 for d in documents)

    # 1. Sachstand — nutzt existierende Summary
    texts = [d.content_text for d in documents if d.content_text]
    sachstand_sources = len([d for d in documents if d.content_text])

    if texts:
        llm_summary = await generate_summary_llm(texts, store.name, max_sentences=3)
        sachstand = llm_summary if llm_summary else generate_summary(texts, max_sentences=3)
        sachstand_model = "llm" if llm_summary else "extraktiv"
        sachstand_confidence = 0.87 if llm_summary else 0.65
    else:
        sachstand = "Noch keine Dokumente in dieser Sammlung."
        sachstand_model = "leer"
        sachstand_confidence = 0.0

    # 2. Risiken
    risk_data = await analyze_store_risks(db, store_id)

    # 3. Naechste Schritte
    next_steps = await _top_next_steps(db, store_id, limit=5)

    # 4. Loesungsvorschlag
    solution = await _generate_solution_proposal(
        store_name=store.name,
        sachstand=sachstand,
        risks=risk_data["risks"],
        next_steps=next_steps,
    )

    return {
        "store": {
            "id": store.id,
            "name": store.name,
            "type": store.type.value if store.type else "akte",
            "doc_count": doc_count,
            "page_count": total_pages,
            "updated_at": store.updated_at.isoformat() if store.updated_at else None,
        },
        "sachstand": {
            "text": sachstand,
            "sources": sachstand_sources,
            "confidence": sachstand_confidence,
            "model": sachstand_model,
        },
        "risiken": risk_data,
        "naechste_schritte": next_steps,
        "loesungsvorschlag": solution,
        "generated_at": datetime.utcnow().isoformat(),
    }
