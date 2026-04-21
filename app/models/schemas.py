"""
Pydantic-Schemas fuer API-Validierung.
Erweitert: LLM-Provider-Auswahl, Pagination, Auth.
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


# ━━━━━━━ Pagination ━━━━━━━

class PaginationParams(BaseModel):
    offset: int = Field(0, ge=0)
    limit: int = Field(50, ge=1, le=200)


# ━━━━━━━ Store / Sammlung ━━━━━━━

class StoreCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field("wissensdb", pattern=r"^(akte|wissensdb)$")
    description: str = ""
    color: str = Field("#00B2A9", pattern=r"^#[0-9A-Fa-f]{6}$")
    analyse_fokus: str = "Allgemeine Analyse"


class StoreUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    analyse_fokus: Optional[str] = None


class StoreResponse(BaseModel):
    id: str
    name: str
    type: str
    description: str
    color: str
    analyse_fokus: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    document_count: int = 0


class StoreLiveView(BaseModel):
    store: StoreResponse
    summary: str = ""
    key_takeaways: list[dict] = []
    entities: dict = {}
    stats: dict = {}


# ━━━━━━━ Dokument ━━━━━━━

class DocumentResponse(BaseModel):
    id: str
    store_id: str
    title: str
    file_type: str
    file_size: int = 0
    page_count: int = 0
    status: str = "pending"
    content_summary: str = ""
    has_images: bool = False
    has_tables: bool = False
    chunk_count: int = 0
    indexed_at: Optional[str] = None
    tags: list[str] = []
    source_type: str = "upload"
    source_uri: str = ""
    created_at: Optional[str] = None


class DocumentDetail(DocumentResponse):
    content_text: str = ""
    metadata_extra: dict = {}
    entities: list[dict] = []
    chunks: list[dict] = []


class DocumentTagsUpdate(BaseModel):
    tags: list[str]


# ━━━━━━━ Suche ━━━━━━━

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    store_id: Optional[str] = None
    search_type: str = Field("hybrid", pattern=r"^(hybrid|bm25|semantic)$")
    max_results: int = Field(20, ge=1, le=100)


class SearchResult(BaseModel):
    document_id: str
    document_title: str
    store_id: str
    store_name: str
    chunk_id: str
    chunk_content: str
    chunk_index: int
    score: float
    file_type: str
    tags: list[str] = []
    page_start: Optional[int] = None


class SearchResponse(BaseModel):
    query: str
    search_type: str
    total_results: int
    results: list[SearchResult]
    execution_time_ms: float


# ━━━━━━━ Ingestion ━━━━━━━

class IngestionStatus(BaseModel):
    document_id: str
    status: str
    step: str = ""
    progress: float = 0.0
    message: str = ""


class WebScrapeRequest(BaseModel):
    url: str = Field(..., min_length=5)
    store_id: str


# ━━━━━━━ Entitaeten ━━━━━━━

class EntityResponse(BaseModel):
    type: str
    value: str
    count: int = 1
    context: str = ""


# ━━━━━━━ Chat (Store-isoliert + LLM-Provider) ━━━━━━━

class ChatRequest(BaseModel):
    """Chat-Anfrage mit optionaler LLM-Provider-Auswahl.

    API-Keys werden nur noch über Umgebungsvariablen konfiguriert (DOCSTORE_*_API_KEY).
    """
    message: str = Field(..., min_length=1, max_length=5000)
    session_id: Optional[str] = None
    # LLM-Konfiguration (optional, Fallback: Ollama lokal)
    provider: str = Field("ollama", pattern=r"^(ollama|openai|anthropic|mistral|azure)$")
    model: Optional[str] = None  # None = Provider-Default


class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    sources: list[dict] = []
    created_at: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    store_id: str
    store_name: str
    answer: ChatMessageResponse
    context_documents: int
    model: str = ""
    provider: str = ""


# ━━━━━━━ LLM Provider ━━━━━━━

class LLMProviderInfo(BaseModel):
    id: str
    name: str
    models: list[str]
    default_model: str
    requires_key: bool


# ━━━━━━━ Skills (Store-isoliert) ━━━━━━━

class SkillExecuteRequest(BaseModel):
    """Skill-Ausführung mit optionaler LLM-Provider-Auswahl.

    API-Keys werden nur noch über Umgebungsvariablen konfiguriert (DOCSTORE_*_API_KEY).
    """
    skill_id: str = Field(..., pattern=r"^(pptx|docx|blog|press|anon|planning)$")
    parameters: dict = {}
    # Optionale LLM-Konfig fuer Skills die LLM nutzen
    provider: str = Field("ollama", pattern=r"^(ollama|openai|anthropic|mistral|azure)$")
    model: Optional[str] = None


class SkillStatusResponse(BaseModel):
    id: str
    store_id: str
    skill_id: str
    skill_name: str
    status: str
    parameters: dict = {}
    result: dict = {}
    output_path: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


# ━━━━━━━ Planung (Store-isoliert) ━━━━━━━

class PlanTaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str = ""
    priority: str = Field("mittel", pattern=r"^(hoch|mittel|niedrig)$")
    due_date: str = ""
    assignee: str = ""
    depends_on: list[str] = []  # Task-IDs von Vorgaengern


class PlanTaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = Field(None, pattern=r"^(backlog|planning|active|done)$")
    priority: Optional[str] = Field(None, pattern=r"^(hoch|mittel|niedrig)$")
    due_date: Optional[str] = None
    assignee: Optional[str] = None
    depends_on: Optional[list[str]] = None


class PlanTaskResponse(BaseModel):
    id: str
    store_id: str
    title: str
    description: str = ""
    status: str
    priority: str
    due_date: str = ""
    assignee: str = ""
    source_document: str = ""
    source_entity: str = ""
    color: str = ""
    depends_on: list[str] = []
    blocked_by_count: int = 0
    created_at: Optional[str] = None
