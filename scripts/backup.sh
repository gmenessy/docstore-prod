#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Backup-Skript
# Sichert PostgreSQL-DB + alle persistenten Volumes
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Config
BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_NAME="docstore-${TIMESTAMP}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

# .env laden
if [ -f .env ]; then
    # shellcheck source=/dev/null
    source .env
else
    echo "FEHLER: .env nicht gefunden" >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"

echo "═══ Backup: $BACKUP_NAME ═══"

# 1. PostgreSQL-Dump
echo "[1/3] PostgreSQL-Dump..."
docker compose exec -T postgres pg_dump \
    -U docstore \
    -d docstore \
    --format=custom \
    --compress=9 \
    > "$BACKUP_DIR/${BACKUP_NAME}-db.dump"
echo "    → $(du -h "$BACKUP_DIR/${BACKUP_NAME}-db.dump" | cut -f1)"

# 2. Upload-Volume sichern
echo "[2/3] Uploads und Outputs sichern..."
docker run --rm \
    -v docstore-prod_backend_uploads:/uploads:ro \
    -v docstore-prod_backend_outputs:/outputs:ro \
    -v "$(pwd)/$BACKUP_DIR":/backup \
    alpine:latest \
    tar czf "/backup/${BACKUP_NAME}-files.tar.gz" -C / uploads outputs
echo "    → $(du -h "$BACKUP_DIR/${BACKUP_NAME}-files.tar.gz" | cut -f1)"

# 3. Config mitsichern (ohne .env Secrets!)
echo "[3/3] Konfiguration..."
tar czf "$BACKUP_DIR/${BACKUP_NAME}-config.tar.gz" \
    docker-compose.yml \
    .env.example \
    scripts/ \
    frontend/nginx.conf \
    2>/dev/null || true
echo "    → $(du -h "$BACKUP_DIR/${BACKUP_NAME}-config.tar.gz" | cut -f1)"

# Alte Backups loeschen
echo ""
echo "[cleanup] Backups aelter als ${RETENTION_DAYS} Tage entfernen..."
find "$BACKUP_DIR" -name "docstore-*" -type f -mtime +${RETENTION_DAYS} -print -delete || true

echo ""
echo "═══ Backup erfolgreich ═══"
echo "Dateien: $BACKUP_DIR/${BACKUP_NAME}-*"
ls -lh "$BACKUP_DIR/${BACKUP_NAME}-"* 2>/dev/null || true
