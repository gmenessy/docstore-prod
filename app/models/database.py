"""
Datenbank-Modelle – Sammlungen, Dokumente, Chunks, Entitäten.
Mandantenfähig: Jede Sammlung (Store) ist ein isoliertes Ökosystem.
"""
import datetime
import enum
import uuid

from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean, DateTime,
    ForeignKey, Enum, JSON, Index,
)
from sqlalchemy.orm import DeclarativeBase, relationship


def gen_id() -> str:
    return uuid.uuid4().hex[:12]


class Base(DeclarativeBase):
    pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Enums
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class StoreType(str, enum.Enum):
    AKTE = "akte"
    WISSENSDB = "wissensdb"


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class EntityType(str, enum.Enum):
    PERSON = "person"
    DATUM = "datum"
    FACHBEGRIFF = "fachbegriff"
    ORT = "ort"
    ORGANISATION = "organisation"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Sammlung (Store) – Akte oder WissensDB
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Store(Base):
    __tablename__ = "stores"

    id = Column(String(12), primary_key=True, default=gen_id)
    name = Column(String(255), nullable=False, index=True)
    type = Column(Enum(StoreType), nullable=False, default=StoreType.WISSENSDB)
    description = Column(Text, default="")
    color = Column(String(7), default="#00B2A9")
    analyse_fokus = Column(String(255), default="Allgemeine Analyse")

    # Metadaten
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Beziehungen
    documents = relationship("Document", back_populates="store", cascade="all, delete-orphan")

    def to_dict(self, include_doc_count=False):
        from sqlalchemy.orm import object_session
        from sqlalchemy import inspect as sa_inspect
        d = {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "description": self.description,
            "color": self.color,
            "analyse_fokus": self.analyse_fokus,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "document_count": 0,
        }
        # Nur auf documents zugreifen wenn bereits geladen (kein Lazy-Load trigger)
        state = sa_inspect(self, raiseerr=False)
        if state and "documents" in state.dict:
            d["document_count"] = len(self.documents) if self.documents else 0
        return d


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Dokument
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Document(Base):
    __tablename__ = "documents"

    id = Column(String(12), primary_key=True, default=gen_id)
    store_id = Column(String(12), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    file_type = Column(String(10), nullable=False)  # pdf, docx, pptx, md, ...
    file_path = Column(String(1000), nullable=False)
    file_size = Column(Integer, default=0)  # Bytes
    page_count = Column(Integer, default=0)

    # Verarbeitungsstatus
    status = Column(Enum(DocumentStatus), default=DocumentStatus.PENDING)
    content_text = Column(Text, default="")  # Extrahierter Volltext
    content_summary = Column(Text, default="")  # Auto-Zusammenfassung

    # Medien-Flags
    has_images = Column(Boolean, default=False)
    has_tables = Column(Boolean, default=False)

    # Indexierung
    chunk_count = Column(Integer, default=0)
    indexed_at = Column(DateTime, nullable=True)

    # Tags & Metadaten
    tags = Column(JSON, default=list)
    metadata_extra = Column(JSON, default=dict)

    # Quelle (Upload vs. Web-Scraper)
    source_type = Column(String(20), default="upload")  # upload | url
    source_uri = Column(String(2000), default="")

    # Versionierung
    version = Column(Integer, default=1)
    previous_version_id = Column(String(12), nullable=True)  # FK auf aeltere Version
    is_latest = Column(Boolean, default=True)

    # Zeitstempel
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Beziehungen
    store = relationship("Store", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
    entities = relationship("Entity", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_doc_store_status", "store_id", "status"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "store_id": self.store_id,
            "title": self.title,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "page_count": self.page_count,
            "status": self.status.value,
            "content_summary": self.content_summary,
            "has_images": self.has_images,
            "has_tables": self.has_tables,
            "chunk_count": self.chunk_count,
            "indexed_at": self.indexed_at.isoformat() if self.indexed_at else None,
            "tags": self.tags or [],
            "source_type": self.source_type,
            "source_uri": self.source_uri,
            "version": self.version or 1,
            "is_latest": self.is_latest if self.is_latest is not None else True,
            "previous_version_id": self.previous_version_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def to_detail_dict(self):
        d = self.to_dict()
        d["content_text"] = self.content_text
        d["metadata_extra"] = self.metadata_extra or {}
        d["entities"] = [e.to_dict() for e in (self.entities or [])]
        d["chunks"] = [c.to_dict() for c in (self.chunks or [])]
        return d


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Chunk – Textfragment für Suche & Retrieval
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(String(12), primary_key=True, default=gen_id)
    document_id = Column(String(12), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)  # Position im Dokument
    content = Column(Text, nullable=False)
    token_count = Column(Integer, default=0)

    # Für BM25-Suche
    content_normalized = Column(Text, default="")  # Lowercase, stemmed

    # Vektor-Embedding (JSON-Array als Fallback ohne Qdrant)
    embedding = Column(JSON, nullable=True)

    # Seitenzuordnung
    page_start = Column(Integer, nullable=True)
    page_end = Column(Integer, nullable=True)

    # Beziehung
    document = relationship("Document", back_populates="chunks")

    __table_args__ = (
        Index("idx_chunk_doc_index", "document_id", "chunk_index"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "chunk_index": self.chunk_index,
            "content": self.content,
            "token_count": self.token_count,
            "page_start": self.page_start,
            "page_end": self.page_end,
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Entität – Extrahierte Informationen (NER)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Entity(Base):
    __tablename__ = "entities"

    id = Column(String(12), primary_key=True, default=gen_id)
    document_id = Column(String(12), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type = Column(Enum(EntityType), nullable=False)
    value = Column(String(500), nullable=False)
    count = Column(Integer, default=1)  # Häufigkeit im Dokument
    context = Column(Text, default="")  # Umgebender Text

    document = relationship("Document", back_populates="entities")

    __table_args__ = (
        Index("idx_entity_doc_type", "document_id", "entity_type"),
        Index("idx_entity_value", "value"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.entity_type.value,
            "value": self.value,
            "count": self.count,
            "context": self.context,
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Chat-Nachricht – pro Store isoliert
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String(12), primary_key=True, default=gen_id)
    store_id = Column(String(12), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String(32), nullable=False, index=True)
    role = Column(String(10), nullable=False)  # user | assistant
    content = Column(Text, nullable=False)
    sources = Column(JSON, default=list)  # Quellenverweise [{doc_id, title, score}]
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        Index("idx_chat_store_session", "store_id", "session_id"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "store_id": self.store_id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "sources": self.sources or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Plan-Task – Maßnahme pro Store
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TaskStatus(str, enum.Enum):
    BACKLOG = "backlog"
    PLANNING = "planning"
    ACTIVE = "active"
    DONE = "done"

class TaskPriority(str, enum.Enum):
    HIGH = "hoch"
    MEDIUM = "mittel"
    LOW = "niedrig"

class PlanTask(Base):
    __tablename__ = "plan_tasks"

    id = Column(String(12), primary_key=True, default=gen_id)
    store_id = Column(String(12), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, default="")
    status = Column(Enum(TaskStatus), default=TaskStatus.BACKLOG)
    priority = Column(Enum(TaskPriority), default=TaskPriority.MEDIUM)
    due_date = Column(String(20), default="")
    assignee = Column(String(255), default="")
    source_document = Column(String(500), default="")
    source_entity = Column(String(255), default="")
    color = Column(String(7), default="#00B2A9")
    # Task-Abhaengigkeiten: JSON-Array von Task-IDs
    depends_on = Column(JSON, default=list)  # ["task_id_1", "task_id_2"]
    blocked_by_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    __table_args__ = (
        Index("idx_task_store_status", "store_id", "status"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "store_id": self.store_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "due_date": self.due_date,
            "assignee": self.assignee,
            "source_document": self.source_document,
            "source_entity": self.source_entity,
            "color": self.color,
            "depends_on": self.depends_on or [],
            "blocked_by_count": self.blocked_by_count or 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Skill-Ausführung – Log pro Store
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SkillExecution(Base):
    __tablename__ = "skill_executions"

    id = Column(String(12), primary_key=True, default=gen_id)
    store_id = Column(String(12), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    skill_id = Column(String(30), nullable=False)  # pptx, docx, blog, press, anon, planning
    skill_name = Column(String(255), nullable=False)
    parameters = Column(JSON, default=dict)
    status = Column(String(20), default="running")  # running | completed | failed
    result = Column(JSON, default=dict)
    output_path = Column(String(1000), default="")
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "store_id": self.store_id,
            "skill_id": self.skill_id,
            "skill_name": self.skill_name,
            "parameters": self.parameters or {},
            "status": self.status,
            "result": self.result or {},
            "output_path": self.output_path,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Wiki-Layer (WissensDB v2)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class WikiPageType(str, enum.Enum):
    """
    Kategorie einer Wiki-Seite.
      - index:       Navigations-/Katalog-Seite
      - entity:      Personen, Organisationen, Orte aus NER aggregiert
      - concept:     Fachbegriff mit Synthese ueber alle Quellen
      - summary:     Zusammenfassung eines Quelldokuments
      - synthesis:   Uebergreifende Synthese zu einem Thema
      - comparison:  Vergleich (Quellen, Optionen, Zeitpunkte)
      - log:         Chronik (append-only)
    """
    INDEX = "index"
    ENTITY = "entity"
    CONCEPT = "concept"
    SUMMARY = "summary"
    SYNTHESIS = "synthesis"
    COMPARISON = "comparison"
    LOG = "log"


class WikiPage(Base):
    """
    Eine Wiki-Seite im Wissensprodukt einer Sammlung.
    Persistentes, kumulierendes Artefakt — wird durch LLM gepflegt,
    nicht bei jeder Anfrage neu generiert.
    """
    __tablename__ = "wiki_pages"

    id = Column(String(12), primary_key=True, default=gen_id)
    store_id = Column(String(12), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    page_type = Column(Enum(WikiPageType), default=WikiPageType.CONCEPT, index=True)
    slug = Column(String(200), nullable=False, index=True)  # URL-sicherer Name, eindeutig pro Store
    title = Column(String(500), nullable=False)
    content_md = Column(Text, default="")  # Markdown-Inhalt
    # Verlinkungen
    outgoing_links = Column(JSON, default=list)  # [{"slug": "...", "title": "..."}]
    source_documents = Column(JSON, default=list)  # [{"document_id": "...", "title": "..."}]
    # Qualitaetsmetriken
    update_count = Column(Integer, default=1)  # Wie oft wurde diese Seite aktualisiert
    contradiction_flags = Column(JSON, default=list)  # [{"claim": "...", "sources": [...]}]
    # Zeitstempel
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        Index("ix_wiki_store_slug", "store_id", "slug", unique=True),
    )

    def to_dict(self, include_content: bool = True):
        d = {
            "id": self.id,
            "store_id": self.store_id,
            "page_type": self.page_type.value if self.page_type else "concept",
            "slug": self.slug,
            "title": self.title,
            "outgoing_links": self.outgoing_links or [],
            "source_documents": self.source_documents or [],
            "update_count": self.update_count or 1,
            "contradiction_flags": self.contradiction_flags or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }
        if include_content:
            d["content_md"] = self.content_md or ""
        return d


class WikiOperation(Base):
    """
    Chronik-Eintrag fuer das Wiki (log.md Aequivalent).
    Append-only: Ingest-, Query-, Lint-Operationen werden hier protokolliert.
    """
    __tablename__ = "wiki_operations"

    id = Column(String(12), primary_key=True, default=gen_id)
    store_id = Column(String(12), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    operation = Column(String(20), nullable=False, index=True)  # ingest | query | lint | save_answer
    summary = Column(String(500), default="")
    pages_affected = Column(JSON, default=list)  # [slug1, slug2, ...]
    source_document_id = Column(String(12), nullable=True)
    details = Column(JSON, default=dict)  # Operations-spezifische Details
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "store_id": self.store_id,
            "operation": self.operation,
            "summary": self.summary,
            "pages_affected": self.pages_affected or [],
            "source_document_id": self.source_document_id,
            "details": self.details or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
