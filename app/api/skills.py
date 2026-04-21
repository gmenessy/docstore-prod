"""
API-Routen: Skills – Automatisierte Verarbeitung pro Store.
Alle Skills arbeiten ausschließlich mit Dokumenten des angegebenen Stores.
"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from app.core.auth import verify_api_key
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.schemas import SkillExecuteRequest
from app.services.skill_service import execute_skill, get_skill_catalog, get_executions

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stores/{store_id}/skills", tags=["Skills"])


@router.get("")
async def list_skills(store_id: str,auth: str = Depends(verify_api_key)):
    """
    Verfügbare Skills für diesen Store auflisten.
    Jeder Skill wird ausschließlich mit den Dokumenten
    dieses Stores ausgeführt.
    """
    catalog = await get_skill_catalog(store_id)
    return {
        "store_id": store_id,
        "skills": catalog,
        "note": "Alle Skills arbeiten ausschließlich mit den Dokumenten dieser Sammlung.",
    }


@router.post("/execute")
async def run_skill(
    store_id: str,
    data: SkillExecuteRequest,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    Skill ausfuehren - gibt SSE-Stream mit Fortschritt zurueck.
    """
    async def event_stream():
        async for status in execute_skill(
            db=db,
            store_id=store_id,
            skill_id=data.skill_id,
            parameters=data.parameters,
        ):
            yield f"data: {json.dumps(status, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/execute-sync")
async def run_skill_sync(
    store_id: str,
    data: SkillExecuteRequest,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """Skill synchron ausfuehren."""
    last_status = {}
    async for status in execute_skill(
        db=db,
        store_id=store_id,
        skill_id=data.skill_id,
        parameters=data.parameters,
    ):
        last_status = status

    if last_status.get("step") == "error":
        raise HTTPException(500, last_status.get("message", "Skill fehlgeschlagen"))

    return last_status


@router.get("/executions")
async def list_executions(
    store_id: str,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """Vergangene Skill-Ausfuehrungen dieses Stores abrufen."""
    executions = await get_executions(db, store_id)
    return {
        "store_id": store_id,
        "executions": executions,
        "count": len(executions),
    }
