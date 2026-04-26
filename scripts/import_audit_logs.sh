#!/bin/bash
# Importiere alte JSONL-Audit-Logs in die Datenbank

set -e

echo "=========================================="
echo "Audit-Log Migration: JSONL → PostgreSQL"
echo "=========================================="
echo ""

# Farben
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Prüfe ob .env existiert
if [ ! -f .env ]; then
    echo -e "${RED}Fehler: .env Datei nicht gefunden${NC}"
    exit 1
fi

# Prüfe ob data/audit Verzeichnis existiert
if [ ! -d "data/audit" ]; then
    echo -e "${YELLOW}Keine alten Audit-Logs gefunden (data/audit existiert nicht)${NC}"
    echo "Migration wird übersprungen."
    exit 0
fi

# Zähle JSONL-Files
JSONL_COUNT=$(find data/audit -name "audit_*.jsonl" 2>/dev/null | wc -l | tr -d ' ')

if [ "$JSONL_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}Keine JSONL-Files gefunden${NC}"
    echo "Migration wird übersprungen."
    exit 0
fi

echo -e "${YELLOW}Gefundene JSONL-Files: $JSONL_COUNT${NC}"
echo ""

# Backup erstellen
echo -e "${YELLOW}Erstelle Backup...${NC}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="backups/pre-audit-migration-$TIMESTAMP"
mkdir -p "$BACKUP_DIR"

# JSONL-Files sichern
cp -r data/audit "$BACKUP_DIR/"

echo -e "${GREEN}✓ Backup erstellt: $BACKUP_DIR${NC}"
echo ""

# Python-Script für Import erstellen
cat > /tmp/import_audit_logs.py << 'EOFPYTHON'
import sys
import json
from pathlib import Path
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# App importieren
sys.path.insert(0, '/app')

from app.models.comments import AuditLog
from app.models.database import Base
from app.core.config import settings


async def import_jsonl_logs():
    """Importiert JSONL-Logs in die Datenbank"""

    # Database Engine erstellen
    engine = create_async_engine(settings.database_url, echo=False)
    async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    audit_dir = Path("data/audit")
    imported_count = 0
    error_count = 0
    skipped_count = 0

    print(f"Importiere Audit-Logs aus: {audit_dir}")

    async with async_session_maker() as session:
        # Alle JSONL-Files importieren
        for jsonl_file in sorted(audit_dir.glob("audit_*.jsonl")):
            print(f"Verarbeite: {jsonl_file.name}")

            try:
                with open(jsonl_file, 'r') as f:
                    for line_num, line in enumerate(f, 1):
                        if not line.strip():
                            continue

                        try:
                            log_entry = json.loads(line)

                            # Prüfen ob Log bereits in DB existiert
                            existing = await session.execute(
                                select(AuditLog).where(AuditLog.id == log_entry.get("id"))
                            )
                            if existing.scalar_one_or_none():
                                skipped_count += 1
                                continue

                            # AuditLog erstellen
                            audit_log = AuditLog(
                                id=log_entry.get("id"),
                                store_id=log_entry.get("store_id"),
                                user_id=log_entry.get("user_id"),
                                action=log_entry.get("action"),
                                resource_type=log_entry.get("resource_type"),
                                resource_id=log_entry.get("resource_id"),
                                changes=log_entry.get("changes"),
                                ip_address=log_entry.get("ip_address"),
                                user_agent=log_entry.get("user_agent"),
                                metadata=log_entry.get("metadata"),
                                created_at=datetime.fromisoformat(log_entry.get("created_at", datetime.utcnow().isoformat())),
                            )

                            session.add(audit_log)
                            imported_count += 1

                            # Alle 100 Logs committen
                            if imported_count % 100 == 0:
                                await session.commit()
                                print(f"  Importiert: {imported_count} Logs")

                        except json.JSONDecodeError as e:
                            print(f"  Fehler in Zeile {line_num}: {e}")
                            error_count += 1
                        except Exception as e:
                            print(f"  Fehler beim Import von Log: {e}")
                            error_count += 1

                # File committen
                await session.commit()
                print(f"  ✓ File abgeschlossen: {jsonl_file.name}")

            except Exception as e:
                print(f"  Fehler beim Verarbeiten von {jsonl_file.name}: {e}")
                error_count += 1

    print(f"\nImport abgeschlossen:")
    print(f"  Importiert: {imported_count}")
    print(f"Übersprungen (bereits in DB): {skipped_count}")
    print(f"  Fehler: {error_count}")

    await engine.dispose()


if __name__ == "__main__":
    import asyncio
    asyncio.run(import_jsonl_logs())
EOFPYTHON

# Python-Script im Backend-Container ausführen
echo -e "${YELLOW}Importiere JSONL-Logs in Datenbank...${NC}"
docker compose exec -T backend python /tmp/import_audit_logs.py

# Cleanup
rm /tmp/import_audit_logs.py

echo ""
echo -e "${GREEN}✓ Import abgeschlossen${NC}"
echo ""

# Optional: JSONL-Files nach erfolgreichem Import archivieren
read -p "Sollen die JSONL-Files nach erfolgreichem Import archiviert werden? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    ARCHIVE_DIR="data/audit/jsonl_archived_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$ARCHIVE_DIR"

    echo -e "${YELLOW}Archiviere JSONL-Files...${NC}"
    mv data/audit/*.jsonl "$ARCHIVE_DIR/" 2>/dev/null || true

    echo -e "${GREEN}✓ JSONL-Files archiviert: $ARCHIVE_DIR${NC}"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}Audit-Log Migration abgeschlossen!${NC}"
echo "=========================================="
echo ""
echo "Nächste Schritte:"
echo "  1. Prüfen Sie die Audit-Logs in der Datenbank:"
echo "     docker compose exec backend psql -U docstore -d docstore -c 'SELECT COUNT(*) FROM audit_logs;'"
echo ""
echo "  2. Verifizieren Sie die Logs im Browser:"
echo "     http://localhost/api/v1/audit/logs?store_id=YOUR_STORE_ID"
echo ""
echo "  3. Optional: JSONL-Backup löschen nach erfolgreicher Verifikation:"
echo "     rm -rf $BACKUP_DIR"
echo ""
