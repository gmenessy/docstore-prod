"""
Intelligence-Service – Zusammenfassung, Fusion, Destillierung.
Generiert Live-View-Daten fuer jede Sammlung (Store).
LLM-gestuetzte Zusammenfassung wenn Provider verfuegbar, sonst extraktiv.
"""
import re
import logging
from collections import Counter

logger = logging.getLogger(__name__)


async def generate_summary_llm(texts: list[str], store_name: str = "", max_sentences: int = 7) -> str | None:
    """
    Abstraktive Zusammenfassung via LLM.
    Gibt None zurueck wenn kein LLM verfuegbar (→ Fallback auf extraktiv).
    """
    if not texts:
        return None
    try:
        from app.core.llm_client import llm_client
        source = "\n\n".join(texts)[:3000]
        result = await llm_client.chat_completion(
            messages=[
                {"role": "system", "content": f"""Fasse die folgenden Dokumente in {max_sentences} Saetzen zusammen.
Verwende AUSSCHLIESSLICH Informationen aus den Quellen. Erfinde NICHTS.
Schreibe auf Deutsch in klarem Verwaltungsdeutsch. Keine Aufzaehlungen."""},
                {"role": "user", "content": f"Dokumente aus '{store_name}':\n{source}"},
            ],
            provider_id="ollama",
            temperature=0.2,
            max_tokens=500,
        )
        content = result.get("content", "").strip()
        if content and len(content) > 30:
            return content
    except Exception as e:
        logger.debug(f"LLM-Summary nicht verfuegbar: {e}")
    return None


def generate_summary(texts: list[str], max_sentences: int = 7) -> str:
    """
    Extraktive Zusammenfassung (TextRank-inspiriert).
    Wählt die informativsten Sätze basierend auf TF-Gewichtung.
    """
    if not texts:
        return "Keine Dokumente vorhanden."

    all_text = " ".join(texts)
    sentences = _split_sentences(all_text)

    if not sentences:
        return "Kein extrahierbarer Text."

    if len(sentences) <= max_sentences:
        return " ".join(sentences)

    # TF-basierte Satz-Bewertung
    word_freq = Counter()
    for sent in sentences:
        words = _tokenize(sent)
        word_freq.update(words)

    scored = []
    for sent in sentences:
        words = _tokenize(sent)
        if not words:
            continue
        score = sum(word_freq.get(w, 0) for w in words) / len(words)
        # Bonus für längere, informative Sätze
        if len(words) > 8:
            score *= 1.2
        # Bonus für Sätze mit Zahlen (Fakten)
        if re.search(r"\d", sent):
            score *= 1.3
        scored.append((score, sent))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [s for _, s in scored[:max_sentences]]
    return " ".join(top)


def extract_key_takeaways(texts: list[str], max_items: int = 10) -> list[dict]:
    """
    Kernfakten-Destillierung.
    Identifiziert die häufigsten und relevantesten Konzepte.
    """
    all_text = " ".join(texts)

    # Bedeutungsvolle Phrasen extrahieren (2-3 Wörter)
    phrases = Counter()
    words = all_text.split()

    for i in range(len(words) - 1):
        # Bigramme
        bigram = f"{words[i]} {words[i+1]}"
        if _is_meaningful_phrase(bigram):
            phrases[bigram] += 1

    # Auch einzelne Schlüsselwörter
    key_words = Counter()
    for w in words:
        w_clean = re.sub(r"[^\wäöüß]", "", w.lower())
        if len(w_clean) > 4 and w_clean not in _STOPWORDS:
            key_words[w_clean] += 1

    results = []
    for phrase, count in phrases.most_common(max_items):
        results.append({"takeaway": phrase, "count": count, "type": "phrase"})

    # Auffüllen mit Schlüsselwörtern
    remaining = max_items - len(results)
    for word, count in key_words.most_common(remaining * 2):
        if len(results) >= max_items:
            break
        if not any(word in r["takeaway"].lower() for r in results):
            results.append({"takeaway": word.capitalize(), "count": count, "type": "keyword"})

    return results


def fuse_knowledge(texts: list[str]) -> dict:
    """
    Wissens-Fusion: Aggregation über mehrere Dokumente.
    Identifiziert gemeinsame Themen und Divergenzen.
    """
    if not texts:
        return {"common_themes": [], "unique_aspects": [], "coverage": 0}

    # Themen pro Dokument
    doc_themes = []
    for text in texts:
        words = set(_tokenize(text))
        doc_themes.append(words)

    # Gemeinsame Themen (in >50% der Dokumente)
    all_words = Counter()
    for themes in doc_themes:
        for w in themes:
            all_words[w] += 1

    threshold = max(1, len(texts) // 2)
    common = [w for w, c in all_words.items() if c >= threshold and len(w) > 4]
    common.sort(key=lambda w: all_words[w], reverse=True)

    # Einzigartige Aspekte (nur in einem Dokument)
    unique = [w for w, c in all_words.items() if c == 1 and len(w) > 5]

    # Abdeckungsmetrik
    if len(texts) > 1:
        pairwise_overlap = []
        for i in range(len(doc_themes)):
            for j in range(i + 1, len(doc_themes)):
                intersection = doc_themes[i] & doc_themes[j]
                union = doc_themes[i] | doc_themes[j]
                if union:
                    pairwise_overlap.append(len(intersection) / len(union))
        coverage = sum(pairwise_overlap) / len(pairwise_overlap) if pairwise_overlap else 0
    else:
        coverage = 1.0

    return {
        "common_themes": common[:20],
        "unique_aspects": unique[:15],
        "coverage": round(coverage, 3),
        "total_vocabulary": len(all_words),
    }


def distill_facts(texts: list[str]) -> list[dict]:
    """
    Fakten-Destillierung: Extrahiert konkrete Aussagen mit Zahlen/Daten.
    """
    all_text = " ".join(texts)
    sentences = _split_sentences(all_text)
    facts = []

    for sent in sentences:
        # Sätze mit Zahlen, Daten, Beträgen
        has_number = bool(re.search(r"\d+(?:\.\d+)?(?:\s*(?:Euro|EUR|Mio|Mrd|Prozent|%|Tsd))?", sent))
        has_date = bool(re.search(r"\d{1,2}\.\s*\w+\s+\d{4}|\d{1,2}\.\d{1,2}\.\d{2,4}", sent))
        has_keyword = any(kw in sent.lower() for kw in [
            "beschluss", "genehmigung", "betrag", "frist", "ergebnis",
            "kosten", "budget", "fördermittel", "termin", "deadline",
        ])

        if has_number or has_date or has_keyword:
            fact_type = "zahl" if has_number else ("datum" if has_date else "fakt")
            facts.append({
                "text": sent.strip(),
                "type": fact_type,
                "confidence": 0.7 + (0.1 if has_number else 0) + (0.1 if has_keyword else 0),
            })

    # Nach Konfidenz sortieren, Top N
    facts.sort(key=lambda x: x["confidence"], reverse=True)
    return facts[:20]


# ─── Hilfsfunktionen ───

_STOPWORDS = {
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer",
    "und", "oder", "aber", "auch", "auf", "aus", "bei", "bis", "durch",
    "für", "gegen", "mit", "nach", "ohne", "über", "unter", "von",
    "vor", "wird", "werden", "hat", "haben", "ist", "sind", "war",
    "kann", "muss", "soll", "sich", "nicht", "noch", "nur", "sehr",
    "wie", "wenn", "dann", "dass", "damit", "dazu", "doch", "hier",
    "dort", "alle", "diese", "dieser", "jede", "jeder", "seine",
}


def _tokenize(text: str) -> list[str]:
    text = re.sub(r"[^\wäöüß\s]", "", text.lower())
    return [w for w in text.split() if w not in _STOPWORDS and len(w) > 2]


def _split_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if len(s.strip()) > 15]


def _is_meaningful_phrase(phrase: str) -> bool:
    words = phrase.lower().split()
    if any(w in _STOPWORDS for w in words):
        return False
    if any(len(w) < 3 for w in words):
        return False
    return True
