"""
Ingestion-Pipeline-Service.
Orchestriert: Upload → Extraktion → Chunking → NER → Indexierung.
"""
import asyncio
import datetime
import logging
import shutil
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.database import (
    Store, Document, Chunk, Entity,
    DocumentStatus, EntityType, gen_id,
)
from app.ingestion.extractor import extractor, ExtractionResult
from app.ingestion.chunker import chunk_text
from app.ingestion.ner import extract_entities
from app.search.engine import search_engine

logger = logging.getLogger(__name__)


async def ingest_document(
    db: AsyncSession,
    store_id: str,
    file_path: Path,
    original_filename: str,
    source_type: str = "upload",
    source_uri: str = "",
) -> AsyncGenerator[dict, None]:
    """
    Vollständige Ingestion-Pipeline als Async-Generator (für SSE-Streaming).

    Yields Status-Updates in jedem Schritt:
    {"step": "...", "progress": 0.0-1.0, "message": "..."}
    """
    doc_id = gen_id()
    file_type = Path(original_filename).suffix.lstrip(".").lower()

    # ── Schritt 1: Dokument in DB anlegen ──
    yield {"step": "init", "progress": 0.05, "message": "Dokument wird registriert…"}

    document = Document(
        id=doc_id,
        store_id=store_id,
        title=original_filename,
        file_type=file_type,
        file_path=str(file_path),
        file_size=file_path.stat().st_size,
        status=DocumentStatus.PROCESSING,
        source_type=source_type,
        source_uri=source_uri,
    )
    db.add(document)
    await db.commit()

    MAX_RETRIES = 2
    retry_count = 0

    while retry_count <= MAX_RETRIES:
        try:
            # ── Schritt 2: Text-Extraktion ──
            yield {"step": "extraction", "progress": 0.15, "message": f"Text-Extraktion ({file_type.upper()})..." + (f" (Versuch {retry_count + 1})" if retry_count > 0 else "")}

            # Extraktion in Thread-Pool (blockierende I/O)
            loop = asyncio.get_event_loop()
            extraction: ExtractionResult = await loop.run_in_executor(
                None, extractor.extract, file_path
            )

            if extraction.errors:
                if retry_count < MAX_RETRIES:
                    retry_count += 1
                    logger.warning(f"Extraktion fehlgeschlagen (Versuch {retry_count}): {extraction.errors}")
                    await asyncio.sleep(1.0 * retry_count)  # Exponential backoff
                    continue
                document.status = DocumentStatus.FAILED
                document.metadata_extra = {"errors": extraction.errors, "retries": retry_count}
                await db.commit()
                yield {"step": "error", "progress": 0, "message": f"Fehler nach {retry_count + 1} Versuchen: {'; '.join(extraction.errors)}"}
                return

            # Extraktion erfolgreich
            break

        except Exception as exc:
            if retry_count < MAX_RETRIES:
                retry_count += 1
                logger.warning(f"Extraktion Exception (Versuch {retry_count}): {exc}")
                await asyncio.sleep(1.0 * retry_count)
                continue
            document.status = DocumentStatus.FAILED
            document.metadata_extra = {"exception": str(exc), "retries": retry_count}
            await db.commit()
            yield {"step": "error", "progress": 0, "message": f"Extraktion fehlgeschlagen: {str(exc)[:200]}"}
            return

    try:

        document.content_text = extraction.text
        document.page_count = extraction.page_count
        document.has_images = extraction.has_images
        document.has_tables = extraction.has_tables
        document.metadata_extra = extraction.metadata

        yield {"step": "extraction_done", "progress": 0.30, "message":
               f"{extraction.page_count} Seiten extrahiert"
               f"{', Bilder erkannt' if extraction.has_images else ''}"
               f"{', Tabellen erkannt' if extraction.has_tables else ''}"}

        # ── Schritt 3: Adaptives Chunking ──
        yield {"step": "chunking", "progress": 0.40, "message": "Adaptives Chunking…"}

        chunk_results = await loop.run_in_executor(
            None, chunk_text, extraction.text
        )

        db_chunks = []
        search_chunks = []

        for cr in chunk_results:
            chunk_id = gen_id()
            db_chunk = Chunk(
                id=chunk_id,
                document_id=doc_id,
                chunk_index=cr.index,
                content=cr.content,
                token_count=cr.token_count,
                content_normalized=cr.content.lower(),
                page_start=cr.page_start,
                page_end=cr.page_end,
            )
            db_chunks.append(db_chunk)

            # Für Suchindex
            store_result = await db.execute(select(Store).where(Store.id == store_id))
            store_obj = store_result.scalar_one_or_none()

            search_chunks.append({
                "id": chunk_id,
                "document_id": doc_id,
                "document_title": original_filename,
                "store_id": store_id,
                "store_name": store_obj.name if store_obj else "",
                "content": cr.content,
                "chunk_index": cr.index,
                "page_start": cr.page_start,
                "file_type": file_type,
                "tags": [],
            })

        db.add_all(db_chunks)
        document.chunk_count = len(db_chunks)

        yield {"step": "chunking_done", "progress": 0.55, "message": f"{len(db_chunks)} Chunks erstellt"}

        # ── Schritt 4: Entitäten-Extraktion (NER) ──
        yield {"step": "ner", "progress": 0.65, "message": "Entitäten-Extraktion (NER)…"}

        entities = await loop.run_in_executor(
            None, extract_entities, extraction.text
        )

        db_entities = []
        type_mapping = {
            "personen": EntityType.PERSON,
            "daten": EntityType.DATUM,
            "fachbegriffe": EntityType.FACHBEGRIFF,
            "orte": EntityType.ORT,
            "organisationen": EntityType.ORGANISATION,
        }

        for category, entity_type in type_mapping.items():
            for entity_data in getattr(entities, category, []):
                db_entity = Entity(
                    id=gen_id(),
                    document_id=doc_id,
                    entity_type=entity_type,
                    value=entity_data["value"],
                    count=entity_data.get("count", 1),
                    context=entity_data.get("context", ""),
                )
                db_entities.append(db_entity)

        db.add_all(db_entities)
        total_entities = len(db_entities)

        yield {"step": "ner_done", "progress": 0.75, "message": f"{total_entities} Entitäten extrahiert"}

        # ── Schritt 5: Zusammenfassung generieren ──
        yield {"step": "summary", "progress": 0.80, "message": "Zusammenfassung wird generiert…"}

        from app.services.intelligence import generate_summary
        document.content_summary = await loop.run_in_executor(
            None, generate_summary, [extraction.text]
        )

        # ── Schritt 6: Suchindex aktualisieren (thread-safe unter Lock) ──
        yield {"step": "indexing", "progress": 0.88, "message": "Suchindex wird aktualisiert..."}

        await search_engine.async_add_and_rebuild(search_chunks)

        # ── Schritt 7: Abschluss ──
        document.status = DocumentStatus.INDEXED
        document.indexed_at = datetime.datetime.utcnow()
        await db.commit()

        # ── Schritt 8: Wiki-Integration (nur fuer WissensDB, nicht Akte) ──
        from app.models.database import StoreType
        # Store nochmal laden (falls store_obj nicht definiert ist)
        ws_result = await db.execute(select(Store).where(Store.id == store_id))
        ws_store = ws_result.scalar_one_or_none()
        if ws_store and ws_store.type == StoreType.WISSENSDB:
            try:
                yield {"step": "wiki_integration", "progress": 0.97, "message": "Wiki-Seiten werden aktualisiert..."}
                from app.services.wiki_service import wiki_ingest
                wiki_result = await wiki_ingest(db, store_id, doc_id)
                wiki_msg = f" | Wiki: {wiki_result.get('pages_created', 0)} neu, {wiki_result.get('pages_updated', 0)} aktualisiert"
            except Exception as exc:
                logger.warning(f"Wiki-Integration fehlgeschlagen (nicht-blockierend): {exc}")
                wiki_msg = ""
        else:
            wiki_msg = ""

        yield {
            "step": "done",
            "progress": 1.0,
            "message": f"Dokument erfolgreich indiziert ({document.chunk_count} Chunks, {total_entities} Entitaeten){wiki_msg}",
            "document_id": doc_id,
        }

    except Exception as e:
        logger.error(f"Ingestion fehlgeschlagen für {original_filename}: {e}", exc_info=True)
        document.status = DocumentStatus.FAILED
        document.metadata_extra = {**(document.metadata_extra or {}), "error": str(e)}
        await db.commit()
        yield {"step": "error", "progress": 0, "message": f"Fehler: {str(e)}"}


async def reindex_all(db: AsyncSession):
    """Kompletten Suchindex aus der Datenbank neu aufbauen."""
    logger.info("Starte Reindexierung aller Dokumente…")

    result = await db.execute(
        select(Document)
        .where(Document.status == DocumentStatus.INDEXED)
        .options(selectinload(Document.chunks), selectinload(Document.store))
    )
    documents = result.scalars().all()

    all_chunks = []
    for doc in documents:
        for chunk in doc.chunks:
            all_chunks.append({
                "id": chunk.id,
                "document_id": doc.id,
                "document_title": doc.title,
                "store_id": doc.store_id,
                "store_name": doc.store.name if doc.store else "",
                "content": chunk.content,
                "chunk_index": chunk.chunk_index,
                "page_start": chunk.page_start,
                "file_type": doc.file_type,
                "tags": doc.tags or [],
            })

    async with search_engine._lock:
        search_engine._corpus.clear()
        search_engine.add_chunks(all_chunks)
        search_engine.rebuild_index()

    logger.info(f"Reindexierung abgeschlossen: {len(all_chunks)} Chunks aus {len(documents)} Dokumenten")
    return len(all_chunks)
