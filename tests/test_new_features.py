"""
Tests für neue Features:
- Wiki-Freshness Berechnung
- Notification Rate-Limiting
- Notification Logging
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.wiki_auto_curator import WikiAutoCurator, QualityScore
from app.services.notification_service import NotificationService
from app.models.database import WikiPage, Document, Store
from app.models.comments import NotificationLog, NotificationPreference


# ─── Wiki-Freshness Tests ───

@pytest.mark.asyncio
async def test_freshness_new_documents(db_session: AsyncSession):
    """Test Freshness-Score mit neuen Dokumenten (< 7 Tage)"""
    curator = WikiAutoCurator()

    # Test-WikiPage erstellen
    wiki_page = WikiPage(
        id="test_wiki_1",
        store_id="test_store",
        title="Test Wiki",
        slug="test-wiki",
        content_md="# Test\n\nDies ist ein Test.",
        source_documents=[
            {"document_id": "doc1", "title": "Doc 1"},
            {"document_id": "doc2", "title": "Doc 2"},
        ],
        updated_at=datetime.utcnow(),
    )

    # Neue Dokumente erstellen (1-3 Tage alt)
    doc1 = Document(
        id="doc1",
        store_id="test_store",
        title="Doc 1",
        filename="doc1.pdf",
        status="indexed",
        created_at=datetime.utcnow() - timedelta(days=2),
    )
    doc2 = Document(
        id="doc2",
        store_id="test_store",
        title="Doc 2",
        filename="doc2.pdf",
        status="indexed",
        created_at=datetime.utcnow() - timedelta(days=5),
    )

    db_session.add_all([wiki_page, doc1, doc2])
    await db_session.commit()

    # Freshness berechnen
    freshness = await curator._calculate_freshness(db_session, wiki_page)

    # Sollte sehr hoch sein (> 80), da Quellen neu sind
    assert freshness > 80.0, f"Freshness sollte > 80 sein, ist aber {freshness}"


@pytest.mark.asyncio
async def test_freshness_old_documents(db_session: AsyncSession):
    """Test Freshness-Score mit alten Dokumenten (> 90 Tage)"""
    curator = WikiAutoCurator()

    # Test-WikiPage erstellen
    wiki_page = WikiPage(
        id="test_wiki_2",
        store_id="test_store",
        title="Test Wiki Alt",
        slug="test-wiki-alt",
        content_md="# Test\n\nDies ist ein Test.",
        source_documents=[
            {"document_id": "doc3", "title": "Doc 3"},
        ],
        updated_at=datetime.utcnow() - timedelta(days=100),  # Wiki selbst alt
    )

    # Altes Dokument erstellen (100 Tage alt)
    doc3 = Document(
        id="doc3",
        store_id="test_store",
        title="Doc 3",
        filename="doc3.pdf",
        status="indexed",
        created_at=datetime.utcnow() - timedelta(days=100),
    )

    db_session.add_all([wiki_page, doc3])
    await db_session.commit()

    # Freshness berechnen
    freshness = await curator._calculate_freshness(db_session, wiki_page)

    # Sollte sehr niedrig sein (< 20), da Quellen alt sind
    assert freshness < 30.0, f"Freshness sollte < 30 sein, ist aber {freshness}"


@pytest.mark.asyncio
async def test_freshness_mixed_age_documents(db_session: AsyncSession):
    """Test Freshness-Score mit Dokumenten verschiedenen Alters"""
    curator = WikiAutoCurator()

    # Test-WikiPage
    wiki_page = WikiPage(
        id="test_wiki_3",
        store_id="test_store",
        title="Test Wiki Mixed",
        slug="test-wiki-mixed",
        content_md="# Test\n\nMixed age docs.",
        source_documents=[
            {"document_id": "doc4", "title": "Doc 4"},
            {"document_id": "doc5", "title": "Doc 5"},
            {"document_id": "doc6", "title": "Doc 6"},
        ],
        updated_at=datetime.utcnow(),
    )

    # Dokumente verschiedenen Alters
    doc4 = Document(  # Neu: 5 Tage
        id="doc4",
        store_id="test_store",
        title="Doc 4",
        filename="doc4.pdf",
        status="indexed",
        created_at=datetime.utcnow() - timedelta(days=5),
    )
    doc5 = Document(  # Mittel: 25 Tage
        id="doc5",
        store_id="test_store",
        title="Doc 5",
        filename="doc5.pdf",
        status="indexed",
        created_at=datetime.utcnow() - timedelta(days=25),
    )
    doc6 = Document(  # Alt: 60 Tage
        id="doc6",
        store_id="test_store",
        title="Doc 6",
        filename="doc6.pdf",
        status="indexed",
        created_at=datetime.utcnow() - timedelta(days=60),
    )

    db_session.add_all([wiki_page, doc4, doc5, doc6])
    await db_session.commit()

    # Freshness berechnen
    freshness = await curator._calculate_freshness(db_session, wiki_page)

    # Sollte mittel sein (30-70)
    assert 30.0 <= freshness <= 70.0, f"Freshness sollte 30-70 sein, ist aber {freshness}"


@pytest.mark.asyncio
async def test_freshness_no_documents(db_session: AsyncSession):
    """Test Freshness-Score ohne Quellen"""
    curator = WikiAutoCurator()

    # WikiPage ohne Quellen
    wiki_page = WikiPage(
        id="test_wiki_4",
        store_id="test_store",
        title="Test Wiki No Docs",
        slug="test-wiki-no-docs",
        content_md="# Test\n\nKeine Quellen.",
        source_documents=[],  # Keine Quellen
        updated_at=datetime.utcnow(),
    )

    db_session.add(wiki_page)
    await db_session.commit()

    # Freshness berechnen
    freshness = await curator._calculate_freshness(db_session, wiki_page)

    # Sollte niedrig sein (30, da keine Quellen)
    assert freshness == 30.0, f"Freshness sollte 30 sein (keine Quellen), ist aber {freshness}"


@pytest.mark.asyncio
async def test_freshness_many_documents_bonus(db_session: AsyncSession):
    """Test Freshness-Score mit vielen Dokumenten (Source Count Bonus)"""
    curator = WikiAutoCurator()

    # WikiPage mit vielen Quellen
    source_docs = [
        {"document_id": f"doc_bulk_{i}", "title": f"Doc {i}"}
        for i in range(10)  # 10 Dokumente
    ]

    wiki_page = WikiPage(
        id="test_wiki_5",
        store_id="test_store",
        title="Test Wiki Many Docs",
        slug="test-wiki-many-docs",
        content_md="# Test\n\nViele Quellen.",
        source_documents=source_docs,
        updated_at=datetime.utcnow(),
    )

    # Dokumente erstellen (alle neu, 10 Tage alt)
    docs = [
        Document(
            id=f"doc_bulk_{i}",
            store_id="test_store",
            title=f"Doc {i}",
            filename=f"doc{i}.pdf",
            status="indexed",
            created_at=datetime.utcnow() - timedelta(days=10),
        )
        for i in range(10)
    ]

    db_session.add_all([wiki_page] + docs)
    await db_session.commit()

    # Freshness berechnen
    freshness = await curator._calculate_freshness(db_session, wiki_page)

    # Sollte höher sein als ohne Source Count Bonus
    # Bei 10 Docs: Bonus bis +25 Punkte
    assert freshness > 60.0, f"Freshness sollte > 60 sein (viele Quellen Bonus), ist aber {freshness}"


# ─── Notification Rate-Limiting Tests ───

@pytest.mark.asyncio
async def test_rate_limit_under_limit(db_session: AsyncSession):
    """Test Rate-Limiting unter dem Limit"""
    service = NotificationService()
    service.configure(
        smtp_host="localhost",
        smtp_port=1025,
        smtp_user="test",
        smtp_password="test",
        from_email="test@example.com",
    )

    # Präferenzen erstellen
    prefs = NotificationPreference(
        id="pref_1",
        store_id="test_store",
        user_id="user_1",
        max_emails_per_day=50,
        max_notifications_per_hour=20,
    )

    db_session.add(prefs)
    await db_session.commit()

    # Rate-Limit prüfen (sollte True zurückgeben)
    can_send = await service._check_rate_limits(db_session, prefs, "comment.mention")

    assert can_send is True, "Sollte Notifications senden dürfen (unter Limit)"


@pytest.mark.asyncio
async def test_rate_limit_hourly_limit(db_session: AsyncSession):
    """Test stündliches Rate-Limit"""
    service = NotificationService()
    service.configure(
        smtp_host="localhost",
        smtp_port=1025,
        smtp_user="test",
        smtp_password="test",
        from_email="test@example.com",
    )

    # Präferenzen mit niedrigem Limit erstellen
    prefs = NotificationPreference(
        id="pref_2",
        store_id="test_store",
        user_id="user_2",
        max_notifications_per_hour=5,  # Niedriges Limit
        max_emails_per_day=100,
    )

    db_session.add(prefs)
    await db_session.commit()

    # 6 Notifications in letzter Stunde erstellen (über Limit)
    now = datetime.utcnow()
    for i in range(6):
        log = NotificationLog(
            id=f"log_{i}",
            store_id="test_store",
            user_id="user_2",
            notification_type="comment.mention",
            channel="email",
            status="sent",
            created_at=now - timedelta(minutes=i),  # 0-5 Minuten her
        )
        db_session.add(log)

    await db_session.commit()

    # Rate-Limit prüfen (sollte False zurückgeben)
    can_send = await service._check_rate_limits(db_session, prefs, "comment.mention")

    assert can_send is False, "Sollte keine Notifications mehr senden dürfen (stündliches Limit erreicht)"


@pytest.mark.asyncio
async def test_rate_limit_daily_limit(db_session: AsyncSession):
    """Test tägliches E-Mail-Limit"""
    service = NotificationService()
    service.configure(
        smtp_host="localhost",
        smtp_port=1025,
        smtp_user="test",
        smtp_password="test",
        from_email="test@example.com",
    )

    # Präferenzen mit niedrigem Daily-Limit erstellen
    prefs = NotificationPreference(
        id="pref_3",
        store_id="test_store",
        user_id="user_3",
        max_notifications_per_hour=100,
        max_emails_per_day=10,  # Niedriges Daily-Limit
    )

    db_session.add(prefs)
    await db_session.commit()

    # 11 E-Mails in letzter Tag erstellen (über Limit)
    now = datetime.utcnow()
    for i in range(11):
        log = NotificationLog(
            id=f"log_daily_{i}",
            store_id="test_store",
            user_id="user_3",
            notification_type="comment.mention",
            channel="email",
            status="sent",
            created_at=now - timedelta(hours=i),  # 0-10 Stunden her
        )
        db_session.add(log)

    await db_session.commit()

    # Rate-Limit prüfen (sollte False zurückgeben)
    can_send = await service._check_rate_limits(db_session, prefs, "comment.mention")

    assert can_send is False, "Sollte keine E-Mails mehr senden dürfen (tägliches Limit erreicht)"


@pytest.mark.asyncio
async def test_rate_limit_expired_logs(db_session: AsyncSession):
    """Test dass alte Logs nicht gegen Limit zählen"""
    service = NotificationService()
    service.configure(
        smtp_host="localhost",
        smtp_port=1025,
        smtp_user="test",
        smtp_password="test",
        from_email="test@example.com",
    )

    # Präferenzen mit niedrigem Limit erstellen
    prefs = NotificationPreference(
        id="pref_4",
        store_id="test_store",
        user_id="user_4",
        max_notifications_per_hour=5,
        max_emails_per_day=10,
    )

    db_session.add(prefs)
    await db_session.commit()

    # Alte Notifications erstellen (> 1 Stunde / > 1 Tag)
    old_log_hour = NotificationLog(
        id="log_old_hour",
        store_id="test_store",
        user_id="user_4",
        notification_type="comment.mention",
        channel="email",
        status="sent",
        created_at=datetime.utcnow() - timedelta(hours=2),  # Zu alt für stündliches Limit
    )
    old_log_day = NotificationLog(
        id="log_old_day",
        store_id="test_store",
        user_id="user_4",
        notification_type="comment.mention",
        channel="email",
        status="sent",
        created_at=datetime.utcnow() - timedelta(days=2),  # Zu alt für tägliches Limit
    )

    db_session.add_all([old_log_hour, old_log_day])
    await db_session.commit()

    # Rate-Limit prüfen (sollte True zurückgeben, da Logs zu alt)
    can_send = await service._check_rate_limits(db_session, prefs, "comment.mention")

    assert can_send is True, "Sollte Notifications senden dürfen (alte Logs zählen nicht)"


# ─── Notification Logging Tests ───

@pytest.mark.asyncio
async def test_notification_logging_success(db_session: AsyncSession):
    """Test Logging einer erfolgreichen Notification"""
    service = NotificationService()
    service.configure(
        smtp_host="localhost",
        smtp_port=1025,
        smtp_user="test",
        smtp_password="test",
        from_email="test@example.com",
    )

    # Notification loggen
    await service._log_notification(
        db=db_session,
        store_id="test_store",
        user_id="user_5",
        notification_type="comment.mention",
        data={
            "subject": "Test Subject",
            "store_name": "Test Store",
            "resource_type": "document",
            "resource_id": "doc_1",
        },
        status="sent",
        channel="email",
    )

    # Prüfen dass Log erstellt wurde
    from sqlalchemy import select

    result = await db_session.execute(
        select(NotificationLog).where(NotificationLog.user_id == "user_5")
    )
    logs = result.scalars().all()

    assert len(logs) == 1, "Es sollte 1 Log-Eintrag geben"
    assert logs[0].status == "sent", "Status sollte 'sent' sein"
    assert logs[0].notification_type == "comment.mention", "Typ sollte 'comment.mention' sein"
    assert logs[0].channel == "email", "Channel sollte 'email' sein"


@pytest.mark.asyncio
async def test_notification_logging_failure(db_session: AsyncSession):
    """Test Logging einer fehlgeschlagenen Notification"""
    service = NotificationService()
    service.configure(
        smtp_host="localhost",
        smtp_port=1025,
        smtp_user="test",
        smtp_password="test",
        from_email="test@example.com",
    )

    # Notification mit Fehler loggen
    await service._log_notification(
        db=db_session,
        store_id="test_store",
        user_id="user_6",
        notification_type="comment.reply",
        data={
            "subject": "Test Subject",
        },
        status="failed",
        error_message="SMTP connection error",
        channel="email",
    )

    # Prüfen dass Log mit Fehler erstellt wurde
    from sqlalchemy import select

    result = await db_session.execute(
        select(NotificationLog).where(NotificationLog.user_id == "user_6")
    )
    logs = result.scalars().all()

    assert len(logs) == 1, "Es sollte 1 Log-Eintrag geben"
    assert logs[0].status == "failed", "Status sollte 'failed' sein"
    assert logs[0].error_message == "SMTP connection error", "Fehlermeldung sollte gesetzt sein"


@pytest.mark.asyncio
async def test_notification_logging_skipped(db_session: AsyncSession):
    """Test Logging einer übersprungenen Notification (z.B. Quiet Hours)"""
    service = NotificationService()
    service.configure(
        smtp_host="localhost",
        smtp_port=1025,
        smtp_user="test",
        smtp_password="test",
        from_email="test@example.com",
    )

    # Übersprungene Notification loggen
    await service._log_notification(
        db=db_session,
        store_id="test_store",
        user_id="user_7",
        notification_type="wiki.changed",
        data={
            "subject": "Wiki Update",
        },
        status="skipped",
        channel="email",
    )

    # Prüfen dass Log mit 'skipped' erstellt wurde
    from sqlalchemy import select

    result = await db_session.execute(
        select(NotificationLog).where(NotificationLog.user_id == "user_7")
    )
    logs = result.scalars().all()

    assert len(logs) == 1, "Es sollte 1 Log-Eintrag geben"
    assert logs[0].status == "skipped", "Status sollte 'skipped' sein"


# ─── Integration Tests ───

@pytest.mark.asyncio
async def test_full_notification_flow(db_session: AsyncSession, mock_smtp):
    """Test des kompletten Notification-Flows"""
    from unittest.mock import Mock, patch

    service = NotificationService()
    service.configure(
        smtp_host="localhost",
        smtp_port=1025,
        smtp_user="test",
        smtp_password="test",
        from_email="test@example.com",
    )

    # Präferenzen erstellen
    prefs = NotificationPreference(
        id="pref_int",
        store_id="test_store",
        user_id="user_int",
        email_enabled=True,
        email_comment_mentions=True,
        max_emails_per_day=50,
        max_notifications_per_hour=20,
    )

    db_session.add(prefs)
    await db_session.commit()

    # SMTP mocken
    with patch('smtplib.SMTP') as mock_smtp_class:
        mock_server = Mock()
        mock_smtp_class.return_value.__enter__ = Mock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = Mock(return_value=False)
        mock_server.send_message = Mock(return_value=True)

        # Notification senden
        result = await service.send_notification(
            db=db_session,
            store_id="test_store",
            user_id="user_int",
            notification_type="comment.mention",
            data={
                "user_email": "user@example.com",
                "store_name": "Test Store",
                "subject": "Neue Erwähnung",
                "resource_type": "document",
                "resource_id": "doc_1",
            },
            channel="email",
        )

        assert result is True, "Notification sollte erfolgreich gesendet werden"

        # Prüfen dass geloggt wurde
        from sqlalchemy import select

        log_result = await db_session.execute(
            select(NotificationLog).where(NotificationLog.user_id == "user_int")
        )
        logs = log_result.scalars().all()

        assert len(logs) == 1, "Es sollte 1 Log-Eintrag geben"
        assert logs[0].status == "sent", "Status sollte 'sent' sein"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
