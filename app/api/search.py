"""
API-Routen: Hybrid-Suche (BM25 + Semantic).
"""
import logging
import time

from fastapi import APIRouter, Depends
from app.core.auth import verify_api_key
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.schemas import SearchRequest, SearchResponse, SearchResult
from app.search.engine import search_engine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["Suche"])


@router.post("", response_model=SearchResponse)
async def search(data: SearchRequest, db: AsyncSession = Depends(get_db), auth: str = Depends(verify_api_key)):
    """
    Hybrid-Suche über alle oder eine bestimmte Sammlung.

    search_type:
    - "hybrid": BM25 (0.4) + Semantic (0.6)
    - "bm25": Nur Keyword-Suche
    - "semantic": Nur semantische Suche
    """
    start = time.monotonic()

    hits = await search_engine.search(
        query=data.query,
        search_type=data.search_type,
        max_results=data.max_results,
        store_id=data.store_id,
    )

    results = [
        SearchResult(
            document_id=hit.document_id,
            document_title=hit.document_title,
            store_id=hit.store_id,
            store_name=hit.store_name,
            chunk_id=hit.chunk_id,
            chunk_content=hit.content[:500],  # Max 500 Zeichen
            chunk_index=hit.chunk_index,
            score=hit.score,
            file_type=hit.file_type,
            tags=hit.tags,
            page_start=hit.page_start,
        )
        for hit in hits
    ]

    elapsed = (time.monotonic() - start) * 1000

    return SearchResponse(
        query=data.query,
        search_type=data.search_type,
        total_results=len(results),
        results=results,
        execution_time_ms=round(elapsed, 2),
    )


@router.get("/stats")
async def search_stats(auth: str = Depends(verify_api_key)):
    """Suchindex-Statistiken."""
    return {
        "index_size": search_engine.index_size,
        "index_ready": not search_engine._dirty,
    }
