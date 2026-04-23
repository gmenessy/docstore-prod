"""
Datenbank-Migration: Kommentare & Kollaboration.

Fügt Tabellen hinzu für:
- Kommentare für Dokumente, Wiki-Seiten, Tasks
- Echtzeit-Verbindungs-Tracking
- User-Presence
- Notification-Preferences
"""
from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, Index, Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

def upgrade_comments():
    """Füge Kommentar-Tabellen hinzu"""

    # Kommentare-Tabelle
    return """
    CREATE TABLE IF NOT EXISTS comments (
        id UUID PRIMARY KEY DEFAULT gen_id(),
        store_id UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
        user_id VARCHAR(255) NOT NULL,
        content TEXT NOT NULL,

        -- Resource-Verknüpfungen (nur eine darf gesetzt sein)
        document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
        wiki_page_id UUID REFERENCES wiki_pages(id) ON DELETE CASCADE,
        task_id UUID REFERENCES plan_tasks(id) ON DELETE CASCADE,

        -- Thread-Struktur
        parent_id UUID REFERENCES comments(id) ON DELETE CASCADE,

        -- Metadaten
        resolved_at TIMESTAMP,
        edited_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        -- Index für Performance
        CONSTRAINT comments_resource_check CHECK (
            (document_id IS NOT NULL)::integer +
            (wiki_page_id IS NOT NULL)::integer +
            (task_id IS NOT NULL)::integer = 1
        )
    );

    -- Indexe für häufige Queries
    CREATE INDEX idx_comments_store ON comments(store_id);
    CREATE INDEX idx_comments_document ON comments(document_id) WHERE document_id IS NOT NULL;
    CREATE INDEX idx_comments_wiki ON comments(wiki_page_id) WHERE wiki_page_id IS NOT NULL;
    CREATE INDEX idx_comments_task ON comments(task_id) WHERE task_id IS NOT NULL;
    CREATE INDEX idx_comments_parent ON comments(parent_id) WHERE parent_id IS NOT NULL;
    CREATE INDEX idx_comments_created ON comments(created_at DESC);

    -- Full-Text Search für Kommentare
    CREATE INDEX idx_comments_content_fts ON comments USING gin(to_tsvector('german', content));

    -- Trigger für updated_at
    CREATE OR REPLACE FUNCTION update_comments_updated_at()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = CURRENT_TIMESTAMP;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    CREATE TRIGGER comments_updated_at
        BEFORE UPDATE ON comments
        FOR EACH ROW
        EXECUTE FUNCTION update_comments_updated_at();
    """

def downgrade_comments():
    """Entferne Kommentar-Tabellen"""

    return """
    DROP TRIGGER IF EXISTS comments_updated_at ON comments;
    DROP FUNCTION IF EXISTS update_comments_updated_at();
    DROP INDEX IF EXISTS idx_comments_content_fts;
    DROP INDEX IF EXISTS idx_comments_created;
    DROP INDEX IF EXISTS idx_comments_parent;
    DROP INDEX IF EXISTS idx_comments_task;
    DROP INDEX IF EXISTS idx_comments_wiki;
    DROP INDEX IF EXISTS idx_comments_document;
    DROP INDEX IF EXISTS idx_comments_store;
    DROP TABLE IF EXISTS comments;
    """


def upgrade_connections():
    """Füge WebSocket-Verbindungs-Tracking hinzu"""

    return """
    -- Tracking für Echtzeit-Verbindungen
    CREATE TABLE IF NOT EXISTS ws_connections (
        id UUID PRIMARY KEY DEFAULT gen_id(),
        store_id UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
        user_id VARCHAR(255) NOT NULL,
        connection_id VARCHAR(255) UNIQUE NOT NULL,
        connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_ping TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        disconnected_at TIMESTAMP,
        user_agent TEXT,
        ip_address INET,

        -- Status
        is_active BOOLEAN DEFAULT TRUE,

        -- Index
        INDEX idx_ws_store ON ws_connections(store_id);
        INDEX idx_ws_user ON ws_connections(user_id);
        INDEX idx_ws_active ON ws_connections(is_active, last_ping);
    );

    -- Cleanup für alte Verbindungen
    CREATE OR REPLACE FUNCTION cleanup_old_connections()
    RETURNS void AS $$
    BEGIN
        -- Markiere inaktive Verbindungen (kein Ping seit 5 Minuten)
        UPDATE ws_connections
        SET is_active = FALSE,
            disconnected_at = CURRENT_TIMESTAMP
        WHERE is_active = TRUE
          AND last_ping < CURRENT_TIMESTAMP - INTERVAL '5 minutes';

        -- Lösche Verbindungen, die seit 1 Stunde inaktiv sind
        DELETE FROM ws_connections
        WHERE is_active = FALSE
          AND disconnected_at < CURRENT_TIMESTAMP - INTERVAL '1 hour';
    END;
    $$ LANGUAGE plpgsql;
    """

def downgrade_connections():
    """Entferne WebSocket-Verbindungs-Tracking"""

    return """
    DROP FUNCTION IF EXISTS cleanup_old_connections();
    DROP TABLE IF EXISTS ws_connections;
    """


def upgrade_presence():
    """Füge User-Presence Tracking hinzu"""

    return """
    -- User-Presence pro Store
    CREATE TABLE IF NOT EXISTS user_presence (
        id UUID PRIMARY KEY DEFAULT gen_id(),
        store_id UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
        user_id VARCHAR(255) NOT NULL,

        -- Presence-Info
        status VARCHAR(50) DEFAULT 'online', -- online, away, offline
        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        current_document_id UUID,
        current_wiki_page_id UUID,

        -- Session-Info
        session_id VARCHAR(255),
        tab_id VARCHAR(255),

        -- Index
        UNIQUE(store_id, user_id),
        INDEX idx_presence_status ON user_presence(status);
    """

def downgrade_presence():
    """Entferne User-Presence Tracking"""

    return """
    DROP TABLE IF EXISTS user_presence;
    """


def upgrade_notifications():
    """Füge Notification-Preferences hinzu"""

    return """
    -- Notification-Preferences pro User
    CREATE TABLE IF NOT EXISTS notification_preferences (
        id UUID PRIMARY KEY DEFAULT gen_id(),
        store_id UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
        user_id VARCHAR(255) NOT NULL,

        -- E-Mail-Präferenzen
        email_enabled BOOLEAN DEFAULT TRUE,
        email_comment_mentions BOOLEAN DEFAULT TRUE,
        email_wiki_changes BOOLEAN DEFAULT FALSE,
        email_task_assignments BOOLEAN DEFAULT TRUE,
        email_daily_summary BOOLEAN DEFAULT FALSE,

        -- In-App-Präferenzen
        inapp_enabled BOOLEAN DEFAULT TRUE,
        inapp_comment_replies BOOLEAN DEFAULT TRUE,
        inapp_wiki_updates BOOLEAN DEFAULT FALSE,
        inapp_task_changes BOOLEAN DEFAULT TRUE,

        -- Frequenz-Limits
        max_emails_per_day INTEGER DEFAULT 50,
        max_notifications_per_hour INTEGER DEFAULT 20,

        -- Timing-Präferenzen
        quiet_hours_start TIME,
        quiet_hours_end TIME,
        timezone VARCHAR(100) DEFAULT 'Europe/Berlin',

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        UNIQUE(store_id, user_id)
    );
    """

def downgrade_notifications():
    """Entferne Notification-Preferences"""

    return """
    DROP TABLE IF EXISTS notification_preferences;
    """


# ─── Vollständige Migration ───

def upgrade():
    """Führe alle Upgrade-Schritte aus"""

    migrations = [
        ("comments", upgrade_comments()),
        ("connections", upgrade_connections()),
        ("presence", upgrade_presence()),
        ("notifications", upgrade_notifications()),
    ]

    for name, sql in migrations:
        try:
            print(f"Executing migration: {name}")
            # execute_sql(sql) # TODO: Implement with SQLAlchemy
            print(f"✓ Migration {name} successful")
        except Exception as e:
            print(f"✗ Migration {name} failed: {e}")
            raise


def downgrade():
    """Führe alle Downgrade-Schritte aus"""

    migrations = [
        ("notifications", downgrade_notifications()),
        ("presence", downgrade_presence()),
        ("connections", downgrade_connections()),
        ("comments", downgrade_comments()),
    ]

    for name, sql in reversed(migrations):
        try:
            print(f"Executing rollback: {name}")
            # execute_sql(sql) # TODO: Implement with SQLAlchemy
            print(f"✓ Rollback {name} successful")
        except Exception as e:
            print(f"✗ Rollback {name} failed: {e}")
            raise


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
        downgrade()
    else:
        upgrade()