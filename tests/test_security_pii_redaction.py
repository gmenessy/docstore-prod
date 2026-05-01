"""
Security Tests - PII Redaction

Testet ob PII-Redaction funktioniert und keine Daten durchrutschen.
"""
import pytest
from app.services.pii_redaction import PIIRedactor, redact_search_results


class TestPIIRedaction:
    """Testet PII-Redaktion"""

    def test_email_redaction(self):
        """Testet Email-Redaktion"""
        redactor = PIIRedactor()
        text = "Kontakt: max.mustermann@stadt-musterfeld.de für Rückfragen"
        result = redactor.redact_text(text)

        assert "max.mustermann@stadt-musterfeld.de" not in result.redacted_text
        assert "[REDACTED_EMAIL]" in result.redacted_text
        assert result.counts.get("email") == 1

    def test_multiple_emails_redaction(self):
        """Testet Redaktion mehrerer Emails"""
        redactor = PIIRedactor()
        text = "Email1: admin@stadt.de, Email2: info@stadt.de"
        result = redactor.redact_text(text)

        assert "[REDACTED_EMAIL]" in result.redacted_text
        assert result.counts.get("email") == 2

    def test_phone_redaction(self):
        """Testet Telefonnummer-Redaktion"""
        redactor = PIIRedactor()
        text = "Tel: +49 30 12345678 für Auskunft"
        result = redactor.redact_text(text)

        assert "+49 30 12345678" not in result.redacted_text
        assert "[REDACTED_PHONE]" in result.redacted_text

    def test_iban_redaction(self):
        """Testet IBAN-Redaktion"""
        redactor = PIIRedactor()
        text = "IBAN: DE89 3704 0044 0532 0130 00"
        result = redactor.redact_text(text)

        assert "DE89 3704 0044 0532 0130 00" not in result.redacted_text
        assert "[REDACTED_IBAN]" in result.redacted_text

    def test_iban_without_spaces(self):
        """Testet IBAN ohne Leerzeichen"""
        redactor = PIIRedactor()
        text = "IBAN: DE89370400440532013000"
        result = redactor.redact_text(text)

        assert "DE89370400440532013000" not in result.redacted_text
        assert "[REDACTED_IBAN]" in result.redacted_text

    def test_multiple_pii_types(self):
        """Testet Redaktion mehrerer PII-Typen"""
        redactor = PIIRedactor()
        text = """
        Name: Max Mustermann
        Tel: +49 30 12345678
        Email: max.mustermann@stadt-musterfeld.de
        IBAN: DE89 3704 0044 0532 0130 00
        """
        result = redactor.redact_text(text)

        # Alle PII-Typen sollten redigiert werden
        assert result.counts.get("email") == 1
        assert result.counts.get("phone") == 1
        assert result.counts.get("iban") == 1
        # Überprüfe dass keine PII mehr im Text ist
        assert "max.mustermann@stadt-musterfeld.de" not in result.redacted_text.lower()

    def test_no_pii_returns_empty_counts(self):
        """Testet dass Text ohne PII leere Counts zurückgibt"""
        redactor = PIIRedactor()
        text = "Dies ist ein normaler Text ohne persönliche Daten"
        result = redactor.redact_text(text)

        assert len(result.counts) == 0
        assert text == result.redacted_text  # Text sollte unverändert sein

    def test_redact_dict(self):
        """Testet Redaktion von Dict-Feldern"""
        redactor = PIIRedactor()
        data = {
            "title": "Bauantrag",
            "content": "Kontakt: max@stadt.de, Tel: 030 123456",
            "other_field": "Keine PII hier"
        }

        redacted_data = redactor.redact_dict(data, fields=["content"])

        assert redacted_data["content"] != data["content"]
        assert "[REDACTED_" in redacted_data["content"]
        assert redacted_data["other_field"] == "Keine PII hier"  # Unverändert

    def test_german_address_redaction(self):
        """Testet Redaktion deutscher Adressen"""
        redactor = PIIRedactor()
        text = "Hauptstraße 15, 12345 Musterstadt"
        result = redactor.redact_text(text)

        assert "[REDACTED" in result.redacted_text
        # Entweder address_street oder postcode

    def test_birthdate_redaction(self):
        """Testet Redaktion von Geburtsdaten"""
        redactor = PIIRedactor()
        text = "Geboren am 15. Mai 1980"
        result = redactor.redact_text(text)

        assert "15. Mai 1980" not in result.redacted_text
        # Geburtsdatum sollte redigiert werden

    def test_redacted_items_tracking(self):
        """Testet dass redacted_items für Audit-Trail gefüllt werden"""
        redactor = PIIRedactor()
        text = "Email: test@test.de, Tel: 0123456789"
        result = redactor.redact_text(text)

        assert len(result.redacted_items) >= 2
        # Jedes Item sollte type, original, position haben
        for item in result.redacted_items:
            assert "type" in item
            assert "original" in item
            assert "position" in item

    def test_processing_time_measured(self):
        """Testet dass Processing-Time gemessen wird"""
        redactor = PIIRedactor()
        text = "Email: test@test.de" * 100  # Mehrere PII-Instanzen

        result = redactor.redact_text(text)

        assert result.processing_time_ms > 0
        assert result.processing_time_ms < 1000  # Sollte unter 1 Sekunde sein


class TestPIIRedactionSearchResults:
    """Testet PII-Redaktion in Suchergebnissen"""

    def test_redact_search_results(self):
        """Testet Redaktion von Suchergebnis-Liste"""
        redactor = PIIRedactor()

        results = [
            {
                "id": "doc1",
                "title": "Bauantrag",
                "content": "Kontakt: max@stadt.de, Tel: 030 123456",
                "score": 0.95
            },
            {
                "id": "doc2",
                "title": "Protokoll",
                "content": "Keine PII in diesem Dokument",
                "score": 0.87
            }
        ]

        redacted_results = redact_search_results(results)

        # Erstes Ergebnis sollte redigiert werden
        assert "[REDACTED_" in redacted_results[0]["content"]
        assert redacted_results[0]["pii_redacted"] is not None

        # Zweites Ergebnis sollte unverändert sein
        assert redacted_results[1]["content"] == "Keine PII in diesem Dokument"
        assert "pii_redacted" not in redacted_results[1]

    def test_original_content_removed(self):
        """Testet dass Original-Inhalt entfernt wird (Security)"""
        redactor = PIIRedactor()

        results = [{
            "id": "doc1",
            "title": "Test",
            "content": "Email: secret@test.de",
            "original_content": "Dies sollte entfernt werden"
        }]

        redacted_results = redact_search_results(results)

        # Original-Inhalt sollte entfernt sein
        assert "original_content" not in redacted_results[0]

    def test_empty_results_list(self):
        """Testet Redaktion von leer Ergebnisliste"""
        redactor = PIIRedactor()
        results = []

        redacted_results = redact_search_results(results)

        assert redacted_results == []

    def test_results_without_content_field(self):
        """Testet Ergebnisse ohne 'content' Feld"""
        redactor = PIIRedactor()

        results = [
            {"id": "doc1", "title": "Test"},  # Kein content-Feld
            {"id": "doc2", "score": 0.95}  # Kein content-Feld
        ]

        redacted_results = redact_search_results(results)

        # Sollte keine Fehler werfen
        assert len(redacted_results) == 2
        # Felder sollten unverändert bleiben
        assert redacted_results[0]["title"] == "Test"


class TestPIIRedactionEdgeCases:
    """Edge Cases für PII-Redaktion"""

    def test_overlapping_pii_patterns(self):
        """Testet überlappende PII-Patterns"""
        redactor = PIIRedactor()
        text = "Email: admin@test.de im IBAN: DE123456789"

        result = redactor.redact_text(text)

        # Beide sollten redigiert werden
        assert result.counts.get("email") == 1
        assert result.counts.get("iban") == 1

    def test_embedded_pii_in_text(self):
        """Testet PII die in normalen Text eingebettet sind"""
        redactor = PIIRedactor()
        text = "Bitte wenden Sie sich an max.mustermann@stadt.de für weitere Informationen"

        result = redactor.redact_text(text)

        assert "[REDACTED_EMAIL]" in result.redacted_text
        # Der Rest des Textes sollte erhalten bleiben
        assert "Bitte wenden Sie sich an" in result.redacted_text
        assert "für weitere Informationen" in result.redacted_text

    def test_repeated_pii(self):
        """Testet wiederkehrende PII (z.B. gleiche Email mehrmals)"""
        redactor = PIIRedactor()
        text = "Email: admin@stadt.de oder admin@stadt.de"

        result = redactor.redact_text(text)

        # Alle Vorkommen sollten redigiert werden
        assert "admin@stadt.de" not in result.redacted_text
        assert result.counts.get("email") >= 2

    def test_case_insensitive_pii_detection(self):
        """Testet dass PII-Erkennung case-insensitive ist"""
        redactor = PIIRedactor()
        text = "EMAIL: ADMIN@STADT.DE"  # Großgeschrieben

        result = redactor.redact_text(text)

        assert "[REDACTED_EMAIL]" in result.redacted_text
        assert result.counts.get("email") == 1

    def test_context_aware_redaction(self):
        """Testet kontextbewusste Redaktion (z.B. nach "Email:")"""
        redactor = PIIRedactor()
        text = "E-Mail: max.mustermann@stadt.de"

        result = redactor.redact_text(text)

        # Sollte auch Kontext-Pattern erkennen
        assert "[REDACTED_" in result.redacted_text
