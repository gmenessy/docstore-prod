"""
Hybrid-Suchmaschine – BM25 + Dense-Vector.
Optimiert fuer deutsche Sprache.

Semantic-Suche:
  1. Ollama-Embeddings (nomic-embed-text) wenn verfuegbar
  2. TF-IDF Fallback wenn Ollama nicht erreichbar
"""
import re
import math
import logging
import time
import asyncio
from collections import defaultdict, OrderedDict
from dataclasses import dataclass

import numpy as np
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.core.config import settings

logger = logging.getLogger(__name__)


# ─── Ollama Embedding Client ───

class EmbeddingClient:
    """Erzeugt Dense-Vectors via Ollama (oder anderer OpenAI-kompatibler API)."""

    def __init__(self, cache_max_size: int = 5000):
        self._available = None  # None = nicht getestet
        self._cache_max_size = cache_max_size
        self._cache = OrderedDict()  # LRU-Cache: text_hash -> vector
        self._cache_hits = 0
        self._cache_misses = 0

    async def check_availability(self):
        """Pruefen ob Ollama Embeddings verfuegbar sind."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.post(
                    f"{settings.ollama_url}/api/embeddings",
                    json={"model": settings.ollama_embed_model, "prompt": "test"},
                )
                if r.status_code == 200 and "embedding" in r.json():
                    self._available = True
                    dim = len(r.json()["embedding"])
                    logger.info(f"Ollama Embeddings verfuegbar: {settings.ollama_embed_model} ({dim}d)")
                else:
                    self._available = False
        except Exception:
            self._available = False
        return self._available

    @property
    def available(self):
        return self._available is True

    def _get_from_cache(self, key: str) -> list[float] | None:
        """LRU-Cache Lookup mit Move-to-End."""
        if key in self._cache:
            self._cache_moves_to_end(key)  # Mark als kuerzlich verwendet
            self._cache_hits += 1
            return self._cache[key]
        self._cache_misses += 1
        return None

    def _put_in_cache(self, key: str, value: list[float]) -> None:
        """LRU-Cache Insert mit Eviction."""
        # Wenn Key existiert, aktualisieren und ans Ende verschieben
        if key in self._cache:
            self._cache.move_to_end(key)
            self._cache[key] = value
            return

        # Neue Eintrag
        self._cache[key] = value

        # LRU-Eviction wenn Cache voll
        if len(self._cache) > self._cache_max_size:
            self._cache.popitem(last=False)  # Entferne aeltesten Eintrag

    def embed_sync(self, text: str) -> list[float] | None:
        """Synchrones Embedding (fuer Batch-Indexierung) mit LRU-Cache."""
        if not self.available:
            return None
        text_hash = hash(text[:200])

        # Cache-Lookup
        cached = self._get_from_cache(text_hash)
        if cached is not None:
            return cached
            return self._cache[text_hash]
        try:
            import httpx
            r = httpx.post(
                f"{settings.ollama_url}/api/embeddings",
                json={"model": settings.ollama_embed_model, "prompt": text[:2000]},
                timeout=10.0,
            )
            if r.status_code == 200:
                vec = r.json().get("embedding")
                if vec:
                    self._put_in_cache(text_hash, vec)
                    return vec
        except Exception:
            pass
        return None

    @property
    def cache_stats(self) -> dict:
        """Cache-Statistiken fuer Monitoring."""
        total = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total if total > 0 else 0
        return {
            "size": len(self._cache),
            "max_size": self._cache_max_size,
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "hit_rate": round(hit_rate, 3),
        }

    def embed_batch_sync(self, texts: list[str]) -> list[list[float] | None]:
        """Batch-Embedding (sequentiell, fuer Indexierung)."""
        return [self.embed_sync(t) for t in texts]


embedding_client = EmbeddingClient()


# ─── Deutsche Stoppwörter ───
GERMAN_STOPWORDS = {
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer", "einem",
    "einen", "und", "oder", "aber", "als", "auch", "auf", "aus", "bei", "bis",
    "durch", "für", "gegen", "in", "mit", "nach", "ohne", "über", "um", "unter",
    "von", "vor", "zu", "zum", "zur", "an", "ab", "am", "im", "ist", "sind",
    "war", "wird", "werden", "hat", "haben", "hatte", "sein", "seine", "seiner",
    "diesem", "dieser", "dieses", "diese", "jeder", "jede", "jedes", "nicht",
    "noch", "nur", "schon", "sehr", "sich", "wie", "wenn", "dann", "dass",
    "damit", "davon", "dazu", "doch", "dort", "hier", "kann", "muss", "soll",
    "will", "es", "er", "sie", "wir", "ihr", "sie", "man", "so", "da",
    "was", "wer", "wo", "alle", "allem", "allen", "aller", "alles",
}


def normalize_german(text: str) -> str:
    """Deutsche Textnormalisierung für Suche."""
    text = text.lower()
    text = re.sub(r"[^\w\säöüß]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokenize_german(text: str) -> list[str]:
    """Tokenisierung mit Stoppwort-Filterung."""
    normalized = normalize_german(text)
    tokens = normalized.split()
    return [t for t in tokens if t not in GERMAN_STOPWORDS and len(t) > 1]


@dataclass
class SearchHit:
    """Ein einzelner Suchtreffer."""
    chunk_id: str
    document_id: str
    content: str
    score: float
    bm25_score: float = 0.0
    semantic_score: float = 0.0
    chunk_index: int = 0
    page_start: int | None = None

    # Werden später angereichert
    document_title: str = ""
    store_id: str = ""
    store_name: str = ""
    file_type: str = ""
    tags: list = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class HybridSearchEngine:
    """
    Hybrid-Suchmaschine: BM25 (Keyword) + TF-IDF (Semantic Fallback).

    Produktions-Erweiterung:
    - BM25 → PostgreSQL pg_trgm / Elasticsearch
    - TF-IDF → Qdrant Dense-Vector mit sentence-transformers
    """

    def __init__(self):
        self._corpus: dict[str, dict] = {}
        self._bm25: BM25Okapi | None = None
        self._tfidf: TfidfVectorizer | None = None
        self._tfidf_matrix = None
        self._embeddings: dict[str, list[float]] = {}  # chunk_id -> vector
        self._use_embeddings = False
        self._chunk_ids: list[str] = []
        self._dirty = True
        self._lock = asyncio.Lock()

    async def add_chunks(self, chunks: list[dict]):
        """Chunks zum Index hinzufuegen (Thread-Safe mit Lock)."""
        async with self._lock:
            for chunk in chunks:
                self._corpus[chunk["id"]] = chunk
            self._dirty = True

    async def remove_document(self, document_id: str):
        """Alle Chunks eines Dokuments entfernen (Thread-Safe mit Lock)."""
        async with self._lock:
            to_remove = [
                cid for cid, c in self._corpus.items()
                if c.get("document_id") == document_id
            ]
            for cid in to_remove:
                del self._corpus[cid]
                self._embeddings.pop(cid, None)
            self._dirty = True

    async def rebuild_index(self):
        """BM25- und Semantic-Index neu aufbauen (Thread-Safe mit Lock)."""
        async with self._lock:
            if not self._corpus:
                self._bm25 = None
                self._tfidf = None
                self._tfidf_matrix = None
                self._chunk_ids = []
                self._dirty = False
                return

            self._chunk_ids = list(self._corpus.keys())
            tokenized_corpus = []

            for cid in self._chunk_ids:
                content = self._corpus[cid].get("content", "")
                tokens = tokenize_german(content)
                tokenized_corpus.append(tokens)

            # BM25
            self._bm25 = BM25Okapi(tokenized_corpus)

            # TF-IDF (Fallback wenn keine Embeddings)
            texts = [self._corpus[cid].get("content", "") for cid in self._chunk_ids]
            self._tfidf = TfidfVectorizer(
                max_features=10000,
                ngram_range=(1, 2),
                stop_words=list(GERMAN_STOPWORDS),
                lowercase=True,
            )
            self._tfidf_matrix = self._tfidf.fit_transform(texts)

            # Dense-Embeddings (wenn Ollama verfuegbar)
            if embedding_client.available:
                new_chunks = [cid for cid in self._chunk_ids if cid not in self._embeddings]
                if new_chunks:
                    new_texts = [self._corpus[cid].get("content", "")[:2000] for cid in new_chunks]
                    vecs = embedding_client.embed_batch_sync(new_texts)
                    for cid, vec in zip(new_chunks, vecs):
                        if vec:
                            self._embeddings[cid] = vec
                self._use_embeddings = len(self._embeddings) > len(self._chunk_ids) * 0.5
                if self._use_embeddings:
                    logger.info(f"Dense-Embeddings aktiv: {len(self._embeddings)}/{len(self._chunk_ids)} Chunks")
            else:
                self._use_embeddings = False

            self._dirty = False
            mode = "Embeddings" if self._use_embeddings else "TF-IDF"
            logger.info(f"Suchindex neu gebaut: {len(self._chunk_ids)} Chunks (Semantic: {mode})")

    async def search(
        self,
        query: str,
        search_type: str = "hybrid",
        max_results: int = 20,
        store_id: str | None = None,
        bm25_weight: float | None = None,
        semantic_weight: float | None = None,
    ) -> list[SearchHit]:
        """
        Hybrid-Suche durchführen (Thread-Safe mit automatischem Rebuild).

        search_type: "hybrid" | "bm25" | "semantic"
        """
        start_time = time.monotonic()

        # Lock-basierter Rebuild bei dirty Index
        if self._dirty:
            await self.rebuild_index()

        if not self._chunk_ids:
            return []

        bm25_w = bm25_weight or settings.bm25_weight
        sem_w = semantic_weight or settings.semantic_weight

        if search_type == "bm25":
            bm25_w, sem_w = 1.0, 0.0
        elif search_type == "semantic":
            bm25_w, sem_w = 0.0, 1.0

        query_tokens = tokenize_german(query)
        if not query_tokens:
            return []

        scores = defaultdict(lambda: {"bm25": 0.0, "semantic": 0.0})

        # ─── BM25 Scores ───
        if bm25_w > 0 and self._bm25:
            bm25_scores = self._bm25.get_scores(query_tokens)
            # Normalisieren
            max_bm25 = max(bm25_scores) if max(bm25_scores) > 0 else 1.0
            for i, score in enumerate(bm25_scores):
                cid = self._chunk_ids[i]
                scores[cid]["bm25"] = score / max_bm25

        # ─── Semantic Scores ───
        if sem_w > 0:
            if self._use_embeddings and self._embeddings:
                # Dense-Vector Suche via Ollama-Embeddings
                query_vec = embedding_client.embed_sync(query)
                if query_vec:
                    q_arr = np.array(query_vec)
                    q_norm = np.linalg.norm(q_arr)
                    if q_norm > 0:
                        for cid in self._chunk_ids:
                            if cid in self._embeddings:
                                c_arr = np.array(self._embeddings[cid])
                                c_norm = np.linalg.norm(c_arr)
                                if c_norm > 0:
                                    sim = float(np.dot(q_arr, c_arr) / (q_norm * c_norm))
                                    scores[cid]["semantic"] = max(0.0, sim)
                else:
                    # Embedding fehlgeschlagen, Fallback TF-IDF
                    if self._tfidf is not None:
                        query_v = self._tfidf.transform([query])
                        sim = cosine_similarity(query_v, self._tfidf_matrix).flatten()
                        for i, score in enumerate(sim):
                            scores[self._chunk_ids[i]]["semantic"] = float(score)
            elif self._tfidf is not None:
                # TF-IDF Fallback
                query_vec = self._tfidf.transform([query])
                sim = cosine_similarity(query_vec, self._tfidf_matrix).flatten()
                for i, score in enumerate(sim):
                    cid = self._chunk_ids[i]
                    scores[cid]["semantic"] = float(score)

        # ─── Hybrid Score berechnen ───
        results = []
        for cid, sc in scores.items():
            combined = bm25_w * sc["bm25"] + sem_w * sc["semantic"]
            if combined < 0.01:
                continue

            chunk_data = self._corpus[cid]

            # Store-Filter
            if store_id and chunk_data.get("store_id") != store_id:
                continue

            results.append(SearchHit(
                chunk_id=cid,
                document_id=chunk_data.get("document_id", ""),
                content=chunk_data.get("content", ""),
                score=round(combined, 4),
                bm25_score=round(sc["bm25"], 4),
                semantic_score=round(sc["semantic"], 4),
                chunk_index=chunk_data.get("chunk_index", 0),
                page_start=chunk_data.get("page_start"),
                document_title=chunk_data.get("document_title", ""),
                store_id=chunk_data.get("store_id", ""),
                store_name=chunk_data.get("store_name", ""),
                file_type=chunk_data.get("file_type", ""),
                tags=chunk_data.get("tags", []),
            ))

        # Sortieren und begrenzen
        results.sort(key=lambda x: x.score, reverse=True)
        results = results[:max_results]

        elapsed = (time.monotonic() - start_time) * 1000
        logger.info(f"Suche '{query}' ({search_type}): {len(results)} Treffer in {elapsed:.1f}ms")

        return results

    @property
    def index_size(self) -> int:
        return len(self._corpus)

    @property
    def index_ready(self) -> bool:
        """True wenn der Index aufgebaut und nutzbar ist."""
        return not self._dirty and len(self._corpus) >= 0

    def ensure_ready(self):
        """Index-Bereitschaft erzwingen — baut bei Bedarf neu auf."""
        if self._dirty:
            self.rebuild_index()

    async def async_rebuild(self):
        """Thread-sicherer Index-Rebuild mit Lock."""
        async with self._lock:
            self.rebuild_index()

    async def async_add_and_rebuild(self, chunks: list[dict]):
        """Chunks hinzufuegen und Index unter Lock neu bauen."""
        async with self._lock:
            self.add_chunks(chunks)
            self.rebuild_index()


# Singleton-Instanz
search_engine = HybridSearchEngine()
