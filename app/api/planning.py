"""
API-Routen: Planung – Maßnahmen-Management pro Store.
Alle Maßnahmen werden aus den Dokumenten des angegebenen Stores extrahiert.
Strikte Isolation: Kein Zugriff auf andere Stores.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.auth import verify_api_key
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.schemas import PlanTaskCreate, PlanTaskUpdate, PlanTaskResponse
from app.services.planning_service import (
    get_tasks, create_task, update_task, delete_task, auto_extract_tasks,
    wiki_lint_to_tasks, get_tasks_filtered,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stores/{store_id}/planning", tags=["Planung"])


@router.get("/tasks")
async def list_tasks(
    store_id: str,
    category: str | None = Query(None, description="Filter: wiki-maintenance | documents | (leer = alle)"),
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    Alle Massnahmen dieses Stores abrufen.
    Beim ersten Aufruf werden Massnahmen automatisch aus den
    Dokumenten extrahiert.

    Optional: category-Filter
      - wiki-maintenance: nur Tasks aus Wiki-Lint
      - documents: nur aus Dokumenten extrahierte Tasks
      - (leer): alle Tasks
    """
    try:
        if category:
            tasks = await get_tasks_filtered(db, store_id, category=category)
        else:
            tasks = await get_tasks(db, store_id)
        return {
            "store_id": store_id,
            "tasks": tasks,
            "count": len(tasks),
            "category_filter": category,
            "note": "Massnahmen basieren ausschliesslich auf dieser Sammlung.",
        }
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/tasks", status_code=201)
async def add_task(
    store_id: str,
    data: PlanTaskCreate,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """Neue Maßnahme manuell hinzufügen (diesem Store zugeordnet)."""
    try:
        task = await create_task(db, store_id, data.model_dump())
        return task
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.patch("/tasks/{task_id}")
async def modify_task(
    store_id: str,
    task_id: str,
    data: PlanTaskUpdate,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    Maßnahme aktualisieren (Status, Priorität, Zuweisung etc.).
    Erzwingt Store-Zugehörigkeit – Tasks anderer Stores sind nicht zugänglich.
    """
    try:
        task = await update_task(db, store_id, task_id, data.model_dump(exclude_unset=True))
        return task
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.delete("/tasks/{task_id}", status_code=204)
async def remove_task(
    store_id: str,
    task_id: str,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """Maßnahme löschen (nur innerhalb dieses Stores)."""
    await delete_task(db, store_id, task_id)


@router.post("/extract")
async def extract_tasks(store_id: str, db: AsyncSession = Depends(get_db), auth: str = Depends(verify_api_key)):
    """
    Maßnahmen neu aus Dokumenten extrahieren.
    Überschreibt bestehende automatisch extrahierte Maßnahmen.
    """
    try:
        tasks = await auto_extract_tasks(db, store_id)
        return {
            "store_id": store_id,
            "extracted": len(tasks),
            "tasks": tasks,
            "note": "Maßnahmen wurden aus den Dokumenten dieser Sammlung extrahiert.",
        }
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/wiki-lint-to-tasks")
async def wiki_lint_to_tasks_endpoint(
    store_id: str,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    Wiki-Wartung: Fuehrt Wiki-Lint aus und erzeugt fuer jeden Issue
    einen Planning-Task der Kategorie 'wiki-maintenance'.

    Deduplizierung per Fingerprint: Tasks fuer bereits existierende
    (nicht erledigte) Issues werden uebersprungen.

    Prioritaeten-Mapping:
      - contradiction → hoch
      - missing_concept → mittel
      - orphan_page, stale_page → niedrig

    Gibt zurueck: {total_issues, created, skipped, tasks, lint_summary}
    """
    from app.core.database import get_store_or_404
    await get_store_or_404(db, store_id)
    result = await wiki_lint_to_tasks(db, store_id)
    return {
        "store_id": store_id,
        **result,
        "note": "Neu erzeugte Tasks sind in der Kategorie 'wiki-maintenance' filterbar.",
    }
