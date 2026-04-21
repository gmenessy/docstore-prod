#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Restore-Skript
# Stellt ein Backup wieder her (DB + Files)
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

if [ $# -ne 1 ]; then
    echo "Usage: $0 <backup-timestamp>"
    echo ""
    echo "Beispiel: $0 20260417-140530"
    echo ""
    echo "Verfuegbare Backups:"
    ls -1 backups/docstore-*-db.dump 2>/dev/null | sed 's|.*/docstore-||; s|-db.dump||' || echo "  (keine)"
    exit 1
fi

TIMESTAMP="$1"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
DB_DUMP="$BACKUP_DIR/docstore-${TIMESTAMP}-db.dump"
FILES_TAR="$BACKUP_DIR/docstore-${TIMESTAMP}-files.tar.gz"

# Validierung
[ -f "$DB_DUMP" ] || { echo "FEHLER: $DB_DUMP nicht gefunden" >&2; exit 1; }
[ -f "$FILES_TAR" ] || { echo "FEHLER: $FILES_TAR nicht gefunden" >&2; exit 1; }

echo "═══ Restore: $TIMESTAMP ═══"
echo ""
echo "  DB-Dump:  $(du -h "$DB_DUMP" | cut -f1)"
echo "  Files:    $(du -h "$FILES_TAR" | cut -f1)"
echo ""
read -rp "ACHTUNG: Aktuelle Daten werden ueberschrieben. Fortfahren? (ja/nein): " confirm
[ "$confirm" = "ja" ] || { echo "Abgebrochen."; exit 0; }

# Backend stoppen (DB/Files bleiben verfuegbar)
echo ""
echo "[1/4] Backend stoppen..."
docker compose stop backend worker frontend 2>/dev/null || true

# 1. Datenbank wiederherstellen
echo "[2/4] Datenbank wiederherstellen..."
docker compose exec -T postgres dropdb -U docstore --if-exists docstore
docker compose exec -T postgres createdb -U docstore docstore
docker compose exec -T postgres pg_restore \
    -U docstore \
    -d docstore \
    --no-owner \
    --no-acl \
    < "$DB_DUMP"

# 2. Dateien zurueckspielen
echo "[3/4] Dateien zurueckspielen..."
docker run --rm \
    -v docstore-prod_backend_uploads:/uploads \
    -v docstore-prod_backend_outputs:/outputs \
    -v "$(pwd)/$BACKUP_DIR":/backup:ro \
    alpine:latest \
    sh -c "cd / && tar xzf /backup/docstore-${TIMESTAMP}-files.tar.gz"

# 3. Backend + Frontend starten
echo "[4/4] Services starten..."
docker compose up -d backend frontend

echo ""
echo "═══ Restore erfolgreich ═══"
echo "Backend-Status: docker compose ps"
