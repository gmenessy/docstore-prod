"""
Rate Limiting Configuration

Schützt vor Overload und DoS-Angriffen mit granularen Limits pro Endpoint.
Verwendet Redis für distributed rate limiting.
"""
import os
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request


def get_user_id(request: Request) -> str:
    """
    Identifiziert User für Rate Limiting.

    Priority:
    1. API Key (wenn authentifiziert)
    2. User ID (wenn angemeldet)
    3. IP Address (Fallback)

    Args:
        request: FastAPI Request

    Returns:
        User Identifier für Rate Limiting
    """
    # 1. API Key (für authentifizierte Requests)
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"apikey:{api_key[:8]}"  # Nur erste 8 Zeichen für Privacy

    # 2. User ID (aus Session)
    if hasattr(request.state, "user_id") and request.state.user_id:
        return f"user:{request.state.user_id}"

    # 3. IP Address (Fallback)
    return f"ip:{get_remote_address(request)}"


def get_store_id(request: Request) -> str:
    """
    Identifiziert Store für Rate Limiting.

    Nützlich für pro-Store Limits.

    Args:
        request: FastAPI Request

    Returns:
        Store Identifier
    """
    store_id = request.path_params.get("store_id", "unknown")
    user_part = get_user_id(request)
    return f"{user_part}:store:{store_id}"


# Redis Connection String
REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379/1"
)

# Limiter initialisieren
limiter = Limiter(
    key_func=get_user_id,
    default_limits=["100/hour"],  # Standard: 100 Anfragen/Stunde
    storage_uri=REDIS_URL,
    # Für Development ohne Redis:
    # storage_uri="memory://"  # Fallback auf in-memory
)

# Spezifische Limits für verschiedene Endpoints
RATE_LIMITS = {
    # Chat: Kostbare LLM-Calls → strenges Limit
    "chat": "20/minute",

    # Suche: Weniger kritisch → höheres Limit
    "search": "60/minute",

    # Upload: Datenintensiv → moderates Limit
    "upload": "10/hour",

    # Export: Datenintensiv → strenges Limit
    "export": "5/hour",

    # Wiki: LLM-basiert → moderates Limit
    "wiki_query": "30/minute",
    "wiki_ingest": "10/hour",

    # Skills: Sehr kostenintensiv → sehr strenges Limit
    "skills": "3/hour",

    # Admin: Sehr strenges Limit
    "admin": "50/hour",
}


def get_rate_limit(endpoint_type: str) -> str:
    """
    Gibt Rate-Limit für Endpoint-Typ zurück.

    Args:
        endpoint_type: Typ des Endpoints (z.B. "chat", "search")

    Returns:
        Rate-Limit String (z.B. "20/minute")
    """
    return RATE_LIMITS.get(endpoint_type, "100/hour")


class RateLimitExceededHandler:
    """Handler für Rate Limit Überschreitung"""

    @staticmethod
    def handle_limit_exceeded(request: Request, exc: RateLimitExceeded):
        """
        Reagiert auf Rate Limit Überschreitung.

        Args:
            request: FastAPI Request
            exc: RateLimitExceeded Exception

        Returns:
            JSON Response
        """
        from fastapi import Response
        import json

        response_data = {
            "error": "rate_limit_exceeded",
            "message": "Zu viele Anfragen. Bitte warten Sie einen Moment bevor Sie fortfahren.",
            "retry_after": getattr(exc, "retry_after", 60),  # Sekunden
        }

        return Response(
            content=json.dumps(response_data),
            status_code=429,
            media_type="application/json",
            headers={
                "Retry-After": str(response_data["retry_after"]),
                "X-RateLimit-Limit": str(getattr(exc, "limit", "unknown")),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(getattr(exc, "reset", "unknown")),
            }
        )


# Export für API-Verwendung
__all__ = [
    "limiter",
    "get_user_id",
    "get_store_id",
    "get_rate_limit",
    "RateLimitExceededHandler",
]
