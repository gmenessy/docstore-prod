"""
API-Routen: Wiki-Auto-Kurierung.

Bietet Endpunkte für:
- Qualitäts-Prüfung
- Automatische Refresh-Ausführung
- Batch-Verarbeitung
- Quality-Reporting
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import verify_api_key
from app.services.wiki_auto_curator import wiki_auto_curator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/wiki-curator", tags=["Wiki Auto-Curation"])


@router.get("/quality/{store_id}/{page_id}")
async def get_page_quality(
    store_id: str,
    page_id: str,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    Prüft die Qualität einer Wiki-Seite.

    Returns:
        QualityScore mit Metriken und Empfehlungen
    """
    quality_score = await wiki_auto_curator.check_wiki_quality(db, store_id, page_id)

    return {
        "store_id": store_id,
        "page_id": page_id,
        "quality_score": quality_score.overall_score,
        "metrics": quality_score.metrics,
        "issues": quality_score.issues,
        "recommendations": quality_score.recommendations,
        "needs_refresh": quality_score.needs_refresh,
        "last_checked": quality_score.last_checked.isoformat()
    }


@router.get("/candidates/{store_id}")
async def get_refresh_candidates(
    store_id: str,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    Liste Wiki-Seiten, die aktualisiert werden sollten.

    Sortiert nach Priorität (höchste zuerst).
    """
    candidates = await wiki_auto_curator.get_refresh_candidates(db, store_id, limit)

    return {
        "store_id": store_id,
        "candidates": candidates,
        "count": len(candidates),
        "priority_filter": "score_below_70_or_older_than_7days"
    }


@router.post("/refresh/{store_id}/{page_id}")
async def refresh_page(
    store_id: str,
    page_id: str,
    force: bool = Query(False, description="Erzwingt Refresh auch bei gutem Score"),
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    Führt automatische Wiki-Aktualisierung durch.

    Aktualisiert die Wiki-Seite basierend auf:
    - Quality-Score
    - Neuen Dokumenten
    - User-Feedback
    """
    result = await wiki_auto_curator.auto_refresh_wiki_page(
        db=db,
        store_id=store_id,
        page_id=page_id,
        force=force
    )

    return result


@router.post("/batch-refresh/{store_id}")
async def batch_refresh_wiki(
    store_id: str,
    max_refreshes: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    Führt Batch-Aktualisierung mehrerer Wiki-Seiten durch.

    Aktualisiert die Wiki-Seiten basierend auf:
    - Quality-Score
    - Alter der Inhalte
    - Priorität

    Dies ist eine Background-Task, die asynchron läuft.
    """
    result = await wiki_auto_curator.batch_refresh_wiki(
        db=db,
        store_id=store_id,
        max_refreshes=max_refreshes
    )

    return {
        "store_id": store_id,
        "batch_summary": {
            "candidates_considered": result["candidates_count"],
            "refreshes_attempted": result["refreshes_attempted"],
            "successful": result["refreshes_successful"],
            "failed": result["refreshes_failed"],
            "success_rate": (result["refreshes_successful"] / max(1, result["refreshes_attempted"])) * 100
        },
        "results": result["results"]
    }


@router.get("/report/{store_id}")
async def get_quality_report(
    store_id: str,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    Generiert einen umfassenden Quality-Report für alle Wiki-Seiten.

    Enthält:
    - Gesamt-Score
    - Seiten mit niedrigem Score
    - Empfehlungen
    - Trends
    """
    # Alle Wiki-Seiten laden
    from app.models.database import WikiPage
    from sqlalchemy import select

    result = await db.execute(
        select(WikiPage)
        .where(WikiPage.store_id == store_id)
    )
    pages = result.scalars().all()

    if not pages:
        return {
            "store_id": store_id,
            "total_pages": 0,
            "avg_score": 0,
            "pages_need_refresh": [],
            "recommendations": ["Keine Wiki-Seiten vorhanden"]
        }

    # Qualitäts-Scores für alle Seiten sammeln
    page_scores = []
    pages_need_refresh = []

    for page in pages:
        try:
            quality_score = await wiki_auto_curator.check_wiki_quality(db, store_id, page.id)
            page_scores.append(quality_score)

            if quality_score.needs_refresh:
                pages_need_refresh.append({
                    "page_id": page.id,
                    "title": page.title,
                    "score": quality_score.overall_score,
                    "priority": "high" if quality_score.overall_score < 50 else "medium"
                })
        except Exception as e:
            logger.error(f"Fehler bei Qualitäts-Prüfung für {page.id}: {e}")

    # Durchschnitt berechnen
    avg_score = sum(s.overall_score for s in page_scores) / len(page_scores) if page_scores else 0

    # Gesamtempfehlungen generieren
    all_issues = []
    for score in page_scores:
        all_issues.extend(score.issues)

    issue_counts = {}
    for issue in all_issues:
        issue_counts[issue] = issue_counts.get(issue, 0) + 1

    recommendations = []
    for issue, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True):
        recommendations.append(f"{issue} ({count}x betroffen)")

    if not recommendations:
        recommendations.append("Alle Wiki-Seiten haben gute Qualität")

    return {
        "store_id": store_id,
        "total_pages": len(pages),
        "avg_score": round(avg_score, 1),
        "pages_need_refresh": len(pages_need_refresh),
        "refresh_candidates": pages_need_refresh[:10],
        "top_issues": list(issue_counts.keys())[:5],
        "recommendations": recommendations
    }