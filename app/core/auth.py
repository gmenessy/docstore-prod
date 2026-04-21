"""
Auth & Rate-Limiting Middleware.

- API-Key Authentifizierung (Header: X-API-Key)
- Rate-Limiting via SlowAPI (Redis-backed oder In-Memory)
- Optionaler Bypass fuer lokale Entwicklung
"""
import logging
import os
from typing import Optional

from fastapi import Request, HTTPException, Security, Depends
from fastapi.security import APIKeyHeader

from app.core.config import settings

logger = logging.getLogger(__name__)

# ─── API-Key Setup ───
# Keys koennen via Env-Variable oder DB konfiguriert werden
# Format: Komma-separiert: DOCSTORE_API_KEYS=key1,key2,key3
_raw_keys = os.environ.get("DOCSTORE_API_KEYS", "")
VALID_API_KEYS: set[str] = {k.strip() for k in _raw_keys.split(",") if k.strip()}

# Dev-Modus: Wenn keine Keys konfiguriert, ist Auth deaktiviert
AUTH_ENABLED = len(VALID_API_KEYS) > 0

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> Optional[str]:
    """
    API-Key validieren.
    Wenn AUTH_ENABLED=False (keine Keys konfiguriert), wird alles durchgelassen.
    """
    if not AUTH_ENABLED:
        return "dev-mode"

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API-Key erforderlich. Header: X-API-Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if api_key not in VALID_API_KEYS:
        raise HTTPException(
            status_code=403,
            detail="Ungueltiger API-Key",
        )

    return api_key


# ─── Rate-Limiting ───
# SlowAPI Integration fuer FastAPI

def setup_rate_limiting(app):
    """Rate-Limiting fuer die App konfigurieren."""
    try:
        from slowapi import Limiter, _rate_limit_exceeded_handler
        from slowapi.util import get_remote_address
        from slowapi.errors import RateLimitExceeded

        limiter = Limiter(
            key_func=get_remote_address,
            default_limits=["100/minute"],
            storage_uri=settings.redis_url if settings.redis_url != "redis://localhost:6379/0" else "memory://",
        )
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        logger.info("Rate-Limiting aktiviert (100/min)")
        return limiter
    except ImportError:
        logger.warning("slowapi nicht installiert — Rate-Limiting deaktiviert")
        return None
    except Exception as e:
        logger.warning(f"Rate-Limiting konnte nicht aktiviert werden: {e}")
        return None


# ─── Pagination Helper ───

def paginate_params(
    offset: int = 0,
    limit: int = 50,
) -> dict:
    """Standard-Pagination-Parameter."""
    limit = min(max(1, limit), 200)  # Max 200
    offset = max(0, offset)
    return {"offset": offset, "limit": limit}


def paginated_response(items: list, total: int, offset: int, limit: int) -> dict:
    """Standard-Pagination-Response."""
    return {
        "items": items,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
    }
