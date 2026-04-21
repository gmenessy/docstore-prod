"""
Celery Worker – Hintergrund-Verarbeitung fuer Dokumenten-Ingestion.

Tasks:
  - ingest_document_task: Dokument asynchron verarbeiten
  - scrape_url_task: URL scrapen und in Store einfuegen
  - reindex_store_task: Store-Index neu aufbauen
  - cleanup_files_task: Alte temporaere Dateien aufraeumen

Konfiguration via DOCSTORE_REDIS_URL.
"""
import asyncio
import logging
import os

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

logger = logging.getLogger(__name__)

# ─── Celery App ───
celery_app = Celery(
    "docstore",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Berlin",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,       # 10 min max pro Task
    task_soft_time_limit=540,  # Soft-Limit bei 9 min
    worker_max_tasks_per_child=100,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

# ─── Periodische Tasks ───
celery_app.conf.beat_schedule = {
    "cleanup-temp-files": {
        "task": "app.tasks.cleanup_files_task",
        "schedule": crontab(hour="3", minute="0"),  # Taeglich um 3:00
    },
    "check-storage-usage": {
        "task": "app.tasks.check_storage_task",
        "schedule": crontab(hour="*/6", minute="15"),  # Alle 6h
    },
}


def _run_async(coro):
    """Async-Coroutine in synchronem Celery-Task ausfuehren."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Tasks
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@celery_app.task(name="app.tasks.ingest_document_task", bind=True, max_retries=2)
def ingest_document_task(self, store_id: str, file_path: str, filename: str):
    """Dokument asynchron ueber die Ingestion-Pipeline verarbeiten."""
    from pathlib import Path
    from app.core.database import async_session
    from app.services.ingestion_service import ingest_document

    async def _run():
        async with async_session() as db:
            results = []
            async for status in ingest_document(
                db=db,
                store_id=store_id,
                file_path=Path(file_path),
                original_filename=filename,
            ):
                results.append(status)
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "step": status.get("step", ""),
                        "progress": status.get("progress", 0),
                        "message": status.get("message", ""),
                    },
                )
            return results[-1] if results else {"step": "error", "message": "Keine Ergebnisse"}

    return _run_async(_run())


@celery_app.task(name="app.tasks.scrape_url_task", bind=True, max_retries=1)
def scrape_url_task(self, store_id: str, url: str):
    """URL scrapen und Dokument in Store einfuegen."""
    from pathlib import Path
    from app.core.database import async_session
    from app.services.web_scraper import scraper
    from app.services.ingestion_service import ingest_document

    async def _run():
        store_dir = settings.stores_dir / store_id
        store_dir.mkdir(parents=True, exist_ok=True)

        # Phase 1: Scrapen
        scrape_result = None
        async for status in scraper.scrape_url(url, store_dir):
            self.update_state(state="PROGRESS", meta=status)
            scrape_result = status

        if not scrape_result or scrape_result.get("step") == "error":
            return scrape_result or {"step": "error", "message": "Scraping fehlgeschlagen"}

        file_path = scrape_result.get("file_path")
        filename = scrape_result.get("filename")
        if not file_path:
            return {"step": "error", "message": "Keine Datei erzeugt"}

        # Phase 2: Ingestion
        async with async_session() as db:
            results = []
            async for status in ingest_document(
                db=db,
                store_id=store_id,
                file_path=Path(file_path),
                original_filename=filename,
                source_type="url",
                source_uri=url,
            ):
                results.append(status)
                self.update_state(state="PROGRESS", meta=status)
            return results[-1] if results else {"step": "error", "message": "Ingestion fehlgeschlagen"}

    return _run_async(_run())


@celery_app.task(name="app.tasks.reindex_store_task")
def reindex_store_task(store_id: str = None):
    """Suchindex fuer einen oder alle Stores neu aufbauen."""
    from app.core.database import async_session
    from app.services.ingestion_service import reindex_all

    async def _run():
        async with async_session() as db:
            count = await reindex_all(db)
            return {"reindexed_chunks": count}

    return _run_async(_run())


@celery_app.task(name="app.tasks.cleanup_files_task")
def cleanup_files_task():
    """Alte temporaere Dateien aufraeumen (aelter als 30 Tage)."""
    from app.services.storage_manager import cleanup_old_files
    result = cleanup_old_files(max_age_days=30)
    logger.info(f"Cleanup: {result['deleted_files']} Dateien, {result['freed_mb']:.1f} MB freigegeben")
    return result


@celery_app.task(name="app.tasks.check_storage_task")
def check_storage_task():
    """Speicherverbrauch pruefen und warnen."""
    from app.services.storage_manager import get_storage_stats
    stats = get_storage_stats()
    if stats["usage_percent"] > 90:
        logger.warning(f"Speicher kritisch: {stats['usage_percent']:.0f}% belegt ({stats['used_mb']:.0f} MB)")
    return stats
