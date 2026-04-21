"""
Synthesis-Service — Pipeline-Trace fuer eine Sammlung.

Liefert Daten fuer die Synthesis-View:
- Zaehler pro Pipeline-Stufe (Dokumente → Chunks → Wiki → Entitaeten → Risiken → Loesung)
- Verbindungen zwischen Stufen (welche Chunks kamen aus welchen Dokumenten)
- Drill-Downs auf Einzelelemente (click auf "Kosten-Risiko" zeigt Quellen)
"""
import logging
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Store, Document, Entity, PlanTask, WikiPage
from app.services.risk_service import analyze_store_risks

logger = logging.getLogger(__name__)


async def get_synthesis_trace(db: AsyncSession, store_id: str) -> dict:
    """
    Baut den Pipeline-Trace fuer eine Sammlung.

    Return-Schema:
    {
      "stages": [
        {"id": "documents", "label": "Dokumente", "count": 14, "duration_ms": 0, "items": [...]},
        {"id": "chunks", ...},
        {"id": "wiki", ...},
        {"id": "entities", ...},
        {"id": "risks", ...},
        {"id": "tasks", ...},
        {"id": "briefing", ...}
      ],
      "edges": [
        {"from": "documents", "to": "chunks", "label": "extrahiert"},
        ...
      ],
      "generated_at": ISO
    }
    """
    # Dokumente
    docs_result = await db.execute(
        select(Document).where(Document.store_id == store_id)
    )
    documents = docs_result.scalars().all()
    doc_items = [
        {
            "id": d.id,
            "title": d.title,
            "pages": d.page_count or 0,
            "chunks": d.chunk_count or 0,
            "indexed": d.indexed_at is not None,
            "status": d.status.value if d.status else "pending",
        }
        for d in documents[:10]
    ]

    total_chunks = sum(d.chunk_count or 0 for d in documents)
    total_pages = sum(d.page_count or 0 for d in documents)

    # Entitaeten (NER-Ergebnisse)
    entities_result = await db.execute(
        select(Entity).join(Document).where(Document.store_id == store_id)
    )
    entities = entities_result.scalars().all()
    entity_by_type = {}
    for e in entities:
        etype = e.entity_type.value if e.entity_type else "sonstiges"
        entity_by_type.setdefault(etype, 0)
        entity_by_type[etype] += 1

    # Wiki-Seiten
    wiki_result = await db.execute(
        select(WikiPage).where(WikiPage.store_id == store_id)
    )
    wiki_pages = wiki_result.scalars().all()
    wiki_items = [
        {
            "slug": w.slug,
            "title": w.title,
            "type": w.page_type.value if w.page_type else "entity",
            "sources": len(w.source_documents or []),
            "contradictions": len(w.contradiction_flags or []),
        }
        for w in wiki_pages[:10]
    ]
    total_contradictions = sum(len(w.contradiction_flags or []) for w in wiki_pages)

    # Risiken
    risk_data = await analyze_store_risks(db, store_id)

    # Tasks
    tasks_result = await db.execute(
        select(PlanTask).where(PlanTask.store_id == store_id)
    )
    tasks = tasks_result.scalars().all()
    task_items = [
        {
            "id": t.id,
            "title": t.title,
            "priority": t.priority.value if t.priority else "mittel",
            "status": t.status.value if t.status else "backlog",
            "is_wiki_maintenance": (t.source_document or "").startswith("wiki-lint:"),
        }
        for t in tasks[:10]
    ]
    tasks_open = sum(1 for t in tasks if t.status and t.status.value != "done")
    tasks_wiki = sum(1 for t in tasks if (t.source_document or "").startswith("wiki-lint:"))

    stages = [
        {
            "id": "documents",
            "label": "Dokumente",
            "description": "Extrahierter Volltext aus PDF, DOCX, PPTX",
            "count": len(documents),
            "sublabel": f"{total_pages} Seiten",
            "items": doc_items,
            "icon": "doc",
        },
        {
            "id": "chunks",
            "label": "Text-Chunks",
            "description": "Semantische Segmentierung fuer RAG-Suche",
            "count": total_chunks,
            "sublabel": f"~{total_chunks // max(len(documents), 1)} pro Dokument",
            "items": [],
            "icon": "layers",
        },
        {
            "id": "entities",
            "label": "Entitaeten",
            "description": "Named-Entity-Recognition fuer deutsche Verwaltung",
            "count": len(entities),
            "sublabel": ", ".join(f"{k}: {v}" for k, v in list(entity_by_type.items())[:3]) or "–",
            "items": [{"type": k, "count": v} for k, v in entity_by_type.items()],
            "icon": "tag",
        },
        {
            "id": "wiki",
            "label": "Wiki-Seiten",
            "description": "Kompiliertes Wissen durch LLM-Ingestion",
            "count": len(wiki_pages),
            "sublabel": f"{total_contradictions} Widersprueche geflaggt" if total_contradictions else "keine Widersprueche",
            "items": wiki_items,
            "icon": "book",
        },
        {
            "id": "risks",
            "label": "Risiken",
            "description": "Regel-basierte Erkennung + Wiki-Widersprueche",
            "count": risk_data["total"],
            "sublabel": f"{risk_data['by_severity'].get('rot', 0)} akut, {risk_data['by_severity'].get('amber', 0)} zu beobachten",
            "items": risk_data["risks"][:5],
            "icon": "warn",
        },
        {
            "id": "tasks",
            "label": "Massnahmen",
            "description": "Extrahierte Tasks aus Dokumenten + Wiki-Wartung",
            "count": len(tasks),
            "sublabel": f"{tasks_open} offen, {tasks_wiki} aus Wiki-Lint",
            "items": task_items,
            "icon": "plan",
        },
        {
            "id": "briefing",
            "label": "Decision-Briefing",
            "description": "LLM-Synthese aus allem Vorhergehenden",
            "count": 1,
            "sublabel": "Sachstand + Risiken + Schritte + Empfehlung",
            "items": [],
            "icon": "shield",
        },
    ]

    edges = [
        {"from": "documents", "to": "chunks", "label": "chunking"},
        {"from": "documents", "to": "entities", "label": "NER"},
        {"from": "chunks", "to": "wiki", "label": "LLM-Ingest"},
        {"from": "entities", "to": "wiki", "label": "Entitaets-Seiten"},
        {"from": "wiki", "to": "risks", "label": "Widersprueche"},
        {"from": "documents", "to": "risks", "label": "Regex-Muster"},
        {"from": "risks", "to": "tasks", "label": "Wiki-Lint-to-Tasks"},
        {"from": "documents", "to": "tasks", "label": "Massnahmen-Extraktion"},
        {"from": "risks", "to": "briefing", "label": ""},
        {"from": "tasks", "to": "briefing", "label": ""},
        {"from": "wiki", "to": "briefing", "label": ""},
    ]

    return {
        "stages": stages,
        "edges": edges,
        "generated_at": datetime.utcnow().isoformat(),
    }
