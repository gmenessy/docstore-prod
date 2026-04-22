"""
API-Routen: System-Metriken & Evaluation.

Bietet Endpunkte für:
- Nützlichkeits-Metriken
- Performance-Analyse
- User-Engagement-Tracking
- System-Health-Checks
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import verify_api_key
from tests.test_metrics import nützlichkeit_metrics

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/metrics", tags=["Metrics & Evaluation"])


@router.get("/overview/{store_id}")
async def get_metrics_overview(
    store_id: str,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    Gesamt-Übersicht aller Metriken für einen Store.

    Enthält:
    - Overall Nützlichkeits-Score
    - Einzelne Komponenten-Scores
    - Verbesserungs-Empfehlungen
    """
    overview = await nützlichkeit_metrics.calculate_overall_score(store_id)

    return {
        "store_id": store_id,
        "generated_at": overview["generated_at"] if "generated_at" in overview else "now",
        "overall_score": overview["overall_score"],
        "target": overview["target"],
        "achieved": overview["achieved"],
        "components": overview["components"],
        "recommendations": overview["recommendations"]
    }


@router.get("/collaboration/{store_id}")
async def get_collaboration_metrics(
    store_id: str,
    period_hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    Kollaborations-Metriken für einen Store.

    Enthält:
    - Kommentar-Aktivität
    - Kollaborations-Score
    - User-Diversifikation
    - Thread-Analyse
    """
    comment_activity = await nützlichkeit_metrics.measure_comment_activity(
        store_id, period_hours
    )
    collab_score = await nützlichkeit_metrics.measure_collaboration_score(store_id)

    return {
        "store_id": store_id,
        "period_hours": period_hours,
        "comment_activity": {
            "value": comment_activity.value,
            "unit": comment_activity.unit,
            "target": comment_activity.target,
            "achieved": comment_activity.achieved
        },
        "collaboration_score": {
            "value": collab_score.value,
            "unit": collab_score.unit,
            "target": collab_score.target,
            "achieved": collab_score.achieved,
            "metadata": collab_score.metadata
        }
    }


@router.get("/compliance/{store_id}")
async def get_compliance_metrics(
    store_id: str,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    Compliance-Metriken für einen Store.

    Enthält:
    - Audit-Log-Abdeckung
    - Compliance-Score
    - Sicherheits-Status
    """
    audit_coverage = await nützlichkeit_metrics.measure_audit_coverage(store_id, days)
    compliance_score = await nützlichkeit_metrics.measure_compliance_score(store_id)

    return {
        "store_id": store_id,
        "period_days": days,
        "audit_coverage": {
            "value": audit_coverage.value,
            "unit": audit_coverage.unit,
            "target": audit_coverage.target,
            "achieved": audit_coverage.achieved
        },
        "compliance_score": {
            "value": compliance_score.value,
            "unit": compliance_score.unit,
            "target": compliance_score.target,
            "achieved": compliance_score.achieved,
            "metadata": compliance_score.metadata
        }
    }


@router.get("/performance/{store_id}")
async def get_performance_metrics(
    store_id: str,
    endpoint: str = Query("search", description="Zu testender Endpoint"),
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    Performance-Metriken für einen Store.

    Enthält:
    - Antwortzeiten
    - Throughput
    - Resource-Usage
    """
    response_time = await nützlichkeit_metrics.measure_response_time(
        endpoint, store_id
    )

    return {
        "store_id": store_id,
        "endpoint": endpoint,
        "response_time": {
            "value": response_time.value,
            "unit": response_time.unit,
            "target": response_time.target,
            "achieved": response_time.achieved
        }
    }


@router.get("/engagement/{store_id}")
async def get_engagement_metrics(
    store_id: str,
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    User-Engagement-Metriken für einen Store.

    Enthält:
    - Daily Active Users
    - Feature-Adoption
    - Usage-Trends
    """
    dau = await nützlichkeit_metrics.measure_daily_active_users(store_id, days)
    adoption = await nützlichkeit_metrics.measure_feature_adoption(store_id)

    return {
        "store_id": store_id,
        "period_days": days,
        "daily_active_users": {
            "value": dau.value,
            "unit": dau.unit,
            "target": dau.target,
            "achieved": dau.achieved
        },
        "feature_adoption": {
            "value": adoption.value,
            "unit": adoption.unit,
            "target": adoption.target,
            "achieved": adoption.achieved,
            "metadata": adoption.metadata
        }
    }


@router.get("/trends/{store_id}")
async def get_metric_trends(
    store_id: str,
    metric_name: str = Query("collaboration_score"),
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    Trend-Analyse für eine Metrik.

    Zeigt die Entwicklung über Zeit.
    """
    trends = nützlichkeit_metrics.system_metrics.get_trend(metric_name, hours)

    return {
        "store_id": store_id,
        "metric_name": metric_name,
        "period_hours": hours,
        "values": trends,
        "trend": "improving" if len(trends) > 1 and trends[-1] > trends[0] else "stable" if len(trends) <= 1 else "declining"
    }