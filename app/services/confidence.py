"""
Confidence Score Calculation

Berechnet Vertrauensscores für KI-generierte Antworten.
Hilft Usern bei der Bewertung der Antwortqualität.
"""
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceResult:
    """Ergebnis der Confidence-Berechnung"""
    confidence: float  # 0.0 - 1.0
    level: str  # "high", "medium", "low"
    factors: Dict[str, float]
    explanation: str


class ConfidenceCalculator:
    """
    Berechnet Confidence-Scores basierend auf mehreren Faktoren.

    Faktoren:
    - Source Relevance: Durchschnittlicher Relevanz-Score der Quellen
    - Source Count: Anzahl der gefundenen Quellen
    - Answer Length: Länge der Antwort (zu kurz = niedriges Vertrauen)
    - Uncertainty Markers: Nutzung von unsicheren Ausdrücken
    - Semantic Similarity: Ähnlichkeit zwischen Query und Antwort
    """

    # German uncertainty phrases
    UNCERTAINTY_PHRASES = [
        "vielleicht", "möglicherweise", "eventuell",
        "könnte", "könnten", "würde", "würden",
        "unsicher", "nicht sicher", "scheint",
        "vermute", "vermutlich", "annahmeweise",
        "glaube", "ich glaube", "meines wissens",
        "so weit ich weiß", "ohne garantie",
        "unter umständen", "gegebenenfalls",
    ]

    # Certainty phrases (positive Indikatoren)
    CERTAINTY_PHRASES = [
        "sicher", "gewiss", "bestimmt",
        "definitiv", "absolut", "unbedingt",
        "zweifellos", "sicherlich", "mit sicherheit",
        "nachweislich", "belegt", "dokumentiert",
        "laut", "gemäß", "zufolge",
    ]

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """
        Args:
            weights: Gewichtungen für Faktoren (optional)
        """
        self.weights = weights or {
            "source_relevance": 0.35,  # Wichtigster Faktor
            "source_count": 0.20,
            "answer_length": 0.15,
            "uncertainty_markers": 0.20,
            "semantic_similarity": 0.10,
        }

        # Gewichte müssen sich zu 1.0 summieren
        total_weight = sum(self.weights.values())
        if abs(total_weight - 1.0) > 0.01:
            logger.warning(f"Weights do not sum to 1.0: {total_weight}, normalizing")
            self.weights = {
                k: v / total_weight
                for k, v in self.weights.items()
            }

    def calculate(
        self,
        answer: str,
        sources: List[Dict],
        query: str,
        context: Optional[str] = None
    ) -> ConfidenceResult:
        """
        Berechnet Confidence-Score für eine Antwort.

        Args:
            answer: Generierte Antwort
            sources: Liste der verwendeten Quellen
            query: Original-Query
            context: Optionaler Kontext

        Returns:
            ConfidenceResult
        """
        factors = {}

        # 1. Source Relevance
        factors["source_relevance"] = self._calculate_source_relevance(sources)

        # 2. Source Count
        factors["source_count"] = self._calculate_source_count(sources)

        # 3. Answer Length
        factors["answer_length"] = self._calculate_answer_length(answer)

        # 4. Uncertainty Markers
        factors["uncertainty_markers"] = self._calculate_uncertainty_markers(answer)

        # 5. Semantic Similarity
        if context:
            factors["semantic_similarity"] = self._calculate_semantic_similarity(
                answer, query, context
            )
        else:
            factors["semantic_similarity"] = 0.5  # Neutral wenn kein Kontext

        # Gewichteter Gesamtscore
        confidence = sum(
            factors[factor] * weight
            for factor, weight in self.weights.items()
        )

        # Clamp zwischen 0.0 und 1.0
        confidence = max(0.0, min(1.0, confidence))

        # Level bestimmen
        if confidence >= 0.7:
            level = "high"
        elif confidence >= 0.4:
            level = "medium"
        else:
            level = "low"

        # Explanation generieren
        explanation = self._generate_explanation(factors, level)

        return ConfidenceResult(
            confidence=round(confidence, 2),
            level=level,
            factors=factors,
            explanation=explanation
        )

    def _calculate_source_relevance(self, sources: List[Dict]) -> float:
        """Berechnet durchschnittliche Quellen-Relevanz"""
        if not sources:
            return 0.1  # Sehr niedrig ohne Quellen

        relevance_scores = [
            source.get("score", source.get("relevance", 0.5))
            for source in sources
        ]

        # Durchschnitt mit Penalty für sehr niedrige Scores
        avg_relevance = np.mean(relevance_scores)
        min_penalty = min(0.3, np.min(relevance_scores))

        return max(0.0, avg_relevance - min_penalty)

    def _calculate_source_count(self, sources: List[Dict]) -> float:
        """Berechnet Score basierend auf Quellen-Anzahl"""
        if not sources:
            return 0.0

        count = len(sources)

        # Logarithmische Skalierung (1 Quelle = 0.5, 5+ Quellen = 1.0)
        if count == 1:
            return 0.5
        elif count <= 3:
            return 0.7
        elif count <= 5:
            return 0.9
        else:
            return 1.0

    def _calculate_answer_length(self, answer: str) -> float:
        """Berechnet Score basierend auf Antwortlänge"""
        word_count = len(answer.split())

        # Zu kurz = niedriges Vertrauen
        if word_count < 20:
            return 0.3
        elif word_count < 50:
            return 0.6
        elif word_count < 150:
            return 0.9
        elif word_count < 300:
            return 1.0
        else:
            # Zu lang kann auch Overfitting sein
            return 0.8

    def _calculate_uncertainty_markers(self, answer: str) -> float:
        """
        Berechnet Score basierend auf Unsicherheits-Markern.

        Niedrig = viele uncertainty phrases
        Hoch = viele certainty phrases
        """
        answer_lower = answer.lower()

        # Zähle uncertainty markers
        uncertainty_count = sum(
            1 for phrase in self.UNCERTAINTY_PHRASES
            if phrase in answer_lower
        )

        # Zähle certainty markers
        certainty_count = sum(
            1 for phrase in self.CERTAINTY_PHRASES
            if phrase in answer_lower
        )

        # Penalty für uncertainty
        uncertainty_penalty = min(0.5, uncertainty_count * 0.1)

        # Bonus für certainty
        certainty_bonus = min(0.2, certainty_count * 0.05)

        return max(0.0, 1.0 - uncertainty_penalty + certainty_bonus)

    def _calculate_semantic_similarity(
        self,
        answer: str,
        query: str,
        context: str
    ) -> float:
        """
        Berechnet semantische Ähnlichkeit (vereinfacht).

        In Production: Verwende Embedding-Modelle
        """
        # Vereinfachte Implementierung: Word Overlap
        answer_words = set(answer.lower().split())
        query_words = set(query.lower().split())
        context_words = set(context.lower().split())

        # Query Overlap
        query_overlap = len(answer_words & query_words) / max(len(query_words), 1)

        # Context Overlap
        context_overlap = len(answer_words & context_words) / max(len(context_words), 1)

        # Gewichteter Durchschnitt
        return (query_overlap * 0.3 + context_overlap * 0.7)

    def _generate_explanation(self, factors: Dict[str, float], level: str) -> str:
        """Generiert lesbare Erklärung des Scores"""
        explanations = []

        if factors["source_relevance"] < 0.5:
            explanations.append("niedrige Quellen-Relevanz")
        if factors["source_count"] < 0.5:
            explanations.append("wenige Quellen")
        if factors["answer_length"] < 0.5:
            explanations.append("sehr kurze Antwort")
        if factors["uncertainty_markers"] < 0.5:
            explanations.append("unsichere Ausdrücke")

        if not explanations:
            if level == "high":
                return "Hohe Vertrauenswürdigkeit basierend auf relevanten Quellen"
            else:
                return "Moderate Vertrauenswürdigkeit"

        return f"Signal: {', '.join(explanations)}"


# Singleton-Instanz
calculator = ConfidenceCalculator()


def calculate_confidence(
    answer: str,
    sources: List[Dict],
    query: str,
    context: Optional[str] = None
) -> ConfidenceResult:
    """
    Helper-Funktion für einfachere Aufrufe.

    Args:
        answer: Generierte Antwort
        sources: Quellen-Liste
        query: Original-Query
        context: Optionaler Kontext

    Returns:
        ConfidenceResult
    """
    return calculator.calculate(answer, sources, query, context)


# Export
__all__ = [
    "ConfidenceCalculator",
    "ConfidenceResult",
    "calculator",
    "calculate_confidence",
]
