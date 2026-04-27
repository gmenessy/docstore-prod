"""
API-Routen: Dokumente – Upload, CRUD, Detail-Ansicht.
"""
import asyncio
import json
import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db, get_store_or_404
from app.core.auth import verify_api_key, paginated_response
from app.models.database import Store, Document, DocumentStatus
from app.models.schemas import DocumentResponse, DocumentDetail, DocumentTagsUpdate
from app.services.ingestion_service import ingest_document

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["Dokumente"])


@router.get("/{store_id}")
async def list_documents(
    store_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """Dokumente einer Sammlung auflisten (paginiert)."""
    # Prüfen ob Store existiert
    await get_store_or_404(db, store_id)

    total_result = await db.execute(
        select(func.count(Document.id)).where(Document.store_id == store_id)
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        select(Document)
        .where(Document.store_id == store_id)
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    documents = result.scalars().all()
    return paginated_response([d.to_dict() for d in documents], total, offset, limit)


@router.get("/detail/{document_id}")
async def get_document(document_id: str, db: AsyncSession = Depends(get_db), auth: str = Depends(verify_api_key)):
    """Detailansicht eines Dokuments (inkl. Chunks und Entitäten)."""
    result = await db.execute(
        select(Document)
        .where(Document.id == document_id)
        .options(
            selectinload(Document.chunks),
            selectinload(Document.entities),
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(404, "Dokument nicht gefunden")
    return document.to_detail_dict()


@router.post("/{store_id}/upload")
async def upload_document(
    store_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    Dokument hochladen und Ingestion-Pipeline starten.
    Gibt SSE-Stream mit Fortschrittsstatus zurück.
    """
    # Store prüfen
    store = await get_store_or_404(db, store_id)

    # Dateiformat prüfen
    suffix = Path(file.filename).suffix.lower()
    if suffix not in settings.supported_formats:
        raise HTTPException(
            400,
            f"Format '{suffix}' nicht unterstützt. "
            f"Erlaubt: {', '.join(settings.supported_formats)}"
        )

    # Dateigröße prüfen
    contents = await file.read()
    if len(contents) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(400, f"Datei zu groß (max. {settings.max_upload_size_mb} MB)")

    # Datei speichern
    store_dir = settings.stores_dir / store_id
    store_dir.mkdir(parents=True, exist_ok=True)
    file_path = store_dir / file.filename

    with open(file_path, "wb") as f:
        f.write(contents)

    # Versionierung: Pruefen ob Dokument mit gleichem Namen existiert
    existing_result = await db.execute(
        select(Document)
        .where(Document.store_id == store_id, Document.title == file.filename, Document.is_latest == True)
    )
    existing_doc = existing_result.scalar_one_or_none()
    version_info = None
    if existing_doc:
        # Alte Version markieren
        existing_doc.is_latest = False
        await db.commit()
        version_info = {
            "previous_version_id": existing_doc.id,
            "version": (existing_doc.version or 1) + 1,
        }

    # SSE-Streaming der Ingestion-Pipeline
    async def event_stream():
        async for status in ingest_document(
            db=db,
            store_id=store_id,
            file_path=file_path,
            original_filename=file.filename,
            source_type="upload",
        ):
            yield f"data: {json.dumps(status, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{store_id}/upload-sync")
async def upload_document_sync(
    store_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    Synchroner Upload (ohne SSE) – gibt Endergebnis zurück.
    Für einfache API-Clients.
    """
    # Store prüfen
    store = await get_store_or_404(db, store_id)

    suffix = Path(file.filename).suffix.lower()
    if suffix not in settings.supported_formats:
        raise HTTPException(400, f"Format '{suffix}' nicht unterstützt")

    contents = await file.read()
    store_dir = settings.stores_dir / store_id
    store_dir.mkdir(parents=True, exist_ok=True)
    file_path = store_dir / file.filename

    with open(file_path, "wb") as f:
        f.write(contents)

    # Pipeline durchlaufen (ohne Streaming)
    last_status = {}
    async for status in ingest_document(
        db=db,
        store_id=store_id,
        file_path=file_path,
        original_filename=file.filename,
    ):
        last_status = status

    if last_status.get("step") == "error":
        raise HTTPException(500, last_status.get("message", "Unbekannter Fehler"))

    return last_status


@router.patch("/detail/{document_id}/tags")
async def update_tags(
    document_id: str,
    data: DocumentTagsUpdate,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """Tags eines Dokuments aktualisieren."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(404, "Dokument nicht gefunden")

    document.tags = data.tags
    await db.commit()
    return {"id": document_id, "tags": data.tags}


@router.delete("/detail/{document_id}", status_code=204)
async def delete_document(document_id: str, db: AsyncSession = Depends(get_db), auth: str = Depends(verify_api_key)):
    """Dokument und alle zugehörigen Daten löschen."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(404, "Dokument nicht gefunden")

    # Datei löschen
    file_path = Path(document.file_path)
    if file_path.exists():
        file_path.unlink()

    # Aus Suchindex entfernen (Thread-Safe mit Lock)
    from app.search.engine import search_engine
    await search_engine.remove_document(document_id)

    await db.delete(document)
    await db.commit()
    logger.info(f"Dokument gelöscht: {document.title}")


# ─── Async Upload via Celery ───

@router.post("/{store_id}/upload-async")
async def upload_document_async(
    store_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    Dokument hochladen und asynchron via Celery verarbeiten.
    Gibt sofort eine Task-ID zurueck. Status via GET /tasks/{task_id}.
    """
    await get_store_or_404(db, store_id)

    suffix = Path(file.filename).suffix.lower()
    if suffix not in settings.supported_formats:
        raise HTTPException(400, f"Format '{suffix}' nicht unterstuetzt")

    contents = await file.read()
    if len(contents) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(400, f"Datei zu gross (max. {settings.max_upload_size_mb} MB)")

    store_dir = settings.stores_dir / store_id
    store_dir.mkdir(parents=True, exist_ok=True)
    file_path = store_dir / file.filename
    with open(file_path, "wb") as f:
        f.write(contents)

    try:
        from app.tasks import ingest_document_task
        task = ingest_document_task.delay(store_id, str(file_path), file.filename)
        return {
            "task_id": task.id,
            "status": "queued",
            "message": f"Dokument '{file.filename}' wird asynchron verarbeitet",
            "status_url": f"/api/v1/tasks/{task.id}",
        }
    except Exception as e:
        logger.warning(f"Celery nicht verfuegbar, Fallback auf synchron: {e}")
        last = {}
        async for status in ingest_document(
            db=db, store_id=store_id,
            file_path=file_path, original_filename=file.filename,
        ):
            last = status
        return last


# ─── Task-Status (Celery) ───

@router.get("/tasks/{task_id}")
async def get_task_status(
    task_id: str,
    auth: str = Depends(verify_api_key),
):
    """
    Status eines Celery-Tasks abfragen.
    Gibt Status (PENDING, PROGRESS, SUCCESS, FAILURE) und Ergebnis zurueck.
    """
    try:
        from app.tasks import celery_app
        result = celery_app.AsyncResult(task_id)
        response = {
            "task_id": task_id,
            "status": result.status,
        }
        if result.status == "PROGRESS":
            response["progress"] = result.info
        elif result.status == "SUCCESS":
            response["result"] = result.result
        elif result.status == "FAILURE":
            response["error"] = str(result.result)
        return response
    except Exception as e:
        raise HTTPException(500, f"Celery nicht verfuegbar: {str(e)}")
