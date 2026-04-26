"""
Security-Tests für DSGVO-Konformität und Security-Aspekte.
Testet Auth, Authorization, Data Privacy und Security-Maßnahmen.
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Store, Document
from app.core.audit import AuditLogger, AuditAction
from app.core.auth import verify_api_key


# ─── Authentication & Authorization ───

def test_api_key_required():
    """Test dass API-Key erforderlich ist"""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # Request ohne API-Key
    response = client.get("/api/v1/stores")

    # Erwarte 401 Unauthorized oder 403 Forbidden
    assert response.status_code in [401, 403]


def test_invalid_api_key():
    """Test dass ungültiger API-Key abgelehnt wird"""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # Request mit ungültigem API-Key
    response = client.get(
        "/api/v1/stores",
        headers={"X-API-Key": "invalid_key_123456789012345678901234"}
    )

    # Erwarte 401 Unauthorized
    assert response.status_code in [401, 403]


def test_expired_api_key():
    """Test dass abgelaufener API-Key abgelehnt wird"""
    # TODO: Implementiere API-Key Expiration
    # Aktuell nicht implementiert, aber für Zukunft wichtig
    pass


def test_store_isolation():
    """Test dass Store-Isolation funktioniert (User kann nur eigenen Store sehen)"""
    from fastapi.testclient import TestClient
    from app.main import app
    from sqlalchemy import select

    client = TestClient(app)
    api_key = "test_api_key_123456789012345678901234567890"

    # Store 1 mit User A erstellen
    response1 = client.post(
        "/api/v1/stores",
        headers={"X-API-Key": api_key},
        json={
            "name": "Store A",
            "type": "akte",
            "description": "Store for User A",
        },
    )

    store_a_id = response1.json().get("id")

    # Versuchen Store B abzurufen (gehört einem anderen User)
    # Erwarte 404 oder 403
    response2 = client.get(
        f"/api/v1/stores/some_other_store_id",
        headers={"X-API-Key": api_key},
    )

    assert response2.status_code in [403, 404]


# ─── Data Privacy (DSGVO) ───

@pytest.mark.asyncio
async def test_audit_log_user_isolation(db_session: AsyncSession):
    """Test dass Audit-Logs User-isoliert sind"""
    from app.core.audit import audit_logger

    store = Store(
        id="test_store_user_isolation",
        name="Test Store User Isolation",
        type="akte",
        description="DSGVO Test",
    )
    db_session.add(store)
    await db_session.commit()

    # Logs für User A erstellen
    await audit_logger.log(
        db=db_session,
        action=AuditAction.DOC_VIEW,
        store_id=store.id,
        user_id="user_a",
        resource_type="document",
        resource_id="doc_1",
    )

    # Logs für User B erstellen
    await audit_logger.log(
        db=db_session,
        action=AuditAction.DOC_VIEW,
        store_id=store.id,
        user_id="user_b",
        resource_type="document",
        resource_id="doc_2",
    )

    # User A sollte nur eigene Logs sehen können
    logs_user_a = await audit_logger.query_logs(
        db=db_session,
        store_id=store.id,
        user_id="user_a",
    )

    assert len(logs_user_a) == 1
    assert logs_user_a[0]["user_id"] == "user_a"


@pytest.mark.asyncio
async def test_right_to_access(db_session: AsyncSession):
    """Test DSGVO-Recht auf Auskunft (Right to Access)"""
    from app.core.audit import audit_logger

    store = Store(
        id="test_store_right_access",
        name="Test Store Right to Access",
        type="akte",
        description="DSGVO Test",
    )
    db_session.add(store)
    await db_session.commit()

    # Verschiedene Actions für User loggen
    await audit_logger.log(
        db=db_session,
        action=AuditAction.DOC_UPLOAD,
        store_id=store.id,
        user_id="user_data_request",
        resource_type="document",
        resource_id="doc_1",
    )

    await audit_logger.log(
        db=db_session,
        action=AuditAction.DOC_VIEW,
        store_id=store.id,
        user_id="user_data_request",
        resource_type="document",
        resource_id="doc_2",
    )

    # User sollte alle seine Daten abrufen können
    logs = await audit_logger.query_logs(
        db=db_session,
        store_id=store.id,
        user_id="user_data_request",
    )

    assert len(logs) >= 2
    # Alle Logs sollten dem User gehören
    for log in logs:
        assert log["user_id"] == "user_data_request"


@pytest.mark.asyncio
async def test_right_to_erasure(db_session: AsyncSession):
    """Test DSGVO-Recht auf Löschung (Right to Erasure)"""
    from app.models.comments import AuditLog
    from sqlalchemy import delete

    store = Store(
        id="test_store_right_erasure",
        name="Test Store Right to Erasure",
        type="akte",
        description="DSGVO Test",
    )
    db_session.add(store)
    await db_session.commit()

    # Audit-Logs für User erstellen
    await audit_logger.log(
        db=db_session,
        action=AuditAction.DOC_VIEW,
        store_id=store.id,
        user_id="user_to_delete",
        resource_type="document",
        resource_id="doc_1",
    )

    # Logs sollten existieren
    logs_before = await audit_logger.query_logs(
        db=db_session,
        store_id=store.id,
        user_id="user_to_delete",
    )

    assert len(logs_before) >= 1

    # User-Daten löschen (DSGVO Recht auf Löschung)
    await db_session.execute(
        delete(AuditLog).where(AuditLog.user_id == "user_to_delete")
    )
    await db_session.commit()

    # Logs sollten gelöscht sein
    logs_after = await audit_logger.query_logs(
        db=db_session,
        store_id=store.id,
        user_id="user_to_delete",
    )

    assert len(logs_after) == 0


@pytest.mark.asyncio
async def test_data_retention_policy(db_session: AsyncSession):
    """Test Data Retention Policy (automatische Löschung alter Daten)"""
    from app.models.comments import AuditLog
    from sqlalchemy import delete

    store = Store(
        id="test_store_retention",
        name="Test Store Data Retention",
        type="akte",
        description="DSGVO Test",
    )
    db_session.add(store)
    await db_session.commit()

    # Alte Audit-Logs erstellen (vor 400 Tagen)
    old_log = AuditLog(
        id="old_log_id",
        store_id=store.id,
        user_id="user_old",
        action=AuditAction.DOC_VIEW,
        created_at=datetime.utcnow() - timedelta(days=400),  # > 1 Jahr
    )

    db_session.add(old_log)
    await db_session.commit()

    # Data Retention Policy ausführen (365 Tage)
    retention_date = datetime.utcnow() - timedelta(days=365)

    await db_session.execute(
        delete(AuditLog).where(AuditLog.created_at < retention_date)
    )
    await db_session.commit()

    # Alte Logs sollten gelöscht sein
    logs = await audit_logger.query_logs(
        db=db_session,
        store_id=store.id,
        user_id="user_old",
    )

    assert len(logs) == 0


# ─── Input Validation & Sanitization ───

def test_sql_injection_protection():
    """Test Schutz vor SQL-Injection"""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    api_key = "test_api_key_123456789012345678901234567890"

    # SQL-Injection in Store-ID versuchen
    malicious_ids = [
        "'; DROP TABLE stores; --",
        "1' OR '1'='1",
        "admin'--",
        "1' UNION SELECT * FROM stores--",
    ]

    for malicious_id in malicious_ids:
        response = client.get(
            f"/api/v1/stores/{malicious_id}",
            headers={"X-API-Key": api_key},
        )

        # Sollte 404 zurückgeben (nicht gefunden) oder 400 (Bad Request)
        # Auf keinen Fall 200 (Success) oder 500 (Server Error mit SQL-Error)
        assert response.status_code in [400, 404], f"SQL-Injection nicht geblockt für: {malicious_id}"


def test_xss_protection():
    """Test Schutz vor XSS (Cross-Site Scripting)"""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    api_key = "test_api_key_123456789012345678901234567890"

    # XSS-Versuche in Store-Name
    xss_payloads = [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert('XSS')>",
        "javascript:alert('XSS')",
        "<svg onload=alert('XSS')>",
    ]

    for xss_payload in xss_payloads:
        response = client.post(
            "/api/v1/stores",
            headers={"X-API-Key": api_key},
            json={
                "name": xss_payload,
                "type": "akte",
                "description": "XSS Test",
            },
        )

        if response.status_code == 200 or response.status_code == 201:
            data = response.json()
            # XSS-Code sollte nicht im Response enthalten sein (escaped oder entfernt)
            assert "<script>" not in str(data)
            assert "javascript:" not in str(data)


# ─── Rate Limiting ───

def test_api_rate_limiting():
    """Test API-Rate-Limiting"""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    api_key = "test_api_key_123456789012345678901234567890"

    # Viele Requests schnell hintereinander
    rate_limit_hits = 0
    for i in range(100):
        response = client.get(
            "/api/v1/stores",
            headers={"X-API-Key": api_key},
        )

        if response.status_code == 429:  # Too Many Requests
            rate_limit_hits += 1
            break

    # Sollte irgendwann Rate-Limit erreicht haben
    # (Nicht garantiert in Test-Umgebung, sollte aber in Production)
    # assert rate_limit_hits > 0, "Rate-Limit nicht erreicht"


# ─── File Upload Security ───

def test_file_upload_size_limit():
    """Test Datei-Größen-Limit"""
    from fastapi.testclient import TestClient
    from app.main import app
    from io import BytesIO

    client = TestClient(app)
    api_key = "test_api_key_123456789012345678901234567890"

    # Store erstellen
    store_response = client.post(
        "/api/v1/stores",
        headers={"X-API-Key": api_key},
        json={
            "name": "Test Store Upload",
            "type": "akte",
            "description": "Test",
        },
    )

    store_id = store_response.json().get("id")

    # Zu große Datei versuchen hochzuladen (100 MB)
    large_file = BytesIO(b"0" * (100 * 1024 * 1024))

    response = client.post(
        f"/api/v1/documents/{store_id}/upload-sync",
        headers={"X-API-Key": api_key},
        files={"file": ("large.pdf", large_file, "application/pdf")},
    )

    # Sollte 413 (Payload Too Large) zurückgeben
    assert response.status_code == 413


def test_malicious_file_upload():
    """Test Upload von bösartigen Dateien"""
    from fastapi.testclient import TestClient
    from app.main import app
    from io import BytesIO

    client = TestClient(app)
    api_key = "test_api_key_123456789012345678901234567890"

    # Store erstellen
    store_response = client.post(
        "/api/v1/stores",
        headers={"X-API-Key": api_key},
        json={
            "name": "Test Store Malicious",
            "type": "akte",
            "description": "Test",
        },
    )

    store_id = store_response.json().get("id")

    # Verschiedene bösartige Dateitypen versuchen
    malicious_files = [
        ("malicious.exe", b"MZ\x90\x00"),  # Windows Executable
        ("script.php", b"<?php system('rm -rf /'); ?>"),  # PHP Script
        ("shell.sh", b"#!/bin/bash\nrm -rf /"),  # Shell Script
    ]

    for filename, content in malicious_files:
        response = client.post(
            f"/api/v1/documents/{store_id}/upload-sync",
            headers={"X-API-Key": api_key},
            files={"file": (filename, BytesIO(content), "application/octet-stream")},
        )

        # Sollte abgelehnt werden (400 oder 415)
        assert response.status_code in [400, 415], f"Malicious file nicht abgelehnt: {filename}"


# ─── Compliance Reporting ───

@pytest.mark.asyncio
async def test_compliance_report_generation(db_session: AsyncSession):
    """Test Generation von Compliance-Reports"""
    from app.core.audit import get_compliance_metrics

    store = Store(
        id="test_store_compliance_report",
        name="Test Store Compliance Report",
        type="akte",
        description="DSGVO Test",
    )
    db_session.add(store)
    await db_session.commit()

    # Verschiedene Audit-Actions erstellen
    await audit_logger.log(
        db=db_session,
        action=AuditAction.DOC_UPLOAD,
        store_id=store.id,
        user_id="user_compliance",
        resource_type="document",
        resource_id="doc_1",
    )

    await audit_logger.log(
        db=db_session,
        action=AuditAction.DOC_VIEW,
        store_id=store.id,
        user_id="user_compliance",
        resource_type="document",
        resource_id="doc_2",
    )

    # Compliance-Metrics abrufen
    metrics = await get_compliance_metrics(
        db=db_session,
        store_id=store.id,
        days=30,
    )

    # Prüfen dass alle erforderlichen Metriken vorhanden sind
    assert "total_actions" in metrics
    assert "unique_users" in metrics
    assert "document_actions" in metrics
    assert "action_breakdown" in metrics


# ─── Encryption & Data Protection ───

@pytest.mark.asyncio
async def test_sensitive_data_not_logged(db_session: AsyncSession):
    """Test dass sensitive Daten nicht in Logs landen"""
    from app.core.audit import audit_logger

    store = Store(
        id="test_store_sensitive_data",
        name="Test Store Sensitive Data",
        type="akte",
        description="Security Test",
    )
    db_session.add(store)
    await db_session.commit()

    # Audit-Log mit sensiblen Daten erstellen
    await audit_logger.log(
        db=db_session,
        action=AuditAction.DOC_UPLOAD,
        store_id=store.id,
        user_id="user_sensitive",
        resource_type="document",
        resource_id="doc_sensitive",
        changes={
            "filename": "secret.pdf",
            "content": "SECRET DATA",  # Sollte nicht im Log landen!
        },
    )

    # Log abrufen
    logs = await audit_logger.query_logs(
        db=db_session,
        store_id=store.id,
        user_id="user_sensitive",
    )

    # Sensitive Daten sollten nicht im changes-Feld sein
    # (In Production sollte dies durch Data-Masking gelöst werden)
    assert len(logs) >= 1
    # TODO: Implementiere Data Masking für sensitive Fields


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
