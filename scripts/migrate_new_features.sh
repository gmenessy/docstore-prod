#!/bin/bash
# Automatisches Deployment der neuen Features

set -e  # Bei Fehlern abbrechen

echo "=========================================="
echo "Agentischer Document Store - Feature Deployment"
echo "=========================================="
echo ""

# Farben definieren
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ─── Prerequisites ───
echo -e "${YELLOW}Prüfe Prerequisites...${NC}"

# Prüfe ob Docker läuft
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Fehler: Docker läuft nicht${NC}"
    echo "Bitte starten Sie Docker zuerst"
    exit 1
fi

echo -e "${GREEN}✓ Docker läuft${NC}"

# Prüfe ob .env existiert
if [ ! -f .env ]; then
    echo -e "${RED}Fehler: .env Datei nicht gefunden${NC}"
    echo "Bitte führen Sie zuerst 'make init' aus"
    exit 1
fi

echo -e "${GREEN}✓ .env Datei gefunden${NC}"

# ─── Backup erstellen ───
echo ""
echo -e "${YELLOW}Erstelle Backup...${NC}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="backups/pre-deployment-$TIMESTAMP"

mkdir -p "$BACKUP_DIR"

# DB-Backup
docker compose exec -T postgres pg_dump -U docstore docstore > "$BACKUP_DIR/database.sql"

echo -e "${GREEN}✓ Backup erstellt: $BACKUP_DIR${NC}"

# ─── Images rebuilden ───
echo ""
echo -e "${YELLOW}Rebuild Images...${NC}"
docker compose build backend

echo -e "${GREEN}✓ Images gebuildet${NC}"

# ─── Services restarten ───
echo ""
echo -e "${YELLOW}Restart Services...${NC}"
docker compose up -d backend postgres

echo -e "${GREEN}✓ Services gestartet${NC}"

# ─── Warten auf DB ───
echo ""
echo -e "${YELLOW}Warte auf Datenbank...${NC}"
until docker compose exec -T postgres pg_isready -U docstore > /dev/null 2>&1; do
    echo "Datenbank noch nicht ready..."
    sleep 2
done

echo -e "${GREEN}✓ Datenbank ready${NC}"

# ─── Migrationen ausführen ───
echo ""
echo -e "${YELLOW}Führe Database-Migrationen aus...${NC}"

# Migration 001: Comments Collaboration
echo "Migration 001: Comments & Collaboration..."
docker compose exec -T backend alembic upgrade 001_comments_collaboration

# Migration 002: Notification Logging
echo "Migration 002: Notification Logging..."
docker compose exec -T backend alembic upgrade 002

echo -e "${GREEN}✓ Migrationen ausgeführt${NC}"

# ─── Tests ausführen ───
echo ""
echo -e "${YELLOW}Führe Tests aus...${NC}"

# Tests nur für neue Features
docker compose exec -T backend python -m pytest tests/test_new_features.py -v --tb=short

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Alle Tests bestanden${NC}"
else
    echo -e "${RED}✗ Tests fehlgeschlagen${NC}"
    echo "Rollback wird ausgeführt..."

    # Rollback
    docker compose exec -T backend alembic downgrade base

    echo "Bitte prüfen Sie die Fehler und beheben Sie diese"
    exit 1
fi

# ─── Health Check ───
echo ""
echo -e "${YELLOW}Health Check...${NC}"

sleep 5  # Warten für Services

HEALTH=$(curl -s http://localhost:8000/health | jq -r '.status')

if [ "$HEALTH" = "healthy" ]; then
    echo -e "${GREEN}✓ System ist healthy${NC}"
else
    echo -e "${RED}✗ System ist nicht healthy${NC}"
    echo "Bitte prüfen Sie die Logs: docker compose logs backend"
    exit 1
fi

# ─── Summary ───
echo ""
echo "=========================================="
echo -e "${GREEN}Deployment erfolgreich!${NC}"
echo "=========================================="
echo ""
echo "Neue Features:"
echo "  ✓ Wiki-Freshness echte Berechnung"
echo "  ✓ Notification Rate-Limiting"
echo "  ✓ Notification Logging"
echo ""
echo "API-Endpoints:"
echo "  GET  /api/v1/wiki-curator/quality/{store_id}/{page_id}"
echo "  GET  /api/v1/wiki-curator/candidates/{store_id}"
echo "  POST /api/v1/wiki-curator/refresh/{store_id}/{page_id}"
echo "  GET  /api/v1/metrics/overview/{store_id}"
echo "  GET  /api/v1/compliance/dashboard"
echo ""
echo "Backup: $BACKUP_DIR"
echo ""
echo "Bitte prüfen Sie die neuen Features im Browser:"
echo "  http://localhost"
echo ""
