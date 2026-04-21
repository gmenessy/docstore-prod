"""
API-Routen: Wiki (WissensDB v2).

Drei Kern-Operationen:
  - POST /stores/{id}/wiki/ingest/{doc_id}   Dokument in Wiki integrieren
  - POST /stores/{id}/wiki/query             Frage gegen Wiki beantworten
  - POST /stores/{id}/wiki/lint              Health-Check

Plus Lese-Endpunkte fuer Seiten, Log und Save-Answer.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, get_store_or_404
from app.core.auth import verify_api_key
from app.services.wiki_service import (
    wiki_ingest, wiki_query, wiki_lint,
    list_pages, get_page, get_log, save_query_as_page,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stores/{store_id}/wiki", tags=["Wiki"])


# ─── Request-Schemas ───

class WikiIngestRequest(BaseModel):
    """Wiki-Ingest-Request.

    API-Keys werden nur noch über Umgebungsvariablen konfiguriert (DOCSTORE_*_API_KEY).
    """
    provider: str = "ollama"
    model: str | None = None


class WikiQueryRequest(BaseModel):
    """Wiki-Query-Request.

    API-Keys werden nur noch über Umgebungsvariablen konfiguriert (DOCSTORE_*_API_KEY).
    """
    question: str
    provider: str = "ollama"
    model: str | None = None
    max_pages: int = 5


class WikiSaveAnswerRequest(BaseModel):
    question: str
    answer: str
    title: str | None = None
    page_type: str = "synthesis"


# ─── Operationen ───

@router.post("/ingest/{document_id}")
async def ingest_document_to_wiki(
    store_id: str,
    document_id: str,
    data: WikiIngestRequest = WikiIngestRequest(),
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    Ein bereits indiziertes Dokument in das Wiki integrieren.
    LLM entscheidet welche Seiten zu erstellen/aktualisieren sind.
    """
    await get_store_or_404(db, store_id)
    result = await wiki_ingest(
        db, store_id, document_id,
        provider_id=data.provider, model=data.model,
    )
    if result.get("error"):
        raise HTTPException(404, result["error"])
    return result


@router.post("/query")
async def query_wiki(
    store_id: str,
    data: WikiQueryRequest,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    Frage gegen das Wiki beantworten.
    Sucht relevante Seiten, nutzt sie als Kontext fuer LLM-Antwort.
    """
    await get_store_or_404(db, store_id)
    return await wiki_query(
        db, store_id, data.question,
        provider_id=data.provider, model=data.model,
        max_pages=data.max_pages,
    )


@router.post("/lint")
async def lint_wiki(
    store_id: str,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    Wiki-Health-Check.
    Findet Orphans, Widersprueche, fehlende Konzepte, veraltete Seiten.
    """
    await get_store_or_404(db, store_id)
    return await wiki_lint(db, store_id)


@router.post("/save-answer")
async def save_answer(
    store_id: str,
    data: WikiSaveAnswerRequest,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """Eine Chat-Antwort als neue Wiki-Seite speichern."""
    await get_store_or_404(db, store_id)
    result = await save_query_as_page(
        db, store_id, data.question, data.answer,
        title=data.title, page_type=data.page_type,
    )
    return result


# ─── Read-Endpunkte ───

@router.get("/pages")
async def list_wiki_pages(
    store_id: str,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """Alle Wiki-Seiten dieser Sammlung auflisten (ohne Inhalt)."""
    await get_store_or_404(db, store_id)
    pages = await list_pages(db, store_id)
    return {
        "store_id": store_id,
        "total": len(pages),
        "pages": pages,
    }


@router.get("/pages/{slug}")
async def get_wiki_page(
    store_id: str,
    slug: str,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """Einzelne Wiki-Seite mit Markdown-Inhalt laden."""
    await get_store_or_404(db, store_id)
    page = await get_page(db, store_id, slug)
    if not page:
        raise HTTPException(404, f"Wiki-Seite '{slug}' nicht gefunden")
    return page


@router.get("/log")
async def get_wiki_log(
    store_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """Chronik der Wiki-Operationen (Ingests, Queries, Lints)."""
    await get_store_or_404(db, store_id)
    ops = await get_log(db, store_id, limit=limit)
    return {
        "store_id": store_id,
        "total": len(ops),
        "operations": ops,
    }
