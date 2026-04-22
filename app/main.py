"""
Agentischer Document Store – FastAPI Hauptanwendung.

On-Premise · DSGVO-konform · Keine Cloud-API-Calls
Hybrid-Suche (BM25 + Semantic) · Adaptive Chunking · NER Pipeline
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import init_db
from app.core.auth import setup_rate_limiting
from app.api.stores import router as stores_router
from app.api.documents import router as documents_router
from app.api.search import router as search_router
from app.api.chat import router as chat_router
from app.api.skills import router as skills_router
from app.api.planning import router as planning_router
from app.api.system import router as system_router
from app.api.export import router as export_router
from app.api.wiki import router as wiki_router
from app.api.briefing import router as briefing_router
from app.api.demo import router as demo_router
from app.api.audit import router as audit_router
from app.api.comments import router as comments_router
from app.api.metrics import router as metrics_router
from app.core.websocket import websocket_endpoint

# ─── Logging ───
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(name)-30s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("docstore")


# ─── Lifecycle ───

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup & Shutdown."""
    logger.info("═══════════════════════════════════════════════")
    logger.info("  Agentischer Document Store wird gestartet…")
    logger.info("═══════════════════════════════════════════════")

    # Datenbank initialisieren
    await init_db()
    logger.info("✓ Datenbank initialisiert")

    # Suchindex aus DB laden
    from app.services.ingestion_service import reindex_all
    from app.core.database import async_session
    async with async_session() as db:
        chunk_count = await reindex_all(db)
    logger.info(f"✓ Suchindex geladen ({chunk_count} Chunks)")

    # Embedding-Client pruefen
    from app.search.engine import embedding_client
    emb_ok = await embedding_client.check_availability()
    logger.info(f"{'✓' if emb_ok else '○'} Ollama Embeddings: {'verfuegbar' if emb_ok else 'nicht erreichbar (TF-IDF Fallback)'}")

    logger.info(f"✓ Server bereit auf {settings.host}:{settings.port}")
    logger.info("═══════════════════════════════════════════════")

    yield

    # Shutdown
    from app.core.llm_client import llm_client
    await llm_client.close()
    logger.info("Server wird heruntergefahren…")


# ─── App ───

app = FastAPI(
    title="Agentischer Document Store",
    description=(
        "Dokumenten-Management mit Hybrid-Suche, NER-Pipeline und "
        "Intelligence-Services. Organisiert als Akte oder WissensDB. "
        "100% On-Premise, DSGVO-konform. "
        "Multi-Provider LLM: Ollama, OpenAI, Anthropic, Mistral, Azure."
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS ───
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Rate-Limiting ───
setup_rate_limiting(app)

# ─── Routen ───
app.include_router(stores_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(skills_router, prefix="/api/v1")
app.include_router(planning_router, prefix="/api/v1")
app.include_router(system_router, prefix="/api/v1")
app.include_router(export_router, prefix="/api/v1")
app.include_router(wiki_router, prefix="/api/v1")
app.include_router(briefing_router, prefix="/api/v1")
app.include_router(demo_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(comments_router, prefix="/api/v1")
app.include_router(metrics_router, prefix="/api/v1")

# ─── WebSocket für Echtzeit-Kollaboration ───
@app.websocket("/api/v1/ws/comments/{store_id}")
async def ws_comments(websocket: WebSocket, store_id: str):
    await websocket_endpoint(websocket, store_id)


# ─── Health & Info ───

@app.get("/", tags=["System"])
async def root():
    return {
        "name": "Agentischer Document Store",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["System"])
async def health():
    from app.search.engine import search_engine, embedding_client
    from app.services.storage_manager import get_storage_stats
    storage = get_storage_stats()
    return {
        "status": "healthy",
        "search_index_size": search_engine.index_size,
        "search_index_ready": search_engine.index_ready,
        "semantic_mode": "embeddings" if search_engine._use_embeddings else "tfidf",
        "embeddings_available": embedding_client.available,
        "database": "connected",
        "storage_used_mb": storage["app_used_mb"],
        "storage_percent": storage["usage_percent"],
    }


@app.get("/api/v1/system/info", tags=["System"])
async def system_info():
    """System-Informationen und Konfiguration."""
    from app.search.engine import search_engine
    return {
        "version": "1.0.0",
        "language": settings.primary_language,
        "supported_formats": settings.supported_formats,
        "search": {
            "index_size": search_engine.index_size,
            "bm25_weight": settings.bm25_weight,
            "semantic_weight": settings.semantic_weight,
            "chunk_size": settings.chunk_size,
            "chunk_overlap": settings.chunk_overlap,
        },
        "embedding": {
            "model": settings.embedding_model,
            "dimensions": settings.embedding_dim,
        },
        "limits": {
            "max_upload_size_mb": settings.max_upload_size_mb,
            "max_search_results": settings.max_search_results,
        },
    }
