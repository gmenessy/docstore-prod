"""
Tests für Audit-Log Datenbank-Migration.
Testet die neue AuditLog-Tabelle und die konvertierten Funktionen.
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditLogger, AuditAction
from app.models.comments import AuditLog
from app.models.database import Store


# ─── AuditLog Database Tests ───

@pytest.mark.asyncio
async def test_audit_log_create(db_session: AsyncSession):
    """Test das Erstellen eines Audit-Logs in der Datenbank"""
    from app.core.audit import audit_logger
    from fastapi import Request

    # Test-Store erstellen
    store = Store(
        id="test_store_audit",
        name="Test Store Audit",
        type="akte",
        description="Test Store für Audit-Logs",
    )
    db_session.add(store)
    await db_session.commit()

    # Mock Request erstellen
    class MockRequest:
        def __init__(self):
            self.headers = {
                "X-Forwarded-For": "192.168.1.100",
                "User-Agent": "Test-Browser/1.0",
            }
            self.client = type('obj', (object,), {'host': '10.0.0.1'})()

    request = MockRequest()

    # Audit-Log erstellen
    log_id = await audit_logger.log(
        db=db_session,
        action=AuditAction.DOC_UPLOAD,
        store_id="test_store_audit",
        user_id="user_audit_1",
        resource_type="document",
        resource_id="doc_audit_1",
        changes={"filename": "test.pdf", "size": 1024},
        request=request,
        metadata={"importance": "high"},
    )

    assert log_id is not None, "Log-ID sollte nicht None sein"

    # Prüfen dass Log in DB erstellt wurde
    from sqlalchemy import select

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.id == log_id)
    )
    audit_log = result.scalar_one_or_none()

    assert audit_log is not None, "Audit-Log sollte in DB existieren"
    assert audit_log.action == AuditAction.DOC_UPLOAD
    assert audit_log.user_id == "user_audit_1"
    assert audit_log.resource_type == "document"
    assert audit_log.resource_id == "doc_audit_1"
    assert audit_log.changes == {"filename": "test.pdf", "size": 1024}
    assert audit_log.ip_address == "192.168.1.100"
    assert audit_log.user_agent == "Test-Browser/1.0"
    assert audit_log.metadata == {"importance": "high"}


@pytest.mark.asyncio
async def test_audit_log_query_all(db_session: AsyncSession):
    """Test das Abfragen aller Audit-Logs für einen Store"""
    from app.core.audit import audit_logger

    # Test-Store erstellen
    store = Store(
        id="test_store_query",
        name="Test Store Query",
        type="akte",
        description="Test Store für Query-Tests",
    )
    db_session.add(store)
    await db_session.commit()

    # Mehrere Audit-Logs erstellen
    for i in range(5):
        await audit_logger.log(
            db=db_session,
            action=AuditAction.DOC_VIEW,
            store_id="test_store_query",
            user_id=f"user_query_{i}",
            resource_type="document",
            resource_id=f"doc_query_{i}",
            changes={"view_count": i + 1},
        )

    # Alle Logs abfragen
    logs = await audit_logger.query_logs(
        db=db_session,
        store_id="test_store_query",
        limit=10,
    )

    assert len(logs) == 5, f"Es sollten 5 Logs sein, sind aber {len(logs)}"


@pytest.mark.asyncio
async def test_audit_log_query_by_action(db_session: AsyncSession):
    """Test das Filtern von Audit-Logs nach Action"""
    from app.core.audit import audit_logger

    # Test-Store erstellen
    store = Store(
        id="test_store_filter",
        name="Test Store Filter",
        type="akte",
        description="Test Store für Filter-Tests",
    )
    db_session.add(store)
    await db_session.commit()

    # Verschiedene Actions loggen
    await audit_logger.log(
        db=db_session,
        action=AuditAction.DOC_UPLOAD,
        store_id="test_store_filter",
        user_id="user_1",
        resource_type="document",
        resource_id="doc_1",
    )

    await audit_logger.log(
        db=db_session,
        action=AuditAction.DOC_VIEW,
        store_id="test_store_filter",
        user_id="user_1",
        resource_type="document",
        resource_id="doc_1",
    )

    await audit_logger.log(
        db=db_session,
        action=AuditAction.DOC_VIEW,
        store_id="test_store_filter",
        user_id="user_2",
        resource_type="document",
        resource_id="doc_2",
    )

    # Nur DOC_VIEW Logs abfragen
    logs = await audit_logger.query_logs(
        db=db_session,
        store_id="test_store_filter",
        action=AuditAction.DOC_VIEW,
        limit=10,
    )

    assert len(logs) == 2, f"Es sollten 2 DOC_VIEW Logs sein, sind aber {len(logs)}"
    for log in logs:
        assert log["action"] == AuditAction.DOC_VIEW


@pytest.mark.asyncio
async def test_audit_log_query_by_user(db_session: AsyncSession):
    """Test das Filtern von Audit-Logs nach User"""
    from app.core.audit import audit_logger

    # Test-Store erstellen
    store = Store(
        id="test_store_user",
        name="Test Store User",
        type="akte",
        description="Test Store für User-Filter",
    )
    db_session.add(store)
    await db_session.commit()

    # Verschiedene Users loggen
    await audit_logger.log(
        db=db_session,
        action=AuditAction.DOC_VIEW,
        store_id="test_store_user",
        user_id="user_a",
        resource_type="document",
        resource_id="doc_1",
    )

    await audit_logger.log(
        db=db_session,
        action=AuditAction.DOC_VIEW,
        store_id="test_store_user",
        user_id="user_b",
        resource_type="document",
        resource_id="doc_2",
    )

    await audit_logger.log(
        db=db_session,
        action=AuditAction.DOC_UPLOAD,
        store_id="test_store_user",
        user_id="user_a",
        resource_type="document",
        resource_id="doc_3",
    )

    # Nur user_a Logs abfragen
    logs = await audit_logger.query_logs(
        db=db_session,
        store_id="test_store_user",
        user_id="user_a",
        limit=10,
    )

    assert len(logs) == 2, f"Es sollten 2 user_a Logs sein, sind aber {len(logs)}"
    for log in logs:
        assert log["user_id"] == "user_a"


@pytest.mark.asyncio
async def test_audit_log_query_by_date_range(db_session: AsyncSession):
    """Test das Filtern von Audit-Logs nach Zeitraum"""
    from app.core.audit import audit_logger

    # Test-Store erstellen
    store = Store(
        id="test_store_date",
        name="Test Store Date",
        type="akte",
        description="Test Store für Date-Filter",
    )
    db_session.add(store)
    await db_session.commit()

    now = datetime.utcnow()

    # Log mit altem Datum (manuell in DB einfügen)
    old_log = AuditLog(
        id="old_log_id",
        store_id="test_store_date",
        user_id="user_old",
        action=AuditAction.DOC_VIEW,
        created_at=now - timedelta(days=10),
    )
    db_session.add(old_log)

    # Log mit neuem Datum
    await audit_logger.log(
        db=db_session,
        action=AuditAction.DOC_VIEW,
        store_id="test_store_date",
        user_id="user_new",
        resource_type="document",
        resource_id="doc_new",
    )

    await db_session.commit()

    # Logs der letzten 5 Tage abfragen
    start_date = (now - timedelta(days=5)).isoformat()
    logs = await audit_logger.query_logs(
        db=db_session,
        store_id="test_store_date",
        start_date=start_date,
        limit=10,
    )

    assert len(logs) == 1, f"Es sollte 1 neuer Log sein, sind aber {len(logs)}"
    assert logs[0]["user_id"] == "user_new"


@pytest.mark.asyncio
async def test_audit_log_query_limit(db_session: AsyncSession):
    """Test das Limit bei Audit-Log Queries"""
    from app.core.audit import audit_logger

    # Test-Store erstellen
    store = Store(
        id="test_store_limit",
        name="Test Store Limit",
        type="akte",
        description="Test Store für Limit-Tests",
    )
    db_session.add(store)
    await db_session.commit()

    # 20 Logs erstellen
    for i in range(20):
        await audit_logger.log(
            db=db_session,
            action=AuditAction.DOC_VIEW,
            store_id="test_store_limit",
            user_id=f"user_{i}",
            resource_type="document",
            resource_id=f"doc_{i}",
        )

    # Nur 10 Logs abfragen
    logs = await audit_logger.query_logs(
        db=db_session,
        store_id="test_store_limit",
        limit=10,
    )

    assert len(logs) == 10, f"Es sollten 10 Logs sein, sind aber {len(logs)}"


@pytest.mark.asyncio
async def test_audit_log_combined_filters(db_session: AsyncSession):
    """Test kombinierte Filter (Action + User + Date)"""
    from app.core.audit import audit_logger

    # Test-Store erstellen
    store = Store(
        id="test_store_combined",
        name="Test Store Combined",
        type="akte",
        description="Test Store für Combined-Filter",
    )
    db_session.add(store)
    await db_session.commit()

    now = datetime.utcnow()

    # Verschiedene Kombinationen loggen
    await audit_logger.log(
        db=db_session,
        action=AuditAction.DOC_UPLOAD,
        store_id="test_store_combined",
        user_id="user_x",
        resource_type="document",
        resource_id="doc_1",
    )

    await audit_logger.log(
        db=db_session,
        action=AuditAction.DOC_VIEW,
        store_id="test_store_combined",
        user_id="user_x",
        resource_type="document",
        resource_id="doc_2",
    )

    await audit_logger.log(
        db=db_session,
        action=AuditAction.DOC_UPLOAD,
        store_id="test_store_combined",
        user_id="user_y",
        resource_type="document",
        resource_id="doc_3",
    )

    # Kombinierter Filter: DOC_UPLOAD + user_x
    logs = await audit_logger.query_logs(
        db=db_session,
        store_id="test_store_combined",
        action=AuditAction.DOC_UPLOAD,
        user_id="user_x",
        limit=10,
    )

    assert len(logs) == 1, f"Es sollte 1 Log sein, sind aber {len(logs)}"
    assert logs[0]["action"] == AuditAction.DOC_UPLOAD
    assert logs[0]["user_id"] == "user_x"


@pytest.mark.asyncio
async def test_audit_log_ordering(db_session: AsyncSession):
    """Test dass Audit-Logs korrekt sortiert werden (neueste zuerst)"""
    from app.core.audit import audit_logger

    # Test-Store erstellen
    store = Store(
        id="test_store_order",
        name="Test Store Order",
        type="akte",
        description="Test Store für Ordering-Tests",
    )
    db_session.add(store)
    await db_session.commit()

    # Logs in chronologischer Reihenfolge erstellen
    log_ids = []
    for i in range(5):
        log_id = await audit_logger.log(
            db=db_session,
            action=AuditAction.DOC_VIEW,
            store_id="test_store_order",
            user_id=f"user_{i}",
            resource_type="document",
            resource_id=f"doc_{i}",
        )
        log_ids.append(log_id)

    # Logs abfragen
    logs = await audit_logger.query_logs(
        db=db_session,
        store_id="test_store_order",
        limit=10,
    )

    # Prüfen dass die Reihenfolge umgekehrt ist (neueste zuerst)
    assert len(logs) == 5
    assert logs[0]["id"] == log_ids[4], "Der erste Log sollte der letzte erstellte sein"
    assert logs[4]["id"] == log_ids[0], "Der letzte Log sollte der erste erstellte sein"


@pytest.mark.asyncio
async def test_compliance_metrics_db(db_session: AsyncSession):
    """Test Compliance-Metrics Berechnung mit DB"""
    from app.core.audit import audit_logger, get_compliance_metrics

    # Test-Store erstellen
    store = Store(
        id="test_store_metrics",
        name="Test Store Metrics",
        type="akte",
        description="Test Store für Metrics",
    )
    db_session.add(store)
    await db_session.commit()

    # Verschiedene Actions loggen
    await audit_logger.log(
        db=db_session,
        action=AuditAction.DOC_UPLOAD,
        store_id="test_store_metrics",
        user_id="user_1",
        resource_type="document",
        resource_id="doc_1",
    )

    await audit_logger.log(
        db=db_session,
        action=AuditAction.DOC_VIEW,
        store_id="test_store_metrics",
        user_id="user_2",
        resource_type="document",
        resource_id="doc_1",
    )

    await audit_logger.log(
        db=db_session,
        action=AuditAction.DOC_VIEW,
        store_id="test_store_metrics",
        user_id="user_1",
        resource_type="document",
        resource_id="doc_2",
    )

    # Metrics berechnen
    metrics = await get_compliance_metrics(
        db=db_session,
        store_id="test_store_metrics",
        days=30,
    )

    assert metrics["total_actions"] == 3
    assert metrics["unique_users"] == 2
    assert metrics["document_actions"] == 3
    assert "action_breakdown" in metrics
    assert "most_active_users" in metrics


@pytest.mark.asyncio
async def test_audit_log_to_dict(db_session: AsyncSession):
    """Test die to_dict Methode von AuditLog"""
    from app.models.comments import AuditLog

    # Test-Store erstellen
    store = Store(
        id="test_store_dict",
        name="Test Store Dict",
        type="akte",
        description="Test Store für to_dict",
    )
    db_session.add(store)
    await db_session.commit()

    # Audit-Log erstellen
    audit_log = AuditLog(
        id="test_log_id",
        store_id="test_store_dict",
        user_id="user_dict",
        action=AuditAction.DOC_UPLOAD,
        resource_type="document",
        resource_id="doc_dict",
        changes={"test": "value"},
        ip_address="192.168.1.1",
        user_agent="Test",
        metadata={"meta": "data"},
    )

    db_session.add(audit_log)
    await db_session.commit()

    # to_dict aufrufen
    log_dict = audit_log.to_dict()

    assert log_dict["id"] == "test_log_id"
    assert log_dict["store_id"] == "test_store_dict"
    assert log_dict["user_id"] == "user_dict"
    assert log_dict["action"] == AuditAction.DOC_UPLOAD
    assert log_dict["resource_type"] == "document"
    assert log_dict["resource_id"] == "doc_dict"
    assert log_dict["changes"] == {"test": "value"}
    assert log_dict["ip_address"] == "192.168.1.1"
    assert log_dict["user_agent"] == "Test"
    assert log_dict["metadata"] == {"meta": "data"}
    assert "created_at" in log_dict


@pytest.mark.asyncio
async def test_audit_log_fallback_on_db_error(db_session: AsyncSession):
    """Test JSONL-Fallback bei DB-Fehlern"""
    from app.core.audit import audit_logger
    from unittest.mock import patch, AsyncMock

    # Test-Store erstellen
    store = Store(
        id="test_store_fallback",
        name="Test Store Fallback",
        type="akte",
        description="Test Store für Fallback",
    )
    db_session.add(store)
    await db_session.commit()

    # DB commit mocken um Fehler zu simulieren
    with patch.object(db_session, 'commit', new=AsyncMock(side_effect=Exception("DB Error"))):
        # Log erstellen sollte Fallback verwenden
        log_id = await audit_logger.log(
            db=db_session,
            action=AuditAction.DOC_VIEW,
            store_id="test_store_fallback",
            user_id="user_fallback",
            resource_type="document",
            resource_id="doc_fallback",
        )

        # Log-ID sollte trotzdem zurückgegeben werden
        assert log_id is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
