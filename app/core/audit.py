"""
Audit-Logging Middleware für DSGVO-Konformität.

Protokolliert alle relevanten Aktionen im System:
- Dokument-Upload, -Änderungen, -Löschung
- Wiki-Änderungen
- Chat-Anfragen
- User-Logins
- Export-Aktivitäten

Jedes Log enthält: User, Action, Resource, Changes, IP, User-Agent, Timestamp
"""
import logging
import uuid
from datetime import datetime
from typing import Optional, Any
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.database import gen_id

logger = logging.getLogger(__name__)


# ─── Audit-Log Actions ───
class AuditAction:
    """Kategorisierte Audit-Aktionen"""
    # Dokument-Aktionen
    DOC_UPLOAD = "document.upload"
    DOC_UPDATE = "document.update"
    DOC_DELETE = "document.delete"
    DOC_VIEW = "document.view"
    DOC_EXPORT = "document.export"

    # Wiki-Aktionen
    WIKI_CREATE = "wiki.create"
    WIKI_UPDATE = "wiki.update"
    WIKI_DELETE = "wiki.delete"
    WIKI_VIEW = "wiki.view"
    WIKI_INGEST = "wiki.ingest"

    # Chat-Aktionen
    CHAT_CREATE = "chat.create"
    CHAT_VIEW = "chat.view"

    # Store-Aktionen
    STORE_CREATE = "store.create"
    STORE_UPDATE = "store.update"
    STORE_DELETE = "store.delete"
    STORE_VIEW = "store.view"

    # Skill-Aktionen
    SKILL_EXECUTE = "skill.execute"

    # User-Aktionen
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_FAILED_LOGIN = "user.failed_login"

    # System-Aktionen
    SYSTEM_BACKUP = "system.backup"
    SYSTEM_RESTORE = "system.restore"
    SYSTEM_CONFIG_CHANGE = "system.config_change"


class AuditLogger:
    """Zentraler Audit-Logger für alle System-Aktionen"""

    def __init__(self):
        self._enabled = True

    async def log(
        self,
        db: AsyncSession,
        action: str,
        store_id: str,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        changes: Optional[dict] = None,
        request: Optional[Request] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """
        Protokolliert eine Aktion im Audit-Log.

        Returns:
            log_id: Die ID des erstellten Audit-Logs
        """
        if not self._enabled:
            return None

        try:
            # Audit-Log Datensatz erstellen
            log_entry = {
                "id": gen_id(),
                "action": action,
                "store_id": store_id,
                "user_id": user_id or "anonymous",
                "resource_type": resource_type,
                "resource_id": resource_id,
                "changes": changes or {},
                "ip_address": self._extract_ip(request),
                "user_agent": self._extract_user_agent(request),
                "metadata": metadata or {},
                "created_at": datetime.utcnow().isoformat(),
            }

            # In Datenbank speichern (asynchron für Performance)
            await self._persist_log(db, log_entry)

            logger.info(f"Audit: {action} by {user_id} on {resource_type}/{resource_id}")
            return log_entry["id"]

        except Exception as e:
            logger.error(f"Audit-Log fehlgeschlagen: {e}")
            return None

    async def _persist_log(self, db: AsyncSession, log_entry: dict):
        """Persistiert Audit-Log in Datenbank"""
        # TODO: Implementieren mit eigener Audit-Tabelle
        # Für jetzt: JSON-Log-Datei als Fallback
        import json
        from pathlib import Path

        audit_dir = Path("data/audit")
        audit_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        log_file = audit_dir / f"audit_{date_str}.jsonl"

        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

    def _extract_ip(self, request: Optional[Request]) -> Optional[str]:
        """Extrahiert IP-Adresse aus Request"""
        if not request:
            return None

        # Versuche verschiedene Header (Proxy-Support)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        return request.client.host if request.client else None

    def _extract_user_agent(self, request: Optional[Request]) -> Optional[str]:
        """Extrahiert User-Agent aus Request"""
        if not request:
            return None
        return request.headers.get("User-Agent", "Unknown")

    async def query_logs(
        self,
        db: AsyncSession,
        store_id: str,
        action: Optional[str] = None,
        user_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 1000,
    ) -> list[dict]:
        """
        Fragt Audit-Logs ab (für Compliance-Reports).

        Returns:
            List von Audit-Log Einträgen
        """
        # TODO: Implementieren mit Datenbank-Query
        # Für jetzt: JSON-Files lesen
        import json
        from pathlib import Path

        audit_dir = Path("data/audit")
        logs = []

        if not audit_dir.exists():
            return logs

        # Alle Audit-Files der letzten 30 Tage lesen
        for log_file in sorted(audit_dir.glob("audit_*.jsonl"), reverse=True):
            try:
                with open(log_file, "r") as f:
                    for line in f:
                        if not line.strip():
                            continue

                        log_entry = json.loads(line)

                        # Filter anwenden
                        if log_entry.get("store_id") != store_id:
                            continue
                        if action and log_entry.get("action") != action:
                            continue
                        if user_id and log_entry.get("user_id") != user_id:
                            continue

                        logs.append(log_entry)

                        if len(logs) >= limit:
                            break

                if len(logs) >= limit:
                    break

            except Exception as e:
                logger.error(f"Fehler beim Lesen von {log_file}: {e}")

        return logs


# ─── Singleton Instance ───
audit_logger = AuditLogger()


# ─── FastAPI Dependency ───
async def get_audit_logger():
    """Dependency für FastAPI Endpoints"""
    return audit_logger


# ─── Compliance Metrics ───
async def get_compliance_metrics(
    db: AsyncSession,
    store_id: str,
    days: int = 30,
) -> dict:
    """
    Berechnet Compliance-Metriken für einen Store.

    Returns:
        Dict mit Metriken:
        - total_actions: Gesamtzahl der Aktionen
        - unique_users: Anzahl unterschiedlicher User
        - document_accesses: Dokument-Zugriffe
        - wiki_changes: Wiki-Änderungen
        - export_activity: Export-Aktivitäten
        - failed_logins: Fehlgeschlagene Logins
    """
    logs = await audit_logger.query_logs(
        db=db,
        store_id=store_id,
        limit=10000,
    )

    # Metriken berechnen
    metrics = {
        "period_days": days,
        "total_actions": len(logs),
        "unique_users": len(set(log.get("user_id") for log in logs)),
        "document_actions": len([l for l in logs if l.get("resource_type") == "document"]),
        "wiki_actions": len([l for l in logs if l.get("resource_type") == "wiki_page"]),
        "exports": len([l for l in logs if l.get("action") in [
            AuditAction.DOC_EXPORT, "export.pptx", "export.docx", "export.pdf"
        ]]),
        "failed_logins": len([l for l in logs if l.get("action") == AuditAction.USER_FAILED_LOGIN]),
        "most_active_users": _get_most_active_users(logs),
        "action_breakdown": _get_action_breakdown(logs),
    }

    return metrics


def _get_most_active_users(logs: list[dict], limit: int = 10) -> list[dict]:
    """Berechnet die aktivsten User"""
    user_counts = {}
    for log in logs:
        user_id = log.get("user_id", "anonymous")
        user_counts[user_id] = user_counts.get(user_id, 0) + 1

    sorted_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)
    return [{"user_id": user, "actions": count} for user, count in sorted_users[:limit]]


def _get_action_breakdown(logs: list[dict]) -> dict:
    """Berechnet die Verteilung der Aktionen"""
    action_counts = {}
    for log in logs:
        action = log.get("action", "unknown")
        action_counts[action] = action_counts.get(action, 0) + 1

    return action_counts