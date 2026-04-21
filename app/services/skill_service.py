"""
Skill-Service – Automatisierte Verarbeitung pro Store.

Jeder Skill arbeitet ausschließlich mit den Dokumenten
des zugewiesenen Stores. Kein Zugriff auf andere Stores.

Skills:
  - pptx:     PowerPoint-Präsentation erstellen
  - docx:     Word-Dokument generieren
  - blog:     Blog-Beitrag generieren
  - press:    Presseanfrage beantworten
  - anon:     Anonymisierung (DSGVO)
  - planning: Maßnahmenplanung extrahieren
"""
import datetime
import logging
import re
from typing import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.database import (
    Store, Document, Entity, SkillExecution,
    DocumentStatus, EntityType, gen_id,
)
from app.services.intelligence import generate_summary, extract_key_takeaways, distill_facts, fuse_knowledge
from app.ingestion.ner import extract_entities

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LLM-Hilfsfunktion — von allen Content-Skills genutzt
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _llm_generate(
    system: str,
    user: str,
    provider_id: str = "ollama",
    model: str = None,
    temperature: float = 0.4,
    max_tokens: int = 2000,
) -> str | None:
    """
    Zentrale LLM-Generierung fuer Skills.

    API-Keys werden nur noch über Umgebungsvariablen konfiguriert (DOCSTORE_*_API_KEY).
    Versucht den konfigurierten Provider, gibt None zurueck bei Fehler (→ Fallback).
    """
    try:
        from app.core.llm_client import llm_client
        result = await llm_client.chat_completion(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            provider_id=provider_id,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = result.get("content", "").strip()
        if content and len(content) > 20:
            logger.info(f"LLM-Generierung erfolgreich: {len(content)} Zeichen via {result.get('provider', provider_id)}/{result.get('model', '?')}")
            return content
        return None
    except Exception as e:
        logger.info(f"LLM nicht verfuegbar, Fallback auf Extraktion: {e}")
        return None

# ─── Skill-Definitionen ───
SKILL_CATALOG = {
    "pptx": {
        "name": "PowerPoint erstellen",
        "description": "Generiert eine Präsentation aus den Dokumenten der Sammlung",
        "category": "Dokumente",
        "parameters": ["title", "slides", "focus"],
    },
    "docx": {
        "name": "Word-Dokument erstellen",
        "description": "Erstellt ein formatiertes Dokument aus der Sammlung",
        "category": "Dokumente",
        "parameters": ["title", "sections"],
    },
    "blog": {
        "name": "Blog-Beitrag generieren",
        "description": "Erstellt einen öffentlichkeitstauglichen Blog-Beitrag",
        "category": "Content",
        "parameters": ["title", "tone", "length"],
    },
    "press": {
        "name": "Presseanfrage beantworten",
        "description": "Generiert eine sachliche Antwort auf eine Presseanfrage",
        "category": "Kommunikation",
        "parameters": ["question", "tone"],
    },
    "anon": {
        "name": "Anonymisierung",
        "description": "Entfernt personenbezogene Daten (DSGVO-konform)",
        "category": "DSGVO",
        "parameters": ["scope", "entities"],
    },
    "planning": {
        "name": "Maßnahmenplanung",
        "description": "Extrahiert Maßnahmen und erstellt Umsetzungsplan",
        "category": "Planung",
        "parameters": ["timeframe", "priority"],
    },
}


async def execute_skill(
    db: AsyncSession,
    store_id: str,
    skill_id: str,
    parameters: dict,
) -> AsyncGenerator[dict, None]:
    """
    Skill ausführen – streamt Fortschritt via SSE.
    Arbeitet AUSSCHLIESSLICH mit Dokumenten des angegebenen Stores.
    """
    skill_def = SKILL_CATALOG.get(skill_id)
    if not skill_def:
        yield {"step": "error", "progress": 0, "message": f"Unbekannter Skill: {skill_id}"}
        return

    # ── Store laden (isoliert) ──
    result = await db.execute(
        select(Store)
        .where(Store.id == store_id)
        .options(selectinload(Store.documents).selectinload(Document.entities))
    )
    store = result.scalar_one_or_none()
    if not store:
        yield {"step": "error", "progress": 0, "message": "Sammlung nicht gefunden"}
        return

    indexed_docs = [d for d in store.documents if d.status == DocumentStatus.INDEXED]
    if not indexed_docs:
        yield {"step": "error", "progress": 0, "message": "Keine indizierten Dokumente in dieser Sammlung"}
        return

    # ── Ausführung protokollieren ──
    execution = SkillExecution(
        id=gen_id(),
        store_id=store_id,
        skill_id=skill_id,
        skill_name=skill_def["name"],
        parameters=parameters,
        status="running",
    )
    db.add(execution)
    await db.commit()

    store_label = "Akte" if store.type.value == "akte" else "WissensDB"

    yield {
        "step": "init", "progress": 0.05,
        "message": f"Skill '{skill_def['name']}' gestartet fuer {store_label} '{store.name}'"
    }

    # ── Dokumente analysieren ──
    yield {
        "step": "load", "progress": 0.15,
        "message": f"{len(indexed_docs)} Dokumente aus '{store.name}' werden geladen…"
    }

    texts = [d.content_text for d in indexed_docs if d.content_text]
    all_entities = []
    for doc in indexed_docs:
        for ent in (doc.entities or []):
            all_entities.append(ent)

    yield {"step": "analyze", "progress": 0.30, "message": "Inhalte werden analysiert…"}

    # ── Skill-spezifische Verarbeitung ──
    if skill_id == "pptx":
        result_data = await _skill_pptx(texts, all_entities, parameters, store)
    elif skill_id == "docx":
        result_data = await _skill_docx(texts, all_entities, parameters, store)
    elif skill_id == "blog":
        result_data = await _skill_blog(texts, all_entities, parameters, store)
    elif skill_id == "press":
        result_data = await _skill_press(texts, all_entities, parameters, store)
    elif skill_id == "anon":
        result_data = await _skill_anonymize(texts, all_entities, parameters, store, indexed_docs)
    elif skill_id == "planning":
        result_data = await _skill_planning(texts, all_entities, parameters, store, indexed_docs)
    else:
        result_data = {"error": "Skill nicht implementiert"}

    yield {"step": "generate", "progress": 0.70, "message": f"{skill_def['name']} wird generiert…"}
    yield {"step": "quality", "progress": 0.85, "message": "Qualitätsprüfung…"}

    # ── Abschluss ──
    execution.status = "completed"
    execution.result = result_data
    execution.completed_at = datetime.datetime.utcnow()
    await db.commit()

    yield {
        "step": "done", "progress": 1.0,
        "message": f"✓ {skill_def['name']} erfolgreich erstellt",
        "execution_id": execution.id,
        "result": result_data,
    }


async def get_skill_catalog(store_id: str) -> list[dict]:
    """Skill-Katalog mit Store-Kontext zurückgeben."""
    return [
        {**v, "id": k, "store_id": store_id}
        for k, v in SKILL_CATALOG.items()
    ]


async def get_executions(db: AsyncSession, store_id: str) -> list[dict]:
    """Alle Skill-Ausführungen eines Stores abrufen."""
    result = await db.execute(
        select(SkillExecution)
        .where(SkillExecution.store_id == store_id)
        .order_by(SkillExecution.started_at.desc())
        .limit(50)
    )
    return [e.to_dict() for e in result.scalars().all()]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Skill-Implementierungen
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _skill_pptx(texts, entities, params, store):
    """PowerPoint aus Store-Inhalten generieren (LLM-gestuetzte Folieninhalte)."""
    from app.services.export_service import export_pptx
    from app.core.config import settings

    store_type = store.type.value if hasattr(store.type, "value") else store.type
    title = params.get("title", f"Bericht: {store.name}")
    focus = params.get("focus", "")
    source_text = "\n\n".join(texts)[:3000]

    # LLM generiert Folien-Content
    llm_content = await _llm_generate(
        system=f"""Du bist ein Praesentations-Experte fuer kommunale Verwaltung.
Erstelle Inhalte fuer eine PowerPoint-Praesentation.
{f'Schwerpunkt: {focus}' if focus else ''}
Verwende AUSSCHLIESSLICH Informationen aus den Quellen.

Gib fuer jede Folie zurueck:
- slide_title: Folientitel
- content: 2-4 Stichpunkte (jeweils 1 Satz)

Antwort als JSON-Array: [{{"slide_title":"...","content":"..."}}]
Erstelle 4-6 inhaltliche Folien (ohne Titel- und Schlussfolie).""",
        user=f"Titel: {title}\nQuellen aus '{store.name}':\n{source_text}",
        temperature=0.3,
    )

    # LLM-Folieninhalte in doc_dicts einbauen fuer Export-Service
    doc_dicts = [{"content": t, "title": f"Dok_{i+1}", "file_type": "txt", "page_count": 1}
                 for i, t in enumerate(texts)]

    # Wenn LLM Inhalte liefert, als Metadata mitgeben
    if llm_content:
        try:
            import json as jm
            match = re.search(r"\[.*\]", llm_content, re.DOTALL)
            if match:
                slides_data = jm.loads(match.group())
                params["_llm_slides"] = slides_data
        except Exception:
            pass

    pptx_bytes = export_pptx(store.name, store_type, doc_dicts, params)

    output_dir = settings.stores_dir / store.id
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{store.name.replace(' ', '_')}_Skill.pptx"
    output_path = output_dir / filename
    output_path.write_bytes(pptx_bytes)

    return {
        "type": "pptx", "file_generated": True,
        "output_path": str(output_path), "filename": filename,
        "file_size_kb": len(pptx_bytes) // 1024,
        "source_store": store.name, "source_documents": len(texts),
        "llm_generated": llm_content is not None,
    }


async def _skill_docx(texts, entities, params, store):
    """Word-Dokument aus Store-Inhalten generieren (LLM-gestuetzte Abschnitte)."""
    from app.services.export_service import export_docx
    from app.core.config import settings

    store_type = store.type.value if hasattr(store.type, "value") else store.type
    doc_title = params.get("title", f"Bericht: {store.name}")
    sections_param = params.get("sections", "Zusammenfassung,Analyse,Empfehlung")
    sections = [s.strip() for s in sections_param.split(",")]
    source_text = "\n\n".join(texts)[:3000]

    # LLM generiert Abschnittsinhalte
    llm_content = await _llm_generate(
        system=f"""Du bist ein Fachredakteur fuer kommunale Berichte.
Schreibe Inhalte fuer ein Word-Dokument mit dem Titel '{doc_title}'.
Abschnitte: {', '.join(sections)}

Fuer jeden Abschnitt: 2-4 Saetze Fliesstext. KEINE Aufzaehlungen.
Verwende AUSSCHLIESSLICH Informationen aus den Quellen.
Antwort als JSON-Objekt: {{"Abschnittname": "Inhalt", ...}}""",
        user=f"Quellen aus '{store.name}':\n{source_text}",
        temperature=0.3,
    )

    if llm_content:
        try:
            import json as jm
            match = re.search(r"\{.*\}", llm_content, re.DOTALL)
            if match:
                params["_llm_sections"] = jm.loads(match.group())
        except Exception:
            pass

    doc_dicts = [{"content": t, "title": f"Dok_{i+1}", "file_type": "txt", "page_count": 1}
                 for i, t in enumerate(texts)]
    ent_data = {}
    for ent in entities:
        etype = ent.entity_type.value if hasattr(ent, "entity_type") else (ent.get("type") or "sonstig")
        ent_data.setdefault(etype, []).append(ent.to_dict() if hasattr(ent, "to_dict") else ent)

    docx_bytes = export_docx(store.name, store_type, doc_dicts, ent_data, params)

    output_dir = settings.stores_dir / store.id
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{store.name.replace(' ', '_')}_Skill.docx"
    output_path = output_dir / filename
    output_path.write_bytes(docx_bytes)

    return {
        "type": "docx", "file_generated": True,
        "output_path": str(output_path), "filename": filename,
        "file_size_kb": len(docx_bytes) // 1024,
        "source_store": store.name, "source_documents": len(texts),
        "llm_generated": llm_content is not None,
    }


async def _skill_blog(texts, entities, params, store):
    """Blog-Beitrag aus Store-Inhalten generieren (LLM-gestuetzt)."""
    tone = params.get("tone", "informativ")
    title = params.get("title", store.name)
    length = int(params.get("length", 500))

    # Relevante Quellen vorbereiten (max 3000 Zeichen)
    source_text = "\n\n".join(texts)[:3000]

    llm_result = await _llm_generate(
        system=f"""Du bist ein professioneller Redakteur fuer kommunale Verwaltungskommunikation.
Schreibe einen Blog-Beitrag basierend AUSSCHLIESSLICH auf den folgenden Quellen.
Tonalitaet: {tone}. Ziellaenge: ca. {length} Woerter.
Erfinde KEINE Informationen. Verwende nur Fakten aus den Quellen.
Schreibe auf Deutsch. Struktur: Titel, Einleitung, 2-3 Abschnitte, Fazit.""",
        user=f"Thema: {title}\n\nQuellen aus '{store.name}':\n{source_text}",
    )

    if llm_result:
        blog_text = llm_result
    else:
        # Extraktiver Fallback
        summary = generate_summary(texts, max_sentences=8)
        sentences = summary.split(". ")
        blog_text = f"# {title}\n\n"
        blog_text += ". ".join(sentences[:min(len(sentences), length // 50)]) + ".\n\n"
        blog_text += f"---\n*Dieser Beitrag basiert auf {len(texts)} Dokumenten (Offline-Modus).*"

    return {"type": "blog", "title": title, "content": blog_text, "tone": tone,
            "word_count": len(blog_text.split()), "source_store": store.name,
            "llm_generated": llm_result is not None}


async def _skill_press(texts, entities, params, store):
    """Presseanfrage beantworten (LLM-gestuetzt)."""
    question = params.get("question", "Allgemeine Anfrage")
    tone = params.get("tone", "formell")
    source_text = "\n\n".join(texts)[:3000]
    facts = distill_facts(texts)

    llm_result = await _llm_generate(
        system=f"""Du bist Pressesprecher einer kommunalen Verwaltung.
Beantworte die folgende Presseanfrage sachlich und {tone}.
Verwende AUSSCHLIESSLICH Informationen aus den beigefuegten Quellen.
Erfinde KEINE Fakten. Wenn die Quellen keine Antwort hergeben, sage das offen.
Format: Formeller Brief (Sehr geehrte Damen und Herren, ... Mit freundlichen Gruessen).""",
        user=f"Pressefrage: {question}\n\nQuellen aus '{store.name}':\n{source_text}",
    )

    if llm_result:
        answer = llm_result
    else:
        # Template-Fallback
        summary = generate_summary(texts, max_sentences=5)
        answer = f"Sehr geehrte Damen und Herren,\n\nvielen Dank fuer Ihre Anfrage zum Thema '{question}'.\n\n"
        answer += f"Auf Grundlage der vorliegenden Unterlagen:\n\n{summary}\n\n"
        if facts:
            answer += "Zentrale Fakten:\n" + "\n".join(f"- {f['text'][:120]}" for f in facts[:3]) + "\n\n"
        answer += "Fuer weitere Informationen stehen wir gerne zur Verfuegung.\n\nMit freundlichen Gruessen"

    return {"type": "press", "question": question, "answer": answer, "tone": tone,
            "source_store": store.name, "source_documents": len(texts),
            "llm_generated": llm_result is not None}


async def _skill_anonymize(texts, entities, params, store, documents):
    """DSGVO-Anonymisierung – personenbezogene Daten aus Store-Dokumenten entfernen."""
    entity_types = params.get("entities", "Personen, Adressen, Telefonnummern")
    scope = params.get("scope", "Alle Dokumente")

    # Personenbezogene Entitaeten sammeln
    persons = set()
    dates = set()
    locations = set()

    for doc in documents:
        ents = extract_entities(doc.content_text or "")
        for p in ents.personen:
            persons.add(p["value"] if isinstance(p, dict) else p)
        for d in ents.daten:
            dates.add(d["value"] if isinstance(d, dict) else d)
        for o in ents.orte:
            locations.add(o["value"] if isinstance(o, dict) else o)

    # Erweiterte PII-Patterns (DSGVO-konform)
    import re
    pii_patterns = {
        "email": (re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"), "[EMAIL_{:03d}]"),
        "phone": (re.compile(r"(?:\+49|0049|0)\s*[\d\s/\-]{8,15}"), "[TELEFON_{:03d}]"),
        "iban": (re.compile(r"[A-Z]{2}\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{0,4}"), "[IBAN_{:03d}]"),
        "ip": (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "[IP_{:03d}]"),
        "geburtsdatum": (re.compile(r"(?:geb(?:oren)?\.?\s*(?:am\s*)?\d{1,2}\.\d{1,2}\.\d{2,4})"), "[GEBDAT_{:03d}]"),
        "aktenzeichen": (re.compile(r"Az\.?\s*[:.]?\s*[\w\-/]+\d+"), "[AKTZ_{:03d}]"),
    }

    replacements = {}
    for i, person in enumerate(persons, 1):
        replacements[person] = f"[PERSON_{i:03d}]"
    for i, ort in enumerate(locations, 1):
        replacements[ort] = f"[ORT_{i:03d}]"

    # PII aus Texten extrahieren
    pii_found = {}
    all_texts = " ".join(doc.content_text or "" for doc in documents)
    for pii_type, (pattern, template) in pii_patterns.items():
        matches = set(pattern.findall(all_texts))
        pii_found[pii_type] = len(matches)
        for i, match in enumerate(matches, 1):
            replacements[match] = template.format(i)

    total_replacements = 0
    anonymized_docs = []
    for doc in documents:
        text = doc.content_text or ""
        doc_replacements = 0
        for original, replacement in replacements.items():
            count = text.count(original)
            if count > 0:
                text = text.replace(original, replacement)
                doc_replacements += count
        total_replacements += doc_replacements
        anonymized_docs.append({
            "document": doc.title,
            "replacements": doc_replacements,
        })

    return {
        "type": "anonymization",
        "total_entities_found": len(replacements),
        "persons_found": len(persons),
        "locations_found": len(locations),
        "pii_patterns_found": pii_found,
        "total_replacements": total_replacements,
        "documents_processed": len(documents),
        "document_details": anonymized_docs,
        "replacement_map": {k: v for k, v in list(replacements.items())[:10]},
        "source_store": store.name,
    }


async def _skill_planning(texts, entities, params, store, documents):
    """Massnahmen aus Store-Dokumenten extrahieren (LLM-gestuetzt)."""
    import json as json_module
    from app.services.planning_service import extract_tasks_from_store_docs

    timeframe = params.get("timeframe", "")
    priority_mode = params.get("priority", "Nach Dringlichkeit")
    source_text = "\n\n".join(texts)[:4000]

    llm_result = await _llm_generate(
        system=f"""Du bist ein Projektmanager fuer kommunale Verwaltung.
Analysiere die folgenden Dokumente und extrahiere ALLE konkreten Massnahmen, Beschluesse und Aufgaben.

Fuer jede Massnahme gib an:
- title: Kurztitel der Massnahme
- description: Was genau zu tun ist (1-2 Saetze)
- priority: hoch/mittel/niedrig (basierend auf {priority_mode})
- due_date: Geschaetzter Zeitraum oder Frist (wenn im Text erwaehnt)
- assignee: Zustaendige Stelle/Person (wenn im Text erwaehnt)
- depends_on_title: Von welcher anderen Massnahme haengt diese ab (wenn erkennbar)
- source_quote: Kurzes Zitat aus dem Dokument das diese Massnahme begruendet

{f'Zeitraum: {timeframe}' if timeframe else ''}

Antwort NUR als JSON-Array: [{{"title":"...","description":"...","priority":"...","due_date":"...","assignee":"...","depends_on_title":"","source_quote":"..."}}]
Maximal 15 Massnahmen. Erfinde KEINE Massnahmen — nur was in den Quellen steht.""",
        user=f"Dokumente aus '{store.name}':\n{source_text}",
        temperature=0.2,
        max_tokens=3000,
    )

    llm_tasks = []
    if llm_result:
        try:
            # JSON parsen (robust)
            json_match = re.search(r"\[.*\]", llm_result, re.DOTALL)
            if json_match:
                parsed = json_module.loads(json_match.group())
                for t in parsed:
                    if isinstance(t, dict) and t.get("title"):
                        llm_tasks.append({
                            "title": t["title"],
                            "description": t.get("description", ""),
                            "priority": t.get("priority", "mittel"),
                            "due_date": t.get("due_date", ""),
                            "assignee": t.get("assignee", "Zustaendige Stelle"),
                            "depends_on_title": t.get("depends_on_title", ""),
                            "source_quote": t.get("source_quote", ""),
                            "source_document": store.name,
                            "extraction_method": "llm",
                        })
        except Exception as e:
            logger.warning(f"LLM-Planning JSON-Parse fehlgeschlagen: {e}")

    # Fallback oder Merge mit Regex-Tasks
    regex_tasks = extract_tasks_from_store_docs(documents)

    if llm_tasks:
        # LLM-Tasks als primaer, Regex als Ergaenzung
        seen_titles = {t["title"].lower() for t in llm_tasks}
        for rt in regex_tasks:
            if rt["title"].lower() not in seen_titles:
                rt["extraction_method"] = "regex"
                llm_tasks.append(rt)
        tasks = llm_tasks
    else:
        for rt in regex_tasks:
            rt["extraction_method"] = "regex"
        tasks = regex_tasks

    return {
        "type": "planning",
        "tasks_extracted": len(tasks),
        "tasks": tasks,
        "llm_tasks": len([t for t in tasks if t.get("extraction_method") == "llm"]),
        "regex_tasks": len([t for t in tasks if t.get("extraction_method") == "regex"]),
        "timeframe": timeframe,
        "priority_mode": priority_mode,
        "source_store": store.name,
        "source_documents": len(documents),
        "llm_generated": len(llm_tasks) > 0,
    }
