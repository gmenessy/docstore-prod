"""
API-Routen: Sammlungen (Stores) – CRUD + Live-View.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from app.core.auth import verify_api_key
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db, get_store_or_404
from app.models.database import Store, Document, Entity, StoreType, DocumentStatus, EntityType
from app.models.schemas import (
    StoreCreate, StoreUpdate, StoreResponse, StoreLiveView,
)
from app.services.intelligence import (
    generate_summary, extract_key_takeaways, fuse_knowledge, distill_facts,
)
from app.ingestion.ner import extract_entities as extract_entities_fn
from app.ingestion.ner import extract_entities

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stores", tags=["Sammlungen"])


# ─── CRUD ───

@router.get("", response_model=list[StoreResponse])
async def list_stores(db: AsyncSession = Depends(get_db), auth: str = Depends(verify_api_key)):
    """Alle Sammlungen auflisten."""
    result = await db.execute(
        select(Store).options(selectinload(Store.documents)).order_by(Store.created_at.desc())
    )
    stores = result.scalars().all()
    return [s.to_dict() for s in stores]


@router.post("", response_model=StoreResponse, status_code=201)
async def create_store(data: StoreCreate, db: AsyncSession = Depends(get_db), auth: str = Depends(verify_api_key)):
    """Neue Sammlung erstellen (Akte oder WissensDB)."""
    store = Store(
        name=data.name,
        type=StoreType(data.type),
        description=data.description,
        color=data.color,
        analyse_fokus=data.analyse_fokus,
    )
    db.add(store)
    await db.commit()
    await db.refresh(store)
    logger.info(f"Neue Sammlung erstellt: {store.name} ({store.type.value})")
    return store.to_dict()


@router.get("/{store_id}", response_model=StoreResponse)
async def get_store(store_id: str, db: AsyncSession = Depends(get_db), auth: str = Depends(verify_api_key)):
    """Einzelne Sammlung abrufen."""
    store = await get_store_or_404(db, store_id, load_docs=True)
    return store.to_dict()


@router.patch("/{store_id}", response_model=StoreResponse)
async def update_store(store_id: str, data: StoreUpdate, db: AsyncSession = Depends(get_db), auth: str = Depends(verify_api_key)):
    """Sammlung aktualisieren (Name, Beschreibung, Analyse-Fokus)."""
    store = await get_store_or_404(db, store_id, load_docs=True)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(store, field, value)

    await db.commit()
    await db.refresh(store)
    return store.to_dict()


@router.delete("/{store_id}", status_code=204)
async def delete_store(store_id: str, db: AsyncSession = Depends(get_db), auth: str = Depends(verify_api_key)):
    """Sammlung und alle zugehörigen Dokumente löschen."""
    store = await get_store_or_404(db, store_id)

    await db.delete(store)
    await db.commit()
    logger.info(f"Sammlung gelöscht: {store.name}")


# ─── Live-View ───

@router.get("/{store_id}/live-view")
async def get_live_view(store_id: str, db: AsyncSession = Depends(get_db), auth: str = Depends(verify_api_key)):
    """
    Live-View einer Sammlung: Zusammenfassung, Fusion, Destillierung, Entitäten.
    """
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

    # Dokument-Texte sammeln
    texts = [
        doc.content_text for doc in store.documents
        if doc.content_text and doc.status == DocumentStatus.INDEXED
    ]

    # Intelligence-Services
    summary = generate_summary(texts) if texts else "Keine indizierten Dokumente vorhanden."
    takeaways = extract_key_takeaways(texts) if texts else []
    fusion = fuse_knowledge(texts) if len(texts) > 1 else {}
    facts = distill_facts(texts) if texts else []

    # Entitäten aggregieren
    entity_agg = {"personen": [], "daten": [], "fachbegriffe": [], "orte": [], "organisationen": []}
    type_map = {
        "person": "personen", "datum": "daten", "fachbegriff": "fachbegriffe",
        "ort": "orte", "organisation": "organisationen",
    }
    seen = set()
    for doc in store.documents:
        for entity in (doc.entities or []):
            key = f"{entity.entity_type.value}:{entity.value}"
            if key not in seen:
                seen.add(key)
                cat = type_map.get(entity.entity_type.value, "fachbegriffe")
                entity_agg[cat].append(entity.to_dict())

    # Statistiken
    total_docs = len(store.documents)
    indexed_docs = sum(1 for d in store.documents if d.status == DocumentStatus.INDEXED)
    total_pages = sum(d.page_count for d in store.documents)
    total_chunks = sum(d.chunk_count for d in store.documents)
    with_images = sum(1 for d in store.documents if d.has_images)
    with_tables = sum(1 for d in store.documents if d.has_tables)

    return {
        "store": store.to_dict(),
        "summary": summary,
        "key_takeaways": takeaways,
        "fusion": fusion,
        "distilled_facts": facts,
        "entities": entity_agg,
        "stats": {
            "total_documents": total_docs,
            "indexed_documents": indexed_docs,
            "total_pages": total_pages,
            "total_chunks": total_chunks,
            "with_images": with_images,
            "with_tables": with_tables,
        },
    }


# ─── NER: Entitaeten neu extrahieren ───

@router.post("/{store_id}/reanalyze-ner")
async def reanalyze_ner(
    store_id: str,
    use_llm: bool = False,
    provider: str = "ollama",
    model: str = None,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    Entitaeten aller Dokumente eines Stores neu extrahieren.

    use_llm=False: Regex-basiert (Standard, schnell, on-premise)
    use_llm=True:  LLM-gestuetzt (optional, hoehere Qualitaet)

    API-Keys werden nur noch über Umgebungsvariablen konfiguriert (DOCSTORE_*_API_KEY).
    """
    result = await db.execute(
        select(Store)
        .where(Store.id == store_id)
        .options(selectinload(Store.documents).selectinload(Document.entities))
    )
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(404, "Sammlung nicht gefunden")

    indexed_docs = [d for d in store.documents if d.status == DocumentStatus.INDEXED]
    if not indexed_docs:
        return {"message": "Keine indizierten Dokumente", "entities_extracted": 0}

    total_new = 0
    for doc in indexed_docs:
        text = doc.content_text or ""
        if not text:
            continue

        # Alte Entitaeten loeschen
        for ent in list(doc.entities or []):
            await db.delete(ent)

        # Neu extrahieren
        if use_llm:
            from app.ingestion.ner import extract_entities_llm
            entities = await extract_entities_llm(text, provider, model)
        else:
            entities = extract_entities_fn(doc.content_text)

        # Speichern
        type_mapping = {
            "personen": EntityType.PERSON,
            "daten": EntityType.DATUM,
            "fachbegriffe": EntityType.FACHBEGRIFF,
            "orte": EntityType.ORT,
            "organisationen": EntityType.ORGANISATION,
        }
        for category, entity_type in type_mapping.items():
            for entity_data in getattr(entities, category, []):
                val = entity_data.get("value", entity_data) if isinstance(entity_data, dict) else str(entity_data)
                ctx = entity_data.get("context", "") if isinstance(entity_data, dict) else ""
                cnt = entity_data.get("count", 1) if isinstance(entity_data, dict) else 1
                from app.models.database import gen_id as gid
                new_ent = Entity(
                    id=gid(),
                    document_id=doc.id,
                    entity_type=entity_type,
                    value=val,
                    count=cnt,
                    context=ctx,
                )
                db.add(new_ent)
                total_new += 1

    await db.commit()
    mode = "LLM" if use_llm else "Regex"
    logger.info(f"NER [{mode}] fuer '{store.name}': {total_new} Entitaeten aus {len(indexed_docs)} Dokumenten")

    return {
        "store_id": store_id,
        "store_name": store.name,
        "mode": mode,
        "documents_processed": len(indexed_docs),
        "entities_extracted": total_new,
    }
