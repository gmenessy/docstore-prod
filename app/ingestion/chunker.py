"""
Adaptives Chunking – Intelligente Text-Segmentierung.
Optimiert für deutsche Sprache, Absatz-Grenzen und semantische Einheiten.
"""
import re
import logging
from dataclasses import dataclass

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ChunkResult:
    """Ein einzelner Chunk mit Metadaten."""
    index: int
    content: str
    token_count: int
    page_start: int | None = None
    page_end: int | None = None


def estimate_tokens(text: str) -> int:
    """Grobe Token-Schätzung (deutsch: ~1.3 Tokens pro Wort)."""
    return int(len(text.split()) * 1.3)


def chunk_text(
    text: str,
    max_tokens: int = None,
    overlap: int = None,
    min_length: int = None,
) -> list[ChunkResult]:
    """
    Adaptives Chunking mit:
    - Absatz-Grenzen respektieren
    - Satz-Grenzen als Fallback
    - Überlappung für Kontext-Erhalt
    - Mindestlänge für sinnvolle Chunks
    """
    max_tokens = max_tokens or settings.chunk_size
    overlap = overlap or settings.chunk_overlap
    min_length = min_length or settings.min_chunk_length

    if not text.strip():
        return []

    # Phase 1: In Absätze aufteilen
    paragraphs = _split_paragraphs(text)

    # Phase 2: Absätze zu Chunks zusammenfassen
    chunks = []
    current_parts = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = estimate_tokens(para)

        # Absatz zu groß → am Satz splitten
        if para_tokens > max_tokens:
            # Aktuellen Chunk abschließen
            if current_parts:
                chunks.append("\n\n".join(current_parts))
                current_parts = []
                current_tokens = 0

            # Großen Absatz in Sätze aufteilen
            sentences = _split_sentences(para)
            sent_buffer = []
            sent_tokens = 0

            for sent in sentences:
                st = estimate_tokens(sent)
                if sent_tokens + st > max_tokens and sent_buffer:
                    chunks.append(" ".join(sent_buffer))
                    # Überlappung: letzte N Sätze mitnehmen
                    overlap_sents = _get_overlap_sents(sent_buffer, overlap)
                    sent_buffer = overlap_sents + [sent]
                    sent_tokens = estimate_tokens(" ".join(sent_buffer))
                else:
                    sent_buffer.append(sent)
                    sent_tokens += st

            if sent_buffer:
                chunks.append(" ".join(sent_buffer))
            continue

        # Passt der Absatz noch in den aktuellen Chunk?
        if current_tokens + para_tokens > max_tokens and current_parts:
            chunks.append("\n\n".join(current_parts))
            # Überlappung: letzten Absatz mitnehmen
            if overlap > 0 and current_parts:
                last = current_parts[-1]
                if estimate_tokens(last) <= overlap:
                    current_parts = [last]
                    current_tokens = estimate_tokens(last)
                else:
                    current_parts = []
                    current_tokens = 0
            else:
                current_parts = []
                current_tokens = 0

        current_parts.append(para)
        current_tokens += para_tokens

    # Letzten Chunk abschließen
    if current_parts:
        chunks.append("\n\n".join(current_parts))

    # Phase 3: Zu kurze Chunks filtern/zusammenführen
    merged_chunks = _merge_short_chunks(chunks, min_length, max_tokens)

    # Phase 4: ChunkResult-Objekte erstellen
    results = []
    for i, content in enumerate(merged_chunks):
        results.append(ChunkResult(
            index=i,
            content=content,
            token_count=estimate_tokens(content),
        ))

    logger.info(f"Chunking: {len(text)} Zeichen → {len(results)} Chunks")
    return results


def _split_paragraphs(text: str) -> list[str]:
    """Text in Absätze aufteilen."""
    parts = re.split(r"\n{2,}", text)
    return [p.strip() for p in parts if p.strip()]


def _split_sentences(text: str) -> list[str]:
    """
    Deutsche Satz-Segmentierung.
    Berücksichtigt Abkürzungen (z.B., Abs., Nr., etc.)
    """
    # Abkürzungen schützen
    abbrevs = ["z\\.B", "bzw", "usw", "etc", "Abs", "Nr", "Art",
               "Ziff", "Verf", "Hrsg", "Aufl", "Bd", "Dr", "Prof",
               "gem", "ggf", "inkl", "max", "min", "vgl", "s\\.o",
               "s\\.u", "u\\.a", "d\\.h", "i\\.d\\.R"]
    pattern = r"(?<!\b(?:" + "|".join(abbrevs) + r"))\. +"
    sentences = re.split(pattern, text)
    # Punkt wieder anhängen
    result = []
    for i, s in enumerate(sentences):
        s = s.strip()
        if s:
            if i < len(sentences) - 1 and not s.endswith((".", "!", "?", ":", ";")):
                s += "."
            result.append(s)
    return result


def _get_overlap_sents(sentences: list[str], max_overlap_tokens: int) -> list[str]:
    """Letzte Sätze für Überlappung auswählen."""
    overlap = []
    tokens = 0
    for sent in reversed(sentences):
        t = estimate_tokens(sent)
        if tokens + t > max_overlap_tokens:
            break
        overlap.insert(0, sent)
        tokens += t
    return overlap


def _merge_short_chunks(chunks: list[str], min_length: int, max_tokens: int) -> list[str]:
    """Zu kurze Chunks mit Nachbarn zusammenführen."""
    if not chunks:
        return []

    merged = []
    buffer = ""

    for chunk in chunks:
        if len(chunk) < min_length and buffer:
            combined = buffer + "\n\n" + chunk
            if estimate_tokens(combined) <= max_tokens:
                buffer = combined
                continue
        if buffer:
            merged.append(buffer)
        buffer = chunk

    if buffer:
        merged.append(buffer)

    return merged
