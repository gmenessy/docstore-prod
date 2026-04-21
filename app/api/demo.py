"""
API-Routen: Demo-Szenarien.
Erzeugt mit einem Klick eine vorbereitete Beispiel-Sammlung fuer Demos.
"""
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import verify_api_key
from app.core.database import get_db
from app.models.database import Store, Document, StoreType, DocumentStatus
from app.data.demo_fixtures import DEMO_FIXTURES

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/demo", tags=["Demo"])


@router.get("/fixtures")
async def list_fixtures(auth: str = Depends(verify_api_key)):
    """Liste verfuegbarer Demo-Szenarien."""
    return [
        {
            "id": fid,
            "name": f["name"],
            "description": f["description"],
            "type": f["type"],
            "doc_count": len(f["documents"]),
        }
        for fid, f in DEMO_FIXTURES.items()
    ]


@router.post("/load/{fixture_id}")
async def load_fixture(
    fixture_id: str,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    Laedt ein Demo-Szenario als neue Sammlung.
    Erzeugt Store + Dokumente mit vorbefuelltem Inhalt.
    Triggert keine Ingestion-Pipeline — Inhalt ist direkt als content_text gespeichert.
    """
    if fixture_id not in DEMO_FIXTURES:
        raise HTTPException(status_code=404, detail=f"Demo-Szenario '{fixture_id}' nicht gefunden")

    fixture = DEMO_FIXTURES[fixture_id]

    # Store erstellen
    store_type = StoreType.WISSENSDB if fixture["type"] == "wissensdb" else StoreType.AKTE
    store = Store(
        name=fixture["name"],
        type=store_type,
        description=fixture["description"],
        color="#00B2A9",
        analyse_fokus="Vollstaendige KI-Analyse (Demo)",
    )
    db.add(store)
    await db.flush()

    # Dokumente hinzufuegen
    for doc_data in fixture["documents"]:
        content = doc_data["content"]
        page_count = max(1, content.count("\n\n") // 3)
        doc = Document(
            store_id=store.id,
            title=doc_data["title"],
            file_type="pdf",
            file_path=f"/demo/{fixture_id}/{doc_data['title']}",
            file_size=len(content.encode("utf-8")),
            page_count=page_count,
            status=DocumentStatus.INDEXED,
            content_text=content,
            content_summary=content[:300] + "...",
            chunk_count=max(1, len(content) // 500),
            indexed_at=datetime.utcnow(),
            tags=["demo"],
        )
        db.add(doc)

    await db.commit()
    await db.refresh(store)

    logger.info(f"Demo-Szenario '{fixture_id}' geladen → Store {store.id}")

    return {
        "store_id": store.id,
        "name": store.name,
        "type": store.type.value,
        "doc_count": len(fixture["documents"]),
        "message": "Demo-Szenario erfolgreich geladen. Oeffnen Sie die Sammlung fuer das Decision-Briefing.",
    }
