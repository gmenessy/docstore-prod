#!/bin/sh
# ═══════════════════════════════════════════════════════════════
# Runtime-Config-Injection fuer Frontend
# Ersetzt __API_BASE__ und __API_KEY__ in der index.html
# ═══════════════════════════════════════════════════════════════
set -e

INDEX_HTML="/usr/share/nginx/html/index.html"

if [ -f "$INDEX_HTML" ]; then
    # Default-Werte wenn nicht gesetzt (via Docker-Compose env)
    API_BASE="${DOCSTORE_API_BASE:-/api/v1}"
    API_KEY="${DOCSTORE_API_KEY:-}"

    # In-place Ersetzung
    sed -i "s|__API_BASE__|${API_BASE}|g" "$INDEX_HTML"
    sed -i "s|__API_KEY__|${API_KEY}|g" "$INDEX_HTML"

    echo "[entrypoint] Runtime-Config gesetzt: API_BASE=${API_BASE}, API_KEY=$([ -n "$API_KEY" ] && echo "***" || echo "(leer)")"
fi
