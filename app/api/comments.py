"""
API-Routen: Kommentare & Kollaboration.

Echtzeit-Kommentare für:
- Dokumente
- Wiki-Seiten
- Tasks
"""
import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.database import get_db, get_store_or_404
from app.core.auth import verify_api_key
from app.models.database import Store, gen_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/comments", tags=["Comments & Collaboration"])


# ─── Schemas ───

class CommentCreate(BaseModel):
    """Kommentar erstellen"""
    content: str = Field(..., min_length=1, max_length=5000)
    document_id: Optional[str] = None
    wiki_page_id: Optional[str] = None
    task_id: Optional[str] = None
    parent_id: Optional[str] = None  # Für Threads


class CommentUpdate(BaseModel):
    """Kommentar bearbeiten"""
    content: str = Field(..., min_length=1, max_length=5000)
    resolved: Optional[bool] = None


class CommentResponse(BaseModel):
    """Kommentar-Antwort"""
    id: str
    store_id: str
    content: str
    user_id: str
    document_id: Optional[str]
    wiki_page_id: Optional[str]
    task_id: Optional[str]
    parent_id: Optional[str]
    created_at: str
    updated_at: Optional[str]
    resolved_at: Optional[str]
    replies: list["CommentResponse"] = []  # Thread-Struktur


# ─── In-Memory Storage (für Demo) ───
# TODO: In echte Datenbank migrieren
_comments_store: dict[str, dict] = {}


def _get_comments(store_id: str) -> list[dict]:
    """Hole alle Kommentare für einen Store"""
    return [c for c in _comments_store.values() if c.get("store_id") == store_id]


def _get_comment(comment_id: str) -> Optional[dict]:
    """Hole einen spezifischen Kommentar"""
    return _comments_store.get(comment_id)


def _create_comment(comment_data: dict) -> dict:
    """Erstelle einen neuen Kommentar"""
    comment_id = gen_id()
    comment = {
        "id": comment_id,
        **comment_data,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": None,
        "resolved_at": None,
        "replies": [],
    }
    _comments_store[comment_id] = comment
    return comment


def _update_comment(comment_id: str, updates: dict) -> Optional[dict]:
    """Aktualisiere einen Kommentar"""
    if comment_id in _comments_store:
        _comments_store[comment_id].update(updates)
        _comments_store[comment_id]["updated_at"] = datetime.utcnow().isoformat()
        return _comments_store[comment_id]
    return None


def _delete_comment(comment_id: str) -> bool:
    """Lösche einen Kommentar"""
    if comment_id in _comments_store:
        del _comments_store[comment_id]
        return True
    return False


# ─── API-Endpunkte ───

@router.post("/{store_id}")
async def create_comment(
    store_id: str,
    data: CommentCreate,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """Erstelle einen neuen Kommentar"""
    # Store validieren
    await get_store_or_404(db, store_id)

    # User-ID aus Auth-Header extrahieren (vereinfacht)
    user_id = auth[:8] if auth else "anonymous"

    comment_data = {
        "store_id": store_id,
        "content": data.content,
        "user_id": user_id,
        "document_id": data.document_id,
        "wiki_page_id": data.wiki_page_id,
        "task_id": data.task_id,
        "parent_id": data.parent_id,
    }

    comment = _create_comment(comment_data)

    # Wenn es eine Antwort ist, zum Thread hinzufügen
    if data.parent_id:
        parent = _get_comment(data.parent_id)
        if parent:
            parent["replies"].append(comment["id"])

    # Audit-Log
    # await audit_logger.log(db, "comment.create", store_id, user_id, "comment", comment["id"])

    return comment


@router.get("/{store_id}")
async def list_comments(
    store_id: str,
    document_id: Optional[str] = None,
    wiki_page_id: Optional[str] = None,
    task_id: Optional[str] = None,
    include_resolved: bool = True,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """Liste alle Kommentare für einen Store (optional gefiltert)"""
    comments = _get_comments(store_id)

    # Filter anwenden
    if document_id:
        comments = [c for c in comments if c.get("document_id") == document_id]
    elif wiki_page_id:
        comments = [c for c in comments if c.get("wiki_page_id") == wiki_page_id]
    elif task_id:
        comments = [c for c in comments if c.get("task_id") == task_id]

    # Gelöste ausfiltern (außer include_resolved=True)
    if not include_resolved:
        comments = [c for c in comments if not c.get("resolved_at")]

    # Nur Top-Level Kommentare (keine Antworten)
    top_level = [c for c in comments if not c.get("parent_id")]

    return {
        "store_id": store_id,
        "comments": top_level,
        "count": len(top_level),
        "filter": {
            "document_id": document_id,
            "wiki_page_id": wiki_page_id,
            "task_id": task_id,
            "include_resolved": include_resolved,
        }
    }


@router.get("/{store_id}/{comment_id}")
async def get_comment(
    store_id: str,
    comment_id: str,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """Hole einen spezifischen Kommentar mit Thread"""
    comment = _get_comment(comment_id)

    if not comment or comment.get("store_id") != store_id:
        raise HTTPException(404, "Kommentar nicht gefunden")

    # Thread aufbauen
    thread = [comment]
    for reply_id in comment.get("replies", []):
        reply = _get_comment(reply_id)
        if reply:
            thread.append(reply)

    return {
        "comment": comment,
        "thread": thread,
    }


@router.patch("/{store_id}/{comment_id}")
async def update_comment(
    store_id: str,
    comment_id: str,
    data: CommentUpdate,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """Aktualisiere einen Kommentar"""
    comment = _get_comment(comment_id)

    if not comment or comment.get("store_id") != store_id:
        raise HTTPException(404, "Kommentar nicht gefunden")

    # Nur der Ersteller darf bearbeiten (vereinfacht)
    user_id = auth[:8] if auth else "anonymous"
    if comment.get("user_id") != user_id:
        raise HTTPException(403, "Keine Berechtigung")

    # Updates anwenden
    updates = {}
    if data.content is not None:
        updates["content"] = data.content
    if data.resolved is not None:
        updates["resolved_at"] = datetime.utcnow().isoformat() if data.resolved else None

    updated = _update_comment(comment_id, updates)

    # Audit-Log
    # await audit_logger.log(db, "comment.update", store_id, user_id, "comment", comment_id)

    return updated


@router.delete("/{store_id}/{comment_id}")
async def delete_comment(
    store_id: str,
    comment_id: str,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """Lösche einen Kommentar"""
    comment = _get_comment(comment_id)

    if not comment or comment.get("store_id") != store_id:
        raise HTTPException(404, "Kommentar nicht gefunden")

    # Nur der Ersteller darf löschen (vereinfacht)
    user_id = auth[:8] if auth else "anonymous"
    if comment.get("user_id") != user_id:
        raise HTTPException(403, "Keine Berechtigung")

    # Aus Eltern-Thread entfernen
    if comment.get("parent_id"):
        parent = _get_comment(comment["parent_id"])
        if parent and comment_id in parent.get("replies", []):
            parent["replies"].remove(comment_id)

    # Kommentare mit Antworten können nicht gelöscht werden
    if comment.get("replies"):
        raise HTTPException(400, "Kommentar mit Antworten kann nicht gelöscht werden")

    deleted = _delete_comment(comment_id)

    # Audit-Log
    # await audit_logger.log(db, "comment.delete", store_id, user_id, "comment", comment_id)

    if deleted:
        return {"deleted": True}
    else:
        raise HTTPException(500, "Löschen fehlgeschlagen")