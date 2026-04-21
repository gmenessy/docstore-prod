"""
API-Routen: Export – PPTX, DOCX, PDF generieren und herunterladen.
Alle Exporte beziehen sich ausschliesslich auf einen Store.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.auth import verify_api_key
from app.models.database import Store, Document, Entity, DocumentStatus
from app.services.export_service import export_pptx, export_docx, export_pdf
from app.services.intelligence import generate_summary, extract_key_takeaways, distill_facts

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stores/{store_id}/export", tags=["Export"])


async def _load_store_data(db: AsyncSession, store_id: str) -> tuple:
    """Store mit Dokumenten und Entitaeten laden."""
    result = await db.execute(
        select(Store)
        .where(Store.id == store_id)
        .options(
            selectinload(Store.documents).selectinload(Document.entities),
        )
    )
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(404, "Sammlung nicht gefunden")

    indexed_docs = [d for d in store.documents if d.status == DocumentStatus.INDEXED]
    texts = [d.content_text for d in indexed_docs if d.content_text]

    # Entitaeten aggregieren
    entity_agg = {"personen": [], "daten": [], "fachbegriffe": [], "orte": [], "organisationen": []}
    type_map = {"person": "personen", "datum": "daten", "fachbegriff": "fachbegriffe",
                "ort": "orte", "organisation": "organisationen"}
    seen = set()
    for doc in indexed_docs:
        for ent in (doc.entities or []):
            key = f"{ent.entity_type.value}:{ent.value}"
            if key not in seen:
                seen.add(key)
                cat = type_map.get(ent.entity_type.value, "fachbegriffe")
                entity_agg[cat].append(ent.to_dict())

    return store, indexed_docs, texts, entity_agg


@router.get("/pptx")
async def export_store_pptx(
    store_id: str,
    title: str = Query(None, description="Praesentationstitel"),
    focus: str = Query("", description="Inhaltlicher Schwerpunkt"),
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    PowerPoint-Praesentation aus Store-Inhalten generieren.
    Gibt eine .pptx Datei zum Download zurueck.
    """
    store, docs, texts, entities = await _load_store_data(db, store_id)
    if not docs:
        raise HTTPException(400, "Keine indizierten Dokumente zum Exportieren")

    doc_dicts = [d.to_dict() for d in docs]
    params = {"title": title or f"Bericht: {store.name}", "focus": focus}
    store_type = store.type.value

    pptx_bytes = export_pptx(store.name, store_type, doc_dicts, params)

    filename = f"{store.name.replace(' ', '_')}_Export.pptx"
    return Response(
        content=pptx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/docx")
async def export_store_docx(
    store_id: str,
    title: str = Query(None, description="Dokumenttitel"),
    sections: str = Query(
        "Zusammenfassung,Kernfakten,Entitaeten,Dokumentenuebersicht,Quellen",
        description="Komma-separierte Abschnitte"
    ),
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    Word-Dokument aus Store-Inhalten generieren.
    Gibt eine .docx Datei zum Download zurueck.
    """
    store, docs, texts, entities = await _load_store_data(db, store_id)
    if not docs:
        raise HTTPException(400, "Keine indizierten Dokumente zum Exportieren")

    doc_dicts = [d.to_dict() for d in docs]
    params = {"title": title or f"Bericht: {store.name}", "sections": sections}
    store_type = store.type.value

    docx_bytes = export_docx(store.name, store_type, doc_dicts, entities, params)

    filename = f"{store.name.replace(' ', '_')}_Export.docx"
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/pdf")
async def export_store_pdf(
    store_id: str,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    PDF der Live-View (Zusammenfassung, Entitaeten, Fakten).
    Gibt eine .pdf Datei zum Download zurueck.
    """
    store, docs, texts, entities = await _load_store_data(db, store_id)

    summary = generate_summary(texts) if texts else "Keine Dokumente."
    takeaways = extract_key_takeaways(texts) if texts else []
    facts = distill_facts(texts) if texts else []
    doc_dicts = [d.to_dict() for d in docs]
    store_type = store.type.value

    pdf_bytes = export_pdf(
        store_name=store.name,
        store_type=store_type,
        summary=summary,
        takeaways=takeaways,
        entities_data=entities,
        facts=facts,
        documents=doc_dicts,
    )

    filename = f"{store.name.replace(' ', '_')}_LiveView.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
