"""
Performance-Tests für Lastsituationen und Stress-Testing.
Testet System-Verhalten unter Last und Performance-Metriken.
"""
import pytest
import time
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Store, Document
from app.search.engine import search_engine
from app.core.audit import AuditLogger, AuditAction


# ─── Database Performance ───

@pytest.mark.asyncio
async def test_bulk_insert_performance(db_session: AsyncSession):
    """Test Performance von Bulk-Inserts"""
    store = Store(
        id="test_store_bulk_insert",
        name="Test Store Bulk Insert",
        type="akte",
        description="Performance Test",
    )
    db_session.add(store)
    await db_session.commit()

    # 1000 Dokumente einfügen
    start_time = time.time()

    documents = []
    for i in range(1000):
        document = Document(
            id=f"test_doc_bulk_{i}",
            store_id=store.id,
            title=f"Bulk Document {i}",
            filename=f"bulk_{i}.pdf",
            status="indexed",
            file_size=1024 * (i + 1),
        )
        documents.append(document)

    db_session.add_all(documents)
    await db_session.commit()

    end_time = time.time()
    duration = end_time - start_time

    # Sollte < 5 Sekunden dauern für 1000 Dokumente
    assert duration < 5.0, f"1000 Inserts dauerten {duration:.2f}s, sollte < 5s sein"

    print(f"✓ 1000 Inserts in {duration:.2f}s ({1000/duration:.0f} docs/s)")


@pytest.mark.asyncio
async def test_query_performance_with_large_dataset(db_session: AsyncSession):
    """Test Query-Performance bei großem Dataset"""
    from sqlalchemy import select, func

    # Store mit vielen Dokumenten erstellen
    store = Store(
        id="test_store_query_perf",
        name="Test Store Query Performance",
        type="akte",
        description="Performance Test",
    )
    db_session.add(store)
    await db_session.commit()

    # 5000 Dokumente erstellen
    for i in range(5000):
        document = Document(
            id=f"test_doc_query_{i}",
            store_id=store.id,
            title=f"Query Document {i}",
            filename=f"query_{i}.pdf",
            status="indexed",
        )
        db_session.add(document)

    await db_session.commit()

    # Query-Performance testen
    start_time = time.time()

    result = await db_session.execute(
        select(Document)
        .where(Document.store_id == store.id)
        .where(Document.status == "indexed")
        .limit(100)
    )
    documents = result.scalars().all()

    end_time = time.time()
    duration = end_time - start_time

    # Sollte < 100ms dauern
    assert duration < 0.1, f"Query dauerte {duration*1000:.0f}ms, sollte < 100ms sein"

    print(f"✓ Query in {duration*1000:.2f}ms für 5000 Dokumente")


# ─── Search Performance ───

@pytest.mark.asyncio
async def test_search_performance_small_corpus(db_session: AsyncSession):
    """Test Such-Performance bei kleinem Corpus"""
    store = Store(
        id="test_store_search_small",
        name="Test Store Search Small",
        type="akte",
        description="Performance Test",
    )
    db_session.add(store)
    await db_session.commit()

    # 100 Dokumente erstellen
    for i in range(100):
        document = Document(
            id=f"test_doc_search_{i}",
            store_id=store.id,
            title=f"Search Document {i}",
            filename=f"search_{i}.pdf",
            status="indexed",
            content_md=f"This is document {i} with search content test.",
        )
        db_session.add(document)

    await db_session.commit()

    # Index re-indexieren (simuliert)
    # In echt: await reindex_all(db_session)

    # Such-Performance testen
    start_time = time.time()

    results = await search_engine.search(
        query="search content test",
        store_id=store.id,
        limit=10,
    )

    end_time = time.time()
    duration = end_time - start_time

    # Sollte < 50ms dauern
    assert duration < 0.05, f"Search dauerte {duration*1000:.0f}ms, sollte < 50ms sein"

    print(f"✓ Search in {duration*1000:.2f}ms für 100 Dokumente")


@pytest.mark.asyncio
async def test_search_performance_large_corpus(db_session: AsyncSession):
    """Test Such-Performance bei großem Corpus"""
    store = Store(
        id="test_store_search_large",
        name="Test Store Search Large",
        type="akte",
        description="Performance Test",
    )
    db_session.add(store)
    await db_session.commit()

    # 10000 Dokumente erstellen
    for i in range(10000):
        document = Document(
            id=f"test_doc_search_large_{i}",
            store_id=store.id,
            title=f"Large Search Document {i}",
            filename=f"large_search_{i}.pdf",
            status="indexed",
            content_md=f"This is document {i} with large search content test.",
        )
        db_session.add(document)

    await db_session.commit()

    # Such-Performance testen
    start_time = time.time()

    results = await search_engine.search(
        query="large search content test",
        store_id=store.id,
        limit=10,
    )

    end_time = time.time()
    duration = end_time - start_time

    # Sollte < 200ms dauern
    assert duration < 0.2, f"Search dauerte {duration*1000:.0f}ms, sollte < 200ms sein"

    print(f"✓ Search in {duration*1000:.2f}ms für 10000 Dokumente")


# ─── Concurrent Operations Performance ───

@pytest.mark.asyncio
async def test_concurrent_searches(db_session: AsyncSession):
    """Test gleichzeitige Suchanfragen"""
    store = Store(
        id="test_store_concurrent_search",
        name="Test Store Concurrent Search",
        type="akte",
        description="Performance Test",
    )
    db_session.add(store)
    await db_session.commit()

    # 500 Dokumente erstellen
    for i in range(500):
        document = Document(
            id=f"test_doc_concurrent_search_{i}",
            store_id=store.id,
            title=f"Concurrent Search Document {i}",
            filename=f"concurrent_search_{i}.pdf",
            status="indexed",
            content_md=f"This is document {i} with concurrent search content.",
        )
        db_session.add(document)

    await db_session.commit()

    # 50 gleichzeitige Suchanfragen
    async def perform_search(query_num):
        start = time.time()
        results = await search_engine.search(
            query=f"concurrent search content {query_num}",
            store_id=store.id,
            limit=10,
        )
        duration = time.time() - start
        return duration

    # Gleichzeitig ausführen
    start_time = time.time()

    tasks = [perform_search(i) for i in range(50)]
    durations = await asyncio.gather(*tasks)

    end_time = time.time()
    total_duration = end_time - start_time

    # Durchschnittliche Duration pro Search
    avg_duration = sum(durations) / len(durations)

    # Total sollte < 3 Sekunden dauern (parallel execution)
    assert total_duration < 3.0, f"50 concurrent searches dauerten {total_duration:.2f}s, sollte < 3s sein"

    print(f"✓ 50 concurrent searches in {total_duration:.2f}s (avg: {avg_duration*1000:.2f}ms per search)")


# ─── Audit Log Performance ───

@pytest.mark.asyncio
async def test_audit_log_write_performance(db_session: AsyncSession):
    """Test Schreib-Performance von Audit-Logs"""
    from app.core.audit import audit_logger

    store = Store(
        id="test_store_audit_perf",
        name="Test Store Audit Performance",
        type="akte",
        description="Performance Test",
    )
    db_session.add(store)
    await db_session.commit()

    # 1000 Audit-Logs schreiben
    start_time = time.time()

    for i in range(1000):
        await audit_logger.log(
            db=db_session,
            action=AuditAction.DOC_VIEW,
            store_id=store.id,
            user_id=f"user_{i % 100}",  # 100 verschiedene Users
            resource_type="document",
            resource_id=f"doc_{i}",
        )

    end_time = time.time()
    duration = end_time - start_time

    # Sollte < 10 Sekunden dauern
    assert duration < 10.0, f"1000 audit logs dauerten {duration:.2f}s, sollte < 10s sein"

    print(f"✓ 1000 audit logs in {duration:.2f}s ({1000/duration:.0f} logs/s)")


@pytest.mark.asyncio
async def test_audit_log_query_performance(db_session: AsyncSession):
    """Test Lese-Performance von Audit-Logs"""
    from app.core.audit import audit_logger

    store = Store(
        id="test_store_audit_query_perf",
        name="Test Store Audit Query Performance",
        type="akte",
        description="Performance Test",
    )
    db_session.add(store)
    await db_session.commit()

    # 10000 Audit-Logs erstellen
    for i in range(10000):
        await audit_logger.log(
            db=db_session,
            action=AuditAction.DOC_VIEW if i % 2 == 0 else AuditAction.DOC_UPLOAD,
            store_id=store.id,
            user_id=f"user_{i % 1000}",
            resource_type="document",
            resource_id=f"doc_{i}",
        )

    # Query-Performance testen
    start_time = time.time()

    logs = await audit_logger.query_logs(
        db=db_session,
        store_id=store.id,
        limit=1000,
    )

    end_time = time.time()
    duration = end_time - start_time

    # Sollte < 100ms dauern
    assert duration < 0.1, f"Query dauerte {duration*1000:.0f}ms, sollte < 100ms sein"

    assert len(logs) == 1000, f"Es sollten 1000 Logs sein, sind aber {len(logs)}"

    print(f"✓ Audit query in {duration*1000:.2f}ms für 10000 Logs (returned 1000)")


# ─── Wiki Curator Performance ───

@pytest.mark.asyncio
async def test_wiki_quality_check_performance(db_session: AsyncSession):
    """Test Performance der Wiki-Qualitätsprüfung"""
    from app.services.wiki_auto_curator import wiki_auto_curator

    store = Store(
        id="test_store_wiki_perf",
        name="Test Store Wiki Performance",
        type="wissensdb",
        description="Performance Test",
    )
    db_session.add(store)
    await db_session.commit()

    # 100 Wiki-Seiten erstellen
    for i in range(100):
        wiki_page = WikiPage(
            id=f"test_wiki_perf_{i}",
            store_id=store.id,
            title=f"Performance Wiki {i}",
            slug=f"perf-wiki-{i}",
            content_md=f"# Performance Wiki {i}\n\nContent for testing.",
            page_type="concept",
        )
        db_session.add(wiki_page)

    await db_session.commit()

    # Quality Check Performance testen
    start_time = time.time()

    for i in range(100):
        await wiki_auto_curator.check_wiki_quality(
            db=db_session,
            store_id=store.id,
            page_id=f"test_wiki_perf_{i}",
        )

    end_time = time.time()
    duration = end_time - start_time

    # Sollte < 5 Sekunden dauern
    assert duration < 5.0, f"100 quality checks dauerten {duration:.2f}s, sollte < 5s sein"

    print(f"✓ 100 quality checks in {duration:.2f}s ({100/duration:.0f} checks/s)")


# ─── Memory Usage ───

@pytest.mark.asyncio
async def test_memory_usage_large_result_set(db_session: AsyncSession):
    """Test Memory-Usage bei großen Result-Sets"""
    from sqlalchemy import select

    store = Store(
        id="test_store_memory",
        name="Test Store Memory",
        type="akte",
        description="Performance Test",
    )
    db_session.add(store)
    await db_session.commit()

    # 10000 Dokumente erstellen
    for i in range(10000):
        document = Document(
            id=f"test_doc_memory_{i}",
            store_id=store.id,
            title=f"Memory Test Document {i}",
            filename=f"memory_{i}.pdf",
            status="indexed",
            content_md=f"Content " * 100,  # ~600 Bytes pro Doc
        )
        db_session.add(document)

    await db_session.commit()

    # Large Result Set abfragen mit Yield
    start_time = time.time()

    result = await db_session.execute(
        select(Document)
        .where(Document.store_id == store.id)
        .execution_options(yield_per=1000)  # Batch processing
    )

    # Iterieren mit yield_per
    document_count = 0
    for document in result.scalars():
        document_count += 1
        if document_count >= 10000:
            break

    end_time = time.time()
    duration = end_time - start_time

    # Sollte < 2 Sekunden dauern
    assert duration < 2.0, f"Large result set dauerte {duration:.2f}s, sollte < 2s sein"

    assert document_count == 10000

    print(f"✓ 10000 documents in {duration:.2f}s with yield_per batching")


# ─── Stress Tests ───

@pytest.mark.asyncio
async def test_rapid_document_uploads(db_session: AsyncSession):
    """Test schnelle aufeinanderfolgende Dokument-Uploads"""
    store = Store(
        id="test_store_rapid_uploads",
        name="Test Store Rapid Uploads",
        type="akte",
        description="Stress Test",
    )
    db_session.add(store)
    await db_session.commit()

    # 100 Dokumente schnell hintereinander erstellen
    start_time = time.time()

    for i in range(100):
        document = Document(
            id=f"test_doc_rapid_{i}",
            store_id=store.id,
            title=f"Rapid Upload Document {i}",
            filename=f"rapid_{i}.pdf",
            status="processing",
        )
        db_session.add(document)
        await db_session.commit()

    end_time = time.time()
    duration = end_time - start_time

    # Sollte < 2 Sekunden dauern
    assert duration < 2.0, f"100 rapid uploads dauerten {duration:.2f}s, sollte < 2s sein"

    print(f"✓ 100 rapid uploads in {duration:.2f}s ({100/duration:.0f} uploads/s)")


@pytest.mark.asyncio
async def test_concurrent_store_operations(db_session: AsyncSession):
    """Test gleichzeitige Store-Operationen"""
    async def create_and_delete_store(i):
        # Store erstellen
        store = Store(
            id=f"test_store_concurrent_ops_{i}",
            name=f"Concurrent Store {i}",
            type="akte",
            description=f"Concurrent operation {i}",
        )
        db_session.add(store)
        await db_session.commit()

        # Sofort wieder löschen
        from sqlalchemy import delete

        await db_session.execute(
            delete(Store).where(Store.id == store.id)
        )
        await db_session.commit()

    # 50 gleichzeitige Create/Delete Operationen
    start_time = time.time()

    tasks = [create_and_delete_store(i) for i in range(50)]
    await asyncio.gather(*tasks)

    end_time = time.time()
    duration = end_time - start_time

    # Sollte < 5 Sekunden dauern
    assert duration < 5.0, f"50 concurrent operations dauerten {duration:.2f}s, sollte < 5s sein"

    print(f"✓ 50 concurrent create/delete operations in {duration:.2f}s")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
