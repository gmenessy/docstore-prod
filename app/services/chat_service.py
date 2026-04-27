"""
Chat-Service – Echtes RAG-System pro Store (isoliertes Oekosystem).

Ablauf:
1. Hybrid-Suche ueber Chunks des Stores (BM25 + Semantic)
2. Top-K Chunks als Kontext zusammenstellen
3. LLM-Anfrage via OpenAI-kompatibler API (Multi-Provider)
4. Antwort mit Quellenverweisen zurueckgeben
5. Chat-Verlauf in DB persistieren

Der Chat nutzt AUSSCHLIESSLICH Dokumente des zugewiesenen Stores.
Weltwissen des Modells wird durch den System-Prompt unterdrueckt.
"""
import logging
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.database import (
    Store, Document, ChatMessage, DocumentStatus, gen_id,
)
from app.search.engine import search_engine
from app.core.llm_client import llm_client

logger = logging.getLogger(__name__)


async def chat_with_store(
    db: AsyncSession,
    store_id: str,
    user_message: str,
    session_id: Optional[str] = None,
    provider_id: str = "ollama",
    model: str = None,
) -> dict:
    """
    RAG-Chat gegen einen einzelnen Store.

    Args:
        store_id: Ziel-Store (isoliertes Oekosystem)
        user_message: Frage des Nutzers
        session_id: Chat-Session (None = neue Session)
        provider_id: LLM-Provider (ollama, openai, anthropic, mistral, azure)
        model: Modellname (None = Provider-Default)

    API-Keys werden nur noch über Umgebungsvariablen konfiguriert (DOCSTORE_*_API_KEY).
    """
    if not session_id:
        session_id = uuid.uuid4().hex[:16]

    # ── Store laden ──
    result = await db.execute(
        select(Store)
        .where(Store.id == store_id)
        .options(selectinload(Store.documents))
    )
    store = result.scalar_one_or_none()
    if not store:
        raise ValueError(f"Store {store_id} nicht gefunden")

    indexed_docs = [d for d in store.documents if d.status == DocumentStatus.INDEXED]
    store_label = "Akte" if store.type.value == "akte" else "WissensDB"

    if not indexed_docs:
        answer_text = (
            f"In der {store_label} '{store.name}' sind noch keine indizierten "
            f"Dokumente vorhanden. Bitte laden Sie zunachst Dokumente hoch."
        )
        sources = []
        used_model = "none"
        used_provider = "none"
    else:
        # ── Multi-Turn: Letzte 4 Nachrichten als Kontext laden ──
        chat_history_msgs = []
        try:
            hist_result = await db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.desc())
                .limit(4)
            )
            prev_msgs = list(reversed(hist_result.scalars().all()))
            for m in prev_msgs:
                chat_history_msgs.append({
                    "role": m.role,
                    "content": m.content[:300],
                })
        except Exception:
            pass  # Erster Nachricht in Session — kein Verlauf

        # ── Hybrid-Suche – NUR innerhalb dieses Stores ──
        hits = await search_engine.search(
            query=user_message,
            search_type="hybrid",
            max_results=10,
            store_id=store_id,
        )

        if hits:
            context_chunks = [
                {
                    "content": h.content,
                    "document_title": h.document_title,
                    "chunk_index": h.chunk_index,
                    "score": h.score,
                }
                for h in hits[:6]
            ]

            # Deduplizierte Quellen
            seen = set()
            sources = []
            for h in hits[:6]:
                if h.document_id not in seen:
                    seen.add(h.document_id)
                    sources.append({
                        "document_id": h.document_id,
                        "title": h.document_title,
                        "score": round(h.score, 3),
                    })

            # ── LLM-Anfrage (RAG) ──
            try:
                llm_result = await llm_client.rag_query(
                    question=user_message,
                    context_chunks=context_chunks,
                    store_name=store.name,
                    store_type=store_label,
                    doc_count=len(indexed_docs),
                    provider_id=provider_id,
                    model=model,
                    chat_history=chat_history_msgs,
                )
                answer_text = llm_result["content"]
                used_model = llm_result["model"]
                used_provider = llm_result["provider"]
            except ValueError as e:
                # Provider-Fehler: Extraktiver Fallback
                logger.warning(f"LLM-Fehler, Fallback: {e}")
                fallback = llm_client._extractive_fallback(
                    user_message, context_chunks, store.name
                )
                answer_text = fallback["content"]
                used_model = "extractive-fallback"
                used_provider = "local"
        else:
            answer_text = (
                f"In den {len(indexed_docs)} Dokumenten der {store_label} "
                f"'{store.name}' konnte ich keine relevanten Informationen "
                f"zu Ihrer Frage finden.\n\n"
                f"Mein Wissen beschrankt sich ausschliesslich auf diese "
                f"Sammlung. Weltwissen steht mir nicht zur Verfuegung."
            )
            sources = []
            used_model = "none"
            used_provider = "none"

    # ── Nachrichten persistieren ──
    user_msg = ChatMessage(
        id=gen_id(), store_id=store_id, session_id=session_id,
        role="user", content=user_message,
    )
    assistant_msg = ChatMessage(
        id=gen_id(), store_id=store_id, session_id=session_id,
        role="assistant", content=answer_text,
        sources=[{"title": s["title"], "score": s.get("score", 0)} for s in sources],
    )
    db.add(user_msg)
    db.add(assistant_msg)
    await db.commit()

    logger.info(
        f"Chat [{store.name}] Session={session_id[:8]}... "
        f"Provider={used_provider}/{used_model} "
        f"Quellen={len(sources)}"
    )

    return {
        "session_id": session_id,
        "store_id": store_id,
        "store_name": store.name,
        "answer": assistant_msg.to_dict(),
        "context_documents": len(indexed_docs),
        "model": used_model,
        "provider": used_provider,
    }


async def get_chat_history(
    db: AsyncSession,
    store_id: str,
    session_id: str,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[dict], int]:
    """Chat-Verlauf einer Session abrufen (Store-isoliert, paginiert)."""
    from sqlalchemy import func

    # Count
    count_result = await db.execute(
        select(func.count(ChatMessage.id))
        .where(ChatMessage.store_id == store_id, ChatMessage.session_id == session_id)
    )
    total = count_result.scalar() or 0

    # Fetch
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.store_id == store_id, ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    messages = result.scalars().all()
    return [m.to_dict() for m in messages], total
