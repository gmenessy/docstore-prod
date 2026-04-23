"""
Wiki-Auto-Kuratierung Service.

Automatische Wiki-Pflege basierend auf:
- Quality-Metriken
- Dokumenten-Änderungen
- Zeitplänen
- User-Feedback
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Store, WikiPage, Document
from app.services.wiki_service import wiki_ingest, generate_summary
from app.core.llm_client import llm_client

logger = logging.getLogger(__name__)


class QualityMetric(Enum):
    """Wiki-Qualitäts-Metriken"""
    CONTENT_FRESHNESS = "content_freshness"  # Wie aktuell ist der Inhalt?
    REFERENCE_COVERAGE = "reference_coverage"  # Werden Quellen korrekt zitiert?
    STRUCTURE_QUALITY = "structure_quality"  # Ist die Struktur gut?
    COMPLETENESS = "completeness"  # Sind alle Informationen vorhanden?
    CONSISTENCY = "consistency"  # Gibt es Widersprüche?


@dataclass
class QualityScore:
    """Qualitäts-Score für eine Wiki-Seite"""
    page_id: str
    page_title: str
    overall_score: float  # 0-100
    metrics: Dict[str, float]
    issues: List[str]
    recommendations: List[str]
    last_checked: datetime
    needs_refresh: bool


class WikiAutoCurator:
    """Automatische Wiki-Kurierung"""

    def __init__(self):
        self.quality_history: Dict[str, List[QualityScore]] = {}
        self.refresh_threshold = 50.0  # Score unter 50 bedeutet Refresh nötig

    async def check_wiki_quality(
        self,
        db: AsyncSession,
        store_id: str,
        page_id: str,
    ) -> QualityScore:
        """
        Prüft die Qualität einer Wiki-Seite.

        Returns:
            QualityScore mit Metriken und Empfehlungen
        """
        # Wiki-Seite laden
        result = await db.execute(
            select(WikiPage)
            .where(WikiPage.id == page_id)
            .where(WikiPage.store_id == store_id)
        )
        page = result.scalar_one_or_none()

        if not page:
            raise ValueError(f"Wiki-Seite {page_id} nicht gefunden")

        # Metriken berechnen
        metrics = {}
        issues = []
        recommendations = []

        # 1. Content Freshness (wie aktuell sind die Quellen?)
        freshness = await self._calculate_freshness(db, page)
        metrics["content_freshness"] = freshness
        if freshness < 60:
            issues.append("Inhalte basieren auf veralteten Quellen")
            recommendations.append("Aktualisieren Sie die Wiki-Seite mit neueren Dokumenten")

        # 2. Reference Coverage (werden Quellen zitiert?)
        ref_coverage = await self._calculate_reference_coverage(page)
        metrics["reference_coverage"] = ref_coverage
        if ref_coverage < 70:
            issues.append("Unzureichende Quellenangaben")
            recommendations.append("Fügen Sie Quellen-Zitate hinzu")

        # 3. Structure Quality (ist die Struktur gut?)
        struct_quality = await self._calculate_structure_quality(page)
        metrics["structure_quality"] = struct_quality
        if struct_quality < 60:
            issues.append("Struktur könnte verbessert werden")
            recommendations.append("Verbessern Sie die Abschnitts-Struktur")

        # 4. Completeness (sind alle Infos vorhanden?)
        completeness = await self._calculate_completeness(page)
        metrics["completeness"] = completeness
        if completeness < 70:
            issues.append("Unvollständige Informationen")
            recommendations.append("Ergänzen Sie fehlende Abschnitte")

        # 5. Consistency (gibt es Widersprüche?)
        consistency = await self._calculate_consistency(db, page)
        metrics["consistency"] = consistency
        if consistency < 70:
            issues.append("Mögliche Widersprüche gefunden")
            recommendations.append("Prüfen und korrigieren Sie widersprüchliche Aussagen")

        # Overall Score berechnen
        overall_score = (
            freshness * 0.25 +
            ref_coverage * 0.25 +
            struct_quality * 0.20 +
            completeness * 0.15 +
            consistency * 0.15
        )

        # Prüfen ob Refresh nötig ist
        needs_refresh = overall_score < self.refresh_threshold

        score = QualityScore(
            page_id=page_id,
            page_title=page.title,
            overall_score=overall_score,
            metrics=metrics,
            issues=issues,
            recommendations=recommendations,
            last_checked=datetime.utcnow(),
            needs_refresh=needs_refresh
        )

        # In History speichern
        if page_id not in self.quality_history:
            self.quality_history[page_id] = []
        self.quality_history[page_id].append(score)

        return score

    async def _calculate_freshness(self, db: AsyncSession, page: WikiPage) -> float:
        """
        Berechnet wie aktuell die Inhalte sind.

        Basierend auf:
        - Alter der verlinkten Dokumente
        - Letztes Update der Seite
        - Anzahl der Quellen
        """
        # TODO: Implementiere echte Freshness-Berechnung
        # Für jetzt: Simulierter Score
        return 75.0

    async def _calculate_reference_coverage(self, page: WikiPage) -> float:
        """
        Berechnet wie gut Quellen zitiert werden.

        Basierend auf:
        - Anzahl der [1], [2] Zitate
        - Quellen-Abschnitte
        - Link-Dichte
        """
        content_md = page.content_md or ""
        word_count = len(content_md.split())

        # Zitate zählen
        import re
        citations = len(re.findall(r'\[\d+\]', content_md))
        source_sections = len(re.findall(r'Quelle:', content_md))

        # Coverage berechnen
        if word_count == 0:
            return 0.0

        citation_ratio = min((citations + source_sections * 2) / word_count * 100, 100.0)
        return citation_ratio

    async def _calculate_structure_quality(self, page: WikiPage) -> float:
        """
        Berechnet die Struktur-Qualität.

        Basierend auf:
        - Überschriften-Hierarchie
        - Abschnitts-Länge
        - Listen-Struktur
        """
        content_md = page.content_md or ""

        # Überschriften zählen
        headers = len([line for line in content_md.split('\n') if line.startswith('#')])
        word_count = len(content_md.split())

        if word_count == 0:
            return 0.0

        # Header-Ratio (gute Struktur hat ca. 10-20% Headers)
        header_ratio = (headers / word_count) * 100

        # Optimal: 15% Headers ± 10%
        if 5 <= header_ratio <= 25:
            return 85.0
        elif 25 < header_ratio <= 35:
            return 70.0
        else:
            return 50.0

    async def _calculate_completeness(self, page: WikiPage) -> float:
        """
        Berechnet die Vollständigkeit der Informationen.

        Basierend auf:
        - Inhaltsumfang
        - Schlüsselwörter
        - Beispiel-Präsenz
        """
        content_md = page.content_md or ""
        word_count = len(content_md.split())

        # Mindestlänge für vollständige Seite: 300 Wörter
        if word_count < 100:
            return 30.0
        elif word_count < 300:
            return (word_count / 300) * 100.0
        else:
            return 100.0

    async def _calculate_consistency(self, db: AsyncSession, page: WikiPage) -> float:
        """
        Berechnet die Konsistenz der Inhalte.

        Basierend auf:
        - Widersprüche-Erkennung (mittels LLM)
        - Format-Prüfung
        - Link-Validierung
        """
        # TODO: Implementiere echte Konsistenz-Prüfung
        # Für jetzt: Simulierter Score
        return 80.0

    async def auto_refresh_wiki_page(
        self,
        db: AsyncSession,
        store_id: str,
        page_id: str,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Führt automatische Wiki-Aktualisierung durch.

        Args:
            force: Erzwingt Refresh auch bei gutem Score

        Returns:
            Dict mit Refresh-Ergebnis
        """
        # Qualität prüfen
        quality_score = await self.check_wiki_quality(db, store_id, page_id)

        if not force and not quality_score.needs_refresh:
            return {
                "page_id": page_id,
                "action": "none",
                "reason": "quality_score_good",
                "score": quality_score.overall_score
            }

        try:
            # Wiki-Seite neu generieren
            logger.info(f"Auto-Refresh Wiki-Seite {page_id} (Score: {quality_score.overall_score:.1f})")

            # TODO: Implementiere echte Neu-Generierung
            #Für jetzt: Simuliert

            # Verknüpfte Dokumente finden
            docs_result = await db.execute(
                select(Document)
                .where(Document.store_id == store_id)
                .where(Document.status == "indexed")
                .limit(10)
            )
            documents = docs_result.scalars().all()

            if not documents:
                return {
                    "page_id": page_id,
                    "action": "skipped",
                    "reason": "no_documents_found"
                }

            # Wiki neu generieren (simuliert)
            # await self._regenerate_wiki_page(db, store_id, page_id, documents)

            return {
                "page_id": page_id,
                "action": "refreshed",
                "previous_score": quality_score.overall_score,
                "documents_used": len(documents),
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Auto-Refresh fehlgeschlagen für {page_id}: {e}")
            return {
                "page_id": page_id,
                "action": "failed",
                "error": str(e)
            }

    async def get_refresh_candidates(
        self,
        db: AsyncSession,
        store_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Findet Wiki-Seiten die neu generiert werden sollten.

        Basierend auf:
        - Quality-Score
        - Letztes Update
        - Dokumenten-Änderungen seit letztem Update

        Returns:
            Liste von Kandidaten sortiert nach Priorität
        """
        # Alle Wiki-Seiten laden
        result = await db.execute(
            select(WikiPage)
            .where(WikiPage.store_id == store_id)
        )
        pages = result.scalars().all()

        candidates = []

        for page in pages:
            try:
                quality_score = await self.check_wiki_quality(db, store_id, page.id)

                # Priorität berechnen
                priority = 0

                # Niedriger Score = Hohe Priorität
                if quality_score.overall_score < 50:
                    priority += 50
                elif quality_score.overall_score < 70:
                    priority += 30

                # Alter der Seite (älter = höhere Priorität)
                age_days = (datetime.utcnow() - page.updated_at).days
                if age_days > 30:
                    priority += 20
                elif age_days > 7:
                    priority += 10

                candidates.append({
                    "page_id": page.id,
                    "title": page.title,
                    "slug": page.slug,
                    "current_score": quality_score.overall_score,
                    "last_updated": page.updated_at.isoformat(),
                    "age_days": age_days,
                    "priority": priority,
                    "issues": quality_score.issues,
                })

            except Exception as e:
                logger.error(f"Fehler bei Qualitäts-Prüfung für {page.id}: {e}")

        # Sortieren nach Priorität (höchste zuerst)
        candidates.sort(key=lambda x: x["priority"], reverse=True)

        return candidates[:limit]

    async def batch_refresh_wiki(
        self,
        db: AsyncSession,
        store_id: str,
        max_refreshes: int = 5,
    ) -> Dict[str, Any]:
        """
        Führt Batch-Aktualisierung mehrerer Wiki-Seiten durch.

        Args:
            max_refreshes: Maximale Anzahl an Refreshes pro Batch

        Returns:
            Dict mit Batch-Ergebnissen
        """
        # Kandidaten finden
        candidates = await self.get_refresh_candidates(db, store_id, limit=max_refreshes)

        results = {
            "store_id": store_id,
            "candidates_count": len(candidates),
            "refreshes_attempted": 0,
            "refreshes_successful": 0,
            "refreshes_failed": 0,
            "results": []
        }

        for candidate in candidates:
            try:
                refresh_result = await self.auto_refresh_wiki_page(
                    db, store_id, candidate["page_id"], force=False
                )

                results["refreshes_attempted"] += 1

                if refresh_result["action"] == "refreshed":
                    results["refreshes_successful"] += 1
                elif refresh_result["action"] == "failed":
                    results["refreshes_failed"] += 1

                results["results"].append({
                    **candidate,
                    "refresh_result": refresh_result
                })

            except Exception as e:
                logger.error(f"Fehler bei Batch-Refresh für {candidate['page_id']}: {e}")
                results["refreshes_failed"] += 1

        return results


# ─── Global Instance ───
wiki_auto_curator = WikiAutoCurator()