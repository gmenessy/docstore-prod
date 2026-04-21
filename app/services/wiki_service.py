"""
Wiki-Service - WissensDB v2 (kompiliertes, LLM-gepflegtes Wiki).

Drei Kern-Operationen:
  - wiki_ingest(doc):  Nach Dokument-Upload Wiki-Seiten erzeugen/aktualisieren
  - wiki_query(q):     RAG gegen Wiki-Seiten statt Chunks
  - wiki_lint():       Health-Check (Widersprueche, Orphans, fehlende Konzepte)

Der LLM ist der Wiki-Maintainer. Der Mensch kuratiert Quellen und stellt Fragen.
"""
import logging
import json as json_module
import re
import datetime
from typing import Optional

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import (
    Store, Document, DocumentStatus, Entity, EntityType,
    WikiPage, WikiPageType, WikiOperation, gen_id,
)
from app.core.llm_client import llm_client
from app.ingestion.ner import extract_entities

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Hilfsfunktionen
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _slugify(text: str) -> str:
    """URL-sicheren Slug aus Text erzeugen."""
    slug = text.lower().strip()
    slug = re.sub(r"[aeiou]e", lambda m: {"ae": "ae", "oe": "oe", "ue": "ue"}.get(m.group(), m.group()), slug)
    slug = slug.replace("ae", "ae").replace("oe", "oe").replace("ue", "ue").replace("ss", "ss")
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug[:100] or f"page-{gen_id()[:6]}"


async def _log_operation(
    db: AsyncSession,
    store_id: str,
    operation: str,
    summary: str,
    pages_affected: list = None,
    source_document_id: str = None,
    details: dict = None,
):
    """Wiki-Operation in den Log schreiben."""
    op = WikiOperation(
        id=gen_id(),
        store_id=store_id,
        operation=operation,
        summary=summary,
        pages_affected=pages_affected or [],
        source_document_id=source_document_id,
        details=details or {},
    )
    db.add(op)
    await db.commit()
    return op


async def _get_or_create_page(
    db: AsyncSession,
    store_id: str,
    slug: str,
    title: str,
    page_type: WikiPageType,
) -> tuple[WikiPage, bool]:
    """Seite laden oder neu anlegen. Gibt (page, created) zurueck."""
    result = await db.execute(
        select(WikiPage).where(
            and_(WikiPage.store_id == store_id, WikiPage.slug == slug)
        )
    )
    page = result.scalar_one_or_none()
    if page:
        return page, False

    page = WikiPage(
        id=gen_id(),
        store_id=store_id,
        slug=slug,
        title=title,
        page_type=page_type,
        content_md="",
        outgoing_links=[],
        source_documents=[],
    )
    db.add(page)
    await db.flush()
    return page, True


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Operation: INGEST
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

INGEST_SYSTEM_PROMPT = """Du bist ein Wiki-Maintainer fuer kommunale Verwaltungsdokumente.
Deine Aufgabe: Ein neues Dokument wurde eingelesen. Entscheide welche Wiki-Seiten
erstellt oder aktualisiert werden muessen.

Arbeitsprinzipien:
- Die Wiki-Seiten sind kompilierte Synthese, KEINE Kopie der Quelle.
- Jede Seite hat einen klaren Fokus: ein Konzept, eine Entitaet, ein Thema.
- Verweise zwischen Seiten als Markdown-Links: [[slug]] oder [Text](./slug.md).
- Widersprueche zu bestehenden Seiten explizit markieren.

Gib eine JSON-Antwort mit Seiten-Updates zurueck:
{
  "summary": "Kurze Beschreibung was das Dokument beitraegt",
  "pages": [
    {
      "slug": "urlsafe-name",
      "title": "Lesbare Ueberschrift",
      "type": "summary|entity|concept|synthesis",
      "action": "create|update",
      "content_md": "Markdown-Inhalt (Synthese, nicht Kopie)",
      "related_slugs": ["andere-seite"]
    }
  ],
  "contradictions": [
    {"page_slug": "...", "new_claim": "...", "conflicts_with": "..."}
  ]
}

Erfinde NICHTS. Nur Fakten aus dem Dokument. Erzeuge max. 5 Seiten pro Ingest.
"""


async def wiki_ingest(
    db: AsyncSession,
    store_id: str,
    document_id: str,
    provider_id: str = "ollama",
    model: str = None,
) -> dict:
    """
    Nach erfolgreichem Document-Ingestion:
    LLM analysiert das Dokument im Kontext bestehender Wiki-Seiten
    und entscheidet welche Seiten zu erstellen oder zu aktualisieren sind.

    API-Keys werden nur noch über Umgebungsvariablen konfiguriert (DOCSTORE_*_API_KEY).
    """
    # Dokument + Store laden
    doc_result = await db.execute(select(Document).where(Document.id == document_id))
    document = doc_result.scalar_one_or_none()
    if not document or document.store_id != store_id:
        return {"error": "Dokument nicht gefunden"}

    store_result = await db.execute(select(Store).where(Store.id == store_id))
    store = store_result.scalar_one_or_none()
    if not store:
        return {"error": "Store nicht gefunden"}

    # Bestehende Wiki-Seiten als Kontext laden (nur Titel+Slugs, keine Inhalte)
    existing_result = await db.execute(
        select(WikiPage.slug, WikiPage.title, WikiPage.page_type)
        .where(WikiPage.store_id == store_id)
    )
    existing_pages = [
        {"slug": s, "title": t, "type": pt.value if pt else "concept"}
        for s, t, pt in existing_result.all()
    ]

    # LLM-Prompt aufbauen
    doc_text = (document.content_text or "")[:4000]
    user_prompt = f"""Neues Dokument: '{document.title}'
Sammlung: '{store.name}'

Bestehende Wiki-Seiten ({len(existing_pages)}):
{json_module.dumps(existing_pages, ensure_ascii=False, indent=2) if existing_pages else "[] (leeres Wiki)"}

Dokumentinhalt:
{doc_text}

Entscheide welche Wiki-Seiten zu erstellen oder zu aktualisieren sind.
Berueksichtige bestehende Seiten (update statt dupliziere)."""

    try:
        result = await llm_client.chat_completion(
            messages=[
                {"role": "system", "content": INGEST_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            provider_id=provider_id,
            model=model,
            temperature=0.2,
            max_tokens=3000,
        )
        content = result.get("content", "")
    except Exception as e:
        logger.warning(f"Wiki-Ingest LLM-Fehler: {e}, Fallback auf Regex-basierte Seiten")
        return await _wiki_ingest_fallback(db, store_id, document)

    # JSON parsen
    try:
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if not json_match:
            raise ValueError("Kein JSON in LLM-Antwort")
        data = json_module.loads(json_match.group())
    except Exception as e:
        logger.warning(f"Wiki-Ingest JSON-Parse fehlgeschlagen: {e}")
        return await _wiki_ingest_fallback(db, store_id, document)

    # Seiten erstellen/aktualisieren
    pages_affected = []
    pages_created = 0
    pages_updated = 0

    for page_data in data.get("pages", [])[:5]:  # Max 5 Seiten pro Ingest
        slug = page_data.get("slug", "")
        if not slug:
            continue
        slug = _slugify(slug)
        title = page_data.get("title", slug.replace("-", " ").title())
        ptype_str = page_data.get("type", "concept")
        try:
            ptype = WikiPageType(ptype_str)
        except ValueError:
            ptype = WikiPageType.CONCEPT
        content_md = page_data.get("content_md", "")
        related_slugs = page_data.get("related_slugs", [])

        page, created = await _get_or_create_page(db, store_id, slug, title, ptype)

        # Quellen-Dokument ergaenzen
        sources = list(page.source_documents or [])
        if not any(s.get("document_id") == document_id for s in sources):
            sources.append({"document_id": document_id, "title": document.title})
        page.source_documents = sources

        # Outgoing Links aktualisieren
        links = list(page.outgoing_links or [])
        existing_link_slugs = {l.get("slug") for l in links}
        for rs in related_slugs:
            rs_slug = _slugify(rs)
            if rs_slug and rs_slug not in existing_link_slugs:
                links.append({"slug": rs_slug, "title": rs.replace("-", " ").title()})
        page.outgoing_links = links

        # Content: bei update mergen/ersetzen
        if created:
            page.content_md = content_md
        else:
            # Append mit Trenner, damit Historie erhalten bleibt
            separator = f"\n\n---\n*Aktualisiert am {datetime.date.today().isoformat()} aus '{document.title}'*\n\n"
            page.content_md = (page.content_md or "") + separator + content_md
            page.update_count = (page.update_count or 1) + 1

        page.last_updated = datetime.datetime.utcnow()

        # Widersprueche flaggen
        contradictions_for_page = [
            c for c in data.get("contradictions", [])
            if c.get("page_slug") == slug
        ]
        if contradictions_for_page:
            flags = list(page.contradiction_flags or [])
            flags.extend(contradictions_for_page)
            page.contradiction_flags = flags

        pages_affected.append(slug)
        if created:
            pages_created += 1
        else:
            pages_updated += 1

    await db.commit()

    # Log-Eintrag
    await _log_operation(
        db, store_id, "ingest",
        f"{document.title}: {pages_created} neu, {pages_updated} aktualisiert",
        pages_affected=pages_affected,
        source_document_id=document_id,
        details={
            "doc_title": document.title,
            "pages_created": pages_created,
            "pages_updated": pages_updated,
            "contradictions": len(data.get("contradictions", [])),
        },
    )

    # Index-Seite aktualisieren
    await _update_index_page(db, store_id)

    logger.info(f"Wiki-Ingest '{document.title}': {pages_created} neu, {pages_updated} aktualisiert")
    return {
        "document_title": document.title,
        "pages_created": pages_created,
        "pages_updated": pages_updated,
        "pages_affected": pages_affected,
        "contradictions_flagged": len(data.get("contradictions", [])),
        "llm_generated": True,
    }


async def _wiki_ingest_fallback(db: AsyncSession, store_id: str, document: Document) -> dict:
    """
    Fallback wenn LLM nicht erreichbar:
    Erzeugt Summary-Seite aus Dokument + Entity-Seiten aus NER.
    """
    pages_affected = []

    # 1. Summary-Seite fuer das Dokument
    slug = _slugify(f"summary-{document.title}")
    title = f"Zusammenfassung: {document.title}"
    page, created = await _get_or_create_page(db, store_id, slug, title, WikiPageType.SUMMARY)
    excerpt = (document.content_text or "")[:1500]
    page.content_md = f"# {document.title}\n\n{excerpt}\n\n---\n*Automatisch erstellt (Regex-Fallback)*"
    sources = list(page.source_documents or [])
    if not any(s.get("document_id") == document.id for s in sources):
        sources.append({"document_id": document.id, "title": document.title})
    page.source_documents = sources
    page.last_updated = datetime.datetime.utcnow()
    pages_affected.append(slug)

    # 2. Entity-Seiten aus NER (max 3)
    ents = extract_entities(document.content_text or "")
    for entity_info in (ents.personen + ents.organisationen)[:3]:
        e_value = entity_info.get("value", "") if isinstance(entity_info, dict) else str(entity_info)
        if len(e_value) < 4:
            continue
        e_slug = _slugify(e_value)
        e_page, e_created = await _get_or_create_page(
            db, store_id, e_slug, e_value, WikiPageType.ENTITY,
        )
        context = entity_info.get("context", "") if isinstance(entity_info, dict) else ""
        entry = f"\n\n**Aus '{document.title}':** {context}"
        e_page.content_md = (e_page.content_md or f"# {e_value}\n") + entry
        e_sources = list(e_page.source_documents or [])
        if not any(s.get("document_id") == document.id for s in e_sources):
            e_sources.append({"document_id": document.id, "title": document.title})
        e_page.source_documents = e_sources
        if not e_created:
            e_page.update_count = (e_page.update_count or 1) + 1
        e_page.last_updated = datetime.datetime.utcnow()
        pages_affected.append(e_slug)

    await db.commit()
    await _log_operation(
        db, store_id, "ingest",
        f"{document.title}: {len(pages_affected)} Seiten (Regex-Fallback)",
        pages_affected=pages_affected,
        source_document_id=document.id,
        details={"mode": "fallback"},
    )
    await _update_index_page(db, store_id)

    return {
        "document_title": document.title,
        "pages_created": len(pages_affected),
        "pages_updated": 0,
        "pages_affected": pages_affected,
        "contradictions_flagged": 0,
        "llm_generated": False,
    }


async def _update_index_page(db: AsyncSession, store_id: str):
    """Index-Seite mit allen Wiki-Seiten neu aufbauen."""
    result = await db.execute(
        select(WikiPage)
        .where(and_(WikiPage.store_id == store_id, WikiPage.page_type != WikiPageType.INDEX))
        .order_by(WikiPage.page_type, WikiPage.title)
    )
    pages = list(result.scalars().all())

    # Nach Typ gruppieren
    by_type: dict[str, list] = {}
    for p in pages:
        ptype = p.page_type.value if p.page_type else "concept"
        by_type.setdefault(ptype, []).append(p)

    md = "# Wiki-Index\n\nAutomatisch gepflegter Katalog aller Wiki-Seiten dieser Sammlung.\n\n"
    type_labels = {
        "summary": "Dokument-Zusammenfassungen",
        "entity": "Entitaeten (Personen, Organisationen, Orte)",
        "concept": "Konzepte & Fachbegriffe",
        "synthesis": "Synthesen",
        "comparison": "Vergleiche",
    }
    for ptype, pages_in_type in sorted(by_type.items()):
        md += f"\n## {type_labels.get(ptype, ptype.capitalize())} ({len(pages_in_type)})\n\n"
        for p in pages_in_type:
            snippet = (p.content_md or "")[:120].replace("\n", " ").strip()
            md += f"- [{p.title}](./{p.slug}.md) — {snippet}...\n"

    # Index-Seite speichern
    idx_slug = "index"
    idx_page, _ = await _get_or_create_page(
        db, store_id, idx_slug, "Wiki-Index", WikiPageType.INDEX,
    )
    idx_page.content_md = md
    idx_page.last_updated = datetime.datetime.utcnow()
    await db.commit()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Operation: QUERY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

QUERY_SYSTEM_PROMPT = """Du beantwortest Fragen AUSSCHLIESSLICH auf Basis der bereitgestellten
Wiki-Seiten einer kommunalen Sammlung. Erfinde NICHTS.
Wenn die Seiten die Frage nicht beantworten, sage das klar.
Zitiere die Quellen-Wikiseiten in deiner Antwort."""


async def wiki_query(
    db: AsyncSession,
    store_id: str,
    question: str,
    provider_id: str = "ollama",
    model: str = None,
    max_pages: int = 5,
) -> dict:
    """
    RAG gegen Wiki-Seiten statt Chunks.
    Liest zuerst den Index, identifiziert relevante Seiten per Keyword-Match,
    dann LLM-Antwort mit Seiten-Inhalten als Kontext.

    API-Keys werden nur noch über Umgebungsvariablen konfiguriert (DOCSTORE_*_API_KEY).
    """
    # Alle Wiki-Seiten laden (ohne Inhalt fuer Scoring)
    result = await db.execute(
        select(WikiPage)
        .where(WikiPage.store_id == store_id)
        .where(WikiPage.page_type != WikiPageType.INDEX)
    )
    all_pages = list(result.scalars().all())

    if not all_pages:
        return {
            "question": question,
            "answer": "Das Wiki dieser Sammlung ist noch leer. Laden Sie zunaechst Dokumente hoch.",
            "pages_used": [],
            "llm_generated": False,
        }

    # Einfaches Keyword-Scoring auf Titel + Content
    q_words = set(re.findall(r"\w+", question.lower()))
    q_words = {w for w in q_words if len(w) > 3}

    scored = []
    for p in all_pages:
        title_words = set(re.findall(r"\w+", (p.title or "").lower()))
        content_words = set(re.findall(r"\w+", (p.content_md or "").lower()))
        title_hits = len(q_words & title_words) * 3
        content_hits = len(q_words & content_words)
        score = title_hits + content_hits
        if score > 0:
            scored.append((score, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_pages = [p for _, p in scored[:max_pages]]

    if not top_pages:
        return {
            "question": question,
            "answer": f"Keine Wiki-Seiten gefunden die zur Frage passen ({len(all_pages)} Seiten insgesamt).",
            "pages_used": [],
            "llm_generated": False,
        }

    # Kontext aus Top-Seiten aufbauen
    context_parts = []
    pages_used = []
    for p in top_pages:
        content_snippet = (p.content_md or "")[:1500]
        context_parts.append(f"## [{p.title}] (slug: {p.slug})\n{content_snippet}")
        pages_used.append({"slug": p.slug, "title": p.title})

    context = "\n\n---\n\n".join(context_parts)

    # LLM-Anfrage
    try:
        result = await llm_client.chat_completion(
            messages=[
                {"role": "system", "content": QUERY_SYSTEM_PROMPT},
                {"role": "user", "content": f"Frage: {question}\n\nWiki-Seiten:\n{context}"},
            ],
            provider_id=provider_id,
            model=model,
            temperature=0.2,
            max_tokens=1500,
        )
        answer = result.get("content", "").strip()
        llm_ok = True
    except Exception as e:
        logger.warning(f"Wiki-Query LLM-Fehler: {e}")
        answer = f"Relevante Wiki-Seiten ({len(top_pages)}):\n\n"
        for p in top_pages:
            answer += f"- **{p.title}**: {(p.content_md or '')[:200]}...\n"
        llm_ok = False

    await _log_operation(
        db, store_id, "query",
        f"Frage: {question[:100]}",
        pages_affected=[p.slug for p in top_pages],
        details={"pages_used": len(top_pages), "llm": llm_ok},
    )

    return {
        "question": question,
        "answer": answer,
        "pages_used": pages_used,
        "llm_generated": llm_ok,
    }


async def save_query_as_page(
    db: AsyncSession,
    store_id: str,
    question: str,
    answer: str,
    title: str = None,
    page_type: str = "synthesis",
) -> dict:
    """Eine gute Chat-Antwort als neue Wiki-Seite speichern."""
    t = title or f"Antwort: {question[:80]}"
    slug = _slugify(t)
    try:
        ptype = WikiPageType(page_type)
    except ValueError:
        ptype = WikiPageType.SYNTHESIS

    page, created = await _get_or_create_page(db, store_id, slug, t, ptype)
    content = f"# {t}\n\n**Frage:** {question}\n\n**Antwort:**\n\n{answer}\n\n---\n*Gespeichert am {datetime.date.today().isoformat()}*"
    page.content_md = content
    page.last_updated = datetime.datetime.utcnow()
    await db.commit()

    await _log_operation(
        db, store_id, "save_answer",
        f"Antwort gespeichert: {t[:80]}",
        pages_affected=[slug],
    )
    await _update_index_page(db, store_id)

    return {"slug": slug, "title": t, "created": created}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Operation: LINT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def wiki_lint(db: AsyncSession, store_id: str) -> dict:
    """
    Wiki-Health-Check:
    - Orphan-Pages (keine eingehenden Links)
    - Seiten mit Widersprueche-Flags
    - Fachbegriffe ohne eigene Seite
    - Stale pages (>90 Tage nicht aktualisiert bei >2 neuen Sources)
    """
    # Alle Seiten
    result = await db.execute(
        select(WikiPage).where(
            and_(WikiPage.store_id == store_id, WikiPage.page_type != WikiPageType.INDEX)
        )
    )
    pages = list(result.scalars().all())

    issues = []

    # 1. Orphan-Pages finden
    all_slugs = {p.slug for p in pages}
    linked_to = set()
    for p in pages:
        for link in (p.outgoing_links or []):
            linked_to.add(link.get("slug"))
    orphans = [p for p in pages if p.slug not in linked_to and p.page_type != WikiPageType.SUMMARY]
    for o in orphans[:10]:
        issues.append({
            "type": "orphan_page",
            "severity": "info",
            "slug": o.slug,
            "title": o.title,
            "recommendation": f"Seite '{o.title}' hat keine eingehenden Links. Pruefen ob sie mit anderen verlinkt werden sollte.",
        })

    # 2. Seiten mit Widerspruechen
    contradiction_pages = [p for p in pages if p.contradiction_flags]
    for c in contradiction_pages:
        for flag in (c.contradiction_flags or [])[:3]:
            issues.append({
                "type": "contradiction",
                "severity": "warning",
                "slug": c.slug,
                "title": c.title,
                "recommendation": f"Widerspruch auf '{c.title}': {flag.get('new_claim', '')[:100]} vs {flag.get('conflicts_with', '')[:100]}",
            })

    # 3. Fachbegriffe ohne eigene Seite (aus NER-Daten aggregieren)
    doc_result = await db.execute(
        select(Document).where(Document.store_id == store_id)
    )
    docs = list(doc_result.scalars().all())

    all_terms: dict[str, int] = {}
    for doc in docs:
        if not doc.content_text:
            continue
        ents = extract_entities(doc.content_text)
        for fb in ents.fachbegriffe[:10]:
            val = fb.get("value", "") if isinstance(fb, dict) else str(fb)
            if val:
                all_terms[val] = all_terms.get(val, 0) + 1

    terms_with_pages = {p.title.lower() for p in pages}
    for term, count in all_terms.items():
        if count >= 2 and term.lower() not in terms_with_pages:
            issues.append({
                "type": "missing_concept",
                "severity": "info",
                "term": term,
                "occurrence_count": count,
                "recommendation": f"Fachbegriff '{term}' erscheint {count}x in Dokumenten, hat aber keine eigene Wiki-Seite.",
            })

    # 4. Stale pages
    now = datetime.datetime.utcnow()
    threshold = now - datetime.timedelta(days=90)
    stale = [p for p in pages if p.last_updated and p.last_updated < threshold]
    for s in stale[:5]:
        age_days = (now - s.last_updated).days
        issues.append({
            "type": "stale_page",
            "severity": "info",
            "slug": s.slug,
            "title": s.title,
            "age_days": age_days,
            "recommendation": f"Seite '{s.title}' seit {age_days} Tagen nicht aktualisiert.",
        })

    # Log
    await _log_operation(
        db, store_id, "lint",
        f"Health-Check: {len(issues)} Hinweise",
        details={
            "orphans": len(orphans),
            "contradictions": len(contradiction_pages),
            "missing_concepts": len([i for i in issues if i["type"] == "missing_concept"]),
            "stale": len(stale),
        },
    )

    return {
        "total_pages": len(pages),
        "issues_found": len(issues),
        "issues": issues,
        "summary": {
            "orphans": len(orphans),
            "contradictions": len(contradiction_pages),
            "missing_concepts": len([i for i in issues if i["type"] == "missing_concept"]),
            "stale": len(stale),
        },
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Read-Funktionen
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def list_pages(db: AsyncSession, store_id: str) -> list[dict]:
    """Alle Wiki-Seiten eines Stores auflisten."""
    result = await db.execute(
        select(WikiPage).where(WikiPage.store_id == store_id)
        .order_by(WikiPage.page_type, WikiPage.title)
    )
    return [p.to_dict(include_content=False) for p in result.scalars().all()]


async def get_page(db: AsyncSession, store_id: str, slug: str) -> Optional[dict]:
    """Einzelne Wiki-Seite laden (mit Inhalt)."""
    result = await db.execute(
        select(WikiPage).where(
            and_(WikiPage.store_id == store_id, WikiPage.slug == slug)
        )
    )
    page = result.scalar_one_or_none()
    return page.to_dict(include_content=True) if page else None


async def get_log(db: AsyncSession, store_id: str, limit: int = 50) -> list[dict]:
    """Chronik-Eintraege einer Sammlung."""
    result = await db.execute(
        select(WikiOperation)
        .where(WikiOperation.store_id == store_id)
        .order_by(desc(WikiOperation.created_at))
        .limit(limit)
    )
    return [op.to_dict() for op in result.scalars().all()]
