"""
LLM-Client — OpenAI-kompatible API fuer multiple Provider.

Unterstuetzt drei Provider-Kategorien:

1. SELF-HOSTED (On-Premise, DSGVO-konform):
   - Ollama (default, kein API-Key)
   - llama.cpp / llama-server
   - mistral.rs
   - vLLM
   - LocalAI
   - Text Generation Inference (TGI, HuggingFace)

2. KOMMERZIELLE OPENAI-KOMPATIBLE APIs:
   - OpenAI (gpt-4o, gpt-4o-mini, o1)
   - Mistral AI
   - Azure OpenAI
   - Groq (schnelle Inferenz)
   - Together AI
   - DeepSeek (guenstig, stark in Code)
   - Fireworks AI
   - OpenRouter (Meta-Router)

3. EIGENE API (nicht OpenAI-kompatibel):
   - Anthropic (Claude via native Messages-API)

4. CUSTOM via Environment:
   Beliebige OpenAI-kompatible Endpunkte koennen ueber
   DOCSTORE_CUSTOM_PROVIDERS (JSON) registriert werden —
   ohne Code-Aenderung. Siehe unten.

Jeder Request kann Provider + Modell + API-Key dynamisch waehlen.
Fallback: Ollama lokal ohne Key.
"""
import logging
import json
import os
from dataclasses import dataclass, field
from typing import Optional, AsyncGenerator

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMProvider:
    """Konfiguration eines LLM-Providers."""
    id: str
    name: str
    base_url: str
    default_model: str
    models: list[str]
    requires_key: bool = True
    headers_template: dict = field(default_factory=dict)
    category: str = "commercial"  # self-hosted | commercial | custom
    supports_model_discovery: bool = True  # True wenn GET /v1/models verfuegbar
    notes: str = ""


# ─── Provider-Registry ───
PROVIDERS: dict[str, LLMProvider] = {

    # ═══════════════════════════════════════════════════
    # SELF-HOSTED (On-Premise, DSGVO-konform)
    # ═══════════════════════════════════════════════════

    "ollama": LLMProvider(
        id="ollama",
        name="Ollama (Lokal)",
        base_url=settings.ollama_url + "/v1",
        default_model="llama3.2",
        models=["llama3.2", "llama3.1", "mistral", "mixtral", "gemma2", "qwen2.5", "phi4"],
        requires_key=False,
        category="self-hosted",
        notes="Standard-Setup fuer Komm.ONE. Modelle via 'ollama pull' hinzufuegen.",
    ),
    "llamacpp": LLMProvider(
        id="llamacpp",
        name="llama.cpp Server",
        base_url=os.getenv("DOCSTORE_LLAMACPP_URL", "http://localhost:8080/v1"),
        default_model="local-model",
        models=["local-model"],  # llama.cpp laedt ein Modell beim Start
        requires_key=False,
        category="self-hosted",
        notes="Schlank, C++-basiert. Start mit: llama-server -m model.gguf --port 8080",
    ),
    "mistralrs": LLMProvider(
        id="mistralrs",
        name="mistral.rs",
        base_url=os.getenv("DOCSTORE_MISTRALRS_URL", "http://localhost:1234/v1"),
        default_model="mistral",
        models=["mistral", "llama", "mixtral"],
        requires_key=False,
        category="self-hosted",
        notes="Rust-Inferenz-Server. GPU + quantisierte Modelle.",
    ),
    "vllm": LLMProvider(
        id="vllm",
        name="vLLM",
        base_url=os.getenv("DOCSTORE_VLLM_URL", "http://localhost:8000/v1"),
        default_model=os.getenv("DOCSTORE_VLLM_MODEL", "mistralai/Mistral-Small-24B-Instruct-2501"),
        models=[],  # dynamisch via /v1/models
        requires_key=False,
        category="self-hosted",
        notes="Hoher Durchsatz. Auf Komm.ONE DGX Spark produktiv einsetzbar.",
    ),
    "localai": LLMProvider(
        id="localai",
        name="LocalAI",
        base_url=os.getenv("DOCSTORE_LOCALAI_URL", "http://localhost:8080/v1"),
        default_model="gpt-3.5-turbo",
        models=[],  # dynamisch
        requires_key=False,
        category="self-hosted",
        notes="OpenAI-Drop-in-Replacement mit mehreren Backends.",
    ),
    "tgi": LLMProvider(
        id="tgi",
        name="Text Generation Inference",
        base_url=os.getenv("DOCSTORE_TGI_URL", "http://localhost:3000/v1"),
        default_model="tgi",
        models=["tgi"],
        requires_key=False,
        category="self-hosted",
        notes="HuggingFace-Inferenz-Server. Shardable, optimiert fuer grosse Modelle.",
    ),

    # ═══════════════════════════════════════════════════
    # KOMMERZIELLE API-ANBIETER (OpenAI-kompatibel)
    # ═══════════════════════════════════════════════════

    "openai": LLMProvider(
        id="openai",
        name="OpenAI",
        base_url="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
        models=["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo", "o1-mini", "o1-preview"],
        requires_key=True,
        category="commercial",
    ),
    "mistral": LLMProvider(
        id="mistral",
        name="Mistral AI",
        base_url="https://api.mistral.ai/v1",
        default_model="mistral-small-latest",
        models=["mistral-small-latest", "mistral-large-latest", "open-mistral-nemo", "codestral-latest"],
        requires_key=True,
        category="commercial",
    ),
    "azure": LLMProvider(
        id="azure",
        name="Azure OpenAI",
        base_url="",  # Dynamisch: https://{resource}.openai.azure.com/openai/deployments/{model}
        default_model="gpt-4o",
        models=["gpt-4o", "gpt-4o-mini", "gpt-4"],
        requires_key=True,
        category="commercial",
        supports_model_discovery=False,
        notes="Key-Format: 'endpoint|key' z.B. 'https://myres.openai.azure.com|abc123'",
    ),
    "groq": LLMProvider(
        id="groq",
        name="Groq",
        base_url="https://api.groq.com/openai/v1",
        default_model="llama-3.3-70b-versatile",
        models=["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"],
        requires_key=True,
        category="commercial",
        notes="Sehr schnelle Inferenz (>500 t/s) via LPU-Hardware.",
    ),
    "together": LLMProvider(
        id="together",
        name="Together AI",
        base_url="https://api.together.xyz/v1",
        default_model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
        models=[
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "mistralai/Mistral-Small-24B-Instruct-2501",
            "Qwen/Qwen2.5-72B-Instruct-Turbo",
            "deepseek-ai/DeepSeek-V3",
        ],
        requires_key=True,
        category="commercial",
        notes="Guenstige OSS-Inferenz, viele Modelle.",
    ),
    "deepseek": LLMProvider(
        id="deepseek",
        name="DeepSeek",
        base_url="https://api.deepseek.com/v1",
        default_model="deepseek-chat",
        models=["deepseek-chat", "deepseek-reasoner"],
        requires_key=True,
        category="commercial",
        notes="Sehr guenstig, stark in Code und Reasoning.",
    ),
    "fireworks": LLMProvider(
        id="fireworks",
        name="Fireworks AI",
        base_url="https://api.fireworks.ai/inference/v1",
        default_model="accounts/fireworks/models/llama-v3p3-70b-instruct",
        models=[
            "accounts/fireworks/models/llama-v3p3-70b-instruct",
            "accounts/fireworks/models/mixtral-8x22b-instruct",
            "accounts/fireworks/models/deepseek-v3",
        ],
        requires_key=True,
        category="commercial",
    ),
    "openrouter": LLMProvider(
        id="openrouter",
        name="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        default_model="meta-llama/llama-3.3-70b-instruct",
        models=[
            "meta-llama/llama-3.3-70b-instruct",
            "anthropic/claude-sonnet-4",
            "openai/gpt-4o-mini",
            "mistralai/mistral-large",
        ],
        requires_key=True,
        category="commercial",
        headers_template={"HTTP-Referer": "https://docstore.kommone.de", "X-Title": "Komm.ONE Docstore"},
        notes="Meta-Router zu 200+ Modellen. Einzelner Key, viele Provider.",
    ),

    # ═══════════════════════════════════════════════════
    # EIGENES PROTOKOLL (nicht OpenAI-kompatibel)
    # ═══════════════════════════════════════════════════

    "anthropic": LLMProvider(
        id="anthropic",
        name="Anthropic",
        base_url="https://api.anthropic.com/v1",
        default_model="claude-sonnet-4-20250514",
        models=["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001", "claude-opus-4-5"],
        requires_key=True,
        category="commercial",
        headers_template={"anthropic-version": "2023-06-01"},
        supports_model_discovery=False,
        notes="Nutzt Anthropic-Messages-API, nicht OpenAI-kompatibel (Adapter intern).",
    ),
}


# ─── Custom Provider aus ENV ───
# Format: JSON-Liste in DOCSTORE_CUSTOM_PROVIDERS
# Beispiel:
#   DOCSTORE_CUSTOM_PROVIDERS='[{"id":"komm1-gpu","name":"Komm.ONE GPU","base_url":"http://gpu.intern:8000/v1","default_model":"mistral-24b","requires_key":false}]'
def _load_custom_providers() -> None:
    """Laedt benutzerdefinierte Provider aus Env-Variable."""
    raw = os.getenv("DOCSTORE_CUSTOM_PROVIDERS", "").strip()
    if not raw:
        return
    try:
        items = json.loads(raw)
        if not isinstance(items, list):
            logger.warning("DOCSTORE_CUSTOM_PROVIDERS muss eine JSON-Liste sein")
            return
        for item in items:
            if not isinstance(item, dict) or "id" not in item or "base_url" not in item:
                continue
            pid = item["id"]
            PROVIDERS[pid] = LLMProvider(
                id=pid,
                name=item.get("name", pid),
                base_url=item["base_url"].rstrip("/"),
                default_model=item.get("default_model", "default"),
                models=item.get("models", []),
                requires_key=item.get("requires_key", False),
                headers_template=item.get("headers", {}),
                category="custom",
                supports_model_discovery=item.get("supports_model_discovery", True),
                notes=item.get("notes", "Benutzerdefiniert via .env"),
            )
            logger.info(f"Custom Provider geladen: {pid} → {item['base_url']}")
    except json.JSONDecodeError as e:
        logger.error(f"DOCSTORE_CUSTOM_PROVIDERS JSON-Fehler: {e}")


_load_custom_providers()


# ─── Zentrale API-Key-Aufloesung ───
# Keys werden in der .env als DOCSTORE_{PROVIDER_ID}_API_KEY gesetzt.
# Beispiele:
#   DOCSTORE_OPENAI_API_KEY=sk-proj-...
#   DOCSTORE_MISTRAL_API_KEY=...
#   DOCSTORE_ANTHROPIC_API_KEY=sk-ant-...
#   DOCSTORE_AZURE_API_KEY=https://myres.openai.azure.com|abc123   (Azure: Format 'endpoint|key')
#   DOCSTORE_GROQ_API_KEY=gsk_...
#
# API-Keys werden nur noch über Umgebungsvariablen konfiguriert.
# Der explicit_key Parameter wird ignoriert (Sicherheit).
def resolve_api_key(provider_id: str, explicit_key: str = None) -> str:
    """
    Liefert den API-Key fuer einen Provider nur aus Umgebungsvariablen.

    Args:
        provider_id: Provider-ID (z.B. 'openai', 'anthropic')
        explicit_key: Wird ignoriert (Sicherheit: nur ENV-Keys erlaubt)

    Returns:
        API-Key aus DOCSTORE_{PROVIDER_ID}_API_KEY oder None
    """
    # explicit_key Parameter wird ignoriert (Sicherheit)
    env_name = f"DOCSTORE_{provider_id.upper().replace('-', '_')}_API_KEY"
    key = os.getenv(env_name)
    if not key:
        logger.warning(f"Kein API-Key für Provider '{provider_id}' in ENV gefunden ({env_name})")
    return key


def is_provider_configured(provider_id: str) -> bool:
    """
    Prueft ob ein Provider betriebsbereit ist:
    - Self-Hosted: immer True (Verbindungstest separat)
    - Commercial: True wenn Key per ENV vorhanden
    """
    provider = PROVIDERS.get(provider_id)
    if not provider:
        return False
    if not provider.requires_key:
        return True
    return resolve_api_key(provider_id) is not None


# ─── RAG System-Prompt (Store-isoliert) ───
RAG_SYSTEM_PROMPT = """Du bist ein Assistent fuer den Agentischen Document Store.
Du antwortest AUSSCHLIESSLICH auf Basis der bereitgestellten Dokument-Chunks.

STRIKTE REGELN:
- Verwende NUR Informationen aus den bereitgestellten Kontext-Chunks.
- Erfinde KEINE Informationen. Halluziniere NICHT.
- Wenn die Antwort nicht in den Chunks enthalten ist, sage das ehrlich.
- Nenne die Quelldokumente bei jeder Antwort.
- Antworte auf Deutsch.
- Du hast KEINEN Zugriff auf Weltwissen. Nur auf diese Sammlung.

KONTEXT-INFORMATIONEN:
Sammlung: {store_name} ({store_type})
Anzahl Dokumente: {doc_count}
"""

RAG_USER_TEMPLATE = """Kontext-Chunks aus der Sammlung:

{context}

---

Frage des Nutzers: {question}

Antworte basierend auf den obigen Chunks. Nenne die Quellen."""


class LLMClient:
    """
    OpenAI-kompatibler LLM-Client mit Multi-Provider-Support.
    Verwendet /v1/chat/completions fuer alle Provider.
    """

    def __init__(self):
        self._http = httpx.AsyncClient(timeout=60.0)

    async def close(self):
        await self._http.aclose()

    def get_providers(self) -> list[dict]:
        """Alle verfuegbaren Provider und Modelle auflisten."""
        return [
            {
                "id": p.id,
                "name": p.name,
                "models": p.models,
                "default_model": p.default_model,
                "requires_key": p.requires_key,
                "category": p.category,
                "base_url": p.base_url if p.category in ("self-hosted", "custom") else None,
                "supports_model_discovery": p.supports_model_discovery,
                "notes": p.notes,
                "configured": is_provider_configured(p.id),
                "key_env_var": f"DOCSTORE_{p.id.upper().replace('-', '_')}_API_KEY" if p.requires_key else None,
            }
            for p in PROVIDERS.values()
        ]

    async def discover_models(self, provider_id: str) -> list[str]:
        """
        Fragt den Provider dynamisch nach verfuegbaren Modellen via GET /v1/models.
        Nuetzlich fuer vLLM, LocalAI, Ollama, TGI — wo Modelle zur Laufzeit wechseln.

        API-Keys werden nur noch über Umgebungsvariablen konfiguriert (DOCSTORE_*_API_KEY).
        """
        provider = PROVIDERS.get(provider_id)
        if not provider or not provider.supports_model_discovery:
            return provider.models if provider else []

        # Azure und Anthropic unterstuetzen kein /v1/models
        if provider_id in ("azure", "anthropic"):
            return provider.models

        # Key-Resolution: nur ENV
        api_key = resolve_api_key(provider_id)

        url = f"{provider.base_url}/models"
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            response = await self._http.get(url, headers=headers, timeout=5.0)
            response.raise_for_status()
            data = response.json()
            # OpenAI-Format: {"data": [{"id": "model-name", ...}, ...]}
            if "data" in data and isinstance(data["data"], list):
                return [m["id"] for m in data["data"] if "id" in m]
            return provider.models
        except Exception as e:
            logger.warning(f"Model-Discovery fuer {provider_id} fehlgeschlagen: {e}")
            return provider.models

    async def chat_completion(
        self,
        messages: list[dict],
        provider_id: str = "ollama",
        model: str = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> dict:
        """
        Chat-Completion via OpenAI-kompatible API.

        API-Keys werden nur noch über Umgebungsvariablen konfiguriert (DOCSTORE_*_API_KEY).
        Gibt das vollstaendige Response-Dict zurueck.
        """
        provider = PROVIDERS.get(provider_id)
        if not provider:
            raise ValueError(f"Unbekannter Provider: {provider_id}. Verfuegbar: {list(PROVIDERS.keys())}")

        # Key-Resolution: nur ENV
        api_key = resolve_api_key(provider_id)

        if provider.requires_key and not api_key:
            env_name = f"DOCSTORE_{provider_id.upper()}_API_KEY"
            raise ValueError(
                f"Provider '{provider.name}' erfordert einen API-Key. "
                f"Setze {env_name} in der .env oder gib api_key im Request mit."
            )

        model = model or provider.default_model

        # ─── Anthropic: Messages API (nicht OpenAI-kompatibel) ───
        if provider_id == "anthropic":
            return await self._anthropic_completion(
                messages=messages,
                model=model,
                api_key=api_key,  # Aus ENV aufgelöst
                temperature=temperature,
                max_tokens=max_tokens,
            )

        # ─── OpenAI-kompatible API ───
        url = f"{provider.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}

        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        # Azure: URL-Anpassung
        if provider_id == "azure" and api_key:
            # api_key Format: "endpoint|key" z.B. "https://myres.openai.azure.com|abc123"
            parts = api_key.split("|", 1)
            if len(parts) == 2:
                endpoint, key = parts
                url = f"{endpoint}/openai/deployments/{model}/chat/completions?api-version=2024-02-01"
                headers["api-key"] = key
                headers.pop("Authorization", None)

        # Extra Headers (z.B. Anthropic-Version)
        headers.update(provider.headers_template)

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            response = await self._http.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

            # Response normalisieren
            content = ""
            if "choices" in data and data["choices"]:
                content = data["choices"][0].get("message", {}).get("content", "")

            return {
                "content": content,
                "model": data.get("model", model),
                "provider": provider_id,
                "usage": data.get("usage", {}),
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"LLM API Fehler [{provider_id}]: {e.response.status_code} - {e.response.text[:200]}")
            raise ValueError(f"LLM-Anfrage fehlgeschlagen ({provider.name}): {e.response.status_code}")
        except httpx.ConnectError:
            raise ValueError(f"Verbindung zu {provider.name} ({provider.base_url}) fehlgeschlagen")
        except Exception as e:
            logger.error(f"LLM Fehler [{provider_id}]: {e}")
            raise ValueError(f"LLM-Fehler: {str(e)}")

    async def _anthropic_completion(
        self,
        messages: list[dict],
        model: str,
        api_key: str,
        temperature: float,
        max_tokens: int,
    ) -> dict:
        """Anthropic Messages API (eigenes Format)."""
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }

        # System-Message extrahieren
        system_msg = ""
        user_messages = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            else:
                user_messages.append(m)

        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": user_messages,
        }
        if system_msg:
            payload["system"] = system_msg

        response = await self._http.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")

        return {
            "content": content,
            "model": data.get("model", model),
            "provider": "anthropic",
            "usage": data.get("usage", {}),
        }

    async def rag_query(
        self,
        question: str,
        context_chunks: list[dict],
        store_name: str,
        store_type: str,
        doc_count: int,
        provider_id: str = "ollama",
        model: str = None,
        chat_history: list[dict] = None,
    ) -> dict:
        """
        RAG-Anfrage: Frage + Kontext-Chunks + Chat-Historie -> Antwort.
        Der LLM sieht NUR die bereitgestellten Chunks, kein Weltwissen.

        API-Keys werden nur noch über Umgebungsvariablen konfiguriert (DOCSTORE_*_API_KEY).
        """
        # Kontext aus Chunks aufbauen
        context_parts = []
        for i, chunk in enumerate(context_chunks, 1):
            source = chunk.get("document_title", "Unbekannt")
            text = chunk.get("content", "")[:800]
            context_parts.append(f"[Quelle {i}: {source}]\n{text}")

        context = "\n\n".join(context_parts)

        system_prompt = RAG_SYSTEM_PROMPT.format(
            store_name=store_name,
            store_type=store_type,
            doc_count=doc_count,
        )

        user_prompt = RAG_USER_TEMPLATE.format(
            context=context,
            question=question,
        )

        messages = [
            {"role": "system", "content": system_prompt},
        ]

        # Multi-Turn: Bisherige Chat-Nachrichten einfuegen
        if chat_history:
            for msg in chat_history[-4:]:  # Max 4 vorherige Nachrichten
                messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")[:300]})

        messages.append({"role": "user", "content": user_prompt})

        try:
            result = await self.chat_completion(
                messages=messages,
                provider_id=provider_id,
                model=model,
                temperature=0.2,
                max_tokens=2000,
            )
            return result
        except ValueError:
            # Fallback: Extraktive Antwort wenn LLM nicht erreichbar
            logger.warning(f"LLM nicht erreichbar, verwende extraktive Antwort")
            return self._extractive_fallback(question, context_chunks, store_name)

    def _extractive_fallback(
        self,
        question: str,
        chunks: list[dict],
        store_name: str,
    ) -> dict:
        """Fallback ohne LLM: Extraktive Antwort aus Chunks."""
        q_terms = set(question.lower().split())
        q_terms -= {"was", "wie", "wer", "wo", "wann", "welche", "ist", "sind",
                     "hat", "der", "die", "das", "ein", "eine", "und", "oder",
                     "fuer", "mit", "von", "zu", "in", "auf", "an"}

        all_text = " ".join(c.get("content", "") for c in chunks)
        sentences = [s.strip() for s in all_text.split(".") if len(s.strip()) > 15]

        scored = []
        for sent in sentences:
            words = set(sent.lower().split())
            overlap = len(q_terms & words)
            if overlap > 0:
                scored.append((overlap, sent))

        scored.sort(key=lambda x: x[0], reverse=True)
        relevant = [s for _, s in scored[:5]]

        if relevant:
            content = f"Basierend auf den Dokumenten in '{store_name}':\n\n"
            content += "\n".join(f"- {s}." for s in relevant)
            content += "\n\n(Extraktive Antwort — LLM nicht verfuegbar)"
        else:
            content = f"Keine relevanten Informationen in '{store_name}' gefunden."

        return {"content": content, "model": "extractive-fallback", "provider": "local", "usage": {}}


# Singleton
llm_client = LLMClient()
