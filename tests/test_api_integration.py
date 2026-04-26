"""
Integration-Tests für alle API-Endpoints.
Testet die vollständigen Request/Response-Cycles mit echter Datenbank.
"""
import pytest
from datetime import datetime
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.database import Store, Document, WikiPage
from app.core.audit import AuditAction


# ─── Test Fixtures ───

@pytest.fixture
def client():
    """Test-Client für FastAPI App"""
    return TestClient(app)


@pytest.fixture
def test_api_key():
    """Test-API-Key"""
    return "test_api_key_123456789012345678901234567890"


@pytest.fixture
async def test_store(db_session: AsyncSession):
    """Test-Store erstellen"""
    store = Store(
        id="test_store_integration",
        name="Test Store Integration",
        type="akte",
        description="Integration Test Store",
        language="de",
        primary_language="de",
    )
    db_session.add(store)
    await db_session.commit()
    await db_session.refresh(store)
    return store


@pytest.fixture
async def test_document(db_session: AsyncSession, test_store):
    """Test-Dokument erstellen"""
    document = Document(
        id="test_doc_integration",
        store_id=test_store.id,
        title="Integration Test Document",
        filename="test_integration.pdf",
        status="indexed",
        file_size=1024,
        content_md="Test content for integration testing.",
        created_at=datetime.utcnow(),
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    return document


@pytest.fixture
async def test_wiki_page(db_session: AsyncSession, test_store):
    """Test-WikiPage erstellen"""
    wiki_page = WikiPage(
        id="test_wiki_integration",
        store_id=test_store.id,
        title="Integration Test Wiki",
        slug="integration-test-wiki",
        content_md="# Integration Test\n\nThis is a test wiki page.",
        page_type="concept",
        source_documents=[],
    )
    db_session.add(wiki_page)
    await db_session.commit()
    await db_session.refresh(wiki_page)
    return wiki_page


# ─── System Endpoints ───

def test_root_endpoint(client):
    """Test des Root-Endpoints"""
    response = client.get("/")
    assert response.status_code == 200

    data = response.json()
    assert "name" in data
    assert "version" in data
    assert data["name"] == "Agentischer Document Store"


def test_health_endpoint(client):
    """Test des Health-Endpoints"""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert data["status"] == "healthy"


# ─── Store Management ───

def test_create_store(client, test_api_key):
    """Test Store-Erstellung"""
    response = client.post(
        "/api/v1/stores",
        headers={"X-API-Key": test_api_key},
        json={
            "name": "New Test Store",
            "type": "akte",
            "description": "Test store creation",
        },
    )

    assert response.status_code in [200, 201]  # CREATED oder OK
    data = response.json()
    assert "id" in data
    assert data["name"] == "New Test Store"
    assert data["type"] == "akte"


def test_list_stores(client, test_api_key):
    """Test Store-Listing"""
    response = client.get(
        "/api/v1/stores",
        headers={"X-API-Key": test_api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert "stores" in data
    assert isinstance(data["stores"], list)


def test_get_store(client, test_api_key, test_store):
    """Test Abruf eines einzelnen Stores"""
    response = client.get(
        f"/api/v1/stores/{test_store.id}",
        headers={"X-API-Key": test_api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_store.id
    assert data["name"] == test_store.name


def test_update_store(client, test_api_key, test_store):
    """Test Store-Aktualisierung"""
    response = client.patch(
        f"/api/v1/stores/{test_store.id}",
        headers={"X-API-Key": test_api_key},
        json={
            "name": "Updated Test Store",
            "description": "Updated description",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Test Store"
    assert data["description"] == "Updated description"


def test_delete_store(client, test_api_key, db_session: AsyncSession):
    """Test Store-Löschung"""
    # Test-Store erstellen
    store = Store(
        id="test_store_delete",
        name="Test Store Delete",
        type="akte",
        description="Will be deleted",
    )
    db_session.add(store)
    await db_session.commit()

    response = client.delete(
        f"/api/v1/stores/{store.id}",
        headers={"X-API-Key": test_api_key},
    )

    assert response.status_code in [200, 204]  # OK oder No Content


# ─── Document Management ───

def test_upload_document_sync(client, test_api_key, test_store):
    """Test synchronen Dokument-Upload"""
    # Test-Datei erstellen
    from io import BytesIO

    file_content = b"Test document content for upload"

    response = client.post(
        f"/api/v1/documents/{test_store.id}/upload-sync",
        headers={"X-API-Key": test_api_key},
        files={
            "file": ("test.txt", BytesIO(file_content), "text/plain")
        },
        data={
            "title": "Test Upload Document",
        },
    )

    # Erwarte Erfolg oder async processing
    assert response.status_code in [200, 201, 202]


def test_list_documents(client, test_api_key, test_store, test_document):
    """Test Dokument-Listing"""
    response = client.get(
        f"/api/v1/documents/{test_store.id}",
        headers={"X-API-Key": test_api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert "documents" in data
    assert isinstance(data["documents"], list)
    assert len(data["documents"]) >= 1


def test_get_document(client, test_api_key, test_document):
    """Test Abruf eines einzelnen Dokuments"""
    response = client.get(
        f"/api/v1/documents/detail/{test_document.id}",
        headers={"X-API-Key": test_api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_document.id
    assert data["title"] == test_document.title


def test_delete_document(client, test_api_key, test_store, test_document):
    """Test Dokument-Löschung"""
    response = client.delete(
        f"/api/v1/documents/{test_store.id}/{test_document.id}",
        headers={"X-API-Key": test_api_key},
    )

    assert response.status_code in [200, 204]


# ─── Search ───

def test_search_hybrid(client, test_api_key, test_store, test_document):
    """Test Hybrid-Suche"""
    response = client.post(
        f"/api/v1/search/{test_store.id}",
        headers={"X-API-Key": test_api_key},
        json={
            "query": "integration test",
            "limit": 10,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert isinstance(data["results"], list)


# ─── Chat (RAG) ───

def test_chat_create(client, test_api_key, test_store):
    """Test Chat-Anfrage erstellen"""
    response = client.post(
        f"/api/v1/stores/{test_store.id}/chat",
        headers={"X-API-Key": test_api_key},
        json={
            "message": "Was ist ein Integration Test?",
            "provider": "ollama",
            "model": "llama3.2",
        },
    )

    # Erfolgreich oder async processing
    assert response.status_code in [200, 202]


def test_chat_get_providers(client, test_api_key):
    """Test Abruf verfügbarer LLM-Provider"""
    response = client.get(
        "/api/v1/chat/providers",
        headers={"X-API-Key": test_api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert "providers" in data


# ─── Wiki ───

def test_wiki_ingest(client, test_api_key, test_store, test_document):
    """Test Wiki-Ingest"""
    response = client.post(
        f"/api/v1/stores/{test_store.id}/wiki/ingest/{test_document.id}",
        headers={"X-API-Key": test_api_key},
        json={
            "force": False,
        },
    )

    # Erfolgreich oder async processing
    assert response.status_code in [200, 202]


def test_wiki_query(client, test_api_key, test_store):
    """Test Wiki-Query"""
    response = client.post(
        f"/api/v1/stores/{test_store.id}/wiki/query",
        headers={"X-API-Key": test_api_key},
        json={
            "question": "Was ist ein Integration Test?",
        },
    )

    assert response.status_code in [200, 202]


def test_wiki_list_pages(client, test_api_key, test_store):
    """Test Wiki-Pages Listing"""
    response = client.get(
        f"/api/v1/stores/{test_store.id}/wiki/pages",
        headers={"X-API-Key": test_api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert "pages" in data


def test_wiki_get_page(client, test_api_key, test_wiki_page):
    """Test Abruf einer Wiki-Seite"""
    response = client.get(
        f"/api/v1/stores/{test_wiki_page.store_id}/wiki/pages/{test_wiki_page.slug}",
        headers={"X-API-Key": test_api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["slug"] == test_wiki_page.slug


# ─── Comments ───

def test_comments_list(client, test_api_key, test_store):
    """Test Kommentar-Listing"""
    response = client.get(
        f"/api/v1/comments/{test_store.id}",
        headers={"X-API-Key": test_api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert "comments" in data


def test_comments_create(client, test_api_key, test_store, test_document):
    """Test Kommentar-Erstellung"""
    response = client.post(
        f"/api/v1/comments/{test_store.id}",
        headers={"X-API-Key": test_api_key},
        json={
            "content": "This is a test comment",
            "document_id": test_document.id,
        },
    )

    assert response.status_code in [200, 201]


# ─── Metrics ───

def test_metrics_overview(client, test_api_key, test_store):
    """Test Metrics Overview"""
    response = client.get(
        f"/api/v1/metrics/overview/{test_store.id}",
        headers={"X-API-Key": test_api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert "collaboration_score" in data or "overall_score" in data


def test_metrics_collaboration(client, test_api_key, test_store):
    """Test Kollaborations-Metriken"""
    response = client.get(
        f"/api/v1/metrics/collaboration/{test_store.id}",
        headers={"X-API-Key": test_api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert "comment_count" in data or "active_users" in data


# ─── Compliance ───

def test_audit_logs(client, test_api_key, test_store):
    """Test Audit-Logs Abfrage"""
    response = client.get(
        f"/api/v1/audit/logs?store_id={test_store.id}",
        headers={"X-API-Key": test_api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert "logs" in data or isinstance(data, list)


def test_compliance_dashboard(client, test_api_key, test_store):
    """Test Compliance Dashboard"""
    response = client.get(
        f"/api/v1/compliance/dashboard?store_id={test_store.id}",
        headers={"X-API-Key": test_api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert "total_actions" in data or "unique_users" in data


# ─── Wiki Curator ───

def test_wiki_curator_quality(client, test_api_key, test_store, test_wiki_page):
    """Test Wiki-Qualitätsprüfung"""
    response = client.get(
        f"/api/v1/wiki-curator/quality/{test_store.id}/{test_wiki_page.id}",
        headers={"X-API-Key": test_api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert "quality_score" in data
    assert "metrics" in data


def test_wiki_curator_candidates(client, test_api_key, test_store):
    """Test Wiki-Refresh Kandidaten"""
    response = client.get(
        f"/api/v1/wiki-curator/candidates/{test_store.id}",
        headers={"X-API-Key": test_api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert "candidates" in data


# ─── Error Cases ───

def test_api_key_missing(client):
    """Test fehlenden API-Key"""
    response = client.get("/api/v1/stores")

    # Erwarte Unauthorized oder Forbidden
    assert response.status_code in [401, 403]


def test_store_not_found(client, test_api_key):
    """Test nicht existierenden Store"""
    response = client.get(
        "/api/v1/stores/nonexistent_store_id",
        headers={"X-API-Key": test_api_key},
    )

    assert response.status_code == 404


def test_document_not_found(client, test_api_key, test_store):
    """Test nicht existierendes Dokument"""
    response = client.get(
        f"/api/v1/documents/detail/nonexistent_doc_id",
        headers={"X-API-Key": test_api_key},
    )

    assert response.status_code == 404


def test_invalid_store_type(client, test_api_key):
    """Test ungültigen Store-Type"""
    response = client.post(
        "/api/v1/stores",
        headers={"X-API-Key": test_api_key},
        json={
            "name": "Invalid Store",
            "type": "invalid_type",  # Ungültiger Typ
            "description": "Test invalid type",
        },
    )

    # Erwarte Validation Error
    assert response.status_code == 422


def test_empty_search_query(client, test_api_key, test_store):
    """Test leere Suchanfrage"""
    response = client.post(
        f"/api/v1/search/{test_store.id}",
        headers={"X-API-Key": test_api_key},
        json={
            "query": "",  # Leere Query
            "limit": 10,
        },
    )

    # Erwarte Validation Error
    assert response.status_code in [400, 422]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
