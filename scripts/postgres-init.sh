#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# PostgreSQL-Initialisierung fuer Agentischer Document Store
# Wird beim ersten Start vom offiziellen postgres-Image ausgefuehrt
# ═══════════════════════════════════════════════════════════════
set -e

echo "[postgres-init] Applying extensions and performance tuning..."

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-'EOSQL'
    -- Extensions fuer Performance
    CREATE EXTENSION IF NOT EXISTS pg_trgm;        -- Trigram-Suche fuer Text
    CREATE EXTENSION IF NOT EXISTS btree_gin;      -- GIN-Indizes fuer Jsonb + Text

    -- Conservative Performance-Settings
    -- (SQLAlchemy erstellt die Tabellen beim ersten Backend-Start)
    ALTER DATABASE docstore SET log_min_duration_statement = '500ms';
    ALTER DATABASE docstore SET work_mem = '16MB';
    ALTER DATABASE docstore SET maintenance_work_mem = '128MB';
EOSQL

echo "[postgres-init] Setup abgeschlossen."
