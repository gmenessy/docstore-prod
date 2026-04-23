"""
SQLAlchemy Modelle für Kommentare & Kollaboration.
"""
from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, Integer, Time, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.database import Base


class Comment(Base):
    """Kommentar-Modell"""
    __tablename__ = "comments"

    id = Column(UUID(as_uuid=True), primary_key=True)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id"), nullable=False)
    user_id = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)

    # Resource-Verknüpfungen (nur eine darf gesetzt sein)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True)
    wiki_page_id = Column(UUID(as_uuid=True), ForeignKey("wiki_pages.id"), nullable=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("plan_tasks.id"), nullable=True)

    # Thread-Struktur
    parent_id = Column(UUID(as_uuid=True), ForeignKey("comments.id"), nullable=True)

    # Metadaten
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    edited_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "store_id": str(self.store_id),
            "user_id": self.user_id,
            "content": self.content,
            "document_id": str(self.document_id) if self.document_id else None,
            "wiki_page_id": str(self.wiki_page_id) if self.wiki_page_id else None,
            "task_id": str(self.task_id) if self.task_id else None,
            "parent_id": str(self.parent_id) if self.parent_id else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "edited_at": self.edited_at.isoformat() if self.edited_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class WebSocketConnection(Base):
    """WebSocket-Verbindungs-Tracking"""
    __tablename__ = "ws_connections"

    id = Column(UUID(as_uuid=True), primary_key=True)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id"), nullable=False)
    user_id = Column(String(255), nullable=False)
    connection_id = Column(String(255), unique=True, nullable=False)
    connected_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    last_ping = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    disconnected_at = Column(DateTime(timezone=True), nullable=True)
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6-kompatibel

    is_active = Column(Boolean, default=True, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "store_id": str(self.store_id),
            "user_id": self.user_id,
            "connection_id": self.connection_id,
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "last_ping": self.last_ping.isoformat() if self.last_ping else None,
            "is_active": self.is_active,
        }


class UserPresence(Base):
    """User-Presence pro Store"""
    __tablename__ = "user_presence"

    id = Column(UUID(as_uuid=True), primary_key=True)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id"), nullable=False)
    user_id = Column(String(255), nullable=False)

    status = Column(String(50), default="online", nullable=False)  # online, away, offline
    last_activity = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    current_document_id = Column(UUID(as_uuid=True), nullable=True)
    current_wiki_page_id = Column(UUID(as_uuid=True), nullable=True)

    session_id = Column(String(255), nullable=True)
    tab_id = Column(String(255), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "store_id": str(self.store_id),
            "user_id": self.user_id,
            "status": self.status,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "current_document_id": str(self.current_document_id) if self.current_document_id else None,
            "current_wiki_page_id": str(self.current_wiki_page_id) if self.current_wiki_page_id else None,
        }


class NotificationPreference(Base):
    """Notification-Präferenzen pro User"""
    __tablename__ = "notification_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id"), nullable=False)
    user_id = Column(String(255), nullable=False)

    # E-Mail-Präferenzen
    email_enabled = Column(Boolean, default=True, nullable=False)
    email_comment_mentions = Column(Boolean, default=True, nullable=False)
    email_comment_replies = Column(Boolean, default=True, nullable=False)
    email_wiki_changes = Column(Boolean, default=False, nullable=False)
    email_task_assignments = Column(Boolean, default=True, nullable=False)
    email_daily_summary = Column(Boolean, default=False, nullable=False)

    # In-App-Präferenzen
    inapp_enabled = Column(Boolean, default=True, nullable=False)
    inapp_comment_replies = Column(Boolean, default=True, nullable=False)
    inapp_wiki_updates = Column(Boolean, default=False, nullable=False)
    inapp_task_changes = Column(Boolean, default=True, nullable=False)

    # Frequenz-Limits
    max_emails_per_day = Column(Integer, default=50, nullable=False)
    max_notifications_per_hour = Column(Integer, default=20, nullable=False)

    # Timing-Präferenzen
    quiet_hours_start = Column(Time, nullable=True)
    quiet_hours_end = Column(Time, nullable=True)
    timezone = Column(String(100), default="Europe/Berlin", nullable=False)

    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "store_id": str(self.store_id),
            "user_id": self.user_id,
            "email_enabled": self.email_enabled,
            "email_comment_mentions": self.email_comment_mentions,
            "email_comment_replies": self.email_comment_replies,
            "email_wiki_changes": self.email_wiki_changes,
            "email_task_assignments": self.email_task_assignments,
            "email_daily_summary": self.email_daily_summary,
            "inapp_enabled": self.inapp_enabled,
            "inapp_comment_replies": self.inapp_comment_replies,
            "inapp_wiki_updates": self.inapp_wiki_updates,
            "inapp_task_changes": self.inapp_task_changes,
            "max_emails_per_day": self.max_emails_per_day,
            "max_notifications_per_hour": self.max_notifications_per_hour,
            "quiet_hours_start": self.quiet_hours_start.strftime("%H:%M") if self.quiet_hours_start else None,
            "quiet_hours_end": self.quiet_hours_end.strftime("%H:%M") if self.quiet_hours_end else None,
            "timezone": self.timezone,
        }


class NotificationLog(Base):
    """Protokollierung gesendeter Notifications für Rate-Limiting"""
    __tablename__ = "notification_logs"

    id = Column(UUID(as_uuid=True), primary_key=True)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id"), nullable=False)
    user_id = Column(String(255), nullable=False, index=True)

    # Notification-Details
    notification_type = Column(String(100), nullable=False, index=True)
    channel = Column(String(50), nullable=False)  # "email" oder "inapp"

    # Resource-Kontext
    resource_type = Column(String(100), nullable=True)  # "document", "wiki_page", "task"
    resource_id = Column(String(255), nullable=True)

    # Status
    status = Column(String(50), default="sent", nullable=False)  # "sent", "failed", "skipped"
    error_message = Column(Text, nullable=True)

    # Metadaten
    metadata = Column(Text, nullable=True)  # JSON-encoded

    # Timing
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False, index=True)

    # Indexes für Rate-Limit Queries
    __table_args__ = (
        Index('idx_notification_user_time', 'user_id', 'created_at'),
        Index('idx_notification_type_time', 'notification_type', 'created_at'),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "store_id": str(self.store_id),
            "user_id": self.user_id,
            "notification_type": self.notification_type,
            "channel": self.channel,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }