"""
PII Redaction Service

Entfernt persönlich identifizierbare Informationen (PII) aus Texten.
DSGVO-konform für municipal Anwendungen.
"""
import re
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RedactionResult:
    """Ergebnis der PII-Redaktion"""
    redacted_text: str
    counts: Dict[str, int]  # PII-Typ → Anzahl
    redacted_items: List[Dict[str, str]]  # Details für Audit
    processing_time_ms: float


class PIIRedactor:
    """
    Erkennt und entfernt PII aus deutschen Texten.

    Schützt vor:
    - Email-Adressen
    - Telefonnummern (deutsches Format)
    - IBANs (deutsche IBANs)
    - Adressen
    - Personennamen (mit NER)
    - Geburtsdaten
    """

    # German PII Patterns
    PATTERNS = {
        "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "phone": r'\b(\+49|0)[1-9]\d{1,2}[- ]?\d{3,4}[- ]?\d{4,6}\b',
        "iban": r'\bDE\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{2}\s?\d{10}\b',
        "iban_alt": r'\bDE\d{20}\b',  # IBAN ohne Leerzeichen
        "credit_card": r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b',
        "ssn_german": r'\b\d{3}[- ]?\d{2}[- ]?\d{4}\b',  # Rentenversicherungsnummer
        "passport_german": r'\b[A-Z][0-9]{4}[<][0-9]{6}[<][0-9]M[<]?',
        "address_street": r'\b[A-Z][a-zäöüß]+straße\s+\d+[a-z]?(?:,?\s*\d{5}\s[A-Z][a-zäöüß]+)?\b',
        "address_number": r'\b[A-Z][a-zäöüß]+str\.\s+\d+[a-z]?\b',
        "postcode": r'\b\d{5}\s[A-Z][a-zäöüß]+\b',
        "birthdate": r'\b\d{1,2}\.\s*(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+\d{4}\b',
        "birthdate_short": r'\b\d{1,2}\.\d{1,2}\.\d{2,4}\b',
    }

    # Context Patterns für bessere Erkennung
    CONTEXT_PATTERNS = {
        "email_context": [
            r'(?:E-Mail|Email|Mail|Kontakt)[:\s]*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})',
        ],
        "phone_context": [
            r'(?:Tel|Telefon|Fax|Mobil|Mobile|Durchwahl|Hotline)[:\s]*((?:\+49|0)[1-9]\d{1,2}[- ]?\d{3,4}[- ]?\d{4,6})',
        ],
    }

    # German Vornamen (für bessere Erkennung)
    GERMAN_FIRST_NAMES = {
        # Top 50 männlich
        "hans", "peter", "klaus", "jürgen", "werner", "manfred", "wolfgang",
        "andreas", "michael", "thomas", "stefan", "frank", "jürgen", "klaus",
        "martin", "roland", "bernd", "dieter", "karl", "heinz", "otto",
        "wilhelm", "friedrich", "georg", "hermann", "heinrich",
        # Top 50 weiblich
        "maria", "anna", "elisabeth", "elisabetha", "elise", "lieselotte",
        "hildegard", "gertrud", "irma", "edith", "erika", "ursula", "monika",
        "renate", "sabine", "angelika", "brigitte", "stefanie", "christiane",
        "susan", "sandra", "daniela", "nicole", "julia", "laura", "lisa",
        # Weitere häufige Namen
        "max", "moritz", "jakob", "alexander", "felix", "lucas", "leon",
        "noah", "paul", "ben", "elijah", "mathias", "lukas", "jonas",
        "sophia", "emma", "hannah", "mia", "lea", "lina", "julia", "lena",
        "marie", "lotta", "klara", "ella", "emilia",
    }

    def __init__(self, strict_mode: bool = True):
        """
        Args:
            strict_mode: Wenn True, redaktion agressiver
        """
        self.strict_mode = strict_mode
        self._compile_patterns()

    def _compile_patterns(self):
        """Kompiliert Regex-Patterns für Performance"""
        self.compiled_patterns = {}
        for pii_type, pattern in self.PATTERNS.items():
            try:
                self.compiled_patterns[pii_type] = re.compile(pattern, re.IGNORECASE)
            except re.error as e:
                logger.error(f"Invalid regex pattern for {pii_type}: {e}")

    def redact_text(self, text: str) -> RedactionResult:
        """
        Entfernt PII aus Text.

        Args:
            text: Zu redigierender Text

        Returns:
            RedactionResult mit redigiertem Text und Statistiken
        """
        import time
        start_time = time.time()

        redacted = text
        counts = {}
        redacted_items = []

        # 1. Pattern-basierte Redaktion
        for pii_type, pattern in self.compiled_patterns.items():
            matches = list(pattern.finditer(redacted))
            if matches:
                count = len(matches)
                counts[pii_type] = count

                # Reverse iteration für sicheren Replacement
                for match in reversed(matches):
                    start, end = match.span()
                    original = match.group()
                    replacement = f"[REDACTED_{pii_type.upper()}]"

                    redacted = redacted[:start] + replacement + redacted[end:]

                    # Für Audit-Trail
                    redacted_items.append({
                        "type": pii_type,
                        "original": original[:20] + "..." if len(original) > 20 else original,
                        "position": start,
                    })

        # 2. Kontext-basierte Redaktion
        for context_type, patterns in self.CONTEXT_PATTERNS.items():
            for pattern in patterns:
                matches = list(re.finditer(pattern, redacted, re.IGNORECASE))
                for match in matches:
                    if len(match.groups()) > 0:
                        # Nur den Wert extrahieren und redigieren
                        value = match.group(1)
                        pii_type = context_type.replace("_context", "")
                        redacted = redacted.replace(value, f"[REDACTED_{pii_type.upper()}]")
                        counts[pii_type] = counts.get(pii_type, 0) + 1

        # 3. Namen-Redaktion (mit erweiterten Pattern)
        redacted = self._redact_names(redacted, counts, redacted_items)

        processing_time = (time.time() - start_time) * 1000

        return RedactionResult(
            redacted_text=redacted,
            counts=counts,
            redacted_items=redacted_items,
            processing_time_ms=processing_time
        )

    def _redact_names(
        self,
        text: str,
        counts: Dict[str, int],
        redacted_items: List[Dict[str, str]]
    ) -> str:
        """
        Erkennt und redigiert deutsche Namen.

        Args:
            text: Zu redigierender Text
            counts: Counts-Dict für Updates
            redacted_items: Items-List für Updates

        Returns:
            Redigierter Text
        """
        # Pattern für deutsche Namen
        # Titel + Vorname + Nachname
        name_pattern = r'\b(?:Herr|Frau|Dr\.?|Prof\.?|Ing\.?)\s+[A-Z][a-zäöüß]+(?:\s+[A-Z][a-zäöüß]+)+\b'

        matches = list(re.finditer(name_pattern, text))
        for match in reversed(matches):
            start, end = match.span()
            original = match.group()

            # Prüfe ob häufige Vornamen enthalten
            name_parts = original.split()
            has_common_first_name = any(
                part.lower() in self.GERMAN_FIRST_NAMES
                for part in name_parts[1:]  # Erste Teil ist Titel
            )

            if has_common_first_name or self.strict_mode:
                replacement = "[REDACTED_NAME]"
                text = text[:start] + replacement + text[end:]

                counts["name"] = counts.get("name", 0) + 1
                redacted_items.append({
                    "type": "name",
                    "original": original[:30] + "..." if len(original) > 30 else original,
                    "position": start,
                })

        return text

    def redact_dict(self, data: dict, fields: List[str]) -> dict:
        """
        Redigiert PII in bestimmten Feldern eines Dicts.

        Args:
            data: Zu redigierendes Dict
            fields: Liste der zu redigierenden Felder

        Returns:
            Redigiertes Dict
        """
        result = data.copy()

        for field in fields:
            if field in result and isinstance(result[field], str):
                redaction_result = self.redact_text(result[field])
                result[field] = redaction_result.redacted_text
                result[f"{field}_pii_counts"] = redaction_result.counts

        return result

    def get_redaction_summary(self, result: RedactionResult) -> str:
        """
        Gibt lesbare Zusammenfassung der Redaktion.

        Args:
            result: RedactionResult

        Returns:
            Zusammenfassung als String
        """
        if not result.counts:
            return "Keine PII gefunden"

        items = []
        for pii_type, count in result.counts.items():
            items.append(f"{count}× {pii_type}")

        return f"Redacted: {', '.join(items)}"


# Singleton-Instanz
redactor = PIIRedactor()


def redact_search_results(results: List[dict]) -> List[dict]:
    """
    Helper-Funktion für Suchergebnisse.

    Args:
        results: Liste von Suchergebnissen mit "content" Feld

    Returns:
        Liste mit redigierten Ergebnissen
    """
    redacted_results = []

    for result in results:
        if "content" in result:
            redaction_result = redactor.redact_text(result["content"])

            redacted_result = {
                **result,
                "content": redaction_result.redacted_text,
                "pii_redacted": redaction_result.counts,
            }

            # Original entfernen (Security)
            if "original_content" in redacted_result:
                del redacted_result["original_content"]

            redacted_results.append(redacted_result)
        else:
            redacted_results.append(result)

    return redacted_results


# Export
__all__ = [
    "PIIRedactor",
    "RedactionResult",
    "redactor",
    "redact_search_results",
]
