# syntax=docker/dockerfile:1.6
# ═══════════════════════════════════════════════════════════════
# Agentischer Document Store — Backend Dockerfile (Production)
# Multi-Stage · Non-Root · Healthcheck · OCR+PDF Extraction
# ═══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────
# Stage 1: Builder — kompiliert Python-Dependencies
# ─────────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Proxy-Support fuer Corporate-Umgebungen (optional)
ARG HTTP_PROXY=""
ARG HTTPS_PROXY=""
ARG NO_PROXY="localhost,127.0.0.1"
ENV http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY} \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build-Tools und Header
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libffi-dev \
        libssl-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Virtual Environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Dependencies installieren
WORKDIR /build
COPY pyproject.toml ./

# Kern-Dependencies + optionale Extras (OCR optional, Vectors nicht noetig wenn Qdrant extern)
RUN pip install --upgrade pip wheel && \
    pip install \
        "fastapi>=0.110.0" \
        "uvicorn[standard]>=0.27.0" \
        "python-multipart>=0.0.9" \
        "sqlalchemy[asyncio]>=2.0.0" \
        "asyncpg>=0.29.0" \
        "aiosqlite>=0.20.0" \
        "aiofiles>=23.2.0" \
        "pdfplumber>=0.11.0" \
        "python-docx>=1.1.0" \
        "python-pptx>=0.6.23" \
        "openpyxl>=3.1.0" \
        "striprtf>=0.0.26" \
        "markdown>=3.5" \
        "beautifulsoup4>=4.12.0" \
        "lxml>=5.0.0" \
        "rank-bm25>=0.2.2" \
        "numpy>=1.26.0" \
        "scikit-learn>=1.4.0" \
        "httpx>=0.27.0" \
        "pydantic>=2.5.0" \
        "pydantic-settings>=2.1.0" \
        "celery[redis]>=5.3.0" \
        "redis>=5.0.0" \
        "slowapi>=0.1.9" \
        "reportlab>=4.0.0"


# ─────────────────────────────────────────────────
# Stage 2: Runtime — minimaler Footprint
# ─────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="Agentischer Document Store" \
      org.opencontainers.image.description="Akte & WissensDB Backend - DSGVO-konform, On-Premise" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.licenses="Proprietary"

# Proxy-Support zur Laufzeit
ARG HTTP_PROXY=""
ARG HTTPS_PROXY=""
ARG NO_PROXY="localhost,127.0.0.1"
ENV http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

# Runtime-Abhaengigkeiten
# - libpq5 fuer PostgreSQL-Client
# - poppler-utils fuer pdfplumber (PDF-Rendering)
# - libmagic1 fuer Dateityp-Erkennung
# - tesseract-ocr-deu fuer deutsche OCR (optional aber empfohlen)
# - curl fuer Healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        libmagic1 \
        poppler-utils \
        tesseract-ocr \
        tesseract-ocr-deu \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Non-Root User
RUN groupadd --system --gid 1000 docstore \
    && useradd --system --uid 1000 --gid docstore --shell /bin/bash --create-home docstore

# Virtual Environment aus Builder uebernehmen
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    TZ=Europe/Berlin

# Applikations-Code
WORKDIR /app
COPY --chown=docstore:docstore app/ ./app/

# Daten-Verzeichnisse mit korrekten Permissions
RUN mkdir -p /app/data /app/uploads /app/outputs /app/logs \
    && chown -R docstore:docstore /app/data /app/uploads /app/outputs /app/logs

# Port
EXPOSE 8000

# Health-Check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# Non-root switch
USER docstore

# Startbefehl: Uvicorn mit Production-Settings
# Workers werden ueber UVICORN_WORKERS gesteuert (Default: 2)
CMD ["sh", "-c", "uvicorn app.main:app \
      --host 0.0.0.0 \
      --port 8000 \
      --workers ${UVICORN_WORKERS:-2} \
      --access-log \
      --log-level ${LOG_LEVEL:-info} \
      --proxy-headers \
      --forwarded-allow-ips='*'"]
