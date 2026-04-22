"""
WebSocket-Server für Echtzeit-Kollaboration.

Bietet Live-Updates für:
- Kommentare
- Dokument-Änderungen
- Wiki-Updates
- User-Presence
"""
import logging
import json
from typing import Dict, Set
from uuid import uuid4

try:
    import socketio
    from fastapi import WebSocket
    ASGI_APP = True
except ImportError:
    # Socket.io nicht installiert - Fallback auf Grundfunktionalität
    socketio = None
    ASGI_APP = False

logger = logging.getLogger(__name__)


class CollaborationManager:
    """Verwaltung von Echtzeit-Verbindungen"""

    def __init__(self):
        # Store-ID -> Set von Connection-IDs
        self.store_connections: Dict[str, Set[str]] = {}

        # Connection-ID -> Store-ID
        self.connection_stores: Dict[str, str] = {}

        # Connection-ID -> User-ID
        self.connection_users: Dict[str, str] = {}

        # Store-ID -> Set von aktiven User-IDs
        self.store_active_users: Dict[str, Set[str]] = {}

    async def connect(self, store_id: str, connection_id: str, user_id: str):
        """Neue Verbindung herstellen"""
        if store_id not in self.store_connections:
            self.store_connections[store_id] = set()

        self.store_connections[store_id].add(connection_id)
        self.connection_stores[connection_id] = store_id
        self.connection_users[connection_id] = user_id

        # Aktive User tracken
        if store_id not in self.store_active_users:
            self.store_active_users[store_id] = set()
        self.store_active_users[store_id].add(user_id)

        logger.info(f"Connected: {user_id} to {store_id} ({connection_id})")

    async def disconnect(self, connection_id: str):
        """Verbindung trennen"""
        if connection_id not in self.connection_stores:
            return

        store_id = self.connection_stores[connection_id]
        user_id = self.connection_users.get(connection_id, "unknown")

        # Aus Trackern entfernen
        if store_id in self.store_connections:
            self.store_connections[store_id].discard(connection_id)

        # Prüfen ob User noch andere Verbindungen hat
        user_still_active = False
        for conn_id, conn_user_id in self.connection_users.items():
            if conn_id != connection_id and conn_user_id == user_id and self.connection_stores.get(conn_id) == store_id:
                user_still_active = True
                break

        if not user_still_active:
            if store_id in self.store_active_users:
                self.store_active_users[store_id].discard(user_id)

        # Aufräumen
        del self.connection_stores[connection_id]
        del self.connection_users[connection_id]

        logger.info(f"Disconnected: {user_id} from {store_id}")

    async def broadcast_to_store(self, store_id: str, event: str, data: dict):
        """Sende Event an alle Verbindungen in einem Store"""
        if store_id not in self.store_connections:
            return

        # TODO: Implementiere echte WebSocket-Broadcasts
        # Für jetzt: Loggen
        logger.info(f"Broadcast to {store_id}: {event} - {len(self.store_connections[store_id])} connections")

    def get_active_users(self, store_id: str) -> list[str]:
        """Hole aktive User in einem Store"""
        return list(self.store_active_users.get(store_id, set()))

    def get_connection_count(self, store_id: str) -> int:
        """Hole Anzahl der Verbindungen in einem Store"""
        return len(self.store_connections.get(store_id, set()))


# ─── Singleton Instance ───
collaboration_manager = CollaborationManager()


# ─── Event-Hooks ───

async def on_comment_created(store_id: str, comment: dict):
    """Wird aufgerufen wenn ein Kommentar erstellt wurde"""
    await collaboration_manager.broadcast_to_store(
        store_id=store_id,
        event="comment.created",
        data={
            "comment_id": comment.get("id"),
            "user_id": comment.get("user_id"),
            "content": comment.get("content")[:100],  # Erste 100 Zeichen
            "document_id": comment.get("document_id"),
            "wiki_page_id": comment.get("wiki_page_id"),
            "created_at": comment.get("created_at"),
        }
    )

    # Aktive User updaten
    active_users = collaboration_manager.get_active_users(store_id)
    await collaboration_manager.broadcast_to_store(
        store_id=store_id,
        event="users.active",
        data={"users": active_users, "count": len(active_users)}
    )


async def on_document_updated(store_id: str, document: dict):
    """Wird aufgerufen wenn ein Dokument aktualisiert wurde"""
    await collaboration_manager.broadcast_to_store(
        store_id=store_id,
        event="document.updated",
        data={
            "document_id": document.get("id"),
            "title": document.get("title"),
            "updated_at": document.get("updated_at"),
        }
    )


async def on_wiki_updated(store_id: str, wiki_page: dict):
    """Wird aufgerufen wenn eine Wiki-Seite aktualisiert wurde"""
    await collaboration_manager.broadcast_to_store(
        store_id=store_id,
        event="wiki.updated",
        data={
            "page_id": wiki_page.get("id"),
            "slug": wiki_page.get("slug"),
            "title": wiki_page.get("title"),
            "updated_at": wiki_page.get("updated_at"),
        }
    )


# ─── FastAPI WebSocket Endpoints ───

async def websocket_endpoint(websocket: WebSocket, store_id: str):
    """
    WebSocket-Endpunkt für Echtzeit-Updates.

    Verbindungs-URL: ws://localhost/api/v1/ws/comments/{store_id}
    """
    await websocket.accept()

    connection_id = str(uuid4())
    user_id = websocket.query_params.get("user_id", "anonymous")

    try:
        # Verbindung registrieren
        await collaboration_manager.connect(store_id, connection_id, user_id)

        # Begrüßungsnachricht
        await websocket.send_json({
            "event": "connected",
            "connection_id": connection_id,
            "store_id": store_id,
            "active_users": collaboration_manager.get_active_users(store_id)
        })

        # Nachrichten-Loop
        while True:
            data = await websocket.receive_json()

            # Ping/Pong für Connection-Keepalive
            if data.get("event") == "ping":
                await websocket.send_json({"event": "pong"})

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await collaboration_manager.disconnect(connection_id)

        # Verbindungs-Nachricht
        try:
            await websocket.send_json({
                "event": "disconnected",
                "connection_id": connection_id
            })
        except:
            pass