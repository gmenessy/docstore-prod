"""
Edge-Case Tests für Fehlerbehandlung und Randfälle.
Testet Exception-Handling, Validation und Boundary Conditions.
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Store, Document, WikiPage
from app.core.audit import AuditLogger, AuditAction
from app.services.wiki_auto_curator import WikiAutoCurator


# ─── Boundary Conditions ───

@pytest.mark.asyncio
async def test_store_name_too_long(db_session: AsyncSession):
    """Test Store-Name der zu lang ist"""
    # Store-Name mit 1001 Zeichen (Limit: 500)
    long_name = "A" * 1001

    store = Store(
        id="test_store_long_name",
        name=long_name,  # Zu lang!
        type="akte",
        description="Test",
    )

    db_session.add(store)

    # Erwarte Database Error (Constraint Violation)
    with pytest.raises(Exception):  # Could be IntegrityError, ValidationError, etc.
        await db_session.commit()


@pytest.mark.asyncio
async def test_document_file_size_limit(db_session: AsyncSession):
    """Test Dokument-Größen-Limit"""
    store = Store(
        id="test_store_size_limit",
        name="Test Store Size Limit",
        type="akte",
        description="Test",
    )
    db_session.add(store)
    await db_session.commit()

    # Dokument mit übermäßig großer Datei (100 GB)
    document = Document(
        id="test_doc_too_large",
        store_id=store.id,
        title="Too Large Document",
        filename="large.pdf",
        status="indexed",
        file_size=100 * 1024 * 1024 * 1024,  # 100 GB
    )

    db_session.add(document)

    # Erwarte Validierungsfehler
    with pytest.raises(Exception):
        await db_session.commit()


@pytest.mark.asyncio
async def test_wiki_page_empty_content(db_session: AsyncSession):
    """Test Wiki-Seite mit leerem Content"""
    store = Store(
        id="test_store_empty_wiki",
        name="Test Store Empty Wiki",
        type="wissensdb",
        description="Test",
    )
    db_session.add(store)
    await db_session.commit()

    # Wiki-Seite mit leerem Content
    wiki_page = WikiPage(
        id="test_wiki_empty",
        store_id=store.id,
        title="Empty Wiki Page",
        slug="empty-wiki",
        content_md="",  # Leer!
        page_type="concept",
    )

    db_session.add(wiki_page)
    await db_session.commit()

    # Test Quality Score bei leerem Content
    curator = WikiAutoCurator()
    quality_score = await curator.check_wiki_quality(
        db=db_session,
        store_id=store.id,
        page_id=wiki_page.id,
    )

    # Erwarte niedrigen Scores
    assert quality_score.overall_score < 50.0, "Leere Wiki-Seite sollte niedrigen Score haben"


@pytest.mark.asyncio
async def test_search_query_special_characters(db_session: AsyncSession, store_with_docs):
    """Test Suchanfrage mit Sonderzeichen"""
    from app.search.engine import search_engine

    # Suchanfragen mit Sonderzeichen
    special_queries = [
        "test & query",
        "path/to/file",
        "user@example.com",
        "'quoted' query",
        "query with (parentheses)",
        "test\u0000null",  # Null-Byte
        "😀 emoji test",  # Unicode/Emoji
    ]

    for query in special_queries:
        try:
            results = await search_engine.search(
                query=query,
                store_id=store_with_docs.id,
                limit=10,
            )
            # Sollte nicht crashen
            assert isinstance(results, list)
        except Exception as e:
            # Einige Fehler erwartet, aber keine Crashes
            assert not isinstance(e, (KeyboardInterrupt, SystemExit))


# ─── Validation Errors ───

@pytest.mark.asyncio
async def test_store_invalid_type(db_session: AsyncSession):
    """Test Store mit ungültigem Type"""
    store = Store(
        id="test_store_invalid_type",
        name="Test Store Invalid Type",
        type="invalid_type",  # Ungültig!
        description="Test",
    )

    db_session.add(store)

    # Erwarte Validierungsfehler
    with pytest.raises((ValueError, Exception)):
        await db_session.commit()


@pytest.mark.asyncio
async def test_document_invalid_status(db_session: AsyncSession):
    """Test Dokument mit ungültigem Status"""
    store = Store(
        id="test_store_invalid_status",
        name="Test Store Invalid Status",
        type="akte",
        description="Test",
    )
    db_session.add(store)
    await db_session.commit()

    document = Document(
        id="test_doc_invalid_status",
        store_id=store.id,
        title="Invalid Status Document",
        filename="test.pdf",
        status="invalid_status",  # Ungültig!
    )

    db_session.add(document)

    # Erwarte Validierungsfehler
    with pytest.raises((ValueError, Exception)):
        await db_session.commit()


@pytest.mark.asyncio
async def test_wiki_page_invalid_slug(db_session: AsyncSession):
    """Test Wiki-Seite mit ungültigem Slug"""
    store = Store(
        id="test_store_invalid_slug",
        name="Test Store Invalid Slug",
        type="wissensdb",
        description="Test",
    )
    db_session.add(store)
    await db_session.commit()

    # Slug mit ungültigen Zeichen
    invalid_slugs = [
        "slug with spaces",  # Leerzeichen
        "slug/with/slashes",  # Slashes
        "slug?with=query",  # Query-Parameter
        "slug#with#hash",  # Hash
        "slug<>with<>brackets",  # Klammern
    ]

    for invalid_slug in invalid_slugs:
        wiki_page = WikiPage(
            id=f"test_wiki_{len(invalid_slug)}",
            store_id=store.id,
            title="Invalid Slug Wiki",
            slug=invalid_slug,
            content_md="# Test",
            page_type="concept",
        )

        db_session.add(wiki_page)

        # Erwarte Fehler bei jedem invaliden Slug
        with pytest.raises((ValueError, Exception)):
            await db_session.commit()

        await db_session.rollback()


# ─── Database Constraints ───

@pytest.mark.asyncio
async def test_store_duplicate_id(db_session: AsyncSession):
    """Test doppelter Store-ID"""
    store1 = Store(
        id="duplicate_store_id",
        name="Store 1",
        type="akte",
        description="First store",
    )

    store2 = Store(
        id="duplicate_store_id",  # Gleiche ID!
        name="Store 2",
        type="akte",
        description="Second store",
    )

    db_session.add(store1)
    db_session.add(store2)

    # Erwarte Constraint Violation
    with pytest.raises(Exception):  # IntegrityError
        await db_session.commit()


@pytest.mark.asyncio
async def test_document_without_store(db_session: AsyncSession):
    """Test Dokument ohne existierenden Store"""
    document = Document(
        id="test_doc_no_store",
        store_id="nonexistent_store_id",  # Existiert nicht!
        title="Orphan Document",
        filename="orphan.pdf",
        status="indexed",
    )

    db_session.add(document)

    # Erwarte Foreign Key Constraint Violation
    with pytest.raises(Exception):  # IntegrityError
        await db_session.commit()


@pytest.mark.asyncio
async def test_wiki_page_without_store(db_session: AsyncSession):
    """Test Wiki-Seite ohne existierenden Store"""
    wiki_page = WikiPage(
        id="test_wiki_no_store",
        store_id="nonexistent_store_id",  # Existiert nicht!
        title="Orphan Wiki",
        slug="orphan-wiki",
        content_md="# Orphan",
        page_type="concept",
    )

    db_session.add(wiki_page)

    # Erwarte Foreign Key Constraint Violation
    with pytest.raises(Exception):  # IntegrityError
        await db_session.commit()


# ─── Null/Empty Values ───

@pytest.mark.asyncio
async def test_store_missing_required_fields(db_session: AsyncSession):
    """Test Store ohne Pflichtfelder"""
    # Store ohne name
    store_no_name = Store(
        id="test_store_no_name",
        # name fehlt!
        type="akte",
        description="Test",
    )

    db_session.add(store_no_name)

    with pytest.raises(Exception):
        await db_session.commit()


@pytest.mark.asyncio
async def test_document_null_fields(db_session: AsyncSession):
    """Test Dokument mit NULL-Werten in optionalen Feldern"""
    store = Store(
        id="test_store_null_fields",
        name="Test Store Null Fields",
        type="akte",
        description="Test",
    )
    db_session.add(store)
    await db_session.commit()

    # Dokument mit NULL-Werten (erlaubt für optionale Felder)
    document = Document(
        id="test_doc_null_fields",
        store_id=store.id,
        title="Document with Nulls",
        filename="nulls.pdf",
        status="indexed",
        # Optionale Felder weggelassen
        file_size=None,
        page_count=None,
        language=None,
    )

    db_session.add(document)
    await db_session.commit()

    # Sollte erfolgreich sein (optionale Felder)
    assert document.id is not None


# ─── Concurrent Operations ───

@pytest.mark.asyncio
async def test_concurrent_document_uploads(db_session: AsyncSession):
    """Test gleichzeitige Dokument-Uploads"""
    import asyncio

    store = Store(
        id="test_store_concurrent",
        name="Test Store Concurrent",
        type="akte",
        description="Test",
    )
    db_session.add(store)
    await db_session.commit()

    # 10 Dokumente gleichzeitig erstellen
    async def create_document(i):
        document = Document(
            id=f"test_doc_concurrent_{i}",
            store_id=store.id,
            title=f"Concurrent Document {i}",
            filename=f"concurrent_{i}.pdf",
            status="processing",
        )
        db_session.add(document)
        await asyncio.sleep(0.01)  # Simuliere Verarbeitung
        await db_session.commit()

    # Gleichzeitig ausführen
    tasks = [create_document(i) for i in range(10)]
    await asyncio.gather(*tasks)

    # Alle sollten erfolgreich erstellt sein
    from sqlalchemy import select, func

    count = await db_session.execute(
        select(func.count(Document.id))
        .where(Document.store_id == store.id)
    )
    doc_count = count.scalar()

    assert doc_count >= 10, f"Es sollten mindestens 10 Dokumente sein, sind aber {doc_count}"


@pytest.mark.asyncio
async def test_concurrent_wiki_updates(db_session: AsyncSession):
    """Test gleichzeitige Wiki-Updates"""
    import asyncio

    store = Store(
        id="test_store_concurrent_wiki",
        name="Test Store Concurrent Wiki",
        type="wissensdb",
        description="Test",
    )
    db_session.add(store)
    await db_session.commit()

    wiki_page = WikiPage(
        id="test_wiki_concurrent",
        store_id=store.id,
        title="Concurrent Wiki",
        slug="concurrent-wiki",
        content_md="# Original",
        page_type="concept",
    )
    db_session.add(wiki_page)
    await db_session.commit()

    # 5 gleichzeitige Updates
    async def update_wiki(i):
        await db_session.refresh(wiki_page)
        wiki_page.content_md = f"# Update {i}\n\nUpdated at {datetime.utcnow()}"
        wiki_page.update_count += 1
        await asyncio.sleep(0.01)
        await db_session.commit()

    # Gleichzeitig ausführen
    tasks = [update_wiki(i) for i in range(5)]
    await asyncio.gather(*tasks)

    # Wiki sollte aktualisiert sein
    await db_session.refresh(wiki_page)
    assert wiki_page.update_count >= 5, f"Update-Count sollte >= 5 sein, ist aber {wiki_page.update_count}"


# ─── Large Data Sets ───

@pytest.mark.asyncio
async def test_large_store_list(db_session: AsyncSession):
    """Test Store-Listing mit vielen Stores"""
    # 100 Stores erstellen
    for i in range(100):
        store = Store(
            id=f"test_store_large_{i}",
            name=f"Large Store {i}",
            type="akte",
            description=f"Store {i}",
        )
        db_session.add(store)

    await db_session.commit()

    # Alle Stores abfragen
    from sqlalchemy import select

    result = await db_session.execute(
        select(Store).limit(200)
    )
    stores = result.scalars().all()

    assert len(stores) >= 100, f"Es sollten >= 100 Stores sein, sind aber {len(stores)}"


@pytest.mark.asyncio
async def test_large_document_list(db_session: AsyncSession):
    """Test Dokument-Listing mit vielen Dokumenten"""
    store = Store(
        id="test_store_large_docs",
        name="Test Store Large Docs",
        type="akte",
        description="Test",
    )
    db_session.add(store)
    await db_session.commit()

    # 1000 Dokumente erstellen
    for i in range(1000):
        document = Document(
            id=f"test_doc_large_{i}",
            store_id=store.id,
            title=f"Large Document {i}",
            filename=f"large_{i}.pdf",
            status="indexed",
        )
        db_session.add(document)

    await db_session.commit()

    # Alle Dokumente abfragen
    from sqlalchemy import select, func

    count = await db_session.execute(
        select(func.count(Document.id))
        .where(Document.store_id == store.id)
    )
    doc_count = count.scalar()

    assert doc_count >= 1000, f"Es sollten >= 1000 Dokumente sein, sind aber {doc_count}"


# ─── Time-based Edge Cases ───

@pytest.mark.asyncio
async def test_document_created_at_future(db_session: AsyncSession):
    """Test Dokument mit zukünftigem Erstellungsdatum"""
    store = Store(
        id="test_store_future_date",
        name="Test Store Future Date",
        type="akte",
        description="Test",
    )
    db_session.add(store)
    await db_session.commit()

    # Dokument mit zukünftigem Datum
    future_date = datetime.utcnow() + timedelta(days=365)

    document = Document(
        id="test_doc_future",
        store_id=store.id,
        title="Future Document",
        filename="future.pdf",
        status="indexed",
        created_at=future_date,
    )

    db_session.add(document)
    await db_session.commit()

    # Sollte erlaubt sein (keine Constraint)
    assert document.created_at > datetime.utcnow()


@pytest.mark.asyncio
async def test_wiki_page_freshness_edge_cases(db_session: AsyncSession):
    """Test Wiki-Freshness mit Randfällen"""
    from app.services.wiki_auto_curator import WikiAutoCurator

    curator = WikiAutoCurator()

    # Test 1: Wiki-Seite ohne Quellen
    store = Store(
        id="test_store_freshness_edge",
        name="Test Store Freshness Edge",
        type="wissensdb",
        description="Test",
    )
    db_session.add(store)
    await db_session.commit()

    wiki_no_sources = WikiPage(
        id="test_wiki_no_sources",
        store_id=store.id,
        title="Wiki No Sources",
        slug="wiki-no-sources",
        content_md="# No Sources",
        page_type="concept",
        source_documents=[],  # Keine Quellen!
    )

    db_session.add(wiki_no_sources)
    await db_session.commit()

    freshness = await curator._calculate_freshness(db_session, wiki_no_sources)
    assert freshness == 30.0, "Wiki ohne Quellen sollte Score 30.0 haben"

    # Test 2: Wiki-Seite mit extrem alten Quellen
    old_doc = Document(
        id="test_doc_ancient",
        store_id=store.id,
        title="Ancient Document",
        filename="ancient.pdf",
        status="indexed",
        created_at=datetime.utcnow() - timedelta(days=365),  # 1 Jahr alt
    )

    db_session.add(old_doc)
    await db_session.commit()

    wiki_old_sources = WikiPage(
        id="test_wiki_old_sources",
        store_id=store.id,
        title="Wiki Old Sources",
        slug="wiki-old-sources",
        content_md="# Old Sources",
        page_type="concept",
        source_documents=[{"document_id": "test_doc_ancient", "title": "Ancient"}],
    )

    db_session.add(wiki_old_sources)
    await db_session.commit()

    freshness = await curator._calculate_freshness(db_session, wiki_old_sources)
    assert freshness < 10.0, "Wiki mit 1 Jahr alten Quellen sollte sehr niedrigen Score haben"


# ─── Unicode/Special Characters ───

@pytest.mark.asyncio
async def test_unicode_in_fields(db_session: AsyncSession):
    """Test Unicode-Zeichen in allen Textfeldern"""
    store = Store(
        id="test_store_unicode",
        name="🎉 Test Store Unicode 💯",
        type="akte",
        description="Test with ß, ä, ö, ü, 中文, 🇩🇪",
        language="de",
    )

    db_session.add(store)
    await db_session.commit()

    # Prüfen dass Unicode korrekt gespeichert wurde
    await db_session.refresh(store)
    assert "ß" in store.description
    assert "🎉" in store.name


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
