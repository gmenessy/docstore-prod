"""
API-Routen: Web-Scraper, Storage-Management, Dokument-Versionierung, LLM-Provider.
"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, get_store_or_404
from app.core.auth import verify_api_key
from app.core.llm_client import llm_client
from app.models.database import Store, Document, DocumentStatus, gen_id
from app.models.schemas import WebScrapeRequest
from app.services.storage_manager import get_storage_stats, check_store_limit, cleanup_old_files

logger = logging.getLogger(__name__)
router = APIRouter(tags=["System"])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LLM-Provider (system-weit, nicht store-gebunden)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/llm/providers")
async def list_all_providers(auth: str = Depends(verify_api_key)):
    """
    Alle konfigurierten LLM-Provider (self-hosted + kommerziell + custom).
    Gruppiert nach Kategorie fuer UI-Filter.
    """
    providers = llm_client.get_providers()
    by_category = {"self-hosted": [], "commercial": [], "custom": []}
    for p in providers:
        cat = p.get("category", "commercial")
        by_category.setdefault(cat, []).append(p)
    return {
        "providers": providers,
        "by_category": by_category,
        "total": len(providers),
    }


@router.get("/llm/providers/{provider_id}/models")
async def discover_provider_models(
    provider_id: str,
    auth: str = Depends(verify_api_key),
):
    """
    Fragt den Provider live nach verfuegbaren Modellen via /v1/models.
    Nuetzlich bei vLLM/LocalAI/Ollama wo Modelle zur Laufzeit wechseln.

    API-Keys werden nur noch über Umgebungsvariablen konfiguriert (DOCSTORE_*_API_KEY).
    """
    models = await llm_client.discover_models(provider_id)
    return {
        "provider_id": provider_id,
        "models": models,
        "discovered": len(models),
    }


@router.post("/llm/providers/{provider_id}/test")
async def test_provider_connection(
    provider_id: str,
    auth: str = Depends(verify_api_key),
):
    """
    Testet ob Provider erreichbar ist und ein einfacher Prompt durchgeht.
    Fuer Admin-UI: "Verbindung pruefen".

    API-Keys werden nur noch über Umgebungsvariablen konfiguriert (DOCSTORE_*_API_KEY).
    """
    try:
        result = await llm_client.chat_completion(
            messages=[{"role": "user", "content": "Antworte nur mit: OK"}],
            provider_id=provider_id,
            max_tokens=10,
            temperature=0.0,
        )
        return {
            "ok": True,
            "provider": provider_id,
            "model": result.get("model"),
            "response": result.get("content", "").strip()[:50],
        }
    except Exception as e:
        return {
            "ok": False,
            "provider": provider_id,
            "error": str(e)[:200],
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Web-Scraper
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/stores/{store_id}/scrape")
async def scrape_url(
    store_id: str,
    data: WebScrapeRequest,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    URL scrapen und als Dokument in den Store einfuegen.
    Gibt SSE-Stream mit Fortschritt zurueck.

    Ablauf: URL laden -> HTML parsen -> Markdown erzeugen -> Ingestion Pipeline
    """
    from app.core.config import settings
    from app.services.web_scraper import scraper
    from app.services.ingestion_service import ingest_document
    from pathlib import Path

    # Store pruefen
    store = await get_store_or_404(db, store_id)

    # Speicher-Limit pruefen
    limit = check_store_limit(store_id)
    if not limit["ok"]:
        raise HTTPException(
            400,
            f"Speicher-Limit erreicht: {limit['used_mb']:.0f}/{limit['limit_mb']} MB"
        )

    store_dir = settings.stores_dir / store_id
    store_dir.mkdir(parents=True, exist_ok=True)

    async def event_stream():
        # Phase 1: Scrapen
        scrape_result = None
        async for status in scraper.scrape_url(data.url, store_dir):
            yield f"data: {json.dumps(status, ensure_ascii=False)}\n\n"
            scrape_result = status

        if not scrape_result or scrape_result.get("step") != "done":
            return

        file_path = scrape_result.get("file_path")
        filename = scrape_result.get("filename")
        if not file_path:
            yield f'data: {{"step":"error","message":"Keine Datei erzeugt"}}\n\n'
            return

        # Phase 2: Ingestion
        async for status in ingest_document(
            db=db,
            store_id=store_id,
            file_path=Path(file_path),
            original_filename=filename,
            source_type="url",
            source_uri=data.url,
        ):
            yield f"data: {json.dumps(status, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/stores/{store_id}/scrape-sync")
async def scrape_url_sync(
    store_id: str,
    data: WebScrapeRequest,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """URL scrapen (synchron) — gibt Endergebnis zurueck."""
    from app.core.config import settings
    from app.services.web_scraper import scraper
    from app.services.ingestion_service import ingest_document
    from pathlib import Path

    await get_store_or_404(db, store_id)

    store_dir = settings.stores_dir / store_id
    store_dir.mkdir(parents=True, exist_ok=True)

    # Scrapen
    scrape_result = None
    async for status in scraper.scrape_url(data.url, store_dir):
        scrape_result = status

    if not scrape_result or scrape_result.get("step") != "done":
        raise HTTPException(400, scrape_result.get("message", "Scraping fehlgeschlagen") if scrape_result else "Fehler")

    file_path = scrape_result.get("file_path")
    filename = scrape_result.get("filename")
    if not file_path:
        raise HTTPException(500, "Keine Datei erzeugt")

    # Ingestion
    last = {}
    async for status in ingest_document(
        db=db, store_id=store_id,
        file_path=Path(file_path), original_filename=filename,
        source_type="url", source_uri=data.url,
    ):
        last = status

    if last.get("step") == "error":
        raise HTTPException(500, last.get("message"))

    return last


@router.post("/stores/{store_id}/scrape-async")
async def scrape_url_async(
    store_id: str,
    data: WebScrapeRequest,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """URL asynchron scrapen via Celery. Gibt sofort Task-ID zurueck."""
    await get_store_or_404(db, store_id)
    try:
        from app.tasks import scrape_url_task
        task = scrape_url_task.delay(store_id, data.url)
        return {
            "task_id": task.id,
            "status": "queued",
            "message": f"URL '{data.url}' wird asynchron verarbeitet",
            "status_url": f"/api/v1/documents/tasks/{task.id}",
        }
    except Exception as e:
        logger.warning(f"Celery nicht verfuegbar fuer scrape, Fallback synchron: {e}")
        raise HTTPException(503, "Celery-Worker nicht erreichbar. Verwenden Sie /scrape-sync.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Storage-Management
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/system/storage")
async def storage_stats(auth: str = Depends(verify_api_key)):
    """Speicher-Statistiken und -Limits anzeigen."""
    return get_storage_stats()


@router.get("/stores/{store_id}/storage")
async def store_storage(
    store_id: str,
    auth: str = Depends(verify_api_key),
):
    """Speicher-Nutzung eines einzelnen Stores."""
    return check_store_limit(store_id)


@router.post("/system/cleanup")
async def trigger_cleanup(
    max_age_days: int = Query(30, ge=1, le=365),
    auth: str = Depends(verify_api_key),
):
    """Manuelles Cleanup alter Dateien ausloesen."""
    result = cleanup_old_files(max_age_days=max_age_days)
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Dokument-Versionierung
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/documents/detail/{document_id}/versions")
async def list_versions(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """Alle Versionen eines Dokuments auflisten."""
    # Aktuelles Dokument laden
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Dokument nicht gefunden")

    # Versionskette aufbauen (zurueck durch previous_version_id)
    versions = [doc.to_dict()]
    current = doc
    while current.previous_version_id:
        result = await db.execute(select(Document).where(Document.id == current.previous_version_id))
        prev = result.scalar_one_or_none()
        if not prev:
            break
        versions.append(prev.to_dict())
        current = prev

    versions.reverse()  # Aelteste zuerst
    return {
        "document_id": document_id,
        "title": doc.title,
        "current_version": doc.version or 1,
        "total_versions": len(versions),
        "versions": versions,
    }


@router.post("/documents/{store_id}/upload-version/{document_id}")
async def upload_new_version(
    store_id: str,
    document_id: str,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    Neue Version eines bestehenden Dokuments hochladen.
    Das alte Dokument wird als is_latest=False markiert,
    das neue bekommt version+1 und previous_version_id.

    Hinweis: File-Upload via /documents/{store_id}/upload mit dem gleichen Dateinamen
    erkennt automatisch existierende Dokumente und erstellt eine neue Version.
    """
    # Altes Dokument laden
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.store_id == store_id)
    )
    old_doc = result.scalar_one_or_none()
    if not old_doc:
        raise HTTPException(404, "Dokument nicht gefunden")

    return {
        "info": "Verwenden Sie POST /documents/{store_id}/upload mit dem gleichen Dateinamen.",
        "document_id": document_id,
        "current_version": old_doc.version or 1,
        "title": old_doc.title,
    }
