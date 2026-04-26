"""
Test-Utilities für bessere Test-Daten-Generierung und Helper-Funktionen.
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Store, Document, WikiPage
from app.models.comments import Comment, NotificationLog, AuditLog


class TestDataGenerator:
    """Helper-Klasse für Generierung von Test-Daten"""

    @staticmethod
    async def create_store(
        db: AsyncSession,
        id: str = None,
        name: str = None,
        store_type: str = "akte",
        description: str = None,
        language: str = "de",
    ) -> Store:
        """Erstellt einen Test-Store"""
        if id is None:
            id = f"test_store_{datetime.utcnow().timestamp()}"

        if name is None:
            name = f"Test Store {id}"

        if description is None:
            description = f"Test store created at {datetime.utcnow()}"

        store = Store(
            id=id,
            name=name,
            type=store_type,
            description=description,
            language=language,
            primary_language=language,
        )

        db.add(store)
        await db.commit()
        await db.refresh(store)

        return store

    @staticmethod
    async def create_document(
        db: AsyncSession,
        store_id: str,
        id: str = None,
        title: str = None,
        filename: str = None,
        status: str = "indexed",
        file_size: int = 1024,
        content_md: str = None,
    ) -> Document:
        """Erstellt ein Test-Dokument"""
        if id is None:
            id = f"test_doc_{datetime.utcnow().timestamp()}"

        if title is None:
            title = f"Test Document {id}"

        if filename is None:
            filename = f"{id}.pdf"

        if content_md is None:
            content_md = f"# {title}\n\nTest content for {id}."

        document = Document(
            id=id,
            store_id=store_id,
            title=title,
            filename=filename,
            status=status,
            file_size=file_size,
            content_md=content_md,
            created_at=datetime.utcnow(),
        )

        db.add(document)
        await db.commit()
        await db.refresh(document)

        return document

    @staticmethod
    async def create_wiki_page(
        db: AsyncSession,
        store_id: str,
        id: str = None,
        title: str = None,
        slug: str = None,
        content_md: str = None,
        page_type: str = "concept",
        source_documents: List[dict] = None,
    ) -> WikiPage:
        """Erstellt eine Test-Wiki-Seite"""
        if id is None:
            id = f"test_wiki_{datetime.utcnow().timestamp()}"

        if title is None:
            title = f"Test Wiki {id}"

        if slug is None:
            slug = f"test-wiki-{id}"

        if content_md is None:
            content_md = f"# {title}\n\nTest wiki content for {id}."

        if source_documents is None:
            source_documents = []

        wiki_page = WikiPage(
            id=id,
            store_id=store_id,
            title=title,
            slug=slug,
            content_md=content_md,
            page_type=page_type,
            source_documents=source_documents,
            created_at=datetime.utcnow(),
        )

        db.add(wiki_page)
        await db.commit()
        await db.refresh(wiki_page)

        return wiki_page

    @staticmethod
    async def create_comment(
        db: AsyncSession,
        store_id: str,
        user_id: str = "test_user",
        content: str = None,
        document_id: str = None,
        wiki_page_id: str = None,
        task_id: str = None,
        parent_id: str = None,
    ) -> Comment:
        """Erstellt einen Test-Kommentar"""
        import uuid

        if content is None:
            content = f"Test comment created at {datetime.utcnow()}"

        comment = Comment(
            id=uuid.uuid4(),
            store_id=store_id,
            user_id=user_id,
            content=content,
            document_id=document_id,
            wiki_page_id=wiki_page_id,
            task_id=task_id,
            parent_id=parent_id,
            created_at=datetime.utcnow(),
        )

        db.add(comment)
        await db.commit()
        await db.refresh(comment)

        return comment

    @staticmethod
    async def create_bulk_documents(
        db: AsyncSession,
        store_id: str,
        count: int = 100,
        status: str = "indexed",
    ) -> List[Document]:
        """Erstellt mehrere Test-Dokumente auf einmal"""
        documents = []

        for i in range(count):
            document = Document(
                id=f"test_doc_bulk_{i}_{int(datetime.utcnow().timestamp())}",
                store_id=store_id,
                title=f"Bulk Document {i}",
                filename=f"bulk_{i}.pdf",
                status=status,
                file_size=1024 * (i + 1),
                content_md=f"# Bulk Document {i}\n\nContent for bulk document {i}.",
                created_at=datetime.utcnow(),
            )
            documents.append(document)

        db.add_all(documents)
        await db.commit()

        # Refresh aller Dokumente
        for doc in documents:
            await db.refresh(doc)

        return documents

    @staticmethod
    async def create_bulk_wiki_pages(
        db: AsyncSession,
        store_id: str,
        count: int = 50,
        page_type: str = "concept",
    ) -> List[WikiPage]:
        """Erstellt mehrere Wiki-Seiten auf einmal"""
        wiki_pages = []

        for i in range(count):
            wiki_page = WikiPage(
                id=f"test_wiki_bulk_{i}_{int(datetime.utcnow().timestamp())}",
                store_id=store_id,
                title=f"Bulk Wiki {i}",
                slug=f"bulk-wiki-{i}",
                content_md=f"# Bulk Wiki {i}\n\nContent for bulk wiki {i}.",
                page_type=page_type,
                source_documents=[],
                created_at=datetime.utcnow(),
            )
            wiki_pages.append(wiki_page)

        db.add_all(wiki_pages)
        await db.commit()

        # Refresh aller Wiki-Seiten
        for wiki in wiki_pages:
            await db.refresh(wiki)

        return wiki_pages

    @staticmethod
    async def create_wissensdb_with_content(
        db: AsyncSession,
        store_id: str = None,
        doc_count: int = 20,
        wiki_count: int = 10,
    ) -> dict:
        """Erstellt eine vollständige WissensDB mit Dokumenten und Wikis"""
        # Store erstellen
        store = await TestDataGenerator.create_store(
            db=db,
            id=store_id,
            store_type="wissensdb",
            name="Test WissensDB",
            description="Complete test knowledge base",
        )

        # Dokumente erstellen
        documents = await TestDataGenerator.create_bulk_documents(
            db=db,
            store_id=store.id,
            count=doc_count,
            status="indexed",
        )

        # Wiki-Seiten erstellen
        wiki_pages = await TestDataGenerator.create_bulk_wiki_pages(
            db=db,
            store_id=store.id,
            count=wiki_count,
            page_type="concept",
        )

        # Wiki-Seiten mit Dokumenten verknüpfen
        for i, wiki in enumerate(wiki_pages[:5]):  # Erste 5 Wikis mit Docs verknüpfen
            docs_to_link = documents[i*2:(i+1)*2]  # Je 2 Docs pro Wiki
            wiki.source_documents = [
                {"document_id": doc.id, "title": doc.title}
                for doc in docs_to_link
            ]
            await db.commit()

        return {
            "store": store,
            "documents": documents,
            "wiki_pages": wiki_pages,
        }


class DateTimeHelper:
    """Helper für Datums/Zeit-Operationen in Tests"""

    @staticmethod
    def days_ago(days: int) -> datetime:
        """Gibt Datum vor X Tagen zurück"""
        return datetime.utcnow() - timedelta(days=days)

    @staticmethod
    def hours_ago(hours: int) -> datetime:
        """Gibt Datum vor X Stunden zurück"""
        return datetime.utcnow() - timedelta(hours=hours)

    @staticmethod
    def minutes_ago(minutes: int) -> datetime:
        """Gibt Datum vor X Minuten zurück"""
        return datetime.utcnow() - timedelta(minutes=minutes)

    @staticmethod
    def seconds_ago(seconds: int) -> datetime:
        """Gibt Datum vor X Sekunden zurück"""
        return datetime.utcnow() - timedelta(seconds=seconds)

    @staticmethod
    def future_days(days: int) -> datetime:
        """Gibt Datum in X Tagen in der Zukunft zurück"""
        return datetime.utcnow() + timedelta(days=days)

    @staticmethod
    def today() -> datetime:
        """Gibt heute Morgen um 00:00 zurück"""
        return datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def tomorrow() -> datetime:
        """Gibt morgen Morgen um 00:00 zurück"""
        return DateTimeHelper.today() + timedelta(days=1)


class AssertionHelper:
    """Helper für häufige Assertions in Tests"""

    @staticmethod
    def assert_valid_uuid(uuid_string: str):
        """Prüft ob String eine gültige UUID ist"""
        import uuid
        try:
            uuid.UUID(uuid_string)
        except ValueError:
            raise AssertionError(f"Invalid UUID: {uuid_string}")

    @staticmethod
    def assert_valid_iso_date(date_string: str):
        """Prüft ob String ein gültiges ISO-Datum ist"""
        try:
            datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        except ValueError:
            raise AssertionError(f"Invalid ISO date: {date_string}")

    @staticmethod
    def assert_valid_email(email_string: str):
        """Prüft ob String eine gültige E-Mail ist"""
        import re
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email_string):
            raise AssertionError(f"Invalid email: {email_string}")

    @staticmethod
    def assert_between(value: float, min_val: float, max_val: float):
        """Prüft ob Wert innerhalb eines Bereichs liegt"""
        if not (min_val <= value <= max_val):
            raise AssertionError(f"Value {value} not between {min_val} and {max_val}")

    @staticmethod
    def assert_dict_contains(data: dict, required_keys: List[str]):
        """Prüft ob Dict alle erforderlichen Keys enthält"""
        missing_keys = [key for key in required_keys if key not in data]
        if missing_keys:
            raise AssertionError(f"Missing required keys: {missing_keys}")

    @staticmethod
    def assert_list_type(items: list, expected_type: type):
        """Prüft ob alle List-Items vom erwarteten Typ sind"""
        for i, item in enumerate(items):
            if not isinstance(item, expected_type):
                raise AssertionError(
                    f"Item {i} is {type(item)}, expected {expected_type}"
                )


class AsyncTestHelper:
    """Helper für asynchrone Test-Operationen"""

    @staticmethod
    async def wait_for_condition(
        condition_func,
        timeout: float = 5.0,
        interval: float = 0.1,
    ):
        """Wartet bis eine Condition erfüllt ist"""
        start_time = asyncio.get_event_loop().time()

        while True:
            if await condition_func():
                return

            current_time = asyncio.get_event_loop().time()
            if current_time - start_time > timeout:
                raise TimeoutError(f"Condition not met after {timeout}s")

            await asyncio.sleep(interval)

    @staticmethod
    async def run_with_timeout(coro, timeout: float = 5.0):
        """Führt Coroutine mit Timeout aus"""
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Operation timed out after {timeout}s")

    @staticmethod
    async def gather_with_exceptions(*coros):
        """Führt mehrere Coroutines aus und sammelt Exceptions"""
        results = []
        exceptions = []

        for coro in coros:
            try:
                result = await coro
                results.append(result)
            except Exception as e:
                exceptions.append(e)

        return results, exceptions


# ─── Pytest Fixtures ───

import pytest


@pytest.fixture
async def store_with_docs(db_session: AsyncSession):
    """Fixture: Store mit Dokumenten"""
    return await TestDataGenerator.create_store(
        db=db_session,
        store_type="akte",
    )


@pytest.fixture
async def wissensdb_with_content(db_session: AsyncSession):
    """Fixture: Vollständige WissensDB mit Inhalt"""
    return await TestDataGenerator.create_wissensdb_with_content(
        db=db_session,
        doc_count=20,
        wiki_count=10,
    )


@pytest.fixture
def test_data_gen():
    """Fixture: TestDataGenerator Instanz"""
    return TestDataGenerator()


@pytest.fixture
def dt_helper():
    """Fixture: DateTimeHelper Instanz"""
    return DateTimeHelper()


@pytest.fixture
def assert_helper():
    """Fixture: AssertionHelper Instanz"""
    return AssertionHelper()


# ─── Performance Test Decorators ───

def timed_test(max_duration: float = 1.0):
    """Decorator für Performance-Tests mit max Duration"""
    def decorator(test_func):
        async def wrapper(*args, **kwargs):
            import time
            start_time = time.time()

            result = await test_func(*args, **kwargs)

            end_time = time.time()
            duration = end_time - start_time

            if duration > max_duration:
                raise AssertionError(
                    f"Test took {duration:.2f}s, max allowed: {max_duration:.2f}s"
                )

            return result

        return wrapper
    return decorator


# ─── Export als Modul ───

__all__ = [
    "TestDataGenerator",
    "DateTimeHelper",
    "AssertionHelper",
    "AsyncTestHelper",
    "timed_test",
]
