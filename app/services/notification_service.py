"""
E-Mail-Notification Service.

Bietet E-Mail-Benachrichtigungen für:
- Kommentare (Erwähnungen, Antworten)
- Wiki-Änderungen
- Task-Zuweisungen
- Daily Summaries
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, time
from typing import List, Optional
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Store
from app.models.comments import NotificationPreference

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    """E-Mail Nachricht"""
    to: str
    subject: str
    html_body: str
    text_body: str
    reply_to: Optional[str] = None


class NotificationService:
    """Zentraler Notification-Service"""

    def __init__(self):
        self.smtp_host = None
        self.smtp_port = None
        self.smtp_user = None
        self.smtp_password = None
        self.from_email = None
        self._enabled = False

    def configure(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        from_email: str,
    ):
        """Konfiguriere SMTP-Verbindung"""
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_email = from_email
        self._enabled = True

        logger.info(f"E-Mail Service konfiguriert: {smtp_host}:{smtp_port}")

    async def send_notification(
        self,
        db: AsyncSession,
        store_id: str,
        user_id: str,
        notification_type: str,
        data: dict,
        channel: str = "email",
    ) -> bool:
        """
        Sende eine Benachrichtigung an einen User.

        Args:
            channel: "email" oder "inapp"

        Returns:
            True wenn erfolgreich, False sonst
        """
        if not self._enabled and channel == "email":
            logger.warning("E-Mail Service nicht konfiguriert")
            return False

        try:
            # User-Präferenzen laden
            prefs = await self._get_preferences(db, store_id, user_id)

            if not prefs:
                logger.debug(f"Keine Präferenzen für {user_id}")
                return False

            # Prüfen ob Channel aktiviert ist
            if channel == "email" and not prefs.email_enabled:
                logger.debug(f"E-Mail deaktiviert für {user_id}")
                await self._log_notification(
                    db, store_id, user_id, notification_type, data,
                    status="skipped", channel=channel
                )
                return False

            if channel == "inapp" and not prefs.inapp_enabled:
                logger.debug(f"In-App deaktiviert für {user_id}")
                return False

            # Prüfen ob Notification-Type aktiviert ist
            if not self._is_notification_enabled(prefs, notification_type):
                logger.debug(f"{notification_type} deaktiviert für {user_id}")
                await self._log_notification(
                    db, store_id, user_id, notification_type, data,
                    status="skipped", channel=channel
                )
                return False

            # Prüfen ob Quiet Hours aktiv sind
            if self._is_quiet_hours(prefs):
                logger.info(f"Quiet Hours aktiv für {user_id}, Notification verzögert")
                await self._log_notification(
                    db, store_id, user_id, notification_type, data,
                    status="skipped", channel=channel
                )
                return False

            # Prüfen Frequenz-Limits
            if not await self._check_rate_limits(db, prefs, notification_type):
                logger.warning(f"Rate-Limit überschritten für {user_id}")
                await self._log_notification(
                    db, store_id, user_id, notification_type, data,
                    status="skipped", channel=channel
                )
                return False

            # E-Mail erstellen und senden (nur bei email channel)
            if channel == "email":
                email = self._create_email(notification_type, data, prefs)

                if await self._send_email(email):
                    # Versende-Log
                    await self._log_notification(
                        db, store_id, user_id, notification_type, data,
                        status="sent", channel=channel
                    )
                    return True
                else:
                    # Fehler-Log
                    await self._log_notification(
                        db, store_id, user_id, notification_type, data,
                        status="failed", error_message="SMTP error", channel=channel
                    )
                    return False
            else:
                # In-App Notifications werden hier nur geloggt
                await self._log_notification(
                    db, store_id, user_id, notification_type, data,
                    status="sent", channel=channel
                )
                return True

        except Exception as e:
            logger.error(f"Fehler beim Senden der Notification: {e}")
            return False

    async def _get_preferences(
        self,
        db: AsyncSession,
        store_id: str,
        user_id: str,
    ) -> Optional[NotificationPreference]:
        """Hole Notification-Präferenzen für einen User"""
        result = await db.execute(
            select(NotificationPreference)
            .where(NotificationPreference.store_id == store_id)
            .where(NotificationPreference.user_id == user_id)
        )
        return result.scalar_one_or_none()

    def _is_notification_enabled(
        self,
        prefs: NotificationPreference,
        notification_type: str
    ) -> bool:
        """Prüft ob ein Notification-Type aktiviert ist"""
        type_mapping = {
            "comment.mention": prefs.email_comment_mentions,
            "comment.reply": prefs.email_comment_replies,
            "wiki.changed": prefs.email_wiki_changes,
            "task.assigned": prefs.email_task_assignments,
            "daily.summary": prefs.email_daily_summary,
        }
        return type_mapping.get(notification_type, False)

    def _is_quiet_hours(self, prefs: NotificationPreference) -> bool:
        """Prüft ob Quiet Hours aktiv sind"""
        if not prefs.quiet_hours_start or not prefs.quiet_hours_end:
            return False

        now = datetime.now().time()
        start = prefs.quiet_hours_start
        end = prefs.quiet_hours_end

        # Prüfen ob aktuelle Zeit im Quiet-Hours-Intervall liegt
        if start <= end:
            return start <= now <= end
        else:  # Über Mitternacht
            return now >= start or now <= end

    async def _check_rate_limits(
        self,
        db: AsyncSession,
        prefs: NotificationPreference,
        notification_type: str = None,
    ) -> bool:
        """
        Prüft ob Rate-Limits eingehalten werden.

        Rate-Limits:
        - Max emails per day (default: 50)
        - Max notifications per hour (default: 20)

        Returns:
            True wenn Limits eingehalten, False wenn überschritten
        """
        from app.models.comments import NotificationLog
        from datetime import timedelta
        from sqlalchemy import func, and_

        user_id = prefs.user_id

        try:
            # 1. Stündliches Limit prüfen
            one_hour_ago = datetime.now() - timedelta(hours=1)

            hour_result = await db.execute(
                select(func.count(NotificationLog.id))
                .where(NotificationLog.user_id == user_id)
                .where(NotificationLog.created_at >= one_hour_ago)
                .where(NotificationLog.status == "sent")
            )
            hour_count = hour_result.scalar() or 0

            if hour_count >= prefs.max_notifications_per_hour:
                logger.warning(
                    f"Rate-Limit überschritten für {user_id}: "
                    f"{hour_count}/{prefs.max_notifications_per_hour} in letzter Stunde"
                )
                return False

            # 2. Tägliches Limit für E-Mails prüfen
            one_day_ago = datetime.now() - timedelta(days=1)

            day_result = await db.execute(
                select(func.count(NotificationLog.id))
                .where(NotificationLog.user_id == user_id)
                .where(NotificationLog.created_at >= one_day_ago)
                .where(NotificationLog.channel == "email")
                .where(NotificationLog.status == "sent")
            )
            day_count = day_result.scalar() or 0

            if day_count >= prefs.max_emails_per_day:
                logger.warning(
                    f"E-Mail-Limit überschritten für {user_id}: "
                    f"{day_count}/{prefs.max_emails_per_day} in letzter Tag"
                )
                return False

            # Alle Limits eingehalten
            logger.debug(
                f"Rate-Limit OK für {user_id}: "
                f"{hour_count}/{prefs.max_notifications_per_hour} pro Stunde, "
                f"{day_count}/{prefs.max_emails_per_day} pro Tag"
            )
            return True

        except Exception as e:
            logger.error(f"Fehler bei Rate-Limit-Prüfung für {user_id}: {e}")
            # Bei Fehler: konservatives Verhalten (erlauben)
            return True

    def _create_email(
        self,
        notification_type: str,
        data: dict,
        prefs: NotificationPreference,
    ) -> EmailMessage:
        """Erstellt eine E-Mail für einen Notification-Type"""

        templates = {
            "comment.mention": self._create_comment_mention_email,
            "comment.reply": self._create_comment_reply_email,
            "wiki.changed": self._create_wiki_changed_email,
            "task.assigned": self._create_task_assigned_email,
            "daily.summary": self._create_daily_summary_email,
        }

        template_func = templates.get(notification_type)
        if not template_func:
            raise ValueError(f"Unbekannter Notification-Type: {notification_type}")

        return template_func(data, prefs)

    def _create_comment_mention_email(self, data: dict, prefs: NotificationPreference) -> EmailMessage:
        """Erstelle E-Mail für Kommentar-Erwähnung"""
        return EmailMessage(
            to=data.get("user_email"),
            subject=f"💬 Neue Erwähnung in {data.get('store_name')}",
            html_body=self._render_html("comment_mention", data),
            text_body=self._render_text("comment_mention", data),
        )

    def _create_comment_reply_email(self, data: dict, prefs: NotificationPreference) -> EmailMessage:
        """Erstelle E-Mail für Kommentar-Antwort"""
        return EmailMessage(
            to=data.get("user_email"),
            subject=f"💬 Neue Antwort auf deinen Kommentar in {data.get('store_name')}",
            html_body=self._render_html("comment_reply", data),
            text_body=self._render_text("comment_reply", data),
        )

    def _create_wiki_changed_email(self, data: dict, prefs: NotificationPreference) -> EmailMessage:
        """Erstelle E-Mail für Wiki-Änderung"""
        return EmailMessage(
            to=data.get("user_email"),
            subject=f"📝 Wiki-Update in {data.get('store_name')}: {data.get('page_title')}",
            html_body=self._render_html("wiki_changed", data),
            text_body=self._render_text("wiki_changed", data),
        )

    def _create_task_assigned_email(self, data: dict, prefs: NotificationPreference) -> EmailMessage:
        """Erstelle E-Mail für Task-Zuweisung"""
        return EmailMessage(
            to=data.get("user_email"),
            subject=f"✋ Neue Aufgabe zugewiesen: {data.get('task_title')}",
            html_body=self._render_html("task_assigned", data),
            text_body=self._render_text("task_assigned", data),
        )

    def _create_daily_summary_email(self, data: dict, prefs: NotificationPreference) -> EmailMessage:
        """Erstelle E-Mail für Daily-Summary"""
        return EmailMessage(
            to=data.get("user_email"),
            subject=f"📊 Tägliche Zusammenfassung für {data.get('store_name')}",
            html_body=self._render_html("daily_summary", data),
            text_body=self._render_text("daily_summary", data),
        )

    def _render_html(self, template: str, data: dict) -> str:
        """Render HTML-Template"""
        # TODO: Implementiere echtes HTML-Rendering
        # Für jetzt: Platzhalter
        return f"""
        <html>
        <body>
            <h2>Notification: {template}</h2>
            <p>Dies ist eine {template} Benachrichtigung.</p>
            <p>Data: {data}</p>
        </body>
        </html>
        """

    def _render_text(self, template: str, data: dict) -> str:
        """Render Text-Template"""
        return f"""
Notification: {template}

Dies ist eine automatische Benachrichtigung vom Agentischen Document Store.

Details: {data}
        """

    async def _send_email(self, email: EmailMessage) -> bool:
        """Sende eine E-Mail über SMTP"""
        try:
            # Verbindung zum SMTP-Server herstellen
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()

                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)

                # E-Mail erstellen
                msg = MIMEMultipart("alternative")
                msg["Subject"] = email.subject
                msg["From"] = self.from_email
                msg["To"] = email.to

                if email.reply_to:
                    msg["Reply-To"] = email.reply_to

                # Text-Part
                part1 = MIMEText(email.text_body, "plain")
                msg.attach(part1)

                # HTML-Part
                part2 = MIMEText(email.html_body, "html")
                msg.attach(part2)

                # Senden
                server.send_message(msg)

            logger.info(f"E-Mail gesendet an {email.to}: {email.subject}")
            return True

        except Exception as e:
            logger.error(f"Fehler beim Senden der E-Mail: {e}")
            return False

    async def _log_notification(
        self,
        db: AsyncSession,
        store_id: str,
        user_id: str,
        notification_type: str,
        data: dict,
        status: str = "sent",
        error_message: str = None,
        channel: str = "email",
    ):
        """
        Logge eine gesendete Benachrichtigung in die Datenbank.

        Args:
            status: "sent", "failed", oder "skipped"
            channel: "email" oder "inapp"
        """
        from app.models.comments import NotificationLog
        import json

        try:
            # Resource-Typ und ID aus data extrahieren
            resource_type = data.get("resource_type")
            resource_id = data.get("resource_id")

            # Metadata als JSON speichern
            metadata = json.dumps({
                "subject": data.get("subject"),
                "store_name": data.get("store_name"),
                "page_title": data.get("page_title"),
                "task_title": data.get("task_title"),
            })

            # Notification-Log erstellen
            log_entry = NotificationLog(
                store_id=store_id,
                user_id=user_id,
                notification_type=notification_type,
                channel=channel,
                resource_type=resource_type,
                resource_id=resource_id,
                status=status,
                error_message=error_message,
                metadata=metadata,
            )

            db.add(log_entry)
            await db.commit()

            logger.info(
                f"Notification logged: {notification_type} to {user_id} "
                f"(status={status}, channel={channel})"
            )

        except Exception as e:
            logger.error(f"Fehler beim Loggen der Notification: {e}")
            await db.rollback()


# ─── Global Instance ───
notification_service = NotificationService()