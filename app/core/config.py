"""
Agentischer Document Store – Konfiguration
On-Premise, DSGVO-konform, keine Cloud-API-Calls.

Alle Parameter über Umgebungsvariablen konfigurierbar (Docker-ready).
Prefix: DOCSTORE_
"""
import os
from pathlib import Path
from dataclasses import dataclass, field


def _env(key: str, default: str = "") -> str:
    """Umgebungsvariable lesen mit DOCSTORE_ Prefix."""
    return os.environ.get(f"DOCSTORE_{key}", os.environ.get(key, default))


def _env_int(key: str, default: int) -> int:
    val = _env(key, "")
    return int(val) if val else default


def _env_float(key: str, default: float) -> float:
    val = _env(key, "")
    return float(val) if val else default


def _env_list(key: str, default: list) -> list:
    val = _env(key, "")
    return [s.strip() for s in val.split(",") if s.strip()] if val else default


# ─── Pfade ───
BASE_DIR = Path(_env("BASE_DIR", str(Path(__file__).resolve().parent.parent)))
DATA_DIR = Path(_env("DATA_DIR", str(BASE_DIR / "data")))
UPLOAD_DIR = DATA_DIR / "uploads"
STORES_DIR = DATA_DIR / "stores"
DB_PATH = DATA_DIR / "docstore.db"

# Verzeichnisse anlegen
for d in [DATA_DIR, UPLOAD_DIR, STORES_DIR]:
    d.mkdir(parents=True, exist_ok=True)


@dataclass
class Settings:
    """
    Zentrale Anwendungskonfiguration.

    Jeder Parameter ist über Umgebungsvariablen steuerbar:
        DOCSTORE_DATABASE_URL, DOCSTORE_REDIS_URL, DOCSTORE_CHUNK_SIZE, etc.
    """

    # ── Datenbank ──
    database_url: str = _env("DATABASE_URL", f"sqlite+aiosqlite:///{DB_PATH}")

    # ── Redis (Cache + Celery) ──
    redis_url: str = _env("REDIS_URL", "redis://localhost:6379/0")

    # ── Qdrant (Vektor-DB) ──
    qdrant_url: str = _env("QDRANT_URL", "http://localhost:6333")
    qdrant_collection: str = _env("QDRANT_COLLECTION", "docstore")

    # ── Ollama (LLM / Embeddings) ──
    ollama_url: str = _env("OLLAMA_URL", "http://localhost:11434")
    ollama_model: str = _env("OLLAMA_MODEL", "llama3.2")
    ollama_embed_model: str = _env("OLLAMA_EMBED_MODEL", "nomic-embed-text")

    # ── Dateien ──
    upload_dir: Path = UPLOAD_DIR
    stores_dir: Path = STORES_DIR
    max_upload_size_mb: int = _env_int("MAX_UPLOAD_SIZE_MB", 100)

    # ── Chunking ──
    chunk_size: int = _env_int("CHUNK_SIZE", 512)
    chunk_overlap: int = _env_int("CHUNK_OVERLAP", 64)
    min_chunk_length: int = _env_int("MIN_CHUNK_LENGTH", 50)

    # ── Suche ──
    bm25_weight: float = _env_float("BM25_WEIGHT", 0.4)
    semantic_weight: float = _env_float("SEMANTIC_WEIGHT", 0.6)
    max_search_results: int = _env_int("MAX_SEARCH_RESULTS", 50)

    # ── Embedding ──
    embedding_model: str = _env("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
    embedding_dim: int = _env_int("EMBEDDING_DIM", 384)

    # ── NER / Extraktion ──
    supported_formats: list = field(default_factory=lambda: [
        ".pdf", ".doc", ".docx", ".ppt", ".pptx",
        ".md", ".txt", ".xml", ".rtf", ".xlsx", ".xls",
    ])

    # ── Sprache ──
    primary_language: str = _env("LANGUAGE", "de")

    # ── Server ──
    host: str = _env("HOST", "0.0.0.0")
    port: int = _env_int("PORT", 8000)
    workers: int = _env_int("WORKERS", 4)
    cors_origins: list = field(default_factory=lambda: _env_list("CORS_ORIGINS", ["*"]))

    # ── Logging ──
    log_level: str = _env("LOG_LEVEL", "INFO")

    # ── Storage-Limits ──
    max_store_size_mb: int = _env_int("MAX_STORE_SIZE_MB", 500)
    max_total_size_mb: int = _env_int("MAX_TOTAL_SIZE_MB", 5000)
    file_ttl_days: int = _env_int("FILE_TTL_DAYS", 30)
    upload_ttl_hours: int = _env_int("UPLOAD_TTL_HOURS", 24)

    # ── Proxy ──
    http_proxy: str = _env("HTTP_PROXY", "")
    https_proxy: str = _env("HTTPS_PROXY", "")
    no_proxy: str = _env("NO_PROXY", "localhost,127.0.0.1,postgres,redis,qdrant,ollama")


settings = Settings()
