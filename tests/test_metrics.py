"""
Test- und Evaluationsmetriken für die neuen Nützlichkeits-Verbesserungen.

Metriken für:
- Audit-Logs & Compliance
- Kollaboration & Kommentare
- Performance & Usability
- User-Engagement
"""
import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class MetricResult:
    """Ergebnis einer Metrik-Messung"""
    name: str
    value: float
    unit: str
    target: float
    achieved: bool
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


class SystemMetrics:
    """System-Metriken für Evaluierung"""

    def __init__(self):
        self.metrics_history: List[MetricResult] = []

    def add_metric(self, metric: MetricResult):
        """Füge eine Metrik hinzu"""
        self.metrics_history.append(metric)

    def get_current_metrics(self) -> Dict[str, MetricResult]:
        """Hole die aktuellsten Metriken pro Kategorie"""
        current = {}
        for metric in reversed(self.metrics_history):
            if metric.name not in current:
                current[metric.name] = metric
        return current

    def get_trend(self, metric_name: str, hours: int = 24) -> List[float]:
        """Hole Trend einer Metrik über die letzten Stunden"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        values = []

        for metric in self.metrics_history:
            if metric.name == metric_name:
                metric_time = datetime.fromisoformat(metric.timestamp)
                if metric_time >= cutoff:
                    values.append(metric.value)

        return values


class NützlichkeitMetrics:
    """Metriken zur Messung der Nützlichkeits-Steigerung"""

    def __init__(self):
        self.system_metrics = SystemMetrics()

    # ─── Kollaborations-Metriken ───

    async def measure_comment_activity(
        self,
        store_id: str,
        period_hours: int = 24,
    ) -> MetricResult:
        """
        Misst die Kommentar-Aktivität in einem Store.

        Target: Mindestens 5 Kommentare pro Tag bei aktivem Team
        """
        # TODO: Implementiere echte Messung
        from app.api.comments import _get_comments

        comments = _get_comments(store_id)
        recent_comments = [
            c for c in comments
            if self._is_recent(c.get("created_at"), period_hours)
        ]

        value = len(recent_comments) / max(1, period_hours / 24)  # Kommentare pro Tag

        return MetricResult(
            name="comment_activity",
            value=value,
            unit="comments/day",
            target=5.0,
            achieved=value >= 5.0,
            metadata={
                "total_comments": len(recent_comments),
                "period_hours": period_hours,
                "unique_users": len(set(c.get("user_id") for c in recent_comments))
            }
        )

    async def measure_collaboration_score(
        self,
        store_id: str,
    ) -> MetricResult:
        """
        Misst den Kollaborations-Score (0-100).

        Basierend auf:
        - Kommentar-Aktivität
        - Thread-Tiefe
        - User-Diversifikation
        - Resolutions-Rate
        """
        # TODO: Implementiere echte Messung
        from app.api.comments import _get_comments

        comments = _get_comments(store_id)

        if not comments:
            return MetricResult(
                name="collaboration_score",
                value=0.0,
                unit="score",
                target=50.0,
                achieved=False,
                metadata={"reason": "no_comments"}
            )

        # Metriken berechnen
        unique_users = len(set(c.get("user_id") for c in comments))
        total_comments = len(comments)
        avg_thread_depth = sum(len(c.get("replies", [])) for c in comments) / max(1, total_comments)

        # Score berechnen (0-100)
        score = 0
        score += min(unique_users * 10, 40)  # Max 40 Punkte für User-Diversifikation
        score += min(total_comments * 2, 30)   # Max 30 Punkte für Aktivität
        score += min(avg_thread_depth * 10, 20)  # Max 20 Punkte für Thread-Tiefe

        return MetricResult(
            name="collaboration_score",
            value=score,
            unit="score",
            target=50.0,
            achieved=score >= 50.0,
            metadata={
                "unique_users": unique_users,
                "total_comments": total_comments,
                "avg_thread_depth": avg_thread_depth
            }
        )

    # ─── Compliance-Metriken ───

    async def measure_audit_coverage(
        self,
        store_id: str,
        days: int = 30,
    ) -> MetricResult:
        """
        Misst die Audit-Log-Abdeckung.

        Target: Mindestens 90% aller Aktionen geloggt
        """
        # TODO: Implementiere echte Messung
        # Für jetzt: Schätzung basierend auf System-Aktivität

        # Simulierte Metrik (in Realität aus Audit-Logs)
        estimated_coverage = 85.0  # 85% der Aktionen werden aktuell geloggt

        return MetricResult(
            name="audit_coverage",
            value=estimated_coverage,
            unit="percent",
            target=90.0,
            achieved=estimated_coverage >= 90.0,
            metadata={
                "days": days,
                "improvement_needed": max(0, 90.0 - estimated_coverage)
            }
        )

    async def measure_compliance_score(
        self,
        store_id: str,
    ) -> MetricResult:
        """
        Misst den Compliance-Score (0-100).

        Basierend auf:
        - Audit-Log-Abdeckung
        - Data-Export-Kontrollen
        - User-Authentifizierung
        - Retention-Policy-Einhaltung
        """
        # TODO: Implementiere echte Messung
        audit_coverage = (await self.measure_audit_coverage(store_id)).value

        # Score berechnen
        score = audit_coverage * 0.9  # Audit-Abdeckung ist Hauptfaktor
        score += 5.0  # Auth-System vorhanden
        score += 5.0  # Export-Kontrollen teilweise vorhanden

        return MetricResult(
            name="compliance_score",
            value=min(score, 100.0),
            unit="score",
            target=80.0,
            achieved=score >= 80.0,
            metadata={
                "audit_coverage": audit_coverage,
                "auth_system": "present",
                "export_controls": "partial"
            }
        )

    # ─── Performance-Metriken ───

    async def measure_response_time(
        self,
        endpoint: str,
        store_id: str,
    ) -> MetricResult:
        """
        Misst die durchschnittliche Antwortzeit eines Endpoints.

        Target: < 500ms für API-Endpoints
        """
        start_time = time.time()

        # TODO: Implementiere echte API-Call-Messung
        # Für jetzt: Simulierter API-Call
        await asyncio.sleep(0.1)  # Simuliere 100ms Antwortzeit

        response_time = (time.time() - start_time) * 1000  # in ms

        return MetricResult(
            name=f"response_time_{endpoint}",
            value=response_time,
            unit="ms",
            target=500.0,
            achieved=response_time < 500.0,
            metadata={
                "endpoint": endpoint,
                "store_id": store_id
            }
        )

    # ─── User-Engagement-Metriken ───

    async def measure_daily_active_users(
        self,
        store_id: str,
        days: int = 7,
    ) -> MetricResult:
        """
        Misst die Anzahl aktiver User pro Tag.

        Target: Mindestens 3 aktive User bei Teams
        """
        # TODO: Implementiere echte Messung aus Audit-Logs
        # Für jetzt: Simulierte Metrik
        estimated_dau = 2.5  # Durchschnitt 2.5 aktive User

        return MetricResult(
            name="daily_active_users",
            value=estimated_dau,
            unit="users",
            target=3.0,
            achieved=estimated_dau >= 3.0,
            metadata={
                "period_days": days,
                "improvement_needed": max(0, 3.0 - estimated_dau)
            }
        )

    async def measure_feature_adoption(
        self,
        store_id: str,
    ) -> MetricResult:
        """
        Misst die Nutzung der neuen Features.

        Target: Mindestens 60% der User nutzen neue Features
        """
        # TODO: Implementiere echte Messung
        # Features: Kommentare, Audit-Dashboard, etc.

        # Simulierte Metrik
        estimated_adoption = 35.0  # 35% der User nutzen neue Features

        return MetricResult(
            name="feature_adoption",
            value=estimated_adoption,
            unit="percent",
            target=60.0,
            achieved=estimated_adoption >= 60.0,
            metadata={
                "comments_used": True,
                "audit_dashboard_used": False,
                "compliance_reports_used": False
            }
        )

    # ─── Overall Nützlichkeits-Score ───

    async def calculate_overall_score(
        self,
        store_id: str,
    ) -> Dict[str, Any]:
        """
        Berechnet den Gesamt-Nützlichkeits-Score.

        Gewichtung:
        - Kollaboration: 30%
        - Compliance: 25%
        - Performance: 20%
        - User-Engagement: 25%
        """
        # Einzelne Metriken messen
        collab_score = await self.measure_collaboration_score(store_id)
        compliance_score = await self.measure_compliance_score(store_id)
        response_time = await self.measure_response_time("search", store_id)
        dau = await self.measure_daily_active_users(store_id)
        adoption = await self.measure_feature_adoption(store_id)

        # Performance-Score invertieren (niedriger ist besser)
        perf_score = 100.0 - min((response_time.value / 500.0) * 100.0, 100.0)

        # Gewichteter Gesamtscore
        overall_score = (
            collab_score.value * 0.30 +
            compliance_score.value * 0.25 +
            perf_score * 0.20 +
            (dau.value / 5.0) * 100.0 * 0.15 +
            adoption.value * 0.10
        )

        return {
            "overall_score": min(overall_score, 100.0),
            "target": 70.0,
            "achieved": overall_score >= 70.0,
            "components": {
                "collaboration": collab_score.value,
                "compliance": compliance_score.value,
                "performance": perf_score,
                "engagement": (dau.value / 5.0) * 100.0,
                "adoption": adoption.value
            },
            "recommendations": self._get_improvement_recommendations({
                "collaboration": collab_score.value,
                "compliance": compliance_score.value,
                "performance": perf_score,
                "engagement": (dau.value / 5.0) * 100.0,
                "adoption": adoption.value
            })
        }

    def _get_improvement_recommendations(self, scores: Dict[str, float]) -> List[str]:
        """Generiert Verbesserungs-Empfehlungen basierend auf Scores"""
        recommendations = []

        if scores.get("collaboration", 0) < 50:
            recommendations.append("Fördern Sie Kommentierung und Team-Arbeit durch Schulungen")

        if scores.get("compliance", 0) < 80:
            recommendations.append("Verbessern Sie Audit-Log-Abdeckung für Compliance")

        if scores.get("performance", 0) < 70:
            recommendations.append("Optimieren Sie Datenbank-Queries und Caching")

        if scores.get("engagement", 0) < 60:
            recommendations.append("Implementieren Sie User-Onboarding und Tutorials")

        if scores.get("adoption", 0) < 60:
            recommendations.append("Heben Sie neue Features im UI hervor")

        return recommendations if recommendations else ["System arbeitet innerhalb optimaler Parameter"]

    def _is_recent(self, timestamp_str: str, hours: int) -> bool:
        """Prüft ob ein Zeitstempel innerhalb der letzten Stunden liegt"""
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            return timestamp >= cutoff
        except:
            return False


# ─── Global Instance ───
nützlichkeit_metrics = NützlichkeitMetrics()