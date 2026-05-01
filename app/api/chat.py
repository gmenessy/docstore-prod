"""
API-Routen: Chat – RAG-Chat pro Store mit Multi-Provider LLM.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import verify_api_key, paginated_response
from app.models.schemas import ChatRequest, ChatResponse
from app.services.chat_service import chat_with_store, get_chat_history
from app.core.llm_client import llm_client
from app.security.prompt_injection import check_prompt_safety
from app.services.confidence import calculate_confidence

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stores/{store_id}/chat", tags=["Chat"])


@router.post("")
async def send_message(
    store_id: str,
    data: ChatRequest,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    Nachricht an den Chat senden.
    Antwortet AUSSCHLIESSLICH auf Basis der Dokumente des Stores.

    LLM-Provider und Modell koennen pro Request gewaehlt werden:
    - provider: ollama (lokal), openai, anthropic, mistral, azure
    - model: z.B. gpt-4o, claude-sonnet-4-20250514, llama3.2

    API-Keys werden nur noch über Umgebungsvariablen konfiguriert (DOCSTORE_*_API_KEY).

    Security: Prompt-Injection Detection und Confidence Scoring.
    """
    # 1. Prompt-Injection Check
    is_safe, error = check_prompt_safety(data.message)
    if not is_safe:
        logger.warning(f"Prompt injection blocked: {data.message[:100]}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unsupported_query",
                "message": "Diese Anfrage kann nicht verarbeitet werden.",
                "reason": error
            }
        )

    # 2. Chat durchführen
    try:
        result = await chat_with_store(
            db=db,
            store_id=store_id,
            user_message=data.message,
            session_id=data.session_id,
            provider_id=data.provider,
            model=data.model,
        )

        # 3. Confidence-Score berechnen
        if result and result.get("answer"):
            sources = result.get("sources", [])
            confidence_result = calculate_confidence(
                answer=result["answer"],
                sources=sources,
                query=data.message,
                context=None  # Kann erweitert werden
            )

            # Confidence zur Antwort hinzufügen
            result["confidence"] = {
                "confidence": confidence_result.confidence,
                "level": confidence_result.level,
                "factors": confidence_result.factors,
            }

        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/history/{session_id}")
async def get_history(
    store_id: str,
    session_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """Chat-Verlauf (paginiert, Store-isoliert)."""
    messages, total = await get_chat_history(db, store_id, session_id, offset, limit)
    return paginated_response(messages, total, offset, limit)


@router.get("/providers")
async def list_providers(
    auth: str = Depends(verify_api_key),
):
    """Verfuegbare LLM-Provider und Modelle auflisten.

    API-Keys werden nur noch über Umgebungsvariablen konfiguriert (DOCSTORE_*_API_KEY).
    """
    return {
        "providers": llm_client.get_providers(),
        "default_provider": "ollama",
        "note": "Ollama laeuft lokal ohne API-Key. Cloud-Provider erfordern DOCSTORE_*_API_KEY in .env.",
    }
