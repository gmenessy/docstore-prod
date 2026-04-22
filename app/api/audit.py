"""
API-Routen: Audit-Logs & Compliance.

Bietet Endpunkte für:
- Audit-Log Abfragen
- Compliance-Dashboards
- Export von Compliance-Reports
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import verify_api_key
from app.core.audit import audit_logger, get_compliance_metrics

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/audit", tags=["Audit & Compliance"])


@router.get("/logs")
async def get_audit_logs(
    store_id: str,
    action: Optional[str] = Query(None, description="Filter by action type"),
    user_id: Optional[str] = Query(None, description="Filter by user"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    Audit-Logs für einen Store abrufen.

    Verwendet für Compliance-Reporting und Sicherheits-Audits.
    """
    logs = await audit_logger.query_logs(
        db=db,
        store_id=store_id,
        action=action,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )

    return {
        "store_id": store_id,
        "logs": logs,
        "count": len(logs),
        "period": {
            "start": start_date or "earliest",
            "end": end_date or "now",
        }
    }


@router.get("/compliance/dashboard")
async def get_compliance_dashboard(
    store_id: str,
    days: int = Query(30, ge=1, le=365, description="Zeitraum in Tagen"),
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    Compliance-Dashboard für einen Store.

    Zeigt Metriken für DSGVO-Konformität und Nutzung.
    """
    metrics = await get_compliance_metrics(
        db=db,
        store_id=store_id,
        days=days,
    )

    return {
        "store_id": store_id,
        "period_days": days,
        "metrics": metrics,
        "compliance_status": _calculate_compliance_status(metrics),
        "recommendations": _get_compliance_recommendations(metrics),
    }


@router.get("/compliance/report")
async def get_compliance_report(
    store_id: str,
    days: int = Query(30, ge=1, le=365),
    format: str = Query("json", pattern="^(json|csv|pdf)$"),
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    Exportiert einen Compliance-Report.

    Unterstützt Formate: JSON, CSV, PDF (optional)
    """
    metrics = await get_compliance_metrics(
        db=db,
        store_id=store_id,
        days=days,
    )

    # TODO: Implementiere CSV und PDF Export
    if format == "json":
        return {
            "report_type": "compliance",
            "store_id": store_id,
            "period_days": days,
            "generated_at": datetime.utcnow().isoformat(),
            "metrics": metrics,
        }

    elif format == "csv":
        # TODO: CSV-Export implementieren
        return {"error": "CSV-Export noch nicht implementiert"}

    elif format == "pdf":
        # TODO: PDF-Export implementieren
        return {"error": "PDF-Export noch nicht implementiert"}


def _calculate_compliance_status(metrics: dict) -> dict:
    """
    Berechnet den Compliance-Status basierend auf Metriken.

    Returns:
        Dict mit Status-Informationen
    """
    status = "good"  # good, warning, critical

    issues = []

    # Prüfe auf ungewöhnliche Export-Aktivität
    if metrics.get("exports", 0) > 100:
        status = "warning"
        issues.append("Hohe Export-Aktivität erkannt")

    # Prüfe auf fehlgeschlagene Logins
    if metrics.get("failed_logins", 0) > 10:
        status = "critical"
        issues.append("Viele fehlgeschlagene Login-Versuche")

    # Prüfe auf geringe User-Aktivität (kann auf Probleme hindeuten)
    if metrics.get("unique_users", 0) < 2 and metrics.get("total_actions", 0) > 100:
        status = "warning"
        issues.append("Geringe User-Diversifikation")

    return {
        "status": status,
        "issues": issues,
        "score": _calculate_compliance_score(metrics),
    }


def _calculate_compliance_score(metrics: dict) -> int:
    """
    Berechnet einen Compliance-Score (0-100).

    Basierend auf:
    - Audit-Log Coverage
    - User-Aktivität
    - Sicherheits-Metriken
    """
    score = 100

    # Abzüge für Probleme
    if metrics.get("failed_logins", 0) > 0:
        score -= min(metrics["failed_logins"] * 2, 20)

    if metrics.get("unique_users", 0) < 2:
        score -= 10

    if metrics.get("total_actions", 0) < 10:
        score -= 20

    return max(0, min(100, score))


def _get_compliance_recommendations(metrics: dict) -> list[str]:
    """
    Generiert Empfehlungen zur Verbesserung der Compliance.
    """
    recommendations = []

    if metrics.get("failed_logins", 0) > 5:
        recommendations.append("Überprüfen Sie Login-Versuche und erwägen Sie Rate-Limiting")

    if metrics.get("exports", 0) > 50:
        recommendations.append("Implementieren Sie Export-Genehmigungsprozesse")

    if metrics.get("unique_users", 0) < 3:
        recommendations.append("Fördern Sie die Nutzung durch mehrere Team-Mitglieder")

    if metrics.get("document_actions", 0) > 500:
        recommendations.append("Erwägen Sie die Implementierung von Dokumenten-Versionierung")

    return recommendations if recommendations else ["System arbeitet innerhalb normaler Parameter"]