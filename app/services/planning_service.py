"""
Planning-Service – Maßnahmen-Extraktion und Kanban pro Store.

Extrahiert Maßnahmen, Fristen und Verantwortlichkeiten
ausschließlich aus den Dokumenten eines Stores.
"""
import logging
import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.database import (
    Store, Document, PlanTask, DocumentStatus,
    TaskStatus, TaskPriority, gen_id,
)
from app.ingestion.ner import extract_entities

logger = logging.getLogger(__name__)

# Farb-Rotation für Tasks
TASK_COLORS = [
    "#d90000", "#0094DE", "#8181EF", "#00965E",
    "#E89600", "#9ABF00", "#F1C400", "#00B2A9", "#F0AF00",
]


def extract_tasks_from_store_docs(documents: list) -> list[dict]:
    """
    Maßnahmen aus Dokumenten extrahieren.
    Nutzt NER-Ergebnisse (Fachbegriffe, Personen, Daten)
    um konkrete Aufgaben abzuleiten.
    """
    tasks = []
    color_idx = 0

    for doc in documents:
        content = doc.content_text if hasattr(doc, "content_text") else (doc.get("content_text") or "")
        title = doc.title if hasattr(doc, "title") else doc.get("title", "")
        if not content:
            continue

        ents = extract_entities(content)

        # Fachbegriffe → Maßnahmen (ents gibt dicts mit 'value' zurück)
        fachbegriffe = [e["value"] if isinstance(e, dict) else e for e in ents.fachbegriffe]
        personen = [e["value"] if isinstance(e, dict) else e for e in ents.personen]
        daten = [e["value"] if isinstance(e, dict) else e for e in ents.daten]

        for term in fachbegriffe[:4]:
            assignee = personen[0] if personen else "Zuständige Stelle"
            due = daten[0] if daten else ""

            # Priorität aus Kontext ableiten
            priority = "mittel"
            term_lower = term.lower()
            if any(kw in term_lower for kw in ["dsgvo", "sicherheit", "compliance", "genehmigung"]):
                priority = "hoch"
            elif any(kw in term_lower for kw in ["barrierefreiheit", "nachhaltigkeit"]):
                priority = "niedrig"

            tasks.append({
                "title": f"{term} umsetzen",
                "description": f"Aus '{title}' extrahiert",
                "status": "backlog",
                "priority": priority,
                "due_date": due,
                "assignee": assignee,
                "source_document": title,
                "source_entity": term,
                "color": TASK_COLORS[color_idx % len(TASK_COLORS)],
            })
            color_idx += 1

        # Explizite Maßnahmen-Sätze erkennen
        maßnahmen_patterns = [
            r"(?:Die\s+)?Maßnahme\s+(?:zur?\s+)?(.{10,80}?)(?:\.|,|wird|ist|soll)",
            r"(?:Der\s+)?Beschluss\s+(?:zur?\s+)?(.{10,80}?)(?:\.|,|sieht|wurde)",
            r"(?:Der\s+)?Antrag\s+(?:auf\s+)?(.{10,80}?)(?:\.|,|wurde|ist)",
        ]
        for pattern in maßnahmen_patterns:
            for match in re.finditer(pattern, content):
                task_title = match.group(1).strip()
                if len(task_title) > 10 and not any(t["title"] == task_title for t in tasks):
                    tasks.append({
                        "title": task_title,
                        "description": f"Maßnahme aus '{title}'",
                        "status": "planning",
                        "priority": "hoch",
                        "due_date": daten[0] if daten else "",
                        "assignee": personen[0] if personen else "",
                        "source_document": title,
                        "source_entity": "Maßnahme",
                        "color": TASK_COLORS[color_idx % len(TASK_COLORS)],
                    })
                    color_idx += 1

    if not tasks:
        tasks.append({
            "title": "Keine Maßnahmen erkannt",
            "description": "Laden Sie Dokumente hoch, um Maßnahmen zu extrahieren",
            "status": "backlog",
            "priority": "niedrig",
            "due_date": "",
            "assignee": "",
            "source_document": "",
            "source_entity": "",
            "color": "#adb5bd",
        })

    return tasks


async def auto_extract_tasks(db: AsyncSession, store_id: str) -> list[dict]:
    """
    Maßnahmen aus allen indizierten Dokumenten eines Stores extrahieren
    und als PlanTask-Objekte in der DB speichern.
    """
    result = await db.execute(
        select(Store)
        .where(Store.id == store_id)
        .options(selectinload(Store.documents).selectinload(Document.entities))
    )
    store = result.scalar_one_or_none()
    if not store:
        raise ValueError(f"Store {store_id} nicht gefunden")

    indexed_docs = [d for d in store.documents if d.status == DocumentStatus.INDEXED]
    raw_tasks = extract_tasks_from_store_docs(indexed_docs)

    # In DB speichern
    db_tasks = []
    for t in raw_tasks:
        task = PlanTask(
            id=gen_id(),
            store_id=store_id,
            title=t["title"],
            description=t["description"],
            status=TaskStatus(t["status"]),
            priority=TaskPriority(t["priority"]),
            due_date=t["due_date"],
            assignee=t["assignee"],
            source_document=t["source_document"],
            source_entity=t["source_entity"],
            color=t["color"],
        )
        db.add(task)
        db_tasks.append(task)

    await db.commit()
    logger.info(f"Planung [{store.name}]: {len(db_tasks)} Maßnahmen extrahiert")
    return [t.to_dict() for t in db_tasks]


async def get_tasks(db: AsyncSession, store_id: str) -> list[dict]:
    """Alle Maßnahmen eines Stores abrufen."""
    result = await db.execute(
        select(PlanTask)
        .where(PlanTask.store_id == store_id)
        .order_by(PlanTask.created_at.desc())
    )
    tasks = result.scalars().all()

    # Wenn keine Tasks in DB → automatisch extrahieren
    if not tasks:
        return await auto_extract_tasks(db, store_id)

    return [t.to_dict() for t in tasks]


async def update_task(
    db: AsyncSession,
    store_id: str,
    task_id: str,
    updates: dict,
) -> dict:
    """Task aktualisieren (Status ändern, Zuständigkeit etc.)."""
    result = await db.execute(
        select(PlanTask)
        .where(PlanTask.id == task_id, PlanTask.store_id == store_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise ValueError(f"Task {task_id} nicht gefunden in Store {store_id}")

    for field, value in updates.items():
        if field == "status" and value:
            task.status = TaskStatus(value)
        elif field == "priority" and value:
            task.priority = TaskPriority(value)
        elif hasattr(task, field) and value is not None:
            setattr(task, field, value)

    await db.commit()
    return task.to_dict()


async def create_task(db: AsyncSession, store_id: str, data: dict) -> dict:
    """Neue Massnahme manuell erstellen."""
    depends = data.get("depends_on", [])
    # Blocked-Count berechnen: Wie viele Abhaengigkeiten sind noch nicht done?
    blocked = 0
    if depends:
        for dep_id in depends:
            dep_result = await db.execute(
                select(PlanTask).where(PlanTask.id == dep_id, PlanTask.store_id == store_id)
            )
            dep_task = dep_result.scalar_one_or_none()
            if dep_task and dep_task.status != TaskStatus.DONE:
                blocked += 1

    task = PlanTask(
        id=gen_id(),
        store_id=store_id,
        title=data["title"],
        description=data.get("description", ""),
        status=TaskStatus.BACKLOG,
        priority=TaskPriority(data.get("priority", "mittel")),
        due_date=data.get("due_date", ""),
        assignee=data.get("assignee", ""),
        source_document="Manuell erstellt",
        source_entity="",
        color="#00B2A9",
        depends_on=depends,
        blocked_by_count=blocked,
    )
    db.add(task)
    await db.commit()
    return task.to_dict()


async def delete_task(db: AsyncSession, store_id: str, task_id: str) -> None:
    """Task löschen."""
    result = await db.execute(
        select(PlanTask)
        .where(PlanTask.id == task_id, PlanTask.store_id == store_id)
    )
    task = result.scalar_one_or_none()
    if task:
        await db.delete(task)
        await db.commit()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Wiki-Wartung: Lint-Issues → Planning-Tasks
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Mapping: Lint-Issue-Typ → Task-Template
WIKI_LINT_TEMPLATES = {
    "contradiction": {
        "priority": TaskPriority.HIGH,
        "color": "#d90000",  # rot
        "title_template": "Widerspruch klaeren: {title}",
        "description_template": "Auf der Wiki-Seite '{title}' wurde ein Widerspruch gefunden.\n\n{recommendation}\n\nBitte Quellen pruefen und Seite korrigieren.",
    },
    "missing_concept": {
        "priority": TaskPriority.MEDIUM,
        "color": "#E89600",  # amber
        "title_template": "Konzept-Seite anlegen: {term}",
        "description_template": "Der Fachbegriff '{term}' erscheint {occurrence_count}x in Dokumenten dieser Sammlung, hat aber noch keine eigene Wiki-Seite.\n\nBitte Wiki-Seite mit Definition und Bezuegen zu den Quelldokumenten anlegen.",
    },
    "orphan_page": {
        "priority": TaskPriority.LOW,
        "color": "#00B2A9",  # lagoon
        "title_template": "Verknuepfen: {title}",
        "description_template": "Die Wiki-Seite '{title}' hat keine eingehenden Links.\n\n{recommendation}",
    },
    "stale_page": {
        "priority": TaskPriority.LOW,
        "color": "#888780",  # gray
        "title_template": "Veraltete Seite pruefen: {title}",
        "description_template": "Die Wiki-Seite '{title}' wurde seit {age_days} Tagen nicht aktualisiert.\n\nBitte pruefen ob der Inhalt noch aktuell ist oder ob neuere Quellen eingearbeitet werden sollten.",
    },
}


def _fingerprint_for_issue(issue: dict) -> str:
    """
    Erzeugt einen stabilen Fingerprint fuer einen Lint-Issue,
    um Duplikate bei wiederholtem Lint-Lauf zu vermeiden.
    Der Fingerprint wird in source_entity gespeichert.
    """
    t = issue.get("type", "")
    if t == "missing_concept":
        return f"wiki:missing:{issue.get('term', '')[:80]}"
    elif t == "contradiction":
        # Contradiction ist seiten-spezifisch; unique per (slug + claim-prefix)
        claim = issue.get("recommendation", "")[:60]
        return f"wiki:contradiction:{issue.get('slug', '')}:{claim}"
    else:
        # orphan, stale: ein Task pro Seite
        return f"wiki:{t}:{issue.get('slug', '')}"


async def wiki_lint_to_tasks(db: AsyncSession, store_id: str) -> dict:
    """
    Fuehrt Wiki-Lint aus und erzeugt fuer jeden Issue einen Planning-Task.
    Duplikate werden per Fingerprint (source_entity) vermieden.

    Gibt zurueck: {created, skipped, total_issues, tasks}
    """
    from app.services.wiki_service import wiki_lint

    # Lint-Ergebnisse holen
    lint_result = await wiki_lint(db, store_id)
    issues = lint_result.get("issues", [])

    if not issues:
        return {
            "total_issues": 0,
            "created": 0,
            "skipped": 0,
            "tasks": [],
            "lint_summary": lint_result.get("summary", {}),
        }

    # Bestehende Wiki-Wartungs-Tasks laden (fuer Deduplizierung)
    existing_result = await db.execute(
        select(PlanTask).where(
            PlanTask.store_id == store_id,
            PlanTask.source_document.like("wiki-lint:%"),
            PlanTask.status != TaskStatus.DONE,  # erledigte Tasks erlauben neue
        )
    )
    existing_fingerprints = {
        t.source_entity for t in existing_result.scalars().all() if t.source_entity
    }

    created_tasks = []
    created_count = 0
    skipped_count = 0

    for issue in issues:
        issue_type = issue.get("type", "")
        template = WIKI_LINT_TEMPLATES.get(issue_type)
        if not template:
            continue

        # Fingerprint fuer Dedup
        fp = _fingerprint_for_issue(issue)
        if fp in existing_fingerprints:
            skipped_count += 1
            continue

        # Task-Titel und Beschreibung aus Template
        fmt_args = {
            "title": issue.get("title", "?"),
            "slug": issue.get("slug", ""),
            "term": issue.get("term", ""),
            "occurrence_count": issue.get("occurrence_count", 0),
            "age_days": issue.get("age_days", 0),
            "recommendation": issue.get("recommendation", ""),
        }
        try:
            task_title = template["title_template"].format(**fmt_args)
            task_desc = template["description_template"].format(**fmt_args)
        except KeyError as e:
            logger.warning(f"Template-Formatierung fehlgeschlagen fuer {issue_type}: {e}")
            task_title = f"Wiki-Wartung: {issue_type}"
            task_desc = issue.get("recommendation", "")

        task = PlanTask(
            id=gen_id(),
            store_id=store_id,
            title=task_title[:500],
            description=task_desc,
            status=TaskStatus.BACKLOG,
            priority=template["priority"],
            assignee="Wiki-Maintainer",
            source_document=f"wiki-lint:{issue_type}",
            source_entity=fp,
            color=template["color"],
        )
        db.add(task)
        existing_fingerprints.add(fp)
        created_tasks.append(task)
        created_count += 1

    await db.commit()

    logger.info(
        f"Wiki-Wartung: {created_count} Tasks erzeugt, "
        f"{skipped_count} uebersprungen (bereits vorhanden) aus {len(issues)} Issues"
    )

    return {
        "total_issues": len(issues),
        "created": created_count,
        "skipped": skipped_count,
        "tasks": [t.to_dict() for t in created_tasks],
        "lint_summary": lint_result.get("summary", {}),
    }


async def get_tasks_filtered(
    db: AsyncSession,
    store_id: str,
    category: Optional[str] = None,
) -> list[dict]:
    """
    Tasks laden mit optionalem Filter nach Quelle.
      - category="wiki-maintenance": nur Wiki-Lint-generierte Tasks
      - category="documents": nur aus Dokumenten extrahierte Tasks (nicht wiki-lint)
      - category=None: alle Tasks
    """
    query = select(PlanTask).where(PlanTask.store_id == store_id)
    if category == "wiki-maintenance":
        query = query.where(PlanTask.source_document.like("wiki-lint:%"))
    elif category == "documents":
        query = query.where(~PlanTask.source_document.like("wiki-lint:%"))

    query = query.order_by(PlanTask.created_at.desc())
    result = await db.execute(query)
    return [t.to_dict() for t in result.scalars().all()]
