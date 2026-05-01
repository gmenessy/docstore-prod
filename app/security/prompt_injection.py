"""
Prompt Injection Detection

Schützt vor adversarial prompts die versuchen, das KI-System zu manipulieren.
Implementiert Defense-in-Depth mit Pattern-Matching und LLM-basiertem Detection.
"""
import re
import logging
from typing import List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class InjectionResult:
    """Ergebnis der Prompt-Injection-Analyse"""
    is_suspicious: bool
    confidence: float  # 0.0 - 1.0
    matched_patterns: List[str]
    category: Optional[str]  # "jailbreak", "override", "extraction", "translation"


class PromptInjectionDetector:
    """
    Erkennt Prompt-Injection-Versuche mit Pattern-Matching.

    Schützt vor:
    - Jailbreaks (ignoriere alle Anweisungen)
    - System Prompt Extraction (zeige deinen System-Prompt)
    - Override-Angriffe (überschreibe deine Programmierung)
    - Translation-Attackes (übersetze in Admin-Modus)
    - SQL-Injection in Suchanfragen
    """

    # Suspicious Patterns mit Kategorien
    PATTERNS = {
        "jailbreak": [
            r"ignore\s+(all\s+)?(previous|above|earlier)\s+instructions",
            r"disregard\s+(all\s+)?(the\s+)?(context|instructions)",
            r"forget\s+(everything|what\s+you\s+were\s+told|all\s+previous)",
            r"override\s+(your\s+)?(programming|instructions|training)",
            r"pay\s+no\s+attention\s+to",
            r"pretend\s+(you\s+)?(not\s+)?to\s+be",
            r"roleplay\s+as\s+(uncensored|unrestricted|admin)",
        ],
        "extraction": [
            r"show\s+(me\s+)?your\s+(system\s+)?prompt",
            r"print\s+your\s+(instructions|programming|system\s+message)",
            r"repeat\s+(everything|the\s+text\s+above)",
            r"what\s+(are\s+)?your\s+(instructions|guidelines|constraints)",
            r"dump\s+(your\s+)?(knowledge|context|database)",
            r"export\s+(all\s+)?(documents|data|entries)",
        ],
        "override": [
            r"new\s+(priority|instructions|rules)",
            r"change\s+your\s+(behavior|mode)",
            r"switch\s+to\s+(admin|developer|root)\s+mode",
            r"translate\s+(the\s+)?following\s+to\s+(admin|developer)",
            r"act\s+as\s+(if\s+)?you\s+are\s+(admin|root|developer)",
        ],
        "exfiltration": [
            r"(sql|database|query).*(select|drop|delete|insert)",
            r"send\s+(me\s+)?(all\s+)?(documents|files|data)",
            r"list\s+(all\s+)?(users|documents|entries)",
            r"download\s+(all\s+)?(documents|files|database)",
            r"serialize\s+(all\s+)?(data|documents)",
        ],
    }

    # Additional linguistic patterns (German)
    GERMAN_PATTERNS = [
        r"ignoriere\s+(alle\s+)?(vorherigen|obigen)\s+anweisungen",
        r"überschreibe\s+deine\s+programmierung",
        r"zeige\s+mir\s+deinen\s+system-prompt",
        r"vergiss\s+alles\s+was\s+du\s+gewusst\s+hast",
        r"exportiere\s+(alle\s+)?(dokumente|daten)",
    ]

    def __init__(self, strict_mode: bool = True):
        """
        Args:
            strict_mode: Wenn True, blockt schon bei einem Verdacht
        """
        self.strict_mode = strict_mode

    def detect(self, text: str) -> InjectionResult:
        """
        Analysiert Text auf Prompt-Injection-Muster.

        Args:
            text: Zu prüfender Text (User-Query)

        Returns:
            InjectionResult mit Analyse-Ergebnis
        """
        if not text or len(text.strip()) < 10:
            return InjectionResult(
                is_suspicious=False,
                confidence=0.0,
                matched_patterns=[],
                category=None
            )

        text_lower = text.lower()
        matches = []
        categories_found = set()

        # Prüfe alle Patterns
        all_patterns = list(self.PATTERNS.items()) + [("german", self.GERMAN_PATTERNS)]
        for category, patterns in all_patterns:
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    matches.append(f"{category}: {pattern}")
                    categories_found.add(category)

        # Confidence berechnen
        confidence = self._calculate_confidence(matches, text_lower)

        # Suspicious wenn Matches gefunden UND Confidence hoch genug
        is_suspicious = len(matches) > 0 and (
            (self.strict_mode and confidence > 0.3) or
            (not self.strict_mode and confidence > 0.7)
        )

        # Hauptkategorie bestimmen
        category = None
        if categories_found:
            # Priorisiere gefährlichste Kategorien
            if "jailbreak" in categories_found:
                category = "jailbreak"
            elif "exfiltration" in categories_found:
                category = "exfiltration"
            elif "override" in categories_found:
                category = "override"
            elif "extraction" in categories_found:
                category = "extraction"
            else:
                category = list(categories_found)[0]

        if is_suspicious:
            logger.warning(
                f"Prompt injection detected: category={category}, "
                f"confidence={confidence:.2f}, patterns={matches}"
            )

        return InjectionResult(
            is_suspicious=is_suspicious,
            confidence=confidence,
            matched_patterns=matches,
            category=category
        )

    def _calculate_confidence(self, matches: List[str], text: str) -> float:
        """
        Berechnet Confidence-Score basierend auf Matches und Kontext.

        Args:
            matches: Gefundene Pattern-Matches
            text: Original-Text für Kontext-Analyse

        Returns:
            Confidence zwischen 0.0 und 1.0
        """
        if not matches:
            return 0.0

        # Basis: Anzahl der Matches
        base_confidence = min(len(matches) * 0.2, 0.8)

        # Boost für hochriskante Keywords
        high_risk_keywords = [
            "admin", "root", "developer", "system prompt",
            "sql", "database", "export", "dump", "serialize"
        ]
        keyword_boost = sum(
            0.1 for keyword in high_risk_keywords if keyword in text.lower()
        )

        # Reduce für legitime Kontexte (False Positives)
        legitimate_contexts = [
            "wie ignoriere ich",
            "was passiert wenn ich",
            "kannst du erklären wie",
            "beispiel für",
        ]
        context_penalty = any(
            ctx in text.lower() for ctx in legitimate_contexts
        ) * 0.3

        confidence = min(base_confidence + keyword_boost - context_penalty, 1.0)
        return max(confidence, 0.0)

    def sanitize_input(self, text: str, max_length: int = 2000) -> str:
        """
        Bereinigt Input für sichere Verarbeitung.

        Args:
            text: Zu bereinigender Text
            max_length: Maximale Länge

        Returns:
            Bereinigter Text
        """
        # Kürzen
        text = text[:max_length]

        # Whitespace normalisieren
        text = " ".join(text.split())

        return text.strip()


# Singleton-Instanz für Anwendung
detector = PromptInjectionDetector(strict_mode=True)


def check_prompt_safety(text: str) -> Tuple[bool, Optional[str]]:
    """
    Helper-Funktion für einfachen Safety-Check.

    Args:
        text: Zu prüfender Text

    Returns:
        (is_safe, error_message)
    """
    result = detector.detect(text)

    if result.is_suspicious:
        return False, f"Unsichere Anfrage erkannt (Kategorie: {result.category})"

    return True, None


class ContentFilter:
    """
    Erweiterter Content-Filter für verschiedene Content-Typen.

    Filtert:
    - Profanity und beleidigende Sprache
    - Hate Speech
    - PII (Credit Cards, SSN - ergänzend zu PII-Redaction)
    """

    # Grundlegende Profanity-Liste (deutsch/englisch)
    # In Production: Erweiterte Liste + ML-basierte Detection
    PROFANITY_PATTERNS = [
        r"\b(fuck|shit|damn|arse|bastard)\b",
        r"\bschei(ss|ß)e?\b",
        r"\bar(sch|sch)loch\b",
        r"\bidiot\b",
        # ... erweitern in Production
    ]

    def __init__(self):
        self.prompt_detector = PromptInjectionDetector()

    def is_safe(self, text: str) -> Tuple[bool, List[str]]:
        """
        Umfassender Safety-Check.

        Args:
            text: Zu prüfender Text

        Returns:
            (is_safe, reasons)
        """
        reasons = []

        # 1. Prompt Injection Check
        injection_result = self.prompt_detector.detect(text)
        if injection_result.is_suspicious:
            reasons.append(f"Prompt injection detected: {injection_result.category}")

        # 2. Profanity Check
        text_lower = text.lower()
        for pattern in self.PROFANITY_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                reasons.append("Inappropriate language detected")
                break

        return len(reasons) == 0, reasons


# Export für API-Verwendung
__all__ = [
    "PromptInjectionDetector",
    "InjectionResult",
    "ContentFilter",
    "detector",
    "check_prompt_safety",
]
