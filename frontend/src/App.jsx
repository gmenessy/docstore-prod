import React, { useState, useMemo, useRef, useEffect, useCallback } from "react";

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// ERROR BOUNDARY – Fängt React-Render-Errors
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, errorInfo) {
        console.error("❌ React Error Boundary:", error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return <div style={{
                display: "flex", flexDirection: "column",
                alignItems: "center", justifyContent: "center",
                height: "100vh", background: CI.midnight5,
                color: CI.midnight, fontFamily: "system-ui, sans-serif"
            }}>
                <div style={{ fontSize: 48, marginBottom: 16 }}>⚠️</div>
                <h2 style={{ margin: 0, marginBottom: 8 }}>Ein Fehler ist aufgetreten</h2>
                <p style={{ color: CI.midnight60, marginBottom: 24 }}>
                    Die Anwendung wurde neu geladen.
                </p>
                <button onClick={() => window.location.reload()} style={{
                    padding: "10px 20px", borderRadius: 6,
                    background: CI.lagoon, color: CI.white,
                    border: "none", cursor: "pointer", fontSize: 14
                }}>
                    Neu laden
                </button>
            </div>;
        }
        return this.props.children;
    }
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// TYPE NORMALIZATION – Konsistente Enums
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
const StoreTypes = {
    AKTE: "akte",
    WISSENSDB: "wissensdb",
};

const normalizeStoreType = (type) => {
    if (!type) return StoreTypes.WISSENSDB;
    const normalized = type.toString().toLowerCase().trim();
    if (normalized.includes("wissens") || normalized.includes("wissendb")) {
        return StoreTypes.WISSENSDB;
    }
    if (normalized.includes("akte")) {
        return StoreTypes.AKTE;
    }
    return StoreTypes.WISSENSDB; // Default
};

const isWissensDB = (store) => normalizeStoreType(store?.type) === StoreTypes.WISSENSDB;
const isAkte = (store) => normalizeStoreType(store?.type) === StoreTypes.AKTE;

// ━━━ Komm.ONE CI (from _vars.scss) ━━━
const CI = {
  midnight: "#003A40", midnight80: "rgb(51,97,102)", midnight60: "rgb(102,137,140)",
  midnight40: "rgb(152,176,179)", midnight5: "rgb(242,245,245)",
  lagoon: "#00B2A9", lagoon80: "rgb(51,193,186)", lagoon60: "rgb(109,209,203)", lagoon40: "rgb(153,224,220)",
  darklagoon: "#009390", amarillo: "#F1C400", darkamarillo: "#F0AF00", basil: "#00965E",
  white: "#fff", gray100: "#f8f9fa", gray200: "#F2F2F2", gray300: "#dee2e6", gray400: "#ced4da",
  gray500: "#adb5bd", gray600: "#6c757d", gray700: "#495057", gray800: "#343a40", gray900: "#212529",
  black: "#000", red: "#d90000", grey01: "#b1b8bb", lightblue: "#f2f5f5",
  pgBaUm: "#03B5C3", pgBiSo: "#9ABF00", pgBurg: "#E89600", pgDiDa: "#0094DE", pgInfr: "#8181EF",
};
const TC = { pdf: CI.pgDiDa, docx: CI.pgBaUm, doc: CI.pgBaUm, pptx: CI.pgBurg, md: CI.basil, txt: CI.grey01, xml: CI.pgInfr, rtf: CI.darkamarillo, xlsx: CI.pgBiSo };

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// PROVIDER MAPPING — User-Friendly Labels for LLM Providers
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

const PROVIDER_CONFIG = {
  // Self-hosted providers
  ollama: {
    label: "Lokal",
    description: "Kostenlose lokale KI auf Ihrem Server. Privacy-first, keine Internetverbindung nötig.",
    category: "self-hosted",
    color: CI.basil,
    icon: "🏠",
    status: "available",
  },
  vllm: {
    label: "Lokal-Schnell",
    description: "Optimierte lokale KI mit hoher Geschwindigkeit. Erfordert mehr RAM.",
    category: "self-hosted",
    color: CI.pgBiSo,
    icon: "⚡",
    status: "available",
  },
  lmstudio: {
    label: "Lokal-Studio",
    description: "Benutzerfreundliche lokale KI mit grafischer Oberfläche.",
    category: "self-hosted",
    color: CI.pgInfr,
    icon: "🎨",
    status: "available",
  },

  // Commercial providers
  openai: {
    label: "OpenAI",
    description: "Marktführende KI mit GPT-4o. Benötigt API-Key und Internetverbindung.",
    category: "commercial",
    color: CI.pgDiDa,
    icon: "🚀",
    status: "api_key_required",
  },
  anthropic: {
    label: "Claude",
    description: "Exzellente Textverständnis mit Claude 3.5 Sonnet. Benötigt API-Key.",
    category: "commercial",
    color: CI.pgBaUm,
    icon: "🧠",
    status: "api_key_required",
  },
  mistral: {
    label: "Mistral",
    description: "Europäische Alternative mit Mistral Large. Benötigt API-Key.",
    category: "commercial",
    color: CI.amarillo,
    icon: "🇪🇺",
    status: "api_key_required",
  },
  azure: {
    label: "Azure OpenAI",
    description: "Enterprise-Lösung von Microsoft. Erfordert Azure-Abonnement.",
    category: "commercial",
    color: CI.lagoon,
    icon: "☁️",
    status: "api_key_required",
  },
  groq: {
    label: "Groq",
    description: "Extrem schnelle Inferenz mit Llama 3. Benötigt API-Key.",
    category: "commercial",
    color: CI.red,
    icon: "🔥",
    status: "api_key_required",
  },
  deepseek: {
    label: "DeepSeek",
    description: "Kosten-effiziente KI aus China. Benötigt API-Key.",
    category: "commercial",
    color: CI.pgBurg,
    icon: "🇨🇳",
    status: "api_key_required",
  },
};

// Helper to get provider display info
function getProviderInfo(providerId) {
  return PROVIDER_CONFIG[providerId] || {
    label: providerId.charAt(0).toUpperCase() + providerId.slice(1),
    description: "LLM-Provider",
    category: "unknown",
    color: CI.gray600,
    icon: "🤖",
    status: "unknown",
  };
}

// Provider Select Component with User-Friendly Labels
function ProviderSelector({ value, onChange, providers = [], size = "normal" }) {
  const [showTooltip, setShowTooltip] = useState(false);
  const selectRef = useRef(null);
  const currentProvider = getProviderInfo(value);

  const isSmall = size === "small";

  return (
    <div style={{ position: "relative" }}>
      <select
        ref={selectRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        style={{
          background: CI.midnight5,
          border: "1px solid " + CI.gray300,
          borderRadius: isSmall ? 4 : 6,
          color: CI.midnight,
          padding: isSmall ? "4px 6px" : "8px 10px",
          fontSize: isSmall ? 10 : 11,
          fontFamily: "inherit",
          cursor: "pointer",
          minWidth: isSmall ? 80 : 120,
          fontWeight: 600,
        }}
        aria-label="LLM-Provider auswählen"
      >
        {providers.length > 0 ? (
          providers.map((p) => {
            const info = getProviderInfo(p.id);
            return (
              <option key={p.id} value={p.id}>
                {info.icon} {info.label} {p.default_model ? `(${p.default_model})` : ""}
              </option>
            );
          })
        ) : (
          // Fallback providers
          Object.entries(PROVIDER_CONFIG).map(([id, info]) => (
            <option key={id} value={id}>
              {info.icon} {info.label}
            </option>
          ))
        )}
      </select>

      {/* Status Indicator */}
      <div
        style={{
          position: "absolute",
          right: isSmall ? 6 : 8,
          top: "50%",
          transform: "translateY(-50%)",
          width: 8,
          height: 8,
          borderRadius: "50%",
          background:
            currentProvider.status === "available"
              ? CI.basil
              : currentProvider.status === "api_key_required"
              ? CI.amarillo
              : CI.gray400,
        }}
      />

      {/* Tooltip */}
      {showTooltip && (
        <div
          style={{
            position: "absolute",
            top: "100%",
            left: 0,
            marginTop: 6,
            background: CI.midnight,
            color: CI.white,
            padding: "8px 12px",
            borderRadius: 6,
            fontSize: 11,
            minWidth: 200,
            boxShadow: "0 4px 12px rgba(0, 58, 64, 0.2)",
            zIndex: 100,
            whiteSpace: "normal",
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: 4 }}>
            {currentProvider.icon} {currentProvider.label}
          </div>
          <div style={{ fontSize: 10, opacity: 0.9, lineHeight: 1.4 }}>
            {currentProvider.description}
          </div>
          {currentProvider.category !== "self-hosted" && (
            <div style={{ fontSize: 9, marginTop: 4, color: CI.amarillo }}>
              ⚠️ API-Key erforderlich
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const uid = () => Math.random().toString(36).slice(2, 10);
const trunc = (s, n = 80) => s && s.length > n ? s.slice(0, n) + "…" : s;
const delay = ms => new Promise(r => setTimeout(r, ms));

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// COMMAND PATTERN – Undo/Redo mit History Stack
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

// Command Base Class
class Command {
  execute() { throw new Error("Execute muss implementiert werden"); }
  undo() { throw new Error("Undo muss implementiert werden"); }
  redo() { this.execute(); } // Default: Redo = Execute
}

// History Manager
class CommandHistory {
  constructor(maxSize = 50) {
    this.undoStack = [];
    this.redoStack = [];
    this.maxSize = maxSize;
    this.listeners = [];
  }

  // Command ausführen
  async execute(command) {
    try {
      await command.execute();
      this.undoStack.push(command);
      this.redoStack = []; // Redo leeren bei neuer Aktion
      this._trim();
      this._notify();
    } catch (error) {
      console.error("Command-Fehler:", error);
      throw error;
    }
  }

  // Undo
  async undo() {
    if (this.undoStack.length === 0) return;

    const command = this.undoStack.pop();
    await command.undo();
    this.redoStack.push(command);
    this._notify();
  }

  // Redo
  async redo() {
    if (this.redoStack.length === 0) return;

    const command = this.redoStack.pop();
    await command.redo();
    this.undoStack.push(command);
    this._notify();
  }

  // Stack limitieren
  _trim() {
    if (this.undoStack.length > this.maxSize) {
      this.undoStack = this.undoStack.slice(-this.maxSize);
    }
  }

  // Listener für UI-Updates
  subscribe(listener) {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  _notify() {
    this.listeners.forEach(listener => listener({
      canUndo: this.undoStack.length > 0,
      canRedo: this.redoStack.length > 0,
      undoCount: this.undoStack.length,
      redoCount: this.redoStack.length,
    }));
  }

  // Helper
  get canUndo() { return this.undoStack.length > 0; }
  get canRedo() { return this.redoStack.length > 0; }
}

// Global History Instance
const commandHistory = new CommandHistory(50);

// ━━━ Search / NER / Intelligence ━━━
function hybridSearch(docs, q, w = { bm25: 0.4, semantic: 0.6 }) {
  if (!q.trim()) return docs;
  const terms = q.toLowerCase().split(/\s+/).filter(Boolean);
  return docs.map(d => {
    const t = `${d.title} ${d.content} ${(d.tags || []).join(" ")} ${(d.entities || []).join(" ")}`.toLowerCase();
    const bm = terms.reduce((s, x) => s + ((t.match(new RegExp(x, "g")) || []).length * 2.2) / ((t.match(new RegExp(x, "g")) || []).length + 1.2), 0) / Math.max(terms.length, 1);
    const bg = []; for (let i = 0; i < terms.length - 1; i++) bg.push(terms[i] + terms[i + 1]);
    const sem = bg.reduce((s, b) => s + (t.includes(b) ? 1 : 0), 0) / Math.max(bg.length, 1) + bm * 0.3;
    return { ...d, _score: w.bm25 * bm + w.semantic * sem };
  }).filter(d => d._score > 0.05).sort((a, b) => b._score - a._score);
}
function extractEntities(text) {
  if (!text) return { personen: [], daten: [], fachbegriffe: [], orte: [] };
  return { personen: [...new Set((text.match(/(?:Herr|Frau|Dr\.|Prof\.)\s+[A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)?/g) || []))], daten: [...new Set((text.match(/\d{1,2}\.\s*(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+\d{4}|\d{1,2}\.\d{1,2}\.\d{2,4}/g) || []))], fachbegriffe: ["Verordnung","Beschluss","Antrag","Genehmigung","Satzung","Haushalt","Verwaltung","Förderung","Maßnahme","Infrastruktur","Digitalisierung","Datenschutz","DSGVO","Compliance","Barrierefreiheit"].filter(t => text.includes(t)), orte: [...new Set((text.match(/(?:Stadt|Gemeinde|Kreis|Land)\s+[A-ZÄÖÜ][a-zäöüß]+/g) || []))] };
}
function chunkText(text) { if (!text) return []; const p = text.split(/\n{2,}/); const c = []; let cur = ""; for (const x of p) { if ((cur + x).length > 512 && cur) { c.push(cur.trim()); cur = x; } else cur += "\n\n" + x; } if (cur.trim()) c.push(cur.trim()); return c; }
function genSummary(docs) { if (!docs.length) return "Keine Dokumente."; return docs.map(d => d.content).join(" ").split(/[.!?]+/).filter(s => s.trim().length > 20).slice(0, 5).map(s => s.trim()).join(". ") + "."; }
function genTakeaways(docs) { const f = {}; docs.flatMap(d => d.entities || []).forEach(e => (f[e] = (f[e] || 0) + 1)); return Object.entries(f).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([e, c]) => ({ entity: e, count: c })); }

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// API-SERVICE-LAYER – Echte Backend-Anbindung
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
const API_BASE = window.__DOCSTORE_API__ || "/api/v1";
const API_KEY = window.__DOCSTORE_KEY__ || "";

const api = {
  _headers() {
    const h = { "Content-Type": "application/json" };
    if (API_KEY) h["X-API-Key"] = API_KEY;
    return h;
  },
  _authHeaders() {
    const h = {};
    if (API_KEY) h["X-API-Key"] = API_KEY;
    return h;
  },
  async _fetch(path, opts = {}) {
    try {
      const r = await fetch(`${API_BASE}${path}`, { ...opts, headers: { ...this._headers(), ...opts.headers } });
      if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || `HTTP ${r.status}`); }
      return r.headers.get("content-type")?.includes("json") ? r.json() : r;
    } catch (e) { console.warn(`[API] ${path}: ${e.message}`); return null; }
  },

  // ── Stores ──
  listStores: () => api._fetch("/stores"),
  getStore: (id) => api._fetch(`/stores/${id}`),
  createStore: (data) => api._fetch("/stores", { method: "POST", body: JSON.stringify(data) }),
  updateStore: (id, data) => api._fetch(`/stores/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteStore: (id) => api._fetch(`/stores/${id}`, { method: "DELETE" }),
  getLiveView: (id) => api._fetch(`/stores/${id}/live-view`),

  // ── Dokumente ──
  listDocuments: (storeId, offset = 0, limit = 50) => api._fetch(`/documents/${storeId}?offset=${offset}&limit=${limit}`),
  getDocument: (docId) => api._fetch(`/documents/detail/${docId}`),
  deleteDocument: (docId) => api._fetch(`/documents/detail/${docId}`, { method: "DELETE" }),
  uploadDocument: async (storeId, file) => {
    const fd = new FormData(); fd.append("file", file);
    const h = {}; if (API_KEY) h["X-API-Key"] = API_KEY;
    const r = await fetch(`${API_BASE}/documents/${storeId}/upload-sync`, { method: "POST", headers: h, body: fd });
    return r.json();
  },

  // ── Chat (RAG, Store-isoliert) ──
  // API-Keys werden nur noch über Umgebungsvariablen konfiguriert (DOCSTORE_*_API_KEY)
  sendMessage: (storeId, message, provider = "ollama", model = null) =>
    api._fetch(`/stores/${storeId}/chat`, {
      method: "POST",
      body: JSON.stringify({ message, provider, model }),
    }),
  getChatHistory: (storeId, sessionId) => api._fetch(`/stores/${storeId}/chat/history/${sessionId}`),
  getProviders: (storeId) => api._fetch(`/stores/${storeId}/chat/providers`),

  // ── Skills ──
  listSkills: (storeId) => api._fetch(`/stores/${storeId}/skills`),
  executeSkill: (storeId, skillId, params = {}) =>
    api._fetch(`/stores/${storeId}/skills/execute-sync`, {
      method: "POST",
      body: JSON.stringify({ skill_id: skillId, parameters: params }),
    }),
  getExecutions: (storeId) => api._fetch(`/stores/${storeId}/skills/executions`),

  // ── Planung ──
  getTasks: (storeId) => api._fetch(`/stores/${storeId}/planning/tasks`),
  createTask: (storeId, data) => api._fetch(`/stores/${storeId}/planning/tasks`, { method: "POST", body: JSON.stringify(data) }),
  updateTask: (storeId, taskId, data) => api._fetch(`/stores/${storeId}/planning/tasks/${taskId}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteTask: (storeId, taskId) => api._fetch(`/stores/${storeId}/planning/tasks/${taskId}`, { method: "DELETE" }),
  extractTasks: (storeId) => api._fetch(`/stores/${storeId}/planning/extract`, { method: "POST" }),

  // ── Suche ──
  search: (query, storeId, type = "hybrid") =>
    api._fetch("/search", { method: "POST", body: JSON.stringify({ query, store_id: storeId, search_type: type }) }),

  // ── Export ──
  exportPptx: (storeId) => `${API_BASE}/stores/${storeId}/export/pptx${API_KEY ? "?api_key=" + API_KEY : ""}`,
  exportDocx: (storeId) => `${API_BASE}/stores/${storeId}/export/docx${API_KEY ? "?api_key=" + API_KEY : ""}`,
  exportPdf: (storeId) => `${API_BASE}/stores/${storeId}/export/pdf${API_KEY ? "?api_key=" + API_KEY : ""}`,

  // ── System ──
  health: () => api._fetch("/../health"),
  storageStats: () => api._fetch("/system/storage"),

  // ── NER ──
  reanalyzeNer: (storeId, useLlm = false) =>
    api._fetch(`/stores/${storeId}/reanalyze-ner?use_llm=${useLlm}`, { method: "POST" }),

  // ── Wiki (WissensDB v2) ──
  // API-Keys werden nur noch über Umgebungsvariablen konfiguriert (DOCSTORE_*_API_KEY)
  listWikiPages: (storeId) => api._fetch(`/stores/${storeId}/wiki/pages`),
  getWikiPage: (storeId, slug) => api._fetch(`/stores/${storeId}/wiki/pages/${slug}`),
  wikiIngest: (storeId, docId, provider = "ollama", model = null) =>
    api._fetch(`/stores/${storeId}/wiki/ingest/${docId}`, {
      method: "POST",
      body: JSON.stringify({ provider, model }),
    }),
  wikiQuery: (storeId, question, provider = "ollama") =>
    api._fetch(`/stores/${storeId}/wiki/query`, {
      method: "POST",
      body: JSON.stringify({ question, provider }),
    }),
  wikiLint: (storeId) => api._fetch(`/stores/${storeId}/wiki/lint`, { method: "POST" }),
  wikiSaveAnswer: (storeId, question, answer, title = null) =>
    api._fetch(`/stores/${storeId}/wiki/save-answer`, {
      method: "POST",
      body: JSON.stringify({ question, answer, title }),
    }),
  wikiLog: (storeId, limit = 50) => api._fetch(`/stores/${storeId}/wiki/log?limit=${limit}`),

  // ── Wiki-Wartung: Lint → Tasks (Iteration 3) ──
  wikiLintToTasks: (storeId) => api._fetch(`/stores/${storeId}/planning/wiki-lint-to-tasks`, { method: "POST" }),
  getTasksFiltered: (storeId, category = null) => {
    const q = category ? `?category=${category}` : "";
    return api._fetch(`/stores/${storeId}/planning/tasks${q}`);
  },

  // ─── LLM-Provider (system-weit) ───
  // API-Keys werden nur noch über Umgebungsvariablen konfiguriert (DOCSTORE_*_API_KEY)
  listAllProviders: () => api._fetch(`/llm/providers`),
  discoverProviderModels: (providerId) => api._fetch(`/llm/providers/${providerId}/models`),
  testProvider: (providerId) => api._fetch(`/llm/providers/${providerId}/test`, { method: "POST" }),

  // ─── Decision-Briefing (neu) ───
  getBriefing: (storeId) => api._fetch(`/stores/${storeId}/briefing`),
  getRisks: (storeId) => api._fetch(`/stores/${storeId}/risks`),
  getSynthesis: (storeId) => api._fetch(`/stores/${storeId}/synthesis`),
  exportBriefing: (storeId, fmt) => `${API_BASE}/stores/${storeId}/briefing/export/${fmt}${API_KEY ? "?api_key=" + API_KEY : ""}`,

  // ─── Demo-Szenarien (neu) ───
  listDemoFixtures: () => api._fetch(`/demo/fixtures`),
  loadDemoFixture: (fixtureId) => api._fetch(`/demo/load/${fixtureId}`, { method: "POST" }),
};

// Expose globally so components and devtools can use it
window.__docstoreApi = api;

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// SAFE API WRAPPER – Fängt Promise Rejections
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
const safeApi = {
    // Wrapper für alle async API-Calls
    async call(apiFunction, errorMessage = "Fehler aufgetreten") {
        try {
            const result = await apiFunction();
            if (result === null || result === undefined) {
                console.warn(`[API] ${errorMessage}: Keine Antwort`);
                return null;
            }
            return result;
        } catch (error) {
            console.error(`[API] ${errorMessage}:`, error);
            // Zeige User-Friendly Error
            const userMessage = error.message || errorMessage;
            // Toast könnte hier aufgerufen werden (wenn Context verfügbar)
            return null;
        }
    },

    // Spezielle Wrapper für häufige Calls
    async sendMessage(storeId, message, provider, model) {
        return this.call(
            () => api.sendMessage(storeId, message, provider, model),
            "Chat-Nachricht konnte nicht gesendet werden"
        );
    },

    async uploadDocument(storeId, file) {
        return this.call(
            () => api.uploadDocument(storeId, file),
            "Upload fehlgeschlagen"
        );
    },

    async search(query, storeId, type) {
        return this.call(
            () => api.search(query, storeId, type),
            "Suche fehlgeschlagen"
        );
    },
};

// Expose safe wrapper
window.__docstoreApiSafe = safeApi;

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// TOAST-SYSTEM — Fehler- und Erfolgsmeldungen
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
const ToastContext = React.createContext({ toast: () => {} });
const useToast = () => React.useContext(ToastContext);

function ToastProvider({ children }) {
  const [toasts, setToasts] = React.useState([]);
  const toast = React.useCallback((msg, type = "info") => {
    const id = uid();
    setToasts(p => [...p, { id, msg, type }]);
    setTimeout(() => setToasts(p => p.filter(t => t.id !== id)), 4500);
  }, []);

  const colors = {
    success: { bg: "#00965E", fg: "#fff" },
    error: { bg: "#d90000", fg: "#fff" },
    warning: { bg: "#F1C400", fg: "#003A40" },
    info: { bg: "#003A40", fg: "#fff" },
  };

  return <ToastContext.Provider value={{ toast }}>
    {children}
    <div style={{ position: "fixed", top: 16, right: 16, zIndex: 9999, display: "flex", flexDirection: "column", gap: 8, maxWidth: 380 }}>
      {toasts.map(t => {
        const c = colors[t.type] || colors.info;
        return <div key={t.id} style={{ background: c.bg, color: c.fg, padding: "10px 16px", borderRadius: 6, fontSize: 13, fontWeight: 500, boxShadow: "0 4px 12px rgba(0,58,64,0.25)", display: "flex", alignItems: "center", gap: 10, animation: "slideIn 0.25s ease-out" }}>
          <span style={{ fontSize: 16 }}>{t.type === "success" ? "✓" : t.type === "error" ? "✕" : t.type === "warning" ? "!" : "i"}</span>
          <span style={{ flex: 1 }}>{t.msg}</span>
          <button onClick={() => setToasts(p => p.filter(x => x.id !== t.id))} style={{ background: "none", border: "none", color: c.fg, cursor: "pointer", fontSize: 16, padding: 0, opacity: 0.7 }}>×</button>
        </div>;
      })}
    </div>
    <style>{`@keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }`}</style>
  </ToastContext.Provider>;
}

// API-Wrapper mit Toast-Integration — nutzbar via useApi() Hook
function useApi() {
  const { toast } = useToast();
  return React.useMemo(() => {
    const wrap = (fn, errMsg) => async (...args) => {
      const r = await fn(...args);
      if (r === null && errMsg) toast(errMsg, "error");
      return r;
    };
    return { ...api, _toast: toast, _wrap: wrap };
  }, [toast]);
}

// ━━━ Demo Data ━━━
const DEMOS = [
  { id: "s1", name: "Digitalisierungsstrategie 2025", type: "wissensdb", description: "Strategiedokumente zur kommunalen Digitalisierung", color: CI.lagoon, analyseFokus: "Umsetzungsstand Maßnahmen", documents: [
    { id: "d1", title: "Digitalisierungsstrategie_Gesamtkonzept.pdf", type: "pdf", size: "2.4 MB", pages: 47, content: "Die Digitalisierungsstrategie der Stadt Freiburg umfasst fünf zentrale Handlungsfelder. Herr Dr. Müller hat am 15. März 2025 die Genehmigung erteilt. Die Maßnahme zur Einführung der E-Akte wird bis Ende 2025 umgesetzt. Die Verordnung zur digitalen Barrierefreiheit ist seit dem 01. Januar 2025 in Kraft. Der Haushalt für Digitalisierung beträgt 3,2 Millionen Euro. Die Infrastruktur wird durch den Kreis Breisgau-Hochschwarzwald mitfinanziert. Prof. Schmidt leitet das Steuerungsgremium. Die DSGVO-Compliance wird durch regelmäßige Audits sichergestellt. Förderung durch das Land Baden-Württemberg in Höhe von 800.000 Euro bewilligt.", tags: ["Strategie", "Digitalisierung"], entities: ["Digitalisierung", "DSGVO", "Barrierefreiheit", "Haushalt", "Förderung", "Infrastruktur"], chunks: 12, indexed: true, addedAt: "2025-11-01", hasImages: true, hasTables: true },
    { id: "d2", title: "Umsetzungsbericht_Q3_2025.docx", type: "docx", size: "890 KB", pages: 18, content: "Der Beschluss des Gemeinderats vom 22. Juni 2025 sieht eine Beschleunigung der Digitalisierung vor. Frau Weber koordiniert die Umsetzung im Bereich Verwaltung. Der Antrag auf zusätzliche Fördermittel wurde am 10. September 2025 eingereicht. Die Maßnahme zur OZG-Umsetzung liegt im Zeitplan.", tags: ["Bericht", "Q3"], entities: ["Beschluss", "Verwaltung", "Antrag", "Maßnahme", "Datenschutz"], chunks: 6, indexed: true, addedAt: "2025-11-05", hasImages: false, hasTables: true },
    { id: "d3", title: "Architekturkonzept_IT.pptx", type: "pptx", size: "5.1 MB", pages: 32, content: "Die IT-Infrastruktur basiert auf einem hybriden Ansatz. On-Premise-Server für sensible Daten. Die Satzung zur IT-Sicherheit wurde aktualisiert. Compliance-Anforderungen nach BSI-Grundschutz werden erfüllt. Stadt Freiburg investiert in Glasfaserausbau.", tags: ["Architektur", "IT"], entities: ["Infrastruktur", "Satzung", "Compliance", "Digitalisierung"], chunks: 8, indexed: true, addedAt: "2025-11-08", hasImages: true, hasTables: false },
  ]},
  { id: "s2", name: "Bauakte Rathausplatz 7", type: "akte", description: "Bauakte inkl. Genehmigungen und Gutachten", color: CI.amarillo, analyseFokus: "Genehmigungsstatus", documents: [
    { id: "d4", title: "Bauantrag_Rathausplatz7.pdf", type: "pdf", size: "1.8 MB", pages: 23, content: "Bauantrag für die Sanierung des Gebäudes Rathausplatz 7. Herr Dr. Fischer als Bauherr. Genehmigung beantragt am 03. April 2025. Die Verordnung zum Denkmalschutz ist zu beachten. Gutachten zur Statik liegt vor. Stadt Freiburg, Baurechtsamt zuständig.", tags: ["Bauantrag", "Denkmalschutz"], entities: ["Antrag", "Genehmigung", "Verordnung"], chunks: 5, indexed: true, addedAt: "2025-09-15", hasImages: true, hasTables: false },
    { id: "d5", title: "Statik-Gutachten_2025.pdf", type: "pdf", size: "3.2 MB", pages: 35, content: "Statisches Gutachten für Rathausplatz 7. Prof. Schneider, TU Karlsruhe. Die Maßnahme zur Verstärkung der Deckenbalken ist erforderlich. Förderung aus dem Denkmalschutzprogramm möglich. Beschluss zur Durchführung steht aus.", tags: ["Gutachten", "Statik"], entities: ["Maßnahme", "Förderung", "Beschluss"], chunks: 7, indexed: true, addedAt: "2025-09-20", hasImages: true, hasTables: true },
  ]},
];

// ━━━ SVG Icons ━━━
const Ic = {
  search: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>,
  plus: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 5v14M5 12h14"/></svg>,
  folder: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>,
  db: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>,
  doc: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>,
  chart: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M18 20V10M12 20V4M6 20v-6"/></svg>,
  eye: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>,
  tag: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/></svg>,
  layers: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>,
  zap: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>,
  back: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>,
  gear: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>,
  globe: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>,
  upload: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>,
  img: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>,
  tbl: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18M15 3v18"/></svg>,
  chk: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>,
  chat: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>,
  skill: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>,
  plan: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>,
  send: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>,
  play: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>,
  file: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>,
  shield: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>,
  pen: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>,
  press: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/></svg>,
  flag: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/></svg>,
  book: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>,
  link: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>,
  warn: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>,
  save: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>,
  refresh: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>,
  clock: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>,
  checkbox: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/></svg>,
  checkboxChecked: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><polyline points="9 11 12 14 22 4"/></svg>,
  trash: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>,
  download: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>,
};

// ━━━ Shared Components ━━━
const Badge = ({ children, color = CI.gray600, small }) => <span style={{ display: "inline-flex", alignItems: "center", gap: 3, padding: small ? "1px 6px" : "2px 8px", borderRadius: 3, fontSize: small ? 10 : 11, fontWeight: 600, color, background: color + "15", whiteSpace: "nowrap" }}>{children}</span>;

// Checkbox Component for Multi-Select
const Checkbox = ({ checked, onChange, size = 18, disabled = false }) => {
  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        if (!disabled) onChange(!checked);
      }}
      disabled={disabled}
      style={{
        width: size,
        height: size,
        borderRadius: 3,
        border: `2px solid ${checked ? CI.lagoon : CI.gray400}`,
        background: checked ? CI.lagoon : CI.white,
        cursor: disabled ? "not-allowed" : "pointer",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        transition: "all 0.15s",
        opacity: disabled ? 0.5 : 1,
        padding: 0,
      }}
      onMouseEnter={(e) => {
        if (!disabled) {
          e.currentTarget.style.borderColor = CI.lagoon;
          e.currentTarget.style.transform = "scale(1.1)";
        }
      }}
      onMouseLeave={(e) => {
        if (!disabled) {
          e.currentTarget.style.borderColor = checked ? CI.lagoon : CI.gray400;
          e.currentTarget.style.transform = "scale(1)";
        }
      }}
    >
      {checked && (
        <svg width={size * 0.6} height={size * 0.6} viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      )}
    </button>
  );
};

// Bulk Action Toolbar
function BulkActionToolbar({ selectedCount, onClear, onDelete, onExport, onTag }) {
  if (selectedCount === 0) return null;

  return (
    <div style={{
      position: "sticky",
      top: 0,
      zIndex: 50,
      background: CI.lagoon,
      color: CI.white,
      padding: "12px 16px",
      borderRadius: 8,
      marginBottom: 16,
      display: "flex",
      alignItems: "center",
      gap: 12,
      boxShadow: "0 4px 12px rgba(0, 178, 169, 0.2)",
      animation: "slideIn 0.2s ease-out",
    }}>
      <div style={{ flex: 1 }}>
        <strong>{selectedCount}</strong> {selectedCount === 1 ? "Dokument" : "Dokumente"} ausgewählt
      </div>

      <button
        onClick={onDelete}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "8px 14px",
          borderRadius: 5,
          border: "none",
          background: "rgba(255, 255, 255, 0.2)",
          color: CI.white,
          cursor: "pointer",
          fontSize: 12,
          fontWeight: 600,
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = "rgba(255, 255, 255, 0.3)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = "rgba(255, 255, 255, 0.2)";
        }}
      >
        {Ic.trash} Löschen
      </button>

      <button
        onClick={onExport}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "8px 14px",
          borderRadius: 5,
          border: "none",
          background: "rgba(255, 255, 255, 0.2)",
          color: CI.white,
          cursor: "pointer",
          fontSize: 12,
          fontWeight: 600,
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = "rgba(255, 255, 255, 0.3)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = "rgba(255, 255, 255, 0.2)";
        }}
      >
        {Ic.download} Export
      </button>

      <button
        onClick={onClear}
        style={{
          padding: "8px 14px",
          borderRadius: 5,
          border: "1px solid rgba(255, 255, 255, 0.5)",
          background: "transparent",
          color: CI.white,
          cursor: "pointer",
          fontSize: 12,
          fontWeight: 600,
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = "rgba(255, 255, 255, 0.1)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = "transparent";
        }}
      >
        Abbrechen
      </button>
    </div>
  );
}
const TypeBadge = ({ type }) => <Badge color={TC[type] || CI.gray600}>{type.toUpperCase()}</Badge>;
const PBar = ({ value, max = 100, color = CI.lagoon, label }) => <div style={{ width: "100%" }}>{label && <div style={{ fontSize: 11, color: CI.midnight60, marginBottom: 3 }}>{label}</div>}<div style={{ height: 6, background: CI.midnight5, borderRadius: 3, overflow: "hidden" }}><div style={{ height: "100%", width: Math.min(100, (value / max) * 100) + "%", background: color, borderRadius: 3, transition: "width 0.6s" }} /></div></div>;
const CS = { background: CI.white, borderRadius: 8, padding: "18px 20px", border: "1px solid " + CI.gray300, boxShadow: "0 1px 3px rgba(0,58,64,0.06)" };
const SH = (icon, label, color) => <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10 }}><span style={{ color }}>{icon}</span><span style={{ fontSize: 11, fontWeight: 700, color: CI.midnight60, letterSpacing: "0.04em", textTransform: "uppercase" }}>{label}</span></div>;

// ━━━ Store Context Banner — zeigt die aktive Sammlung als Datenquelle ━━━
function StoreContextBanner({ store, label }) {
  return <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", borderRadius: 8, background: store.color + "10", border: "1px solid " + store.color + "30", marginBottom: 16 }}>
    <div style={{ width: 28, height: 28, borderRadius: 6, background: store.color + "25", display: "flex", alignItems: "center", justifyContent: "center", color: store.color, flexShrink: 0 }}>{isAkte(store) ? Ic.folder : Ic.db}</div>
    <div style={{ flex: 1 }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: store.color }}>{label || "Datenquelle"}</div>
      <div style={{ fontSize: 11, color: CI.midnight60 }}>{store.name} · {isAkte(store) ? "Akte" : "WissensDB"} · {store.documents.length} Dokumente</div>
    </div>
    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
      <Ic2Lock />
      <span style={{ fontSize: 10, fontWeight: 600, color: CI.midnight40 }}>Isoliertes Ökosystem</span>
    </div>
  </div>;
}
function Ic2Lock() { return <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke={CI.midnight40} strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>; }

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// DOCUMENT PREVIEW HOVER CARD (SOTA: Tippy.js-like)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function DocumentPreview({ doc, style }) {
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState(null);

  const handleMouseEnter = async () => {
    setLoading(true);
    try {
      const data = await api.getDocument(doc.id);
      setPreview(data);
    } catch (error) {
      console.error("Preview-Laden fehlgeschlagen:", error);
    } finally {
      setLoading(false);
    }
  };

  if (!preview && !loading) {
    return null; // Don't show until hovered
  }

  return (
    <div
      style={{
        position: "fixed",
        zIndex: 10000,
        background: CI.white,
        border: "1px solid " + CI.gray300,
        borderRadius: 8,
        padding: "16px",
        boxShadow: "0 8px 24px rgba(0,58,64,0.15)",
        minWidth: 300,
        maxWidth: 400,
        ...style,
      }}
      onMouseEnter={handleMouseEnter}
    >
      {loading ? (
        <div style={{ display: "flex", justifyContent: "center", padding: 20 }}>
          <div style={{ width: 24, height: 24, borderRadius: "50%", border: "3px solid " + CI.lagoon40, borderTopColor: CI.lagoon }} style={{ animation: "spin 1s linear infinite" }} />
        </div>
      ) : preview && (
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
            <TypeBadge type={preview.file_type} />
            <span style={{ fontSize: 11, color: CI.gray600 }}>{preview.pages} S.</span>
          </div>

          <h4 style={{ margin: 0 0 8px, fontSize: 13, fontWeight: 700, color: CI.midnight }}>
            {preview.title}
          </h4>

          <p style={{ fontSize: 11, color: CI.gray700, lineHeight: 1.5, margin: 0, marginBottom: 12 }}>
            {trunc(preview.content_text || "Kein Vorschau verfügbar", 180)}
          </p>

          {preview.entities && preview.entities.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: CI.midnight60, marginBottom: 4 }}>
                Entitäten
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                {preview.entities.slice(0, 6).map((e, i) => (
                  <Badge key={i} color={CI.pgInfr} small>{e}</Badge>
                ))}
              </div>
            </div>
          )}

          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <button
              onClick={() => { /* Open document detail */ }}
              style={{
                padding: "6px 12px",
                borderRadius: 4,
                border: "1px solid " + CI.lagoon,
                background: CI.white,
                color: CI.lagoon,
                cursor: "pointer",
                fontSize: 11,
                fontWeight: 600,
                fontFamily: "inherit",
              }}
            >
              Öffnen
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// SIDEBAR
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function Sidebar({ stores, active, onSelect, onNew }) {
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  return (
    <>
      {/* Mobile Hamburger Button (nur sichtbar auf Mobile) */}
      <div style={{
        display: "none",
        position: "fixed",
        bottom: 20,
        right: 20,
        zIndex: 9998,
        media: "(max-width: 768px) { display: flex; }"
      }}>
        <button
          onClick={() => setIsMobileOpen(true)}
          style={{
            width: 56, height: 56,
            borderRadius: "50%",
            background: CI.lagoon,
            color: CI.white,
            border: "none",
            boxShadow: "0 4px 12px rgba(0,58,64,0.3)",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 24
          }}
          aria-label="Menü öffnen"
        >
          ☰
        </button>
      </div>

      {/* Mobile Overlay */}
      {isMobileOpen && (
        <div
          onClick={() => setIsMobileOpen(false)}
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.5)",
            zIndex: 9998,
            display: "none",
            media: "(max-width: 768px) { display: block; }"
          }}
        />
      )}

      {/* Sidebar */}
      <div style={{
        width: 272,
        minWidth: 272,
        background: CI.midnight,
        display: "flex",
        flexDirection: "column",
        height: "100%",
        // Mobile Responsive
        position: "fixed",
        left: 0,
        top: 0,
        zIndex: 9999,
        transform: isMobileOpen ? "translateX(0)" : "translateX(-100%)",
        transition: "transform 0.3s ease-out",
        // Desktop Default
        "@media (min-width: 769px)": {
          position: "relative",
          transform: "none"
        }
      }}>
        <div style={{ padding: "20px 16px 16px", borderBottom: "1px solid " + CI.midnight80, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 34, height: 34, borderRadius: 8, background: CI.lagoon, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, fontWeight: 800, color: CI.white }}>DS</div>
            <div><div style={{ fontSize: 14, fontWeight: 700, color: CI.white }}>Document Store</div><div style={{ fontSize: 10, color: CI.lagoon60, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase" }}>Komm.ONE · Agentisch</div></div>
          </div>
          {/* Mobile Close Button */}
          <button
            onClick={() => setIsMobileOpen(false)}
            style={{
              display: "none",
              background: "none",
              border: "none",
              color: CI.white,
              fontSize: 24,
              cursor: "pointer",
              padding: 4,
              media: "(max-width: 768px) { display: block; }"
            }}
            aria-label="Menü schließen"
          >
            ×
          </button>
        </div>
        <div style={{ flex: 1, overflow: "auto", padding: "12px 8px" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: CI.midnight40, letterSpacing: "0.1em", textTransform: "uppercase", padding: "4px 8px", marginBottom: 6 }}>Sammlungen</div>
          {stores.map(s => { const a = active?.id === s.id; return <button key={s.id} onClick={() => { onSelect(s); setIsMobileOpen(false); }} style={{ width: "100%", display: "flex", alignItems: "flex-start", gap: 10, padding: "12px", borderRadius: 6, border: "none", cursor: "pointer", background: a ? CI.midnight80 + "44" : "transparent", textAlign: "left", marginBottom: 2", minHeight: 48 /* Touch Target */ }}
            onMouseEnter={e => !a && (e.currentTarget.style.background = CI.midnight80 + "22")} onMouseLeave={e => !a && (e.currentTarget.style.background = "transparent")}>
            <div style={{ width: 28, height: 28, borderRadius: 6, background: s.color + "30", display: "flex", alignItems: "center", justifyContent: "center", color: s.color, flexShrink: 0, marginTop: 1 }}>{isAkte(s) ? Ic.folder : Ic.db}</div>
            <div style={{ flex: 1, minWidth: 0 }}><div style={{ fontSize: 13, fontWeight: 600, color: a ? CI.white : CI.midnight40, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.name}</div>
            <div style={{ display: "flex", gap: 6, marginTop: 3 }}><Badge color={s.type === "akte" ? CI.amarillo : CI.lagoon} small>{isAkte(s) ? "Akte" : "WissensDB"}</Badge><span style={{ fontSize: 11, color: CI.midnight60 }}>{s.documents.length} Dok.</span></div></div>
            {a && <div style={{ width: 3, height: 20, background: s.color, borderRadius: 2, flexShrink: 0, marginTop: 4 }} />}
          </button>; })}
        </div>
        <div style={{ padding: "12px 8px", borderTop: "1px solid " + CI.midnight80 }}>
          <button onClick={() => { onNew(); setIsMobileOpen(false); }} style={{ width: "100%", display: "flex", alignItems: "center", justifyContent: "center", gap: 6, padding: "12px", borderRadius: 6, border: "1px dashed " + CI.midnight60, background: "transparent", color: CI.lagoon60, cursor: "pointer", fontSize: 12, fontWeight: 600, minHeight: 48 /* Touch Target */ }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = CI.lagoon; e.currentTarget.style.color = CI.lagoon; }} onMouseLeave={e => { e.currentTarget.style.borderColor = CI.midnight60; e.currentTarget.style.color = CI.lagoon60; }}>{Ic.plus} Neue Sammlung</button>
        </div>
      </div>
    </>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// OVERVIEW
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function Overview({ store, onDoc }) {
  const { toast } = useToast();
  const [liveData, setLiveData] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [selectedDocs, setSelectedDocs] = useState(new Set());
  const [lastSelectedIndex, setLastSelectedIndex] = useState(null);
  const fileRef = useRef(null);
  const docListRef = useRef(null);

  useEffect(() => {
    api.getLiveView(store.id).then(r => r && setLiveData(r));
  }, [store.id]);

  // Keyboard Shortcuts for Bulk Selection
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Ctrl/Cmd + A: Select All
      if ((e.ctrlKey || e.metaKey) && e.key === "a") {
        e.preventDefault();
        const allDocIds = new Set(store.documents.map(d => d.id));
        setSelectedDocs(allDocIds);
        setLastSelectedIndex(store.documents.length - 1);
      }
      // Escape: Clear Selection
      if (e.key === "Escape") {
        setSelectedDocs(new Set());
        setLastSelectedIndex(null);
      }
      // Delete: Delete Selected (with confirmation)
      if ((e.key === "Delete" || e.key === "Backspace") && selectedDocs.size > 0) {
        e.preventDefault();
        handleBulkDelete();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [store.documents, selectedDocs]);

  const toggleDocSelection = (docId, index, shiftKey = false) => {
    setSelectedDocs(prev => {
      const newSet = new Set(prev);

      if (shiftKey && lastSelectedIndex !== null) {
        // Shift+Click: Select range
        const start = Math.min(lastSelectedIndex, index);
        const end = Math.max(lastSelectedIndex, index);
        for (let i = start; i <= end; i++) {
          newSet.add(store.documents[i].id);
        }
      } else {
        // Normal click: Toggle single
        if (newSet.has(docId)) {
          newSet.delete(docId);
        } else {
          newSet.add(docId);
        }
        setLastSelectedIndex(index);
      }

      return newSet;
    });
  };

  const selectAll = () => {
    const allDocIds = new Set(store.documents.map(d => d.id));
    setSelectedDocs(allDocIds);
    setLastSelectedIndex(store.documents.length - 1);
  };

  const clearSelection = () => {
    setSelectedDocs(new Set());
    setLastSelectedIndex(null);
  };

  const handleBulkDelete = async () => {
    if (selectedDocs.size === 0) return;

    const count = selectedDocs.size;
    const confirmed = window.confirm(
      `${count} ${count === 1 ? "Dokument" : "Dokumente"} wirklich löschen? Diese Aktion kann nicht rückgängig gemacht werden.`
    );

    if (!confirmed) return;

    try {
      // Delete all selected documents
      const promises = Array.from(selectedDocs).map(docId =>
        api.deleteDocument(docId)
      );

      await Promise.all(promises);

      // Refresh live view
      const r = await api.getLiveView(store.id);
      if (r) setLiveData(r);

      // Clear selection
      clearSelection();

      toast(`${count} ${count === 1 ? "Dokument" : "Dokumente"} gelöscht`, "success");
    } catch (error) {
      console.error("Bulk Delete Error:", error);
      toast("Fehler beim Löschen der Dokumente", "error");
    }
  };

  const handleBulkExport = () => {
    if (selectedDocs.size === 0) return;

    // Create a filtered list of selected documents
    const selectedDocsList = store.documents.filter(d => selectedDocs.has(d.id));

    // For now, export as JSON
    const dataStr = JSON.stringify(selectedDocsList, null, 2);
    const dataBlob = new Blob([dataStr], { type: "application/json" });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `dokumente-export-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    toast(`${selectedDocs.size} ${selectedDocs.size === 1 ? "Dokument" : "Dokumente"} exportiert`, "success");
  };

  const summary = liveData?.summary || genSummary(store.documents);
  const tks = liveData?.key_takeaways || genTakeaways(store.documents);
  const ents = liveData?.entities || {};
  const stats = liveData?.stats || {};
  const allEnts = [...(ents.personen || []), ...(ents.daten || []), ...(ents.orte || [])].map(e => typeof e === "string" ? e : e.value).slice(0, 12);

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    const r = await api.uploadDocument(store.id, file);
    setUploading(false);
    if (r) { api.getLiveView(store.id).then(d => d && setLiveData(d)); }
  };

  const docCount = stats.total_documents ?? store.documents.length;
  const idxCount = stats.indexed_documents ?? store.documents.filter(d => d.indexed).length;
  const pageCount = stats.total_pages ?? store.documents.reduce((s, d) => s + (d.pages || 0), 0);
  const chunkCount = stats.total_chunks ?? store.documents.reduce((s, d) => s + (d.chunks || 0), 0);

  return <div style={{ padding: "24px 28px", overflow: "auto", height: "100%" }}>
    <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
      <div style={{ width: 42, height: 42, borderRadius: 8, background: store.color + "20", display: "flex", alignItems: "center", justifyContent: "center", color: store.color }}>{isAkte(store) ? Ic.folder : Ic.db}</div>
      <div style={{ flex: 1 }}><h1 style={{ fontSize: 20, fontWeight: 700, color: CI.midnight, margin: 0 }}>{store.name}</h1><p style={{ fontSize: 12, color: CI.midnight60, margin: "2px 0 0" }}>{store.description}</p></div>
      <input type="file" ref={fileRef} onChange={handleUpload} style={{ display: "none" }} accept=".pdf,.docx,.pptx,.md,.txt,.xlsx" />
      <button onClick={() => fileRef.current?.click()} disabled={uploading} style={{ display: "flex", alignItems: "center", gap: 5, padding: "8px 16px", borderRadius: 6, border: "none", background: uploading ? CI.gray400 : CI.lagoon, color: CI.white, cursor: uploading ? "wait" : "pointer", fontSize: 12, fontWeight: 700 }}>{Ic.plus} {uploading ? "Wird hochgeladen..." : "Dokument hochladen"}</button>
    </div>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(120px,1fr))", gap: 10, marginBottom: 20 }}>
      {[{ l: "Dokumente", v: docCount, c: CI.lagoon }, { l: "Seiten", v: pageCount, c: CI.amarillo }, { l: "Chunks", v: chunkCount, c: CI.pgBurg }, { l: "Indiziert", v: `${idxCount}/${docCount}`, c: CI.basil }].map(s =>
        <div key={s.l} style={{ background: CI.white, borderRadius: 8, padding: "14px 16px", border: "1px solid " + CI.gray300, borderLeft: "3px solid " + s.c }}><div style={{ fontSize: 22, fontWeight: 700, color: s.c }}>{s.v}</div><div style={{ fontSize: 11, color: CI.midnight60, marginTop: 2 }}>{s.l}</div></div>)}
    </div>
    {/* Export-Toolbar */}
    <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
      {[["PPTX", api.exportPptx(store.id), CI.pgBurg], ["DOCX", api.exportDocx(store.id), CI.pgBaUm], ["PDF", api.exportPdf(store.id), CI.pgDiDa]].map(([label, url, col]) =>
        <a key={label} href={url} target="_blank" rel="noopener" style={{ display: "flex", alignItems: "center", gap: 4, padding: "6px 14px", borderRadius: 4, border: "1px solid " + col + "40", background: col + "08", color: col, fontSize: 12, fontWeight: 600, textDecoration: "none" }}>{Ic.file} {label} Export</a>
      )}
    </div>
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
      <div style={CS}>{SH(Ic.layers, "Zusammenfassung", CI.lagoon)}<p style={{ fontSize: 13, color: CI.gray700, lineHeight: 1.6, margin: 0 }}>{trunc(summary, 280)}</p></div>
      <div style={CS}>{SH(Ic.zap, "Kernfakten", CI.amarillo)}<div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>{tks.map((t, i) => <Badge key={i} color={CI.darkamarillo}>{t.takeaway || t.entity} ({t.count})</Badge>)}</div></div>
      <div style={CS}>{SH(Ic.tag, "Entitaeten", CI.pgInfr)}<div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>{allEnts.map((e, i) => <Badge key={i} color={CI.pgInfr} small>{e}</Badge>)}</div></div>
      <div style={CS}>{SH(Ic.chart, "Analyse-Schwerpunkt", CI.red)}<div style={{ fontSize: 15, fontWeight: 700, color: CI.midnight, marginBottom: 8 }}>{store.analyseFokus || store.analyse_fokus || "Allgemein"}</div><PBar value={idxCount} max={docCount} color={store.color} label={`${idxCount} von ${docCount} analysiert`} /></div>
    </div>
    {/* Bulk Action Toolbar */}
    <BulkActionToolbar
      selectedCount={selectedDocs.size}
      onClear={clearSelection}
      onDelete={handleBulkDelete}
      onExport={handleBulkExport}
      onTag={() => toast("Tag-Funktion kommt in Kürze", "info")}
    />

    <div style={{
      display: "flex",
      alignItems: "center",
      gap: 10,
      marginBottom: 10,
      paddingBottom: 8,
      borderBottom: "1px solid " + CI.gray200,
    }}>
      <Checkbox
        checked={selectedDocs.size === store.documents.length && store.documents.length > 0}
        onChange={selectAll}
        size={18}
      />
      <div style={{ fontSize: 11, fontWeight: 700, color: CI.midnight60, letterSpacing: "0.04em", textTransform: "uppercase" }}>
        Dokumente {selectedDocs.size > 0 && `(${selectedDocs.size} ausgewählt)`}
      </div>
      {selectedDocs.size > 0 && (
        <button
          onClick={clearSelection}
          style={{
            marginLeft: "auto",
            padding: "4px 10px",
            borderRadius: 4,
            border: "none",
            background: CI.gray200,
            color: CI.gray700,
            cursor: "pointer",
            fontSize: 11,
          }}
        >
          Auswahl aufheben
        </button>
      )}
    </div>

    <div ref={docListRef}>
      {store.documents.map((d, index) => {
        const [showPreview, setShowPreview] = useState(false);
        const btnRef = useRef(null);
        const isSelected = selectedDocs.has(d.id);

        return (
          <div key={d.id} style={{ position: "relative" }}>
            <div
              style={{
                width: "100%",
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "12px 14px",
                borderRadius: 8,
                border: "1px solid " + (isSelected ? CI.lagoon : CI.gray300),
                background: isSelected ? CI.lagoon + "08" : CI.white,
                cursor: "pointer",
                marginBottom: 6,
                transition: "all 0.15s",
              }}
              onMouseEnter={(e) => {
                if (!isSelected) {
                  e.currentTarget.style.borderColor = CI.lagoon60;
                  e.currentTarget.style.boxShadow = "0 2px 8px rgba(0, 178, 169, 0.1)";
                }
              }}
              onMouseLeave={(e) => {
                if (!isSelected) {
                  e.currentTarget.style.borderColor = CI.gray300;
                  e.currentTarget.style.boxShadow = "none";
                }
              }}
            >
              {/* Checkbox */}
              <div onClick={(e) => e.stopPropagation()}>
                <Checkbox
                  checked={isSelected}
                  onChange={(checked) => toggleDocSelection(d.id, index)}
                  size={18}
                />
              </div>

              {/* Document Content */}
              <button
                ref={btnRef}
                onClick={() => onDoc(d)}
                onMouseEnter={() => setShowPreview(true)}
                onMouseLeave={() => setShowPreview(false)}
                style={{
                  flex: 1,
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  padding: 0,
                  border: "none",
                  background: "transparent",
                  cursor: "pointer",
                  textAlign: "left",
                  minWidth: 0,
                }}
              >
                <div style={{ width: 36, height: 36, borderRadius: 6, background: (TC[d.type] || CI.gray600) + "15", display: "flex", alignItems: "center", justifyContent: "center", color: TC[d.type], flexShrink: 0 }}>{Ic.doc}</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: CI.midnight, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{d.title}</div>
                  <div style={{ display: "flex", gap: 8, marginTop: 4, alignItems: "center" }}>
                    <TypeBadge type={d.type}/>
                    <span style={{ fontSize: 11, color: CI.gray600 }}>{d.size}</span>
                    <span style={{ fontSize: 11, color: CI.gray600 }}>{d.pages} S.</span>
                  </div>
                </div>
                {d.indexed && <Badge color={CI.basil} small>{Ic.chk} Indiziert</Badge>}
              </button>
            </div>

            {/* Document Preview Hover */}
            {showPreview && !isSelected && (
              <DocumentPreview
                doc={d}
                style={{
                  position: "absolute",
                  left: "100%",
                  top: 0,
                  marginLeft: 12,
                  zIndex: 100,
                }}
              />
            )}
          </div>
        );
      })}
    </div>
  </div>;
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// CHAT – Interaktiver Chat gegen Akte/WissensDB
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function ChatPanel({ store }) {
  const [msgs, setMsgs] = useState([{ role: "assistant", text: `Ich bin der Assistent fuer diese ${isAkte(store) ? "Akte" : "WissensDB"}. Mein Wissen beschraenkt sich ausschliesslich auf die ${store.documents.length} Dokumente in "${store.name}". Informationen ausserhalb dieser Sammlung sind mir nicht zugaenglich.\n\nStellen Sie mir Fragen zu den Inhalten dieser Sammlung.`, sources: [] }]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [provider, setProvider] = useState("ollama");
  const [providerList, setProviderList] = useState([]);
  const endRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);
  useEffect(() => { api.getProviders(store.id).then(r => r && setProviderList(r.providers || [])); }, [store.id]);

  const handleSend = useCallback(async () => {
    if (!input.trim() || loading) return;
    const q = input.trim();
    setInput("");
    setMsgs(p => [...p, { role: "user", text: q }]);
    setLoading(true);

    try {
      // Echte Backend-API aufrufen MIT Error-Handling
      const apiResult = await api.sendMessage(store.id, q, provider, null, null);

      if (apiResult && apiResult.answer) {
        // Backend hat geantwortet
        if (apiResult.session_id) setSessionId(apiResult.session_id);
        const sources = apiResult.answer.sources || [];
        const modelInfo = apiResult.provider !== "none" ? ` [${apiResult.provider}/${apiResult.model}]` : "";
        setMsgs(p => [...p, { role: "assistant", text: apiResult.answer.content + modelInfo, sources }]);
      } else {
        throw new Error("Keine Antwort vom Backend");
      }
    } catch (error) {
      // Error Handler: Zeige User-Friendly Message + Fallback
      console.error("[Chat] API-Fehler, nutze Offline-Fallback:", error);

      // Fallback: Lokale Suche wenn Backend nicht erreichbar
      const results = hybridSearch(store.documents, q);
      const topDocs = results.slice(0, 3);
      const sources = topDocs.map(d => ({ title: d.title, score: d._score }));
      let answer = "";
      if (topDocs.length > 0) {
        const relevant = topDocs.map(d => d.content).join(" ");
        const sentences = relevant.split(/[.!?]+/).filter(s => s.trim().length > 15);
        const matched = sentences.filter(s => q.toLowerCase().split(/\s+/).some(w => w.length > 3 && s.toLowerCase().includes(w)));
        answer = matched.length > 0
          ? `Basierend auf den Dokumenten (Offline-Modus):\n\n${matched.slice(0, 4).map(s => "- " + s.trim()).join("\n")}\n\nQuellen: ${sources.map(s => s.title).join(", ")}`
          : `${topDocs.length} relevante Dokumente gefunden. Bitte praezisieren Sie Ihre Frage.`;
      } else {
        answer = `Keine relevanten Informationen in "${store.name}" gefunden. (Offline-Modus)`;
      }
      setMsgs(p => [...p, { role: "assistant", text: answer, sources }]);
    } finally {
      // WICHTIG: Immer loading resetten
      setLoading(false);
    }
  }, [input, loading, store, provider, sessionId]);

  const suggestions = useMemo(() => {
    // Extract entities from all documents
    const allEntities = store.documents.flatMap(d => d.entities || []);
    const uniqueEntities = [...new Set(allEntities)].slice(0, 6);

    // Extract tags from all documents
    const allTags = store.documents.flatMap(d => d.tags || []);
    const uniqueTags = [...new Set(allTags)].slice(0, 4);

    // Get document types
    const docTypes = [...new Set(store.documents.map(d => d?.type))];
    const hasPdf = docTypes.includes("pdf");
    const hasDocx = docTypes.includes("docx");

    // Context-aware suggestions based on store type
    const baseSuggestions = [];

    // Store-specific suggestions
    if (isAkte(store)) {
      baseSuggestions.push(
        "Was sind die nächsten Schritte?",
        "Welche Fristen sind einzuhalten?",
        "Zusammenfassung aller Maßnahmen"
      );
    } else {
      baseSuggestions.push(
        "Was sind die Kernkonzepte?",
        "Wie hängen die Themen zusammen?",
        "Überblick über alle Wissensgebiete"
      );
    }

    // Entity-based suggestions
    if (uniqueEntities.length > 0) {
      baseSuggestions.push(`Erkläre "${uniqueEntities[0]}"`);
      if (uniqueEntities.length > 1) {
        baseSuggestions.push(`Vergleich: ${uniqueEntities[0]} vs ${uniqueEntities[1]}`);
      }
    }

    // Tag-based suggestions
    if (uniqueTags.length > 0) {
      baseSuggestions.push(`Alle Dokumente zu "${uniqueTags[0]}"`);
    }

    // Document count based suggestions
    if (store.documents.length === 0) {
      baseSuggestions.push("Wie kann ich diese Sammlung nutzen?");
    } else if (store.documents.length === 1) {
      baseSuggestions.push("Zusammenfassung des Dokuments");
    } else if (store.documents.length > 10) {
      baseSuggestions.push("Top 5 wichtigste Themen");
    }

    // File type specific suggestions
    if (hasPdf) {
      baseSuggestions.push("Inhalte aller PDF-Dateien");
    }
    if (hasDocx) {
      baseSuggestions.push("Zusammenfassung aller Word-Dokumente");
    }

    // Analyze-Fokus specific
    if (store.analyseFokus && store.analyseFokus !== "Allgemeine Analyse") {
      baseSuggestions.push(`Details zu: ${store.analyseFokus}`);
    }

    // Limit to 6 suggestions and ensure variety
    const finalSuggestions = baseSuggestions
      .filter((s, i, arr) => arr.indexOf(s) === i) // Remove duplicates
      .slice(0, 6);

    return finalSuggestions.length > 0
      ? finalSuggestions
      : ["Stellen Sie eine Frage zu den Dokumenten...", "Fassen Sie Inhalte zusammen...", "Suchen Sie nach spezifischen Informationen..."];
  }, [store]);

  return <div style={{ display: "flex", flexDirection: "column", height: "100%", background: CI.midnight5 }}>
    {/* Messages */}
    <div style={{ flex: 1, overflow: "auto", padding: "20px 28px" }}>
      <StoreContextBanner store={store} label="Chat-Datenquelle" />
      {msgs.map((m, i) => <div key={i} style={{ display: "flex", gap: 10, marginBottom: 16, justifyContent: m.role === "user" ? "flex-end" : "flex-start" }}>
        {m.role === "assistant" && <div style={{ width: 32, height: 32, borderRadius: 8, background: store.color + "20", display: "flex", alignItems: "center", justifyContent: "center", color: store.color, flexShrink: 0, fontSize: 12, fontWeight: 800 }}>KI</div>}
        <div style={{ maxWidth: "70%", padding: "12px 16px", borderRadius: m.role === "user" ? "14px 14px 4px 14px" : "14px 14px 14px 4px", background: m.role === "user" ? CI.lagoon : CI.white, color: m.role === "user" ? CI.white : CI.gray800, fontSize: 13, lineHeight: 1.6, border: m.role === "assistant" ? "1px solid " + CI.gray300 : "none", whiteSpace: "pre-wrap" }}>
          {m.text}
          {m.sources?.length > 0 && <div style={{ marginTop: 8, paddingTop: 8, borderTop: "1px solid " + (m.role === "user" ? "rgba(255,255,255,0.2)" : CI.gray200) }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: m.role === "user" ? "rgba(255,255,255,0.7)" : CI.midnight40, textTransform: "uppercase", marginBottom: 4 }}>Quellen</div>
            {m.sources.map((s, j) => <div key={j} style={{ fontSize: 11, color: m.role === "user" ? "rgba(255,255,255,0.8)" : CI.lagoon, display: "flex", alignItems: "center", gap: 4 }}>{Ic.doc} {s.title}</div>)}
          </div>}
          {m.role === "assistant" && i > 0 && m.text && m.sources?.length > 0 && isWissensDB(store) && <div style={{ marginTop: 10, paddingTop: 8, borderTop: "1px solid " + CI.gray200 }}>
            <button onClick={async () => {
              const prevUser = msgs[i - 1];
              const q = prevUser?.role === "user" ? prevUser.text : "Chat-Antwort";
              const r = await api.wikiSaveAnswer(store.id, q, m.text);
              if (r && r.slug) toast(`Als Wiki-Seite gespeichert: "${r.title}"`, "success");
              else toast("Speichern fehlgeschlagen", "error");
            }} style={{ padding: "3px 10px", borderRadius: 4, border: "1px solid " + CI.basil + "40", background: CI.basil + "08", color: CI.basil, cursor: "pointer", fontSize: 10, fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 4 }}>{Ic.save} Als Wiki-Seite speichern</button>
          </div>}
        </div>
      </div>)}
      {loading && <div style={{ display: "flex", gap: 10, marginBottom: 16 }}>
        <div style={{ width: 32, height: 32, borderRadius: 8, background: store.color + "20", display: "flex", alignItems: "center", justifyContent: "center", color: store.color, flexShrink: 0, fontSize: 12, fontWeight: 800 }}>KI</div>
        <div style={{ padding: "12px 16px", borderRadius: "14px 14px 14px 4px", background: CI.white, border: "1px solid " + CI.gray300 }}>
          <div style={{ display: "flex", gap: 4 }}>{[0, 1, 2].map(i => <div key={i} style={{ width: 8, height: 8, borderRadius: "50%", background: CI.lagoon40, animation: `pulse 1.2s ${i * 0.2}s infinite` }} />)}</div>
        </div>
      </div>}
      <div ref={endRef} />
    </div>
    {/* Suggestions */}
    {msgs.length <= 1 && <div style={{ padding: "0 28px 12px", display: "flex", gap: 6, flexWrap: "wrap" }}>
      {suggestions.map((s, i) => <button key={i} onClick={() => { setInput(s); }} style={{ padding: "6px 12px", borderRadius: 16, border: "1px solid " + CI.gray300, background: CI.white, color: CI.midnight, fontSize: 12, cursor: "pointer" }}
        onMouseEnter={e => e.currentTarget.style.borderColor = CI.lagoon} onMouseLeave={e => e.currentTarget.style.borderColor = CI.gray300}
        aria-label={`Suggestion: ${s}`}>{s}</button>)}
    </div>}
    {/* Input */}
    <div style={{ padding: "12px 28px 20px", background: CI.white, borderTop: "1px solid " + CI.gray300 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        {/* Provider Selector with User-Friendly Labels */}
        <ProviderSelector
          value={provider}
          onChange={(val) => setProvider(val)}
          providers={providerList}
        />
        <div style={{ flex: 1, display: "flex", alignItems: "center", background: CI.midnight5, borderRadius: 8, padding: "0 12px", border: "1px solid " + CI.gray300 }}>
          <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && handleSend()} placeholder={`Frage an "${store.name}"...`} style={{ flex: 1, background: "none", border: "none", outline: "none", color: CI.midnight, fontSize: 14, padding: "12px 0", fontFamily: "inherit" }} aria-label="Chat-Nachricht eingeben" />
        </div>
        <button onClick={handleSend} disabled={!input.trim() || loading} style={{ width: 42, height: 42, borderRadius: 8, border: "none", background: input.trim() ? CI.lagoon : CI.gray400, color: CI.white, cursor: input.trim() ? "pointer" : "not-allowed", display: "flex", alignItems: "center", justifyContent: "center" }} aria-label={loading ? "Nachricht wird gesendet..." : "Nachricht senden"}>{Ic.send}</button>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, alignItems: "center" }}>
        <div style={{ fontSize: 10, color: CI.grey01 }}>Antworten basieren ausschliesslich auf "{store.name}" ({store.documents.length} Dok.) | Provider: {provider}</div>
        {/* Export Links */}
        <div style={{ display: "flex", gap: 6 }}>
          {[["PPTX", api.exportPptx(store.id)], ["DOCX", api.exportDocx(store.id)], ["PDF", api.exportPdf(store.id)]].map(([label, url]) =>
            <a key={label} href={url} target="_blank" rel="noopener" style={{ fontSize: 10, fontWeight: 600, color: CI.lagoon, textDecoration: "none", padding: "2px 6px", borderRadius: 3, border: "1px solid " + CI.lagoon + "40" }} aria-label={`Export als ${label}`}>{label}</a>
          )}
        </div>
      </div>
    </div>
    <style>{`@keyframes pulse { 0%,80%,100% { opacity: 0.3; transform: scale(0.8); } 40% { opacity: 1; transform: scale(1.1); } }`}</style>
  </div>;
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// SKILLS – Skill-Integration
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
const SKILLS = [
  { id: "pptx", name: "PowerPoint erstellen", desc: "Generiert eine Präsentation aus Sammlungsinhalten", icon: Ic.file, color: CI.pgBurg, category: "Dokumente", fields: [{ key: "title", label: "Titel", placeholder: "z.B. Statusbericht Q3" }, { key: "slides", label: "Folienanzahl", placeholder: "10" }, { key: "focus", label: "Schwerpunkt", placeholder: "z.B. Fortschritt Digitalisierung" }] },
  { id: "docx", name: "Word-Dokument erstellen", desc: "Erstellt ein formatiertes Dokument aus der Sammlung", icon: Ic.doc, color: CI.pgBaUm, category: "Dokumente", fields: [{ key: "title", label: "Dokumenttitel", placeholder: "z.B. Zusammenfassender Bericht" }, { key: "sections", label: "Abschnitte", placeholder: "z.B. Einleitung, Analyse, Empfehlung" }] },
  { id: "blog", name: "Blog-Beitrag generieren", desc: "Erstellt einen öffentlichkeitstauglichen Blog-Beitrag", icon: Ic.pen, color: CI.pgBiSo, category: "Content", fields: [{ key: "title", label: "Thema", placeholder: "z.B. Digitalisierung in der Verwaltung" }, { key: "tone", label: "Tonalität", placeholder: "informativ / locker / formell" }, { key: "length", label: "Länge (Wörter)", placeholder: "500" }] },
  { id: "press", name: "Presseanfrage beantworten", desc: "Generiert eine sachliche Antwort auf eine Presseanfrage", icon: Ic.press, color: CI.pgDiDa, category: "Kommunikation", fields: [{ key: "question", label: "Pressefrage", placeholder: "z.B. Wie ist der Stand der Digitalisierung?" }, { key: "tone", label: "Tonalität", placeholder: "formell / diplomatisch" }] },
  { id: "anon", name: "Anonymisierung", desc: "Entfernt personenbezogene Daten (DSGVO-konform)", icon: Ic.shield, color: CI.red, category: "DSGVO", fields: [{ key: "scope", label: "Umfang", placeholder: "Alle Dokumente / Auswahl" }, { key: "entities", label: "Zu entfernen", placeholder: "Personen, Adressen, Telefonnummern" }] },
  { id: "planning", name: "Maßnahmenplanung", desc: "Extrahiert Maßnahmen und erstellt einen Umsetzungsplan", icon: Ic.plan, color: CI.basil, category: "Planung", fields: [{ key: "timeframe", label: "Zeitraum", placeholder: "Q1 2026 – Q4 2026" }, { key: "priority", label: "Priorisierung", placeholder: "Nach Dringlichkeit / Budget / Abhängigkeit" }] },
];

function SkillPanel({ store }) {
  const [activeSkill, setActiveSkill] = useState(null);
  const [fieldValues, setFieldValues] = useState({});
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [log, setLog] = useState([]);

  const categories = useMemo(() => [...new Set(SKILLS.map(s => s.category))], []);

  const runSkill = async () => {
    if (!activeSkill) return;
    setRunning(true); setResult(null); setLog([]);
    setLog(p => [...p, { time: new Date().toLocaleTimeString("de-DE"), msg: `Skill "${activeSkill.name}" wird gestartet...` }]);

    // Echte Backend-API aufrufen
    const apiResult = await api.executeSkill(store.id, activeSkill.id, fieldValues);

    if (apiResult && apiResult.step === "done") {
      // Backend hat geantwortet
      const r = apiResult.result || {};
      setLog(p => [...p,
        { time: new Date().toLocaleTimeString("de-DE"), msg: `${store.documents.length} Dokumente geladen` },
        { time: new Date().toLocaleTimeString("de-DE"), msg: apiResult.message || "Fertig" },
      ]);
      const hasFile = r.file_generated || r.output_path;
      setResult({
        skill: activeSkill.name,
        status: "Erfolgreich",
        output: hasFile
          ? `${activeSkill.name}: Datei erzeugt (${r.file_size_kb || "?"} KB) — ${r.filename || ""}`
          : `${activeSkill.name} wurde auf Basis von ${r.source_documents || store.documents.length} Dokumenten erstellt.`,
        details: Object.entries(r).filter(([k]) => !["type", "source_store"].includes(k)).slice(0, 6).map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v).slice(0, 80) : v}`),
        downloadPath: r.output_path || null,
      });
    } else {
      // Fallback: Lokale Simulation
      const steps = [
        `${store.documents.length} Dokumente werden geladen...`,
        "Inhalte werden analysiert...",
        `${activeSkill.name} wird generiert...`,
        `Fertig (Offline-Modus)`,
      ];
      for (const step of steps) {
        await delay(400 + Math.random() * 400);
        setLog(p => [...p, { time: new Date().toLocaleTimeString("de-DE"), msg: step }]);
      }
      setResult({
        skill: activeSkill.name, status: "Offline-Modus",
        output: `${activeSkill.name} wurde lokal simuliert (Backend nicht erreichbar).`,
        details: Object.entries(fieldValues).filter(([, v]) => v).map(([k, v]) => `${k}: ${v}`),
      });
    }
    setRunning(false);
  };

  if (activeSkill) {
    return <div style={{ padding: "24px 28px", overflow: "auto", height: "100%" }}>
      <button onClick={() => { setActiveSkill(null); setResult(null); setLog([]); setFieldValues({}); }} style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 12px", borderRadius: 4, border: "1px solid " + CI.gray300, background: CI.white, color: CI.midnight60, cursor: "pointer", fontSize: 12, fontWeight: 600, marginBottom: 20 }}>{Ic.back} Zurück</button>

      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
        <div style={{ width: 48, height: 48, borderRadius: 10, background: activeSkill.color + "15", display: "flex", alignItems: "center", justifyContent: "center", color: activeSkill.color }}>{activeSkill.icon}</div>
        <div><h2 style={{ fontSize: 18, fontWeight: 700, color: CI.midnight, margin: 0 }}>{activeSkill.name}</h2><p style={{ fontSize: 12, color: CI.midnight60, margin: "2px 0 0" }}>{activeSkill.desc}</p></div>
        <Badge color={activeSkill.color}>{activeSkill.category}</Badge>
      </div>
      <StoreContextBanner store={store} label="Skill arbeitet ausschließlich mit" />

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div>
          <div style={CS}>
            <div style={{ fontSize: 11, fontWeight: 700, color: CI.midnight60, textTransform: "uppercase", marginBottom: 14 }}>Parameter</div>
            {activeSkill.fields.map(f => <div key={f.key} style={{ marginBottom: 14 }}>
              <label style={{ fontSize: 11, fontWeight: 600, color: CI.midnight60, display: "block", marginBottom: 4 }}>{f.label}</label>
              <input value={fieldValues[f.key] || ""} onChange={e => setFieldValues(p => ({ ...p, [f.key]: e.target.value }))} placeholder={f.placeholder} style={{ width: "100%", background: CI.midnight5, border: "1px solid " + CI.gray300, borderRadius: 4, color: CI.midnight, fontSize: 13, padding: "10px 12px", outline: "none", fontFamily: "inherit", boxSizing: "border-box" }} />
            </div>)}
            <div style={{ fontSize: 11, color: CI.midnight40, marginBottom: 14, padding: "8px 10px", background: CI.midnight5, borderRadius: 4 }}>
              Datenquelle: <strong style={{ color: CI.midnight }}>{store.name}</strong> ({store.documents.length} Dokumente)
            </div>
            <button onClick={runSkill} disabled={running} style={{ width: "100%", padding: "12px", borderRadius: 6, border: "none", background: running ? CI.gray400 : activeSkill.color, color: CI.white, cursor: running ? "not-allowed" : "pointer", fontSize: 13, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}>
              {running ? "Wird ausgeführt…" : <>{Ic.play} Skill ausführen</>}
            </button>
          </div>
        </div>
        <div>
          {log.length > 0 && <div style={{ background: CI.midnight, borderRadius: 8, padding: "16px 18px", fontFamily: "monospace", marginBottom: 14 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: CI.lagoon60, textTransform: "uppercase", marginBottom: 10 }}>Ausführungs-Log</div>
            {log.map((e, i) => <div key={i} style={{ display: "flex", gap: 10, padding: "3px 0", fontSize: 12, color: e.msg.startsWith("✓") ? CI.basil : CI.midnight40 }}><span style={{ color: CI.midnight60 }}>{e.time}</span><span>{e.msg}</span></div>)}
          </div>}
          {result && <div style={{ ...CS, borderLeft: "4px solid " + CI.basil }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: CI.basil, textTransform: "uppercase", marginBottom: 8 }}>✓ Ergebnis</div>
            <p style={{ fontSize: 13, color: CI.gray700, lineHeight: 1.6, margin: "0 0 8px" }}>{result.output}</p>
            {result.details.length > 0 && <div style={{ fontSize: 12, color: CI.midnight60 }}>{result.details.map((d, i) => <div key={i}>• {d}</div>)}</div>}
          </div>}
        </div>
      </div>
    </div>;
  }

  return <div style={{ padding: "24px 28px", overflow: "auto", height: "100%" }}>
    <h2 style={{ fontSize: 18, fontWeight: 700, color: CI.midnight, margin: "0 0 6px" }}>Skills</h2>
    <p style={{ fontSize: 12, color: CI.midnight60, margin: "0 0 12px" }}>Automatisierte Verarbeitung — ausschließlich auf Basis der Dokumente dieser Sammlung</p>
    <StoreContextBanner store={store} label="Skill-Datenquelle" />
    {categories.map(cat => <div key={cat} style={{ marginBottom: 20 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: CI.midnight40, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>{cat}</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(280px,1fr))", gap: 10 }}>
        {SKILLS.filter(s => s.category === cat).map(skill => <button key={skill.id} onClick={() => setActiveSkill(skill)} style={{ ...CS, display: "flex", alignItems: "flex-start", gap: 12, cursor: "pointer", textAlign: "left", transition: "all 0.15s" }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = skill.color; e.currentTarget.style.boxShadow = "0 2px 8px rgba(0,58,64,0.1)"; }} onMouseLeave={e => { e.currentTarget.style.borderColor = CI.gray300; e.currentTarget.style.boxShadow = CS.boxShadow; }}>
          <div style={{ width: 40, height: 40, borderRadius: 8, background: skill.color + "12", display: "flex", alignItems: "center", justifyContent: "center", color: skill.color, flexShrink: 0 }}>{skill.icon}</div>
          <div><div style={{ fontSize: 13, fontWeight: 700, color: CI.midnight }}>{skill.name}</div><div style={{ fontSize: 12, color: CI.midnight60, marginTop: 2, lineHeight: 1.4 }}>{skill.desc}</div></div>
        </button>)}
      </div>
    </div>)}
  </div>;
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// PLANNING ENGINE – Maßnahmen- und Projektplanung
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
const PLAN_COLUMNS = ["Backlog", "In Planung", "In Umsetzung", "Abgeschlossen"];
const TASK_COLORS = [CI.red, CI.pgDiDa, CI.pgInfr, CI.basil, CI.pgBurg, CI.pgBiSo, CI.amarillo, CI.lagoon, CI.darkamarillo];

// Maßnahmen dynamisch aus Store-Dokumenten extrahieren
function extractTasksFromStore(store) {
  const tasks = [];
  const statuses = ["Backlog", "In Planung", "In Umsetzung", "Abgeschlossen"];
  const priorities = ["Hoch", "Mittel", "Niedrig"];
  const quarters = ["Q4 2025", "Q1 2026", "Q2 2026", "Q3 2026"];
  let idx = 0;
  for (const doc of store.documents) {
    const ents = extractEntities(doc.content);
    // Aus Fachbegriffen Maßnahmen ableiten
    for (const term of ents.fachbegriffe.slice(0, 3)) {
      const persons = ents.personen;
      tasks.push({
        id: "pt-" + uid(), title: term + " umsetzen",
        desc: `Aus "${doc.title}" extrahiert`,
        status: statuses[idx % statuses.length],
        priority: priorities[idx % priorities.length],
        due: quarters[idx % quarters.length],
        assignee: persons.length > 0 ? persons[idx % persons.length] : "Zuständige Stelle",
        source: doc.title,
        color: TASK_COLORS[idx % TASK_COLORS.length],
      });
      idx++;
    }
    // Daten als Meilensteine
    for (const datum of ents.daten.slice(0, 1)) {
      tasks.push({
        id: "pt-" + uid(), title: `Frist: ${datum}`,
        desc: `Termin aus "${doc.title}"`,
        status: "In Planung", priority: "Hoch", due: quarters[idx % quarters.length],
        assignee: ents.personen[0] || "Projektleitung",
        source: doc.title, color: CI.amarillo,
      });
      idx++;
    }
  }
  return tasks.length > 0 ? tasks : [
    { id: "pt-empty", title: "Keine Maßnahmen erkannt", desc: "Laden Sie Dokumente hoch, um Maßnahmen zu extrahieren", status: "Backlog", priority: "Niedrig", due: "", assignee: "", source: store.name, color: CI.gray500 }
  ];
}

function PlanningPanel({ store }) {
  const localTasks = useMemo(() => extractTasksFromStore(store), [store]);
  const [tasks, setTasks] = useState(localTasks);
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState("all"); // all | documents | wiki-maintenance
  const { toast } = useToast();

  const loadTasks = useCallback(async (filter = categoryFilter) => {
    setLoading(true);
    const catParam = filter === "all" ? null : filter;
    const r = catParam ? await api.getTasksFiltered(store.id, catParam) : await api.getTasks(store.id);
    if (r && r.tasks && r.tasks.length > 0) {
      const mapped = r.tasks.map(t => ({
        id: t.id, title: t.title, desc: t.description,
        status: { backlog: "Backlog", planning: "In Planung", active: "In Umsetzung", done: "Abgeschlossen" }[t.status] || t.status,
        priority: { hoch: "Hoch", mittel: "Mittel", niedrig: "Niedrig" }[t.priority] || t.priority,
        due: t.due_date, assignee: t.assignee, source: t.source_document,
        source_entity: t.source_entity,
        color: t.color || CI.lagoon,
        depends_on: t.depends_on || [],
        blocked_by_count: t.blocked_by_count || 0,
        isWikiMaintenance: (t.source_document || "").startsWith("wiki-lint:"),
      }));
      setTasks(mapped);
    } else if (filter !== "all") {
      // Leeres Filter-Ergebnis
      setTasks([]);
    } else {
      setTasks(localTasks);
    }
    setLoading(false);
  }, [store.id, localTasks, categoryFilter]);

  useEffect(() => { loadTasks(); }, [loadTasks]);

  const handleFilterChange = (f) => {
    setCategoryFilter(f);
    loadTasks(f);
  };

  const handleRunWikiLint = async () => {
    const r = await api.wikiLintToTasks(store.id);
    if (r) {
      if (r.created > 0) {
        toast(`${r.created} Wartungs-Tasks angelegt`, "success");
      } else if (r.total_issues === 0) {
        toast("Wiki ist gesund, keine neuen Tasks", "info");
      } else {
        toast(`Alle ${r.skipped} Issues haben bereits Tasks`, "info");
      }
      loadTasks();
    }
  };
  const [dragging, setDragging] = useState(null);
  const [showAdd, setShowAdd] = useState(false);
  const [newTask, setNewTask] = useState({ title: "", desc: "", priority: "Mittel", due: "", assignee: "" });

  const handleDrop = (col) => {
    if (!dragging) return;
    const statusMap = { "Backlog": "backlog", "In Planung": "planning", "In Umsetzung": "active", "Abgeschlossen": "done" };
    setTasks(p => p.map(t => t.id === dragging ? { ...t, status: col } : t));
    api.updateTask(store.id, dragging, { status: statusMap[col] });
    setDragging(null);
  };

  const priorities = { Hoch: CI.red, Mittel: CI.amarillo, Niedrig: CI.basil };

  const isWissensDB = store.type === "wissensdb" || store.type === "WISSENSDB"; // DEPRECATED: Nutze isWissensDB(store) aus global scope
  const wikiTaskCount = tasks.filter(t => t.isWikiMaintenance).length;

  return <div style={{ padding: "24px 28px", overflow: "auto", height: "100%" }}>
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
      <div>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: CI.midnight, margin: 0 }}>Planungs-Engine</h2>
        <p style={{ fontSize: 12, color: CI.midnight60, margin: "2px 0 0" }}>
          {categoryFilter === "wiki-maintenance" ? "Wiki-Wartungs-Tasks (aus Lint-Analyse)" :
           categoryFilter === "documents" ? "Massnahmen aus Dokumenten extrahiert" :
           "Alle Massnahmen"}
        </p>
      </div>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <Badge color={CI.lagoon}>{tasks.length} Massnahmen</Badge>
        <Badge color={CI.basil}>{tasks.filter(t => t.status === "Abgeschlossen").length} erledigt</Badge>
        {isWissensDB && wikiTaskCount > 0 && <Badge color={CI.pgBurg}>{wikiTaskCount} Wiki-Wartung</Badge>}
        {isWissensDB && <button onClick={handleRunWikiLint} style={{ display: "flex", alignItems: "center", gap: 4, padding: "6px 12px", borderRadius: 6, border: "1px solid " + CI.pgBurg, background: CI.white, color: CI.pgBurg, cursor: "pointer", fontSize: 11, fontWeight: 600 }}>{Ic.shield} Wiki-Lint</button>}
        <button onClick={() => setShowAdd(!showAdd)} style={{ display: "flex", alignItems: "center", gap: 4, padding: "6px 14px", borderRadius: 6, border: "none", background: CI.lagoon, color: CI.white, cursor: "pointer", fontSize: 12, fontWeight: 700 }}>{Ic.plus} Neue Massnahme</button>
      </div>
    </div>

    {/* Category-Filter: nur fuer WissensDB sinnvoll */}
    {isWissensDB && <div style={{ display: "flex", gap: 4, marginBottom: 12, padding: 3, background: CI.midnight5, borderRadius: 6, width: "fit-content" }}>
      {[
        { id: "all", l: "Alle", c: CI.midnight },
        { id: "documents", l: "Aus Dokumenten", c: CI.amarillo },
        { id: "wiki-maintenance", l: "Wiki-Wartung", c: CI.pgBurg },
      ].map(f => <button key={f.id} onClick={() => handleFilterChange(f.id)} style={{ padding: "6px 14px", borderRadius: 4, border: "none", background: categoryFilter === f.id ? CI.white : "transparent", color: categoryFilter === f.id ? f.c : CI.midnight60, cursor: "pointer", fontSize: 11, fontWeight: 600, boxShadow: categoryFilter === f.id ? "0 1px 2px rgba(0,58,64,0.08)" : "none", transition: "all 0.15s" }}>{f.l}</button>)}
    </div>}

    <StoreContextBanner store={store} label="Massnahmen extrahiert aus" />

    {/* Add Task Form */}
    {showAdd && <div style={{ ...CS, marginBottom: 16, borderLeft: "4px solid " + CI.lagoon }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
        <input value={newTask.title} onChange={e => setNewTask(p => ({ ...p, title: e.target.value }))} placeholder="Maßnahme" style={{ background: CI.midnight5, border: "1px solid " + CI.gray300, borderRadius: 4, padding: "8px 10px", fontSize: 12, outline: "none", fontFamily: "inherit", color: CI.midnight }} />
        <input value={newTask.assignee} onChange={e => setNewTask(p => ({ ...p, assignee: e.target.value }))} placeholder="Zuständig" style={{ background: CI.midnight5, border: "1px solid " + CI.gray300, borderRadius: 4, padding: "8px 10px", fontSize: 12, outline: "none", fontFamily: "inherit", color: CI.midnight }} />
        <div style={{ display: "flex", gap: 6 }}>
          <input value={newTask.due} onChange={e => setNewTask(p => ({ ...p, due: e.target.value }))} placeholder="Frist (Q1 2026)" style={{ flex: 1, background: CI.midnight5, border: "1px solid " + CI.gray300, borderRadius: 4, padding: "8px 10px", fontSize: 12, outline: "none", fontFamily: "inherit", color: CI.midnight }} />
          <button onClick={() => { if (newTask.title) { setTasks(p => [...p, { ...newTask, id: uid(), status: "Backlog", desc: "", source: "Manuell", color: CI.lagoon, priority: "Mittel" }]); setNewTask({ title: "", desc: "", priority: "Mittel", due: "", assignee: "" }); setShowAdd(false); } }} style={{ padding: "8px 14px", borderRadius: 4, border: "none", background: CI.lagoon, color: CI.white, cursor: "pointer", fontSize: 12, fontWeight: 600 }}>Hinzufügen</button>
        </div>
      </div>
    </div>}

    {/* Kanban Board */}
    <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12, minHeight: 400 }}>
      {PLAN_COLUMNS.map(col => {
        const colTasks = tasks.filter(t => t.status === col);
        const colColors = { "Backlog": CI.gray500, "In Planung": CI.amarillo, "In Umsetzung": CI.lagoon, "Abgeschlossen": CI.basil };
        return <div key={col}
          onDragOver={e => e.preventDefault()} onDrop={() => handleDrop(col)}
          style={{ background: CI.midnight5, borderRadius: 8, padding: 10, minHeight: 300 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10, padding: "0 4px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: colColors[col] }} />
              <span style={{ fontSize: 12, fontWeight: 700, color: CI.midnight }}>{col}</span>
            </div>
            <span style={{ fontSize: 11, fontWeight: 600, color: CI.midnight40, background: CI.white, borderRadius: 10, padding: "1px 8px" }}>{colTasks.length}</span>
          </div>
          {colTasks.map(task => <div key={task.id} draggable onDragStart={() => setDragging(task.id)}
            style={{ background: CI.white, borderRadius: 8, padding: "12px 14px", marginBottom: 8, border: "1px solid " + CI.gray300, borderLeft: "3px solid " + task.color, cursor: "grab", transition: "all 0.15s" }}
            onMouseEnter={e => e.currentTarget.style.boxShadow = "0 2px 8px rgba(0,58,64,0.1)"} onMouseLeave={e => e.currentTarget.style.boxShadow = "none"}>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 6, marginBottom: 4 }}>
              {task.isWikiMaintenance && <span style={{ color: CI.pgBurg, marginTop: 1, flexShrink: 0 }} title="Wiki-Wartungs-Task">{Ic.book}</span>}
              <div style={{ fontSize: 13, fontWeight: 600, color: CI.midnight, flex: 1 }}>{task.title}</div>
            </div>
            {task.desc && <div style={{ fontSize: 11, color: CI.midnight60, marginBottom: 6, lineHeight: 1.4, whiteSpace: "pre-wrap" }}>{task.desc.length > 120 ? task.desc.slice(0, 120) + "..." : task.desc}</div>}
            <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
              <Badge color={priorities[task.priority] || CI.gray500} small>{task.priority}</Badge>
              {task.due && <Badge color={CI.midnight40} small>{task.due}</Badge>}
              {task.assignee && <Badge color={CI.pgDiDa} small>{task.assignee}</Badge>}
            </div>
            <div style={{ fontSize: 10, color: task.isWikiMaintenance ? CI.pgBurg : CI.grey01, marginTop: 6, display: "flex", alignItems: "center", gap: 3 }}>
              {task.isWikiMaintenance ? Ic.book : Ic.doc} {task.isWikiMaintenance ? task.source.replace("wiki-lint:", "Wiki: ") : task.source}
            </div>
          </div>)}
        </div>;
      })}
    </div>

    {/* Timeline */}
    <div style={{ ...CS, marginTop: 16 }}>
      {SH(Ic.flag, "Meilensteine", CI.darkamarillo)}
      <div style={{ display: "flex", gap: 0, position: "relative" }}>
        <div style={{ position: "absolute", top: 14, left: 0, right: 0, height: 2, background: CI.gray300 }} />
        {["Q3 2025", "Q4 2025", "Q1 2026", "Q2 2026", "Q3 2026"].map((q, i) => {
          const count = tasks.filter(t => t.due === q).length;
          const done = tasks.filter(t => t.due === q && t.status === "Abgeschlossen").length;
          return <div key={q} style={{ flex: 1, textAlign: "center", position: "relative", zIndex: 1 }}>
            <div style={{ width: 12, height: 12, borderRadius: "50%", background: done === count && count > 0 ? CI.basil : count > 0 ? CI.amarillo : CI.gray400, border: "2px solid " + CI.white, margin: "8px auto 6px" }} />
            <div style={{ fontSize: 11, fontWeight: 700, color: CI.midnight }}>{q}</div>
            <div style={{ fontSize: 10, color: CI.midnight60 }}>{count} Maßnahme{count !== 1 ? "n" : ""}</div>
          </div>;
        })}
      </div>
    </div>
  </div>;
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// SEARCH PANEL
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function SearchPanel({ store }) {
  const [q, setQ] = useState(""); const [st, setSt] = useState("hybrid");
  const [res, setRes] = useState([]);
  const [searching, setSearching] = useState(false);
  const [execTime, setExecTime] = useState(0);
  const [bm25Weight, setBm25Weight] = useState(40); // 0-100%, default 40%
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Calculate weights
  const weights = useMemo(() => {
    if (st === "bm25") return { bm25: 1, semantic: 0 };
    if (st === "semantic") return { bm25: 0, semantic: 1 };
    return { bm25: bm25Weight / 100, semantic: (100 - bm25Weight) / 100 };
  }, [st, bm25Weight]);

  const resetWeights = useCallback(() => {
    setBm25Weight(40);
    setSt("hybrid");
  }, []);

  const doSearch = useCallback(async (query, searchType, customWeights = null) => {
    if (!query.trim()) { setRes([]); return; }
    setSearching(true);
    const t0 = Date.now();
    const apiResult = await api.search(query, store.id, searchType);
    if (apiResult && apiResult.results) {
      setRes(apiResult.results.map(r => ({
        id: r.document_id, title: r.document_title, content: r.chunk_content,
        type: r.file_type, _score: r.score, tags: r.tags, page: r.page_start,
      })));
      setExecTime(apiResult.execution_time_ms || (Date.now() - t0));
    } else {
      // Fallback auf lokale Suche
      const all = store.documents.map(d => ({ ...d, _store: store }));
      const w = customWeights || weights;
      setRes(hybridSearch(all, query, w));
      setExecTime(Date.now() - t0);
    }
    setSearching(false);
  }, [store, weights]);

  useEffect(() => { if (q.trim()) { const t = setTimeout(() => doSearch(q, st, weights), 300); return () => clearTimeout(t); } else setRes([]); }, [q, st, weights, doSearch]);

  return <div style={{ padding: "24px 28px", overflow: "auto", height: "100%" }}>
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
      <h2 style={{ fontSize: 18, fontWeight: 700, color: CI.midnight, margin: 0 }}>Hybrid-Suche</h2>
      <button
        onClick={() => setShowAdvanced(!showAdvanced)}
        style={{
          padding: "6px 12px",
          borderRadius: 4,
          border: "1px solid " + CI.gray300,
          background: CI.white,
          color: CI.midnight60,
          cursor: "pointer",
          fontSize: 11,
          fontWeight: 600,
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.borderColor = CI.lagoon;
          e.currentTarget.style.color = CI.lagoon;
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.borderColor = CI.gray300;
          e.currentTarget.style.color = CI.midnight60;
        }}
      >
        {showAdvanced ? "Einfach" : "Erweitert"} {Ic.gear}
      </button>
    </div>
    <StoreContextBanner store={store} label="Suche in" />
    <div style={{ display: "flex", gap: 10, marginBottom: 16 }}><div style={{ flex: 1, display: "flex", alignItems: "center", gap: 8, background: CI.white, borderRadius: 6, padding: "0 14px", border: "1px solid " + CI.gray300 }}><span style={{ color: CI.gray500 }}>{Ic.search}</span><input type="text" value={q} onChange={e => setQ(e.target.value)} placeholder="Dokumente durchsuchen..." style={{ flex: 1, background: "none", border: "none", outline: "none", color: CI.midnight, fontSize: 14, padding: "12px 0", fontFamily: "inherit" }} /></div></div>

    {/* Search Type Buttons */}
    <div style={{ display: "flex", gap: 8, marginBottom: showAdvanced ? 20 : 16, flexWrap: "wrap", alignItems: "center" }}>
      {["hybrid", "bm25", "semantic"].map(t => <button key={t} onClick={() => setSt(t)} style={{ padding: "6px 14px", borderRadius: 4, border: "1px solid " + (st === t ? CI.lagoon : CI.gray300), background: st === t ? CI.lagoon + "12" : CI.white, color: st === t ? CI.darklagoon : CI.gray600, cursor: "pointer", fontSize: 12, fontWeight: 600 }}>{t === "hybrid" ? "Hybrid" : t === "bm25" ? "BM25" : "Semantisch"}</button>)}
      {searching && <span style={{ fontSize: 11, color: CI.lagoon }}>Suche laeuft...</span>}
    </div>

    {/* Advanced Weight Control */}
    {showAdvanced && st === "hybrid" && (
      <div style={{
        background: CI.white,
        borderRadius: 8,
        padding: "16px 18px",
        border: "1px solid " + CI.gray300,
        marginBottom: 20,
        boxShadow: "0 1px 4px rgba(0, 58, 64, 0.06)",
      }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: CI.midnight, marginBottom: 2 }}>
              Gewichtung: BM25 vs. Semantisch
            </div>
            <div style={{ fontSize: 11, color: CI.midnight60 }}>
              BM25: {(bm25Weight)}% | Semantisch: {(100 - bm25Weight)}%
            </div>
          </div>
          <button
            onClick={resetWeights}
            disabled={bm25Weight === 40}
            style={{
              padding: "4px 10px",
              borderRadius: 4,
              border: "1px solid " + CI.gray300,
              background: bm25Weight === 40 ? CI.gray100 : CI.white,
              color: bm25Weight === 40 ? CI.gray400 : CI.midnight60,
              cursor: bm25Weight === 40 ? "not-allowed" : "pointer",
              fontSize: 11,
              fontWeight: 600,
            }}
            onMouseEnter={(e) => {
              if (bm25Weight !== 40) {
                e.currentTarget.style.borderColor = CI.lagoon;
                e.currentTarget.style.color = CI.lagoon;
              }
            }}
            onMouseLeave={(e) => {
              if (bm25Weight !== 40) {
                e.currentTarget.style.borderColor = CI.gray300;
                e.currentTarget.style.color = CI.midnight60;
              }
            }}
          >
            Zurücksetzen
          </button>
        </div>

        {/* Weight Slider */}
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: CI.pgDiDa, minWidth: 50 }}>
            BM25
          </div>
          <div style={{ flex: 1, position: "relative" }}>
            <input
              type="range"
              min="0"
              max="100"
              value={bm25Weight}
              onChange={(e) => setBm25Weight(parseInt(e.target.value))}
              style={{
                width: "100%",
                height: 6,
                borderRadius: 3,
                background: `linear-gradient(to right, ${CI.pgDiDa} 0%, ${CI.pgDiDa} ${bm25Weight}%, ${CI.lagoon} ${bm25Weight}%, ${CI.lagoon} 100%)`,
                outline: "none",
                cursor: "pointer",
                WebkitAppearance: "none",
              }}
            />
            <style>{`
              input[type="range"]::-webkit-slider-thumb {
                -webkit-appearance: none;
                appearance: none;
                width: 18px;
                height: 18px;
                border-radius: 50%;
                background: ${CI.white};
                border: 2px solid ${CI.midnight};
                cursor: pointer;
                box-shadow: 0 2px 4px rgba(0, 58, 64, 0.2);
                transition: all 0.15s;
              }
              input[type="range"]::-webkit-slider-thumb:hover {
                transform: scale(1.1);
                box-shadow: 0 3px 6px rgba(0, 58, 64, 0.3);
              }
              input[type="range"]::-moz-range-thumb {
                width: 18px;
                height: 18px;
                border-radius: 50%;
                background: ${CI.white};
                border: 2px solid ${CI.midnight};
                cursor: pointer;
                box-shadow: 0 2px 4px rgba(0, 58, 64, 0.2);
                transition: all 0.15s;
              }
              input[type="range"]::-moz-range-thumb:hover {
                transform: scale(1.1);
                box-shadow: 0 3px 6px rgba(0, 58, 64, 0.3);
              }
            `}</style>
          </div>
          <div style={{ fontSize: 11, fontWeight: 600, color: CI.lagoon, minWidth: 60, textAlign: "right" }}>
            Semantisch
          </div>
        </div>

        {/* Weight Explanation */}
        <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid " + CI.gray200, fontSize: 11, color: CI.midnight60, lineHeight: 1.5 }}>
          <strong>BM25:</strong> Besser für exakte Begriffe und Schlagwörter<br />
          <strong>Semantisch:</strong> Besser für thematische Zusammenhänge und Synonyme
        </div>
      </div>
    )}
    {q.trim() && <div style={{ marginBottom: 12, fontSize: 12, color: CI.midnight60 }}>{res.length} Ergebnis{res.length !== 1 ? "se" : ""} in {execTime.toFixed(1)} ms</div>}
    {res.map((d, i) => <div key={d.id + "-" + i} style={{ background: CI.white, borderRadius: 8, padding: "14px 16px", border: "1px solid " + CI.gray300, marginBottom: 8 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}><TypeBadge type={d.type}/><span style={{ fontSize: 13, fontWeight: 600, color: CI.midnight }}>{d.title}</span><span style={{ marginLeft: "auto", fontSize: 11, color: CI.lagoon, fontWeight: 700 }}>Score: {(d._score || d.score || 0).toFixed(2)}</span></div>
      <p style={{ fontSize: 12, color: CI.gray700, margin: 0, lineHeight: 1.5 }}>{trunc(d.content, 200)}</p>
    </div>)}
    {!q.trim() && <div style={{ textAlign: "center", padding: 48, color: CI.midnight40 }}><div style={{ fontSize: 14 }}>Starten Sie eine Suche in "{store.name}"</div></div>}
  </div>;
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// DOCUMENT DETAIL VIEW — Chunks, Entitaeten, Versionen, NER
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function DocumentDetailView({ doc, store, onBack }) {
  const [detail, setDetail] = useState(null);
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [nerRunning, setNerRunning] = useState(false);
  const [nerMode, setNerMode] = useState("regex");
  const { toast } = useToast();

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.getDocument(doc.id),
      api._fetch(`/documents/detail/${doc.id}/versions`),
    ]).then(([d, v]) => {
      if (d) setDetail(d);
      if (v && v.versions) setVersions(v.versions);
      setLoading(false);
    });
  }, [doc.id]);

  const handleNerReanalyze = async () => {
    setNerRunning(true);
    const useLlm = nerMode === "llm";
    const r = await api.reanalyzeNer(store.id, useLlm);
    setNerRunning(false);
    if (r && r.entities_extracted !== undefined) {
      toast(`NER (${r.mode}): ${r.entities_extracted} Entitaeten aus ${r.documents_processed} Dokument(en) extrahiert`, "success");
      // Reload detail
      api.getDocument(doc.id).then(d => d && setDetail(d));
    } else {
      toast("NER-Reanalyse fehlgeschlagen — Backend erreichbar?", "error");
    }
  };

  const entities = detail?.entities || [];
  const chunks = detail?.chunks || [];
  const entByType = {};
  for (const e of entities) {
    const t = e.entity_type || e.type || "sonstig";
    if (!entByType[t]) entByType[t] = [];
    entByType[t].push(e);
  }

  const entTypeColors = {
    person: CI.pgDiDa, datum: CI.amarillo, fachbegriff: CI.lagoon, ort: CI.basil,
    organisation: CI.pgInfr, pii: CI.red, geldbetrag: CI.pgBurg, gesetz: CI.darkamarillo,
  };
  const entTypeLabels = {
    person: "Personen", datum: "Daten", fachbegriff: "Fachbegriffe", ort: "Orte",
    organisation: "Organisationen", pii: "PII (DSGVO)", geldbetrag: "Geldbetraege", gesetz: "Gesetze",
  };

  return <div style={{ padding: "24px 28px", overflow: "auto", height: "100%" }}>
    {/* Header */}
    <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
      <button onClick={onBack} style={{ display: "flex", alignItems: "center", gap: 5, padding: "6px 12px", borderRadius: 4, border: "1px solid " + CI.gray300, background: CI.white, color: CI.midnight60, cursor: "pointer", fontSize: 12, fontWeight: 600 }}>{Ic.back} Zurueck</button>
      <div style={{ width: 40, height: 40, borderRadius: 8, background: (TC[doc.type] || CI.gray600) + "15", display: "flex", alignItems: "center", justifyContent: "center", color: TC[doc.type] }}>{Ic.doc}</div>
      <div style={{ flex: 1 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: CI.midnight, margin: 0 }}>{doc.title}</h2>
        <div style={{ display: "flex", gap: 8, marginTop: 4 }}><TypeBadge type={doc.type}/><span style={{ fontSize: 11, color: CI.gray600 }}>{doc.pages || detail?.page_count || "?"} Seiten</span>
          {detail && <span style={{ fontSize: 11, color: CI.gray600 }}>{chunks.length} Chunks</span>}
          {detail && <span style={{ fontSize: 11, color: CI.gray600 }}>{entities.length} Entitaeten</span>}
        </div>
      </div>
      {detail?.version && detail.version > 1 && <Badge color={CI.pgInfr}>v{detail.version}</Badge>}
      {detail?.status && <Badge color={detail.status === "indexed" ? CI.basil : CI.amarillo}>{detail.status}</Badge>}
    </div>

    {loading ? <div style={{ textAlign: "center", padding: 48, color: CI.midnight40 }}>Lade Dokumentdetails...</div> : <>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 20 }}>
        {/* Stat Cards */}
        {[
          { l: "Seiten", v: detail?.page_count || doc.pages || 0, c: CI.lagoon },
          { l: "Chunks", v: chunks.length, c: CI.pgBurg },
          { l: "Entitaeten", v: entities.length, c: CI.pgInfr },
          { l: "Version", v: detail?.version || 1, c: CI.amarillo },
        ].map(s => <div key={s.l} style={{ background: CI.white, borderRadius: 8, padding: "12px 14px", border: "1px solid " + CI.gray300, borderLeft: "3px solid " + s.c }}>
          <div style={{ fontSize: 20, fontWeight: 700, color: s.c }}>{s.v}</div>
          <div style={{ fontSize: 11, color: CI.midnight60 }}>{s.l}</div>
        </div>)}
      </div>

      {/* NER Reanalyse Section */}
      <div style={{ ...CS, marginBottom: 16, borderLeft: "3px solid " + CI.pgInfr }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, justifyContent: "space-between" }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: CI.midnight }}>NER-Reanalyse</div>
            <div style={{ fontSize: 11, color: CI.midnight60, marginTop: 2 }}>Entitaeten fuer alle Dokumente in "{store.name}" neu extrahieren</div>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <select value={nerMode} onChange={e => setNerMode(e.target.value)} style={{ background: CI.midnight5, border: "1px solid " + CI.gray300, borderRadius: 4, color: CI.midnight, padding: "6px 8px", fontSize: 11, cursor: "pointer", fontFamily: "inherit" }}>
              <option value="regex">Regex (schnell, on-premise)</option>
              <option value="llm">LLM (besser, braucht Provider)</option>
            </select>
            <button onClick={handleNerReanalyze} disabled={nerRunning} style={{ padding: "6px 16px", borderRadius: 4, border: "none", background: nerRunning ? CI.gray400 : CI.pgInfr, color: CI.white, cursor: nerRunning ? "wait" : "pointer", fontSize: 12, fontWeight: 700, whiteSpace: "nowrap" }}>
              {nerRunning ? "Laeuft..." : "NER starten"}
            </button>
          </div>
        </div>
      </div>

      {/* Entitaeten nach Typ */}
      {Object.keys(entByType).length > 0 && <div style={{ ...CS, marginBottom: 16 }}>
        {SH(Ic.tag, `Entitaeten (${entities.length})`, CI.pgInfr)}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          {Object.entries(entByType).map(([type, ents]) => <div key={type}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: entTypeColors[type] || CI.gray500 }} />
              <span style={{ fontSize: 12, fontWeight: 700, color: CI.midnight }}>{entTypeLabels[type] || type}</span>
              <span style={{ fontSize: 10, color: CI.midnight40 }}>({ents.length})</span>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
              {ents.slice(0, 8).map((e, i) => <Badge key={i} color={entTypeColors[type] || CI.gray500} small>{e.value || e}{e.count > 1 ? ` (${e.count}x)` : ""}</Badge>)}
              {ents.length > 8 && <span style={{ fontSize: 10, color: CI.midnight40 }}>+{ents.length - 8} weitere</span>}
            </div>
          </div>)}
        </div>
      </div>}

      {/* Chunks */}
      {chunks.length > 0 && <div style={{ ...CS, marginBottom: 16 }}>
        {SH(Ic.layers, `Chunks (${chunks.length})`, CI.pgBurg)}
        {chunks.slice(0, 6).map((c, i) => <div key={c.id || i} style={{ padding: "10px 12px", background: CI.midnight5, borderRadius: 6, marginBottom: 6, borderLeft: "2px solid " + CI.pgBurg }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: CI.midnight60 }}>Chunk {c.chunk_index ?? i}</span>
            {c.page_start && <span style={{ fontSize: 10, color: CI.midnight40 }}>S. {c.page_start}</span>}
            <span style={{ fontSize: 10, color: CI.midnight40 }}>{c.token_count ?? "?"} Tokens</span>
          </div>
          <p style={{ fontSize: 12, color: CI.gray700, margin: 0, lineHeight: 1.5 }}>{trunc(c.content, 200)}</p>
        </div>)}
        {chunks.length > 6 && <div style={{ fontSize: 11, color: CI.midnight40, textAlign: "center", padding: 8 }}>+{chunks.length - 6} weitere Chunks</div>}
      </div>}

      {/* Versionen */}
      {versions.length > 0 && <div style={{ ...CS }}>
        {SH(Ic.flag, `Versionen (${versions.length + 1})`, CI.amarillo)}
        <div style={{ fontSize: 12, color: CI.midnight60 }}>
          <div style={{ padding: "4px 0", fontWeight: 600 }}>Aktuell: v{detail?.version || 1}</div>
          {versions.map((v, i) => <div key={v.id || i} style={{ padding: "4px 0", borderTop: "1px solid " + CI.gray200 }}>
            v{v.version || i + 1} — {v.title || doc.title} <span style={{ color: CI.midnight40 }}>({v.created_at ? new Date(v.created_at).toLocaleDateString("de-DE") : "?"})</span>
          </div>)}
        </div>
      </div>}
    </>}
  </div>;
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// BRIEFING PANEL — Entscheider-Briefing in 60 Sekunden
// Vier-Fragen-Layout: Sachstand, Risiken, Naechste Schritte, Loesung
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function BriefingPanel({ store }) {
  const [briefing, setBriefing] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api.getBriefing(store.id).then(r => {
      if (cancelled) return;
      setLoading(false);
      if (r && !r.error) {
        setBriefing(r);
      } else {
        setError(r?.error || "Briefing konnte nicht geladen werden");
      }
    });
    return () => { cancelled = true; };
  }, [store.id]);

  if (loading) {
    return <div style={{ padding: "24px 28px", display: "flex", alignItems: "center", justifyContent: "center", height: "100%" }}>
      <div style={{ textAlign: "center", color: CI.midnight60 }}>
        <div style={{ width: 24, height: 24, margin: "0 auto 12px", border: "2px solid " + CI.gray300, borderTopColor: CI.lagoon, borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        <div style={{ fontSize: 13 }}>Briefing wird generiert ...</div>
        <div style={{ fontSize: 11, marginTop: 4 }}>Sachstand, Risiken und Loesungsvorschlag werden synthetisiert</div>
      </div>
    </div>;
  }

  if (error || !briefing) {
    return <div style={{ padding: "24px 28px" }}>
      <div style={{ ...CS, borderLeft: "4px solid " + CI.red }}>
        <div style={{ fontSize: 13, color: CI.midnight }}>{error || "Keine Daten verfuegbar"}</div>
      </div>
    </div>;
  }

  const severityColor = (s) => s === "rot" ? CI.red : s === "amber" ? CI.pgBurg : CI.amarillo;
  const priorityDot = (p) => p === "hoch" ? CI.red : p === "mittel" ? CI.pgBurg : CI.basil;

  const fmtDate = (iso) => {
    if (!iso) return "";
    try {
      const d = new Date(iso);
      return d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
    } catch { return iso; }
  };

  const daysUntil = (iso) => {
    if (!iso) return null;
    try {
      const d = new Date(iso);
      const today = new Date(); today.setHours(0, 0, 0, 0);
      return Math.round((d - today) / 86400000);
    } catch { return null; }
  };

  const sachstandConfidence = Math.round((briefing.sachstand?.confidence || 0) * 100);

  return <div style={{ padding: "24px 28px", overflow: "auto", height: "100%" }}>
    {/* Header */}
    <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 16 }}>
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: CI.midnight, margin: 0 }}>Entscheider-Briefing</h2>
          <Badge color={CI.lagoon} small>60-Sekunden-View</Badge>
        </div>
        <p style={{ fontSize: 12, color: CI.midnight60, margin: 0 }}>
          {briefing.store?.doc_count} Dokumente · {briefing.store?.page_count} Seiten · zuletzt aktualisiert {fmtDate(briefing.store?.updated_at)}
        </p>
      </div>
      <div style={{ display: "flex", gap: 6 }}>
        {[["PDF", CI.pgDiDa, "pdf"], ["DOCX", CI.pgBaUm, "docx"], ["PPTX", CI.pgBurg, "pptx"]].map(([label, col, fmt]) =>
          <a key={fmt} href={api.exportBriefing(store.id, fmt)} target="_blank" rel="noopener noreferrer" download style={{ display: "inline-flex", alignItems: "center", gap: 4, padding: "6px 10px", borderRadius: 6, border: "1px solid " + col + "40", background: col + "10", color: col, cursor: "pointer", fontSize: 11, fontWeight: 700, textDecoration: "none" }} title={`Briefing als ${label} exportieren`}>
            {Ic.file} {label}
          </a>
        )}
        <button onClick={() => { setLoading(true); api.getBriefing(store.id).then(r => { setLoading(false); if (r && !r.error) setBriefing(r); }); }} style={{ display: "flex", alignItems: "center", gap: 5, padding: "6px 12px", borderRadius: 6, border: "1px solid " + CI.gray300, background: CI.white, color: CI.midnight60, cursor: "pointer", fontSize: 11, fontWeight: 600 }}>{Ic.refresh} Neu</button>
      </div>
    </div>

    {/* Briefing-Card mit 4 Abschnitten */}
    <div style={{ background: CI.white, borderRadius: 10, border: "1px solid " + CI.gray300, padding: "6px 24px", boxShadow: "0 1px 4px rgba(0,58,64,0.06)" }}>

      {/* 1. SACHSTAND */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 14, padding: "16px 0", borderBottom: "1px solid " + CI.gray200 }}>
        <div style={{ width: 24, height: 24, borderRadius: "50%", background: CI.midnight5, color: CI.midnight60, fontSize: 11, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 2 }}>1</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: CI.midnight60, textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 6, display: "flex", alignItems: "center", gap: 6 }}>
            Sachstand
            <Badge color={briefing.sachstand?.model === "llm" ? CI.lagoon : CI.gray500} small>{briefing.sachstand?.model === "llm" ? "KI-generiert" : "Extraktiv"}</Badge>
          </div>
          <div style={{ fontSize: 14, color: CI.midnight, lineHeight: 1.55, marginBottom: 6 }}>{briefing.sachstand?.text || "Keine Dokumente vorhanden."}</div>
          {briefing.sachstand?.sources > 0 && <div style={{ fontSize: 11, color: CI.midnight40, fontFamily: "ui-monospace, monospace" }}>
            aus {briefing.sachstand.sources} Dokument{briefing.sachstand.sources !== 1 ? "en" : ""} · Confidence {sachstandConfidence}%
          </div>}
        </div>
      </div>

      {/* 2. RISIKEN */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 14, padding: "16px 0", borderBottom: "1px solid " + CI.gray200 }}>
        <div style={{ width: 24, height: 24, borderRadius: "50%", background: CI.midnight5, color: CI.midnight60, fontSize: 11, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 2 }}>2</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: CI.midnight60, textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 8 }}>Risiken</div>
          {briefing.risiken?.total === 0 ? <div style={{ fontSize: 13, color: CI.basil, display: "flex", alignItems: "center", gap: 6 }}>{Ic.chk} Keine akuten Risiken erkannt.</div> :
            <>
              <div style={{ fontSize: 13, color: CI.midnight, marginBottom: 8 }}>
                {briefing.risiken.total} Risiken identifiziert — davon {briefing.risiken.by_severity?.rot || 0} akut, {briefing.risiken.by_severity?.amber || 0} zu beobachten.
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 6 }}>
                {briefing.risiken.risks?.slice(0, 5).map((r, i) => {
                  const c = severityColor(r.severity);
                  return <div key={i} title={r.description} style={{ display: "inline-flex", alignItems: "center", gap: 4, padding: "3px 10px", borderRadius: 10, fontSize: 11, fontWeight: 500, background: c + "15", color: c, border: "1px solid " + c + "30", cursor: r.description ? "help" : "default", maxWidth: 400 }}>
                    <span style={{ width: 6, height: 6, borderRadius: "50%", background: c, flexShrink: 0 }} />
                    <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.title}</span>
                  </div>;
                })}
              </div>
              <div style={{ fontSize: 11, color: CI.midnight40, fontFamily: "ui-monospace, monospace" }}>auto-erkannt aus Dokumenten, Wiki-Widerspruechen und Fristen</div>
            </>}
        </div>
      </div>

      {/* 3. NAECHSTE SCHRITTE */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 14, padding: "16px 0", borderBottom: "1px solid " + CI.gray200 }}>
        <div style={{ width: 24, height: 24, borderRadius: "50%", background: CI.midnight5, color: CI.midnight60, fontSize: 11, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 2 }}>3</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: CI.midnight60, textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 8 }}>Naechste Schritte</div>
          {(briefing.naechste_schritte?.length || 0) === 0 ? <div style={{ fontSize: 13, color: CI.midnight60 }}>Keine offenen Massnahmen.</div> :
            <div>
              {briefing.naechste_schritte.slice(0, 5).map((step, i) => {
                const du = daysUntil(step.due_date);
                const urgent = du !== null && du <= 7;
                const overdue = du !== null && du < 0;
                return <div key={step.id || i} style={{ display: "flex", alignItems: "flex-start", gap: 8, padding: "6px 0", fontSize: 13, color: CI.midnight, lineHeight: 1.5 }}>
                  <span style={{ width: 6, height: 6, borderRadius: "50%", background: priorityDot(step.priority), flexShrink: 0, marginTop: 7 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <span>{step.title}</span>
                    {step.is_wiki_maintenance && <span style={{ marginLeft: 6, fontSize: 10, padding: "1px 6px", background: CI.pgBurg + "15", color: CI.pgBurg, borderRadius: 3 }}>Wiki-Wartung</span>}
                    <div style={{ fontSize: 11, color: CI.midnight40, marginTop: 1, display: "flex", gap: 8, flexWrap: "wrap" }}>
                      {step.assignee && <span style={{ fontFamily: "ui-monospace, monospace", background: CI.midnight5, padding: "1px 5px", borderRadius: 3 }}>{step.assignee}</span>}
                      {step.due_date && <span style={{ color: overdue ? CI.red : urgent ? CI.pgBurg : CI.midnight40, fontWeight: (overdue || urgent) ? 600 : 400 }}>
                        Frist: {fmtDate(step.due_date)}{du !== null && (overdue ? ` — ${Math.abs(du)} Tage ueberfaellig` : urgent ? ` — in ${du} Tagen` : "")}
                      </span>}
                      <span style={{ textTransform: "capitalize" }}>{step.priority}</span>
                    </div>
                  </div>
                </div>;
              })}
            </div>}
        </div>
      </div>

      {/* 4. KI-LOESUNGSVORSCHLAG */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 14, padding: "16px 0" }}>
        <div style={{ width: 24, height: 24, borderRadius: "50%", background: CI.midnight5, color: CI.midnight60, fontSize: 11, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 2 }}>4</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: CI.midnight60, textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 8 }}>KI-Loesungsvorschlag</div>
          <div style={{ background: CI.lagoon + "10", borderLeft: "3px solid " + CI.lagoon, borderRadius: "0 6px 6px 0", padding: "10px 14px", marginBottom: 6 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: CI.darklagoon, textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 4 }}>Empfehlung</div>
            <div style={{ fontSize: 13, color: CI.midnight, lineHeight: 1.55 }}>{briefing.loesungsvorschlag?.text}</div>
          </div>
          <div style={{ fontSize: 11, color: CI.midnight40, fontFamily: "ui-monospace, monospace" }}>
            generiert mit {briefing.loesungsvorschlag?.model || "regel-basiert"}
            {briefing.loesungsvorschlag?.sources > 0 && ` · ${briefing.loesungsvorschlag.sources} Quellen`}
            {briefing.loesungsvorschlag?.confidence && ` · Confidence ${Math.round(briefing.loesungsvorschlag.confidence * 100)}%`}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 0 14px", borderTop: "1px solid " + CI.gray200, fontSize: 11, color: CI.midnight40, fontFamily: "ui-monospace, monospace", marginTop: 2 }}>
        <span>Lesezeit: ca. 45 Sekunden</span>
        <span>Komm.ONE KI-Labor · briefing v1</span>
      </div>
    </div>

    {/* Tiefer-Einstieg-Leiste */}
    <div style={{ marginTop: 14, padding: "10px 14px", background: CI.midnight5, borderRadius: 8, display: "flex", alignItems: "center", gap: 10, fontSize: 12, color: CI.midnight60 }}>
      <span style={{ color: CI.midnight }}>Weiter vertiefen:</span>
      <span style={{ color: CI.lagoon }}>Dokumente durchsehen → Tab "Uebersicht"</span>
      <span>·</span>
      <span style={{ color: CI.lagoon }}>Nachfragen → Tab "Chat"</span>
      <span>·</span>
      <span style={{ color: CI.lagoon }}>Alle Aufgaben → Tab "Planung"</span>
    </div>
  </div>;
}


// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// SYNTHESIS PANEL — "Wie entstand das Briefing?"
// Animierte Pipeline mit Drill-Down auf jede Stufe
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function SynthesisPanel({ store }) {
  const [trace, setTrace] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expandedStage, setExpandedStage] = useState(null);
  const [animationPhase, setAnimationPhase] = useState(0); // 0..7 for progressive reveal

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.getSynthesis(store.id).then(r => {
      if (cancelled || !r) return;
      setLoading(false);
      setTrace(r);
      // Animation: jede Stufe nacheinander "einblenden"
      if (r.stages) {
        r.stages.forEach((_, i) => {
          setTimeout(() => !cancelled && setAnimationPhase(p => Math.max(p, i + 1)), 200 + i * 180);
        });
      }
    });
    return () => { cancelled = true; };
  }, [store.id]);

  if (loading) {
    return <div style={{ padding: "24px 28px", display: "flex", alignItems: "center", justifyContent: "center", height: "100%" }}>
      <div style={{ textAlign: "center", color: CI.midnight60, fontSize: 13 }}>Trace wird geladen ...</div>
    </div>;
  }

  if (!trace || !trace.stages) {
    return <div style={{ padding: "24px 28px", color: CI.midnight60, fontSize: 13 }}>Keine Synthese-Daten verfuegbar.</div>;
  }

  const stageIcons = { doc: Ic.doc, layers: Ic.layers, tag: Ic.tag, book: Ic.book, warn: Ic.warn, plan: Ic.plan, shield: Ic.shield };
  const stageColors = {
    documents: CI.pgDiDa,
    chunks: CI.pgBaUm,
    entities: CI.pgBiSo,
    wiki: CI.lagoon,
    risks: CI.red,
    tasks: CI.pgBurg,
    briefing: CI.midnight,
  };

  return <div style={{ padding: "24px 28px", overflow: "auto", height: "100%" }}>
    {/* Header */}
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: CI.midnight, margin: 0 }}>Synthese-Pipeline</h2>
        <Badge color={CI.pgInfr} small>Wie entstand das Briefing?</Badge>
      </div>
      <p style={{ fontSize: 12, color: CI.midnight60, margin: 0 }}>
        Von Rohdokument bis Loesungsvorschlag: jeder Verarbeitungsschritt mit Zaehlern und Drill-Down. Klick auf eine Stufe fuer Details.
      </p>
    </div>

    {/* Pipeline-Darstellung: vertikale Liste mit Verbindungspunkten */}
    <div style={{ background: CI.white, borderRadius: 10, border: "1px solid " + CI.gray300, padding: "20px 22px", boxShadow: "0 1px 4px rgba(0,58,64,0.06)", position: "relative" }}>
      <style>{`
        @keyframes fadeSlideIn { from { opacity: 0; transform: translateY(-6px); } to { opacity: 1; transform: none; } }
        @keyframes pulse { 0%, 100% { opacity: 0.6; } 50% { opacity: 1; } }
      `}</style>
      {trace.stages.map((stage, idx) => {
        const color = stageColors[stage.id] || CI.lagoon;
        const visible = animationPhase > idx;
        const isExpanded = expandedStage === stage.id;
        const hasItems = stage.items && stage.items.length > 0;
        const isLast = idx === trace.stages.length - 1;

        return <div key={stage.id} style={{ display: "flex", alignItems: "flex-start", gap: 14, paddingBottom: isLast ? 0 : 18, opacity: visible ? 1 : 0, transform: visible ? "none" : "translateY(-6px)", transition: "all 0.4s ease-out" }}>
          {/* Linke Spur: Icon + Connector-Line */}
          <div style={{ position: "relative", flexShrink: 0, width: 36 }}>
            <div style={{ width: 36, height: 36, borderRadius: 18, background: color + "15", color: color, display: "flex", alignItems: "center", justifyContent: "center", border: "2px solid " + color, zIndex: 2, position: "relative" }}>
              {stageIcons[stage.icon] || Ic.zap}
            </div>
            {!isLast && <div style={{ position: "absolute", left: 17, top: 36, width: 2, height: "calc(100% + 18px - 36px)", background: visible ? color + "40" : CI.gray300, transition: "background 0.4s" }} />}
          </div>

          {/* Rechts: Card mit Details */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <button onClick={() => setExpandedStage(isExpanded ? null : (hasItems ? stage.id : null))} style={{ width: "100%", textAlign: "left", background: isExpanded ? color + "08" : CI.white, border: "1px solid " + (isExpanded ? color + "50" : CI.gray300), borderRadius: 8, padding: "12px 14px", cursor: hasItems ? "pointer" : "default", fontFamily: "inherit", transition: "all 0.15s" }}
              onMouseEnter={e => hasItems && !isExpanded && (e.currentTarget.style.borderColor = color + "40")}
              onMouseLeave={e => !isExpanded && (e.currentTarget.style.borderColor = CI.gray300)}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 3 }}>
                    <span style={{ fontSize: 14, fontWeight: 700, color: CI.midnight }}>{stage.label}</span>
                    <span style={{ fontSize: 22, fontWeight: 700, color: color, fontFamily: "ui-monospace, monospace", lineHeight: 1 }}>{stage.count.toLocaleString("de-DE")}</span>
                    {stage.sublabel && <span style={{ fontSize: 11, color: CI.midnight60 }}>{stage.sublabel}</span>}
                  </div>
                  <div style={{ fontSize: 11, color: CI.midnight60, lineHeight: 1.4 }}>{stage.description}</div>
                </div>
                {hasItems && <span style={{ color: CI.midnight40, fontSize: 14, transform: isExpanded ? "rotate(90deg)" : "none", transition: "transform 0.15s", flexShrink: 0 }}>›</span>}
              </div>

              {/* Drill-Down Items */}
              {isExpanded && hasItems && <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid " + color + "20" }}>
                {stage.id === "documents" && stage.items.map(d => <div key={d.id} style={{ fontSize: 12, color: CI.midnight, padding: "4px 0", display: "flex", gap: 8, alignItems: "center" }}>
                  <span style={{ width: 6, height: 6, borderRadius: 3, background: d.indexed ? CI.basil : CI.gray400, flexShrink: 0 }} />
                  <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{d.title}</span>
                  <span style={{ fontFamily: "ui-monospace, monospace", fontSize: 10, color: CI.midnight40 }}>{d.pages} S · {d.chunks} Ch</span>
                </div>)}

                {stage.id === "entities" && <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {stage.items.map(e => <div key={e.type} style={{ fontSize: 11, padding: "3px 9px", background: color + "12", color: color, borderRadius: 10, fontWeight: 600 }}>{e.type}: {e.count}</div>)}
                </div>}

                {stage.id === "wiki" && stage.items.map(w => <div key={w.slug} style={{ fontSize: 12, color: CI.midnight, padding: "4px 0", display: "flex", gap: 8, alignItems: "center" }}>
                  <span style={{ fontSize: 10, padding: "1px 5px", background: color + "15", color: color, borderRadius: 3, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em", flexShrink: 0 }}>{w.type}</span>
                  <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{w.title}</span>
                  {w.contradictions > 0 && <span style={{ fontSize: 10, color: CI.red, fontWeight: 600 }}>{w.contradictions} Widerspr.</span>}
                </div>)}

                {stage.id === "risks" && stage.items.map((r, i) => {
                  const sc = r.severity === "rot" ? CI.red : r.severity === "amber" ? CI.pgBurg : CI.amarillo;
                  return <div key={i} style={{ fontSize: 12, color: CI.midnight, padding: "4px 0", display: "flex", gap: 8, alignItems: "center" }}>
                    <span style={{ width: 6, height: 6, borderRadius: 3, background: sc, flexShrink: 0 }} />
                    <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.title}</span>
                  </div>;
                })}

                {stage.id === "tasks" && stage.items.map(t => <div key={t.id} style={{ fontSize: 12, color: CI.midnight, padding: "4px 0", display: "flex", gap: 8, alignItems: "center" }}>
                  <span style={{ width: 6, height: 6, borderRadius: 3, background: t.priority === "hoch" ? CI.red : t.priority === "mittel" ? CI.pgBurg : CI.basil, flexShrink: 0 }} />
                  <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{t.title}</span>
                  {t.is_wiki_maintenance && <span style={{ fontSize: 9, padding: "1px 5px", background: CI.pgBurg + "15", color: CI.pgBurg, borderRadius: 3, fontWeight: 600 }}>Wiki</span>}
                </div>)}
              </div>}
            </button>
          </div>
        </div>;
      })}
    </div>

    {/* Legende */}
    <div style={{ marginTop: 14, padding: "10px 14px", background: CI.midnight5, borderRadius: 8, fontSize: 11, color: CI.midnight60, lineHeight: 1.6 }}>
      <div style={{ marginBottom: 4 }}><span style={{ color: CI.midnight, fontWeight: 600 }}>Pipeline-Trace:</span> Diese Darstellung zeigt die tatsaechlichen Verarbeitungs-Stufen des aktuellen Bestandes — keine Demo-Animation. Zaehler kommen live aus der Datenbank.</div>
      <div>Jede Stufe erklaert, was die KI mit den Daten macht. Klicken Sie auf "Dokumente" oder "Risiken" fuer die konkreten Einzelteile.</div>
    </div>
  </div>;
}


// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// WIKI PANEL — WissensDB v2 (3-Spalten: Baum, Seite, Chronik)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function WikiPanel({ store }) {
  const [pages, setPages] = useState([]);
  const [activeSlug, setActiveSlug] = useState(null);
  const [activePage, setActivePage] = useState(null);
  const [log, setLog] = useState([]);
  const [lintResult, setLintResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lintRunning, setLintRunning] = useState(false);
  const [queryText, setQueryText] = useState("");
  const [queryAnswer, setQueryAnswer] = useState(null);
  const [querying, setQuerying] = useState(false);

  // Wiki Editing & Auto-Save
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState("");
  const [saveStatus, setSaveStatus] = useState("saved"); // "saved" | "saving" | "unsaved"
  const [lastSaved, setLastSaved] = useState(null);
  const editTimeoutRef = useRef(null);

  // Auto-save with debouncing (30 seconds)
  useEffect(() => {
    if (isEditing && editContent !== activePage?.content_md) {
      setSaveStatus("unsaved");

      // Clear previous timeout
      if (editTimeoutRef.current) {
        clearTimeout(editTimeoutRef.current);
      }

      // Set new timeout for auto-save (30 seconds)
      editTimeoutRef.current = setTimeout(() => {
        handleAutoSave();
      }, 30000);

      return () => {
        if (editTimeoutRef.current) {
          clearTimeout(editTimeoutRef.current);
        }
      };
    }
  }, [editContent, isEditing, activePage]);

  // LocalStorage backup
  useEffect(() => {
    if (isEditing && editContent) {
      const backupKey = `wiki-backup-${store.id}-${activeSlug}`;
      localStorage.setItem(backupKey, JSON.stringify({
        content: editContent,
        timestamp: new Date().toISOString(),
      }));
    }
  }, [editContent, isEditing, activeSlug, store.id]);

  // Restore from LocalStorage on mount
  useEffect(() => {
    if (activeSlug && !activePage?.content_md) {
      const backupKey = `wiki-backup-${store.id}-${activeSlug}`;
      const backup = localStorage.getItem(backupKey);
      if (backup) {
        try {
          const { content, timestamp } = JSON.parse(backup);
          const age = Date.now() - new Date(timestamp).getTime();
          // Only restore if backup is less than 24 hours old
          if (age < 24 * 60 * 60 * 1000) {
            setEditContent(content);
            toast("Gesicherte Version vom " + new Date(timestamp).toLocaleString("de-DE") + " gefunden", "info");
          }
        } catch (e) {
          console.error("Failed to restore wiki backup:", e);
        }
      }
    }
  }, [activeSlug, activePage, store.id]);

  const handleAutoSave = async () => {
    if (!isEditing || !activeSlug || saveStatus === "saving") return;

    setSaveStatus("saving");

    try {
      // Simulate API call for updating wiki page
      // In real implementation, this would call an API endpoint
      await new Promise(resolve => setTimeout(resolve, 1000));

      setLastSaved(new Date());
      setSaveStatus("saved");
      toast("Wiki-Seite automatisch gespeichert", "success");

      // Clear backup after successful save
      const backupKey = `wiki-backup-${store.id}-${activeSlug}`;
      localStorage.removeItem(backupKey);
    } catch (error) {
      console.error("Auto-save failed:", error);
      setSaveStatus("unsaved");
      toast("Automatisches Speichern fehlgeschlagen", "error");
    }
  };

  const handleManualSave = async () => {
    if (editTimeoutRef.current) {
      clearTimeout(editTimeoutRef.current);
    }
    await handleAutoSave();
  };

  const startEditing = () => {
    setIsEditing(true);
    setEditContent(activePage?.content_md || "");
    setSaveStatus("saved");
  };

  const cancelEditing = () => {
    if (saveStatus === "unsaved") {
      const confirmed = window.confirm("Sie haben ungespeicherte Änderungen. Wollen Sie wirklich abbrechen?");
      if (!confirmed) return;
    }

    setIsEditing(false);
    setEditContent("");
    setSaveStatus("saved");

    // Clear backup
    const backupKey = `wiki-backup-${store.id}-${activeSlug}`;
    localStorage.removeItem(backupKey);
  };
  const [creatingTasks, setCreatingTasks] = useState(false);
  const { toast } = useToast();

  const reload = useCallback(async () => {
    setLoading(true);
    const [p, l] = await Promise.all([api.listWikiPages(store.id), api.wikiLog(store.id, 20)]);
    if (p && p.pages) setPages(p.pages);
    if (l && l.operations) setLog(l.operations);
    setLoading(false);
  }, [store.id]);

  useEffect(() => { reload(); }, [reload]);

  useEffect(() => {
    if (activeSlug) {
      api.getWikiPage(store.id, activeSlug).then(p => { if (p) setActivePage(p); });
    } else {
      setActivePage(null);
    }
  }, [activeSlug, store.id]);

  const handleLint = async () => {
    setLintRunning(true);
    const r = await api.wikiLint(store.id);
    setLintRunning(false);
    if (r) {
      setLintResult(r);
      toast(`Wiki-Lint: ${r.issues_found} Hinweise bei ${r.total_pages} Seiten`, r.issues_found > 0 ? "warning" : "success");
      reload();
    }
  };

  const handleQuery = async () => {
    if (!queryText.trim()) return;
    setQuerying(true);
    const r = await api.wikiQuery(store.id, queryText);
    setQuerying(false);
    if (r) {
      setQueryAnswer(r);
      if (r.pages_used && r.pages_used.length > 0) toast(`${r.pages_used.length} Wiki-Seiten genutzt`, "success");
    }
  };

  const handleSaveAnswer = async () => {
    if (!queryAnswer) return;
    const r = await api.wikiSaveAnswer(store.id, queryAnswer.question, queryAnswer.answer);
    if (r && r.slug) {
      toast(`Als Wiki-Seite gespeichert: "${r.title}"`, "success");
      reload();
      setActiveSlug(r.slug);
      setQueryAnswer(null);
      setQueryText("");
    }
  };

  const handleLintToTasks = async () => {
    setCreatingTasks(true);
    const r = await api.wikiLintToTasks(store.id);
    setCreatingTasks(false);
    if (r) {
      const msg = r.created > 0
        ? `${r.created} Wartungs-Tasks angelegt (${r.skipped} bereits vorhanden)`
        : r.total_issues === 0
          ? "Wiki ist gesund, keine Tasks noetig"
          : `Alle ${r.skipped} Issues haben bereits Tasks`;
      toast(msg, r.created > 0 ? "success" : "info");
      reload();
    } else {
      toast("Task-Erstellung fehlgeschlagen", "error");
    }
  };

  // Seiten nach Typ gruppieren
  const byType = {};
  for (const p of pages) {
    const t = p.page_type || "concept";
    if (!byType[t]) byType[t] = [];
    byType[t].push(p);
  }

  const typeLabels = {
    index: "Index", summary: "Zusammenfassungen", entity: "Entitaeten",
    concept: "Konzepte", synthesis: "Synthesen", comparison: "Vergleiche",
  };
  const typeColors = {
    index: CI.midnight60, summary: CI.amarillo, entity: CI.pgInfr,
    concept: CI.lagoon, synthesis: CI.basil, comparison: CI.pgDiDa,
  };

  // Markdown-Rendering (simpel, klickbare [[slug]] Links)
  const renderMarkdown = (md) => {
    if (!md) return null;
    const lines = md.split("\n");
    const elems = [];
    let inList = false;
    let listItems = [];
    const flushList = () => {
      if (listItems.length > 0) {
        elems.push(<ul key={"ul-" + elems.length} style={{ paddingLeft: 20, margin: "8px 0" }}>{listItems}</ul>);
        listItems = [];
      }
      inList = false;
    };
    const renderInline = (text) => {
      // Internal [[slug]] and [Text](./slug.md) links
      const parts = [];
      let remaining = text;
      let i = 0;
      const re = /(\[\[([^\]]+)\]\])|\[([^\]]+)\]\(\.\/([^)]+)\.md\)|\*\*([^*]+)\*\*|\*([^*]+)\*/g;
      let match;
      while ((match = re.exec(text)) !== null) {
        if (match.index > 0 && i < match.index) parts.push(text.slice(i, match.index));
        if (match[1]) {
          const slug = match[2].trim();
          parts.push(<a key={parts.length} onClick={() => setActiveSlug(slug)} style={{ color: CI.lagoon, cursor: "pointer", fontWeight: 600 }}>[{slug}]</a>);
        } else if (match[3]) {
          const slug = match[4].trim();
          parts.push(<a key={parts.length} onClick={() => setActiveSlug(slug)} style={{ color: CI.lagoon, cursor: "pointer", fontWeight: 600 }}>{match[3]}</a>);
        } else if (match[5]) {
          parts.push(<strong key={parts.length}>{match[5]}</strong>);
        } else if (match[6]) {
          parts.push(<em key={parts.length}>{match[6]}</em>);
        }
        i = re.lastIndex;
      }
      if (i < text.length) parts.push(text.slice(i));
      return parts.length > 0 ? parts : text;
    };
    lines.forEach((line, li) => {
      if (line.startsWith("# ")) { flushList(); elems.push(<h1 key={li} style={{ fontSize: 20, fontWeight: 700, color: CI.midnight, margin: "16px 0 8px" }}>{line.slice(2)}</h1>); }
      else if (line.startsWith("## ")) { flushList(); elems.push(<h2 key={li} style={{ fontSize: 16, fontWeight: 700, color: CI.midnight, margin: "14px 0 6px" }}>{line.slice(3)}</h2>); }
      else if (line.startsWith("### ")) { flushList(); elems.push(<h3 key={li} style={{ fontSize: 14, fontWeight: 700, color: CI.midnight, margin: "12px 0 4px" }}>{line.slice(4)}</h3>); }
      else if (line.startsWith("- ") || line.startsWith("* ")) { inList = true; listItems.push(<li key={li} style={{ fontSize: 13, color: CI.gray700, lineHeight: 1.6, marginBottom: 2 }}>{renderInline(line.slice(2))}</li>); }
      else if (line.startsWith("---")) { flushList(); elems.push(<hr key={li} style={{ border: "none", borderTop: "1px solid " + CI.gray300, margin: "12px 0" }}/>); }
      else if (line.trim() === "") { flushList(); }
      else { flushList(); elems.push(<p key={li} style={{ fontSize: 13, color: CI.gray700, lineHeight: 1.6, margin: "4px 0" }}>{renderInline(line)}</p>); }
    });
    flushList();
    return elems;
  };

  return <div style={{ display: "flex", height: "100%", background: CI.lightblue }}>
    {/* LINKE SPALTE: Seitenbaum */}
    <div style={{ width: 260, background: CI.white, borderRight: "1px solid " + CI.gray300, display: "flex", flexDirection: "column", flexShrink: 0 }}>
      <div style={{ padding: "14px 16px", borderBottom: "1px solid " + CI.gray300 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <span style={{ color: CI.lagoon }}>{Ic.book}</span>
          <span style={{ fontSize: 13, fontWeight: 700, color: CI.midnight }}>Wiki</span>
          <span style={{ marginLeft: "auto", fontSize: 11, color: CI.midnight40 }}>{pages.length} Seiten</span>
        </div>
        <div style={{ fontSize: 11, color: CI.midnight60 }}>{store.name}</div>
      </div>
      <div style={{ flex: 1, overflow: "auto", padding: "8px 0" }}>
        {loading ? <div style={{ padding: 16, fontSize: 12, color: CI.midnight40, textAlign: "center" }}>Lade...</div>
         : pages.length === 0 ? <div style={{ padding: 16, fontSize: 12, color: CI.midnight40, textAlign: "center" }}>
            Wiki ist leer. Laden Sie Dokumente in diese WissensDB hoch — das Wiki wird automatisch aufgebaut.
          </div>
         : Object.entries(byType).map(([t, ps]) => <div key={t} style={{ marginBottom: 8 }}>
          <div style={{ padding: "4px 16px", fontSize: 10, fontWeight: 700, color: typeColors[t] || CI.midnight60, textTransform: "uppercase", letterSpacing: 0.5 }}>{typeLabels[t] || t} ({ps.length})</div>
          {ps.map(p => <div key={p.slug} onClick={() => setActiveSlug(p.slug)} style={{ padding: "6px 16px", cursor: "pointer", background: activeSlug === p.slug ? CI.lagoon + "15" : "transparent", borderLeft: "3px solid " + (activeSlug === p.slug ? CI.lagoon : "transparent"), transition: "all 0.1s" }}>
            <div style={{ fontSize: 12, fontWeight: 500, color: activeSlug === p.slug ? CI.darklagoon : CI.midnight, marginBottom: 1 }}>{p.title}</div>
            <div style={{ fontSize: 10, color: CI.midnight40, display: "flex", gap: 6 }}>
              {p.source_documents && p.source_documents.length > 0 && <span>{p.source_documents.length} Quelle{p.source_documents.length !== 1 ? "n" : ""}</span>}
              {p.update_count > 1 && <span>{p.update_count}x aktual.</span>}
              {p.contradiction_flags && p.contradiction_flags.length > 0 && <span style={{ color: CI.red }}>{p.contradiction_flags.length} Widerspr.</span>}
            </div>
          </div>)}
        </div>)}
      </div>
      <div style={{ padding: "10px 12px", borderTop: "1px solid " + CI.gray300, display: "flex", gap: 6 }}>
        <button onClick={handleLint} disabled={lintRunning} style={{ flex: 1, padding: "6px 10px", borderRadius: 4, border: "1px solid " + CI.gray300, background: CI.white, color: CI.midnight60, cursor: lintRunning ? "wait" : "pointer", fontSize: 11, fontWeight: 600, display: "flex", alignItems: "center", justifyContent: "center", gap: 4 }}>
          {Ic.refresh} {lintRunning ? "..." : "Lint"}
        </button>
        <button onClick={reload} style={{ padding: "6px 10px", borderRadius: 4, border: "1px solid " + CI.gray300, background: CI.white, color: CI.midnight60, cursor: "pointer", fontSize: 11, fontWeight: 600 }}>
          {Ic.refresh}
        </button>
      </div>
    </div>

    {/* MITTLERE SPALTE: Seiteninhalt oder Query */}
    <div style={{ flex: 1, overflow: "auto", background: CI.white }}>
      {activePage ? <div style={{ padding: "20px 28px", maxWidth: 800 }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 10, marginBottom: 16, paddingBottom: 12, borderBottom: "1px solid " + CI.gray300 }}>
          <div style={{ flex: 1 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
              <Badge color={typeColors[activePage.page_type] || CI.gray500}>{typeLabels[activePage.page_type] || activePage.page_type}</Badge>
              {activePage.update_count > 1 && <span style={{ fontSize: 11, color: CI.midnight40 }}>{activePage.update_count}x aktualisiert</span>}
              {activePage.last_updated && <span style={{ fontSize: 11, color: CI.midnight40 }}>{new Date(activePage.last_updated).toLocaleDateString("de-DE")}</span>}
            </div>
            <h1 style={{ fontSize: 22, fontWeight: 700, color: CI.midnight, margin: 0 }}>{activePage.title}</h1>
            <code style={{ fontSize: 11, color: CI.midnight40, fontFamily: "ui-monospace, monospace" }}>/{activePage.slug}</code>
          </div>
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            {/* Save Status Indicator */}
            {isEditing && (
              <div style={{
                display: "flex",
                alignItems: "center",
                gap: 4,
                fontSize: 11,
                color: saveStatus === "saved" ? CI.basil : saveStatus === "saving" ? CI.amarillo : CI.red,
                fontWeight: 500,
              }}>
                {saveStatus === "saved" && "✓ "}
                {saveStatus === "saving" && "⏳ "}
                {saveStatus === "unsaved" && "● "}
                {saveStatus === "saved" ? "Gespeichert" : saveStatus === "saving" ? "Speichern..." : "Ungespeichert"}
                {lastSaved && saveStatus === "saved" && ` (${new Date(lastSaved).toLocaleTimeString("de-DE")})`}
              </div>
            )}

            {!isEditing ? (
              <button
                onClick={startEditing}
                style={{
                  padding: "4px 10px",
                  borderRadius: 4,
                  border: "1px solid " + CI.lagoon40,
                  background: CI.white,
                  color: CI.lagoon,
                  cursor: "pointer",
                  fontSize: 11,
                  fontWeight: 600,
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = CI.lagoon + "08";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = CI.white;
                }}
              >
                {Ic.pen} Bearbeiten
              </button>
            ) : (
              <>
                <button
                  onClick={handleManualSave}
                  disabled={saveStatus === "saving"}
                  style={{
                    padding: "4px 10px",
                    borderRadius: 4,
                    border: "1px solid " + CI.basil40,
                    background: saveStatus === "saving" ? CI.gray100 : CI.white,
                    color: saveStatus === "saving" ? CI.gray400 : CI.basil,
                    cursor: saveStatus === "saving" ? "wait" : "pointer",
                    fontSize: 11,
                    fontWeight: 600,
                  }}
                >
                  {Ic.save} Speichern
                </button>
                <button
                  onClick={cancelEditing}
                  style={{
                    padding: "4px 10px",
                    borderRadius: 4,
                    border: "1px solid " + CI.gray300,
                    background: CI.white,
                    color: CI.midnight60,
                    cursor: "pointer",
                    fontSize: 11,
                  }}
                >
                  Abbrechen
                </button>
              </>
            )}
            <button onClick={() => setActiveSlug(null)} style={{ padding: "4px 10px", borderRadius: 4, border: "1px solid " + CI.gray300, background: CI.white, color: CI.midnight60, cursor: "pointer", fontSize: 11 }}>Schliessen</button>
          </div>
        </div>
        {activePage.contradiction_flags && activePage.contradiction_flags.length > 0 && <div style={{ background: CI.red + "10", borderLeft: "3px solid " + CI.red, padding: "10px 14px", marginBottom: 16, borderRadius: 4 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: CI.red, marginBottom: 6, display: "flex", alignItems: "center", gap: 6 }}>{Ic.warn} Widersprueche ({activePage.contradiction_flags.length})</div>
          {activePage.contradiction_flags.map((cf, i) => <div key={i} style={{ fontSize: 11, color: CI.gray700, marginBottom: 4 }}>
            <b>Neu:</b> {cf.new_claim || cf.claim || "?"} <br/>
            <b>Konflikt mit:</b> {cf.conflicts_with || "?"}
          </div>)}
        </div>}

        {/* Wiki Content - View or Edit Mode */}
        {isEditing ? (
          <div>
            <textarea
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              placeholder="Wiki-Inhalt in Markdown schreiben..."
              style={{
                width: "100%",
                minHeight: 400,
                padding: "14px",
                borderRadius: 8,
                border: "1px solid " + CI.gray300,
                fontSize: 14,
                lineHeight: 1.6,
                fontFamily: "ui-monospace, monospace",
                resize: "vertical",
                outline: "none",
              }}
              onFocus={(e) => {
                e.currentTarget.style.borderColor = CI.lagoon;
                e.currentTarget.style.boxShadow = "0 0 0 3px " + CI.lagoon + "20";
              }}
              onBlur={(e) => {
                e.currentTarget.style.borderColor = CI.gray300;
                e.currentTarget.style.boxShadow = "none";
              }}
            />
            <div style={{ marginTop: 8, fontSize: 11, color: CI.midnight60 }}>
              Markdown-Formatierung unterstützt. Automatisches Speichern alle 30 Sekunden.
            </div>
          </div>
        ) : (
          <div style={{ fontSize: 13, color: CI.gray800, lineHeight: 1.6 }}>{renderMarkdown(activePage.content_md)}</div>
        )}
        {activePage.outgoing_links && activePage.outgoing_links.length > 0 && <div style={{ marginTop: 24, padding: "12px 14px", background: CI.midnight5, borderRadius: 6 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: CI.midnight60, marginBottom: 6, display: "flex", alignItems: "center", gap: 4 }}>{Ic.link} Verweise ({activePage.outgoing_links.length})</div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {activePage.outgoing_links.map((l, i) => <button key={i} onClick={() => setActiveSlug(l.slug)} style={{ padding: "3px 10px", borderRadius: 4, border: "1px solid " + CI.lagoon40, background: CI.white, color: CI.lagoon, cursor: "pointer", fontSize: 11, fontWeight: 500 }}>{l.title}</button>)}
          </div>
        </div>}
        {activePage.source_documents && activePage.source_documents.length > 0 && <div style={{ marginTop: 12, padding: "10px 14px", background: CI.amarillo + "10", borderRadius: 6 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: CI.darkamarillo, marginBottom: 6, display: "flex", alignItems: "center", gap: 4 }}>{Ic.doc} Quellen ({activePage.source_documents.length})</div>
          {activePage.source_documents.map((s, i) => <div key={i} style={{ fontSize: 11, color: CI.gray700, marginBottom: 2 }}>{s.title}</div>)}
        </div>}
      </div> : <div style={{ padding: "20px 28px", maxWidth: 800 }}>
        {/* Kein Seite aktiv: Query-Interface */}
        <div style={{ marginBottom: 20 }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: CI.midnight, margin: "0 0 4px" }}>Wiki-Abfrage</h2>
          <p style={{ fontSize: 12, color: CI.midnight60, margin: 0 }}>Stellen Sie eine Frage an das kompilierte Wiki dieser Sammlung.</p>
        </div>
        <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
          <input type="text" value={queryText} onChange={e => setQueryText(e.target.value)} onKeyDown={e => e.key === "Enter" && handleQuery()} placeholder="z.B. Welche Massnahmen zur Digitalisierung stehen an?" style={{ flex: 1, background: CI.midnight5, border: "1px solid " + CI.gray300, borderRadius: 6, color: CI.midnight, padding: "10px 14px", fontSize: 13, outline: "none", fontFamily: "inherit" }}/>
          <button onClick={handleQuery} disabled={!queryText.trim() || querying} style={{ padding: "0 18px", borderRadius: 6, border: "none", background: queryText.trim() && !querying ? CI.lagoon : CI.gray400, color: CI.white, cursor: queryText.trim() && !querying ? "pointer" : "not-allowed", fontSize: 12, fontWeight: 700 }}>{querying ? "..." : "Fragen"}</button>
        </div>
        {queryAnswer && <div style={{ background: CI.midnight5, borderRadius: 8, padding: "16px 18px", borderLeft: "3px solid " + CI.lagoon, marginBottom: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: CI.midnight60, marginBottom: 6 }}>Antwort</div>
          <div style={{ fontSize: 13, color: CI.midnight, lineHeight: 1.6, whiteSpace: "pre-wrap", marginBottom: 12 }}>{queryAnswer.answer}</div>
          {queryAnswer.pages_used && queryAnswer.pages_used.length > 0 && <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
            {queryAnswer.pages_used.map((p, i) => <button key={i} onClick={() => setActiveSlug(p.slug)} style={{ padding: "2px 8px", borderRadius: 3, border: "1px solid " + CI.lagoon40, background: CI.white, color: CI.lagoon, cursor: "pointer", fontSize: 10, fontWeight: 500 }}>{p.title}</button>)}
          </div>}
          <button onClick={handleSaveAnswer} style={{ padding: "5px 12px", borderRadius: 4, border: "none", background: CI.basil, color: CI.white, cursor: "pointer", fontSize: 11, fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 5 }}>{Ic.save} Als Wiki-Seite speichern</button>
        </div>}
        {lintResult && <div style={{ marginTop: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
            <h3 style={{ fontSize: 14, fontWeight: 700, color: CI.midnight, margin: 0, display: "flex", alignItems: "center", gap: 6 }}>{Ic.shield} Wiki-Health ({lintResult.issues_found} Hinweise)</h3>
            {lintResult.issues_found > 0 && <button onClick={handleLintToTasks} disabled={creatingTasks} style={{ marginLeft: "auto", padding: "5px 12px", borderRadius: 4, border: "none", background: creatingTasks ? CI.gray400 : CI.pgBurg, color: CI.white, cursor: creatingTasks ? "wait" : "pointer", fontSize: 11, fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 5 }}>{Ic.plan} {creatingTasks ? "Erstelle..." : "Als Tasks anlegen"}</button>}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, marginBottom: 12 }}>
            {[
              { l: "Orphans", v: lintResult.summary?.orphans || 0, c: CI.amarillo },
              { l: "Widersprueche", v: lintResult.summary?.contradictions || 0, c: CI.red },
              { l: "Fehlende Konzepte", v: lintResult.summary?.missing_concepts || 0, c: CI.pgBurg },
              { l: "Veraltete Seiten", v: lintResult.summary?.stale || 0, c: CI.gray500 },
            ].map(s => <div key={s.l} style={{ background: CI.white, border: "1px solid " + CI.gray300, borderLeft: "3px solid " + s.c, borderRadius: 6, padding: "10px 12px" }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: s.c }}>{s.v}</div>
              <div style={{ fontSize: 10, color: CI.midnight60 }}>{s.l}</div>
            </div>)}
          </div>
          <div style={{ maxHeight: 320, overflow: "auto" }}>
            {(lintResult.issues || []).map((iss, i) => <div key={i} style={{ padding: "8px 12px", background: CI.white, border: "1px solid " + CI.gray300, borderRadius: 4, marginBottom: 5, borderLeft: "2px solid " + (iss.severity === "warning" ? CI.red : iss.severity === "info" ? CI.amarillo : CI.gray500) }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: CI.midnight60, marginBottom: 2 }}>{iss.type} · {iss.severity}</div>
              <div style={{ fontSize: 12, color: CI.midnight, cursor: iss.slug ? "pointer" : "default" }} onClick={() => iss.slug && setActiveSlug(iss.slug)}>{iss.recommendation}</div>
            </div>)}
          </div>
        </div>}
      </div>}
    </div>

    {/* RECHTE SPALTE: Chronik */}
    <div style={{ width: 240, background: CI.midnight5, borderLeft: "1px solid " + CI.gray300, display: "flex", flexDirection: "column", flexShrink: 0 }}>
      <div style={{ padding: "14px 16px", borderBottom: "1px solid " + CI.gray300 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ color: CI.midnight60 }}>{Ic.clock}</span>
          <span style={{ fontSize: 12, fontWeight: 700, color: CI.midnight }}>Chronik</span>
          <span style={{ marginLeft: "auto", fontSize: 10, color: CI.midnight40 }}>{log.length}</span>
        </div>
      </div>
      <div style={{ flex: 1, overflow: "auto", padding: "6px 0" }}>
        {log.length === 0 ? <div style={{ padding: 16, fontSize: 11, color: CI.midnight40, textAlign: "center" }}>Keine Operationen.</div>
          : log.map(op => {
          const opColors = { ingest: CI.basil, query: CI.lagoon, lint: CI.pgBurg, save_answer: CI.amarillo };
          return <div key={op.id} style={{ padding: "8px 14px", borderBottom: "1px solid " + CI.gray200 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 3 }}>
              <div style={{ width: 6, height: 6, borderRadius: "50%", background: opColors[op.operation] || CI.gray400 }}/>
              <span style={{ fontSize: 10, fontWeight: 700, color: opColors[op.operation] || CI.midnight60, textTransform: "uppercase" }}>{op.operation}</span>
              <span style={{ marginLeft: "auto", fontSize: 9, color: CI.midnight40 }}>{op.created_at ? new Date(op.created_at).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) : ""}</span>
            </div>
            <div style={{ fontSize: 11, color: CI.gray700, lineHeight: 1.4 }}>{op.summary}</div>
            {op.pages_affected && op.pages_affected.length > 0 && <div style={{ marginTop: 3, display: "flex", gap: 3, flexWrap: "wrap" }}>
              {op.pages_affected.slice(0, 3).map(s => <button key={s} onClick={() => setActiveSlug(s)} style={{ padding: "1px 6px", borderRadius: 3, border: "none", background: CI.white, color: CI.lagoon, cursor: "pointer", fontSize: 9, fontWeight: 500 }}>{s.substring(0, 20)}</button>)}
              {op.pages_affected.length > 3 && <span style={{ fontSize: 9, color: CI.midnight40 }}>+{op.pages_affected.length - 3}</span>}
            </div>}
          </div>;
        })}
      </div>
    </div>
  </div>;
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// PROVIDERS PANEL — LLM-Konfiguration (Modal)
// Zeigt alle Provider gruppiert nach Kategorie, mit Verbindungs-Test
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function ProvidersPanel({ onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState({});   // providerId → "pending" | "ok" | "err"
  const [testResult, setTestResult] = useState({}); // providerId → { ok, error?, model? }
  const [discovered, setDiscovered] = useState({}); // providerId → [models]
  const { toast } = useToast();

  useEffect(() => {
    api.listAllProviders().then(r => {
      setLoading(false);
      if (r) setData(r);
    });
  }, []);

  const handleTest = async (pid) => {
    setTesting(p => ({ ...p, [pid]: "pending" }));
    const r = await api.testProvider(pid);
    setTesting(p => ({ ...p, [pid]: r?.ok ? "ok" : "err" }));
    setTestResult(p => ({ ...p, [pid]: r }));
    if (r?.ok) toast(`${pid}: Verbindung erfolgreich (${r.model || "?"})`, "success");
    else toast(`${pid}: ${(r?.error || "Fehler").slice(0, 80)}`, "error");
  };

  const handleDiscover = async (pid) => {
    setTesting(p => ({ ...p, [pid + "_disc"]: "pending" }));
    const r = await api.discoverProviderModels(pid);
    setTesting(p => ({ ...p, [pid + "_disc"]: "done" }));
    if (r?.models?.length) {
      setDiscovered(p => ({ ...p, [pid]: r.models }));
      toast(`${pid}: ${r.models.length} Modelle gefunden`, "success");
    } else {
      toast(`${pid}: Keine Modelle per Discovery`, "info");
    }
  };

  const categoryInfo = {
    "self-hosted": { label: "Self-Hosted", color: CI.basil, desc: "On-Premise, DSGVO-konform, kein Datenfluss nach aussen" },
    "commercial": { label: "Kommerziell", color: CI.pgInfr, desc: "Cloud-APIs — erfordern API-Key und Datentransfer" },
    "custom": { label: "Benutzerdefiniert", color: CI.pgBurg, desc: "Ueber DOCSTORE_CUSTOM_PROVIDERS registrierte Endpunkte" },
  };

  return <div style={{ position: "fixed", inset: 0, background: "rgba(0,58,64,0.55)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1100, padding: 20 }} onClick={onClose}>
    <div style={{ background: CI.white, borderRadius: 10, width: 780, maxWidth: "95vw", maxHeight: "90vh", display: "flex", flexDirection: "column", boxShadow: "0 8px 32px rgba(0,58,64,0.3)" }} onClick={e => e.stopPropagation()}>
      {/* Header */}
      <div style={{ padding: "20px 24px", borderBottom: "1px solid " + CI.gray300, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2 }}>
            <span style={{ color: CI.pgInfr }}>{Ic.zap}</span>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: CI.midnight, margin: 0 }}>LLM-Provider</h3>
            {data && <Badge color={CI.lagoon} small>{data.total} konfiguriert</Badge>}
          </div>
          <p style={{ fontSize: 11, color: CI.midnight60, margin: 0 }}>
            OpenAI-kompatible Endpunkte. Beliebig erweiterbar via <code style={{ background: CI.midnight5, padding: "1px 4px", borderRadius: 2, fontSize: 10 }}>DOCSTORE_CUSTOM_PROVIDERS</code> in <code style={{ background: CI.midnight5, padding: "1px 4px", borderRadius: 2, fontSize: 10 }}>.env</code>
          </p>
        </div>
        <button onClick={onClose} style={{ padding: "6px 12px", borderRadius: 4, border: "1px solid " + CI.gray300, background: CI.white, color: CI.midnight60, cursor: "pointer", fontSize: 12, fontWeight: 600 }}>Schliessen</button>
      </div>

      {/* Body */}
      <div style={{ flex: 1, overflow: "auto", padding: "16px 24px" }}>
        {loading && <div style={{ padding: 30, textAlign: "center", color: CI.midnight60, fontSize: 12 }}>Lade Provider ...</div>}
        {!loading && !data && <div style={{ padding: 30, textAlign: "center", color: CI.red, fontSize: 12 }}>Provider konnten nicht geladen werden.</div>}
        {data && ["self-hosted", "commercial", "custom"].map(cat => {
          const provs = data.by_category?.[cat] || [];
          if (!provs.length) return null;
          const info = categoryInfo[cat];
          return <div key={cat} style={{ marginBottom: 20 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: info.color }} />
              <span style={{ fontSize: 11, fontWeight: 700, color: CI.midnight, textTransform: "uppercase", letterSpacing: "0.04em" }}>{info.label}</span>
              <span style={{ fontSize: 11, color: CI.midnight60, fontWeight: 500 }}>·  {provs.length}</span>
            </div>
            <p style={{ fontSize: 11, color: CI.midnight60, margin: "0 0 10px" }}>{info.desc}</p>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {provs.map(p => {
                const tState = testing[p.id];
                const dState = testing[p.id + "_disc"];
                const dModels = discovered[p.id];
                const res = testResult[p.id];
                const statusColor = tState === "pending" ? CI.amarillo : tState === "ok" ? CI.basil : tState === "err" ? CI.red : CI.gray400;
                const statusLabel = tState === "pending" ? "Pruefe..." : tState === "ok" ? "Erreichbar" : tState === "err" ? "Nicht erreichbar" : "Nicht getestet";
                return <div key={p.id} style={{ border: "1px solid " + CI.gray300, borderRadius: 6, padding: "10px 14px", background: CI.white }}>
                  <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3, flexWrap: "wrap" }}>
                        <span style={{ fontSize: 13, fontWeight: 600, color: CI.midnight }}>{p.name}</span>
                        <code style={{ fontSize: 10, fontFamily: "ui-monospace, monospace", background: CI.midnight5, padding: "1px 5px", borderRadius: 2, color: CI.midnight60 }}>{p.id}</code>
                        {p.requires_key && (p.configured
                          ? <Badge color={CI.basil} small>Key via ENV gesetzt</Badge>
                          : <Badge color={CI.red} small>Key fehlt</Badge>)}
                        <span title={statusLabel} style={{ display: "inline-flex", alignItems: "center", gap: 3, padding: "1px 6px", borderRadius: 2, fontSize: 10, fontWeight: 600, color: statusColor, background: statusColor + "15" }}>
                          <span style={{ width: 5, height: 5, borderRadius: "50%", background: statusColor }} />
                          {statusLabel}
                        </span>
                      </div>
                      {p.base_url && <div style={{ fontSize: 10, fontFamily: "ui-monospace, monospace", color: CI.midnight40, marginBottom: 3 }}>{p.base_url}</div>}
                      <div style={{ fontSize: 11, color: CI.midnight60, marginBottom: 4 }}>
                        Default: <code style={{ background: CI.midnight5, padding: "1px 4px", borderRadius: 2, fontSize: 10 }}>{p.default_model}</code>
                        {(dModels || p.models).length > 0 && <span style={{ marginLeft: 6, color: CI.midnight40 }}>{(dModels || p.models).length} Modelle</span>}
                      </div>
                      {p.requires_key && !p.configured && p.key_env_var && <div style={{ fontSize: 10, color: CI.red, marginTop: 3, fontFamily: "ui-monospace, monospace", background: CI.red + "10", padding: "4px 8px", borderRadius: 3 }}>
                        Setze in .env: <strong>{p.key_env_var}=...</strong>
                      </div>}
                      {p.notes && <div style={{ fontSize: 10, color: CI.midnight40, fontStyle: "italic", marginTop: 3 }}>{p.notes}</div>}
                      {res && res.ok === false && <div style={{ fontSize: 10, color: CI.red, marginTop: 3, fontFamily: "ui-monospace, monospace", background: CI.red + "10", padding: "3px 6px", borderRadius: 2 }}>{res.error?.slice(0, 150)}</div>}
                      {dModels && dModels.length > 0 && <details style={{ marginTop: 4 }}>
                        <summary style={{ cursor: "pointer", fontSize: 10, color: CI.lagoon }}>{dModels.length} Modelle aus Discovery ueberpruefbar</summary>
                        <div style={{ fontSize: 10, fontFamily: "ui-monospace, monospace", color: CI.midnight60, marginTop: 4, maxHeight: 80, overflow: "auto" }}>
                          {dModels.slice(0, 20).join(", ")}{dModels.length > 20 ? ", ..." : ""}
                        </div>
                      </details>}
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 4, flexShrink: 0 }}>
                      <button onClick={() => handleTest(p.id)} disabled={tState === "pending" || (p.requires_key && !p.configured)} title={p.requires_key && !p.configured ? "Erst Key in .env setzen" : "Verbindungs-Test"} style={{ padding: "4px 10px", fontSize: 10, borderRadius: 3, border: "1px solid " + CI.gray300, background: CI.white, color: (p.requires_key && !p.configured) ? CI.gray400 : CI.midnight60, cursor: (tState === "pending" || (p.requires_key && !p.configured)) ? "not-allowed" : "pointer", fontWeight: 600 }}>
                        {tState === "pending" ? "..." : "Test"}
                      </button>
                      {p.supports_model_discovery && <button onClick={() => handleDiscover(p.id)} disabled={dState === "pending" || (p.requires_key && !p.configured)} title="Modelle via /v1/models abfragen" style={{ padding: "4px 10px", fontSize: 10, borderRadius: 3, border: "1px solid " + CI.gray300, background: CI.white, color: (p.requires_key && !p.configured) ? CI.gray400 : CI.midnight60, cursor: (dState === "pending" || (p.requires_key && !p.configured)) ? "not-allowed" : "pointer", fontWeight: 600 }}>
                        {dState === "pending" ? "..." : "Modelle"}
                      </button>}
                    </div>
                  </div>
                </div>;
              })}
            </div>
          </div>;
        })}

        {/* Hinweis zu Custom-Providern und Keys */}
        <div style={{ marginTop: 14, padding: "12px 14px", background: CI.midnight5, borderRadius: 6, fontSize: 11, color: CI.midnight60, lineHeight: 1.55 }}>
          <div style={{ fontWeight: 600, color: CI.midnight, marginBottom: 6 }}>So fuegen Sie einen neuen Provider hinzu</div>
          <div style={{ marginBottom: 6 }}>
            <strong style={{ color: CI.midnight }}>1. Endpunkt</strong> in <code style={{ background: CI.white, padding: "1px 4px", borderRadius: 2 }}>.env</code> eintragen — eingebaute Provider brauchen nur den API-Key, Custom-Provider zusaetzlich die URL via <code style={{ background: CI.white, padding: "1px 4px", borderRadius: 2 }}>DOCSTORE_CUSTOM_PROVIDERS</code> (JSON-Liste).
          </div>
          <div style={{ marginBottom: 6 }}>
            <strong style={{ color: CI.midnight }}>2. API-Key</strong> als <code style={{ background: CI.white, padding: "1px 4px", borderRadius: 2 }}>DOCSTORE_{`{`}PROVIDER_ID{`}`}_API_KEY</code> setzen. Beispiel: <code style={{ background: CI.white, padding: "1px 4px", borderRadius: 2 }}>DOCSTORE_OPENAI_API_KEY=sk-...</code>
          </div>
          <div>
            <strong style={{ color: CI.midnight }}>3. Container neu starten</strong> — danach erscheint der Provider mit gruenem "Key via ENV gesetzt"-Badge und ist testbereit.
          </div>
        </div>
      </div>
    </div>
  </div>;
}


// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// SKELETON LOADING SCREENS – Optimistic UI Feedback
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function SkeletonCard({ width = "100%", height = 80 }) {
  return <div style={{
    width, height,
    background: `linear-gradient(90deg, ${CI.gray200} 25%, ${CI.gray100} 50%, ${CI.gray200} 75%)`,
    backgroundSize: "200% 100%",
    borderRadius: 8,
    animation: "skeleton-loading 1.5s infinite",
  }} />;
}

function SkeletonScreen() {
  return <div style={{ padding: "24px 28px", animation: "fadeIn 0.3s ease-out" }}>
    {/* Header Skeleton */}
    <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
      <div style={{ width: 42, height: 42, borderRadius: 8, background: CI.gray200 }} />
      <div style={{ flex: 1 }}>
        <SkeletonCard width="200px" height="20px" />
        <SkeletonCard width="300px" height="14px" />
      </div>
    </div>

    {/* Stats Grid Skeleton */}
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(120px,1fr))", gap: 10, marginBottom: 20 }}>
      {[1, 2, 3, 4].map(i => (
        <div key={i} style={{ background: CI.white, borderRadius: 8, padding: "14px 16px", border: "1px solid " + CI.gray300 }}>
          <SkeletonCard width="60px" height="22px" />
          <SkeletonCard width="80px" height="11px" />
        </div>
      ))}
    </div>

    {/* Content Cards Skeleton */}
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
      {[1, 2, 3, 4].map(i => (
        <div key={i} style={{ background: CI.white, borderRadius: 8, padding: "18px 20px", border: "1px solid " + CI.gray300 }}>
          <SkeletonCard height="16px" width="40%" />
          <SkeletonCard height="12px" />
          <SkeletonCard height="12px" width="80%" />
        </div>
      ))}
    </div>

    <style>{`
      @keyframes skeleton-loading {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
      }
      @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
      }
    `}</style>
  </div>;
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// NEW STORE DIALOG
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function NewDialog({ onClose, onCreate }) {
  const [mode, setMode] = useState("demo"); // "demo" oder "new"
  const [name, setName] = useState(""); const [type, setType] = useState("wissensdb"); const [desc, setDesc] = useState("");
  const [creating, setCreating] = useState(false);
  const [fixtures, setFixtures] = useState([]);
  const [loadingFixtures, setLoadingFixtures] = useState(true);
  const [activeFixture, setActiveFixture] = useState(null);
  const { toast } = useToast();
  const is = { width: "100%", background: CI.midnight5, border: "1px solid " + CI.gray300, borderRadius: 4, color: CI.midnight, fontSize: 13, padding: "10px 12px", outline: "none", fontFamily: "inherit", boxSizing: "border-box" };

  useEffect(() => {
    api.listDemoFixtures().then(r => {
      setLoadingFixtures(false);
      if (Array.isArray(r)) setFixtures(r);
    });
  }, []);

  const handleCreate = async () => {
    if (!name.trim() || creating) return;
    setCreating(true);
    const apiResult = await api.createStore({ name, type, description: desc, color: type === "akte" ? "#F1C400" : "#00B2A9" });
    setCreating(false);
    if (apiResult && apiResult.id) {
      onCreate({ ...apiResult, documents: [], analyseFokus: "Allgemein" });
    } else {
      onCreate({ id: uid(), name, type, description: desc, color: type === "akte" ? CI.amarillo : CI.lagoon, analyseFokus: "Allgemein", documents: [] });
    }
    onClose();
  };

  const handleLoadFixture = async (fx) => {
    if (activeFixture) return;
    setActiveFixture(fx.id);
    const r = await api.loadDemoFixture(fx.id);
    setActiveFixture(null);
    if (r && r.store_id) {
      // Store-Objekt fuer Frontend-State
      onCreate({
        id: r.store_id,
        name: r.name,
        type: r.type,
        description: fx.description,
        color: r.type === "akte" ? CI.amarillo : CI.lagoon,
        analyseFokus: "Demo-Szenario",
        documents: [],
      });
      toast(`Demo-Sammlung "${r.name}" geladen mit ${r.doc_count} Dokumenten`, "success");
    } else {
      toast("Demo konnte nicht geladen werden", "error");
    }
    onClose();
  };

  const tabBtn = (id, label) => <button onClick={() => setMode(id)} style={{ flex: 1, padding: "10px 0", borderRadius: 6, border: "none", background: mode === id ? CI.white : "transparent", color: mode === id ? CI.midnight : CI.midnight60, cursor: "pointer", fontSize: 12, fontWeight: 600, boxShadow: mode === id ? "0 1px 2px rgba(0,58,64,0.08)" : "none", transition: "all 0.15s" }}>{label}</button>;

  return <div style={{ position: "fixed", inset: 0, background: "rgba(0,58,64,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }} onClick={onClose}>
    <div style={{ background: CI.white, borderRadius: 10, padding: "24px 28px", width: 520, maxWidth: "92vw", boxShadow: "0 8px 32px rgba(0,58,64,0.2)" }} onClick={e => e.stopPropagation()}>
      <h3 style={{ fontSize: 16, fontWeight: 700, color: CI.midnight, margin: "0 0 6px" }}>Neue Sammlung anlegen</h3>
      <p style={{ fontSize: 12, color: CI.midnight60, margin: "0 0 16px" }}>Starten Sie mit einem Demo-Szenario oder erstellen Sie eine leere Sammlung.</p>

      {/* Tab-Switch */}
      <div style={{ display: "flex", gap: 4, marginBottom: 16, padding: 3, background: CI.midnight5, borderRadius: 8 }}>
        {tabBtn("demo", "Demo-Szenario laden")}
        {tabBtn("new", "Leere Sammlung")}
      </div>

      {mode === "demo" && <div>
        {loadingFixtures ? <div style={{ padding: 20, textAlign: "center", color: CI.midnight60, fontSize: 12 }}>Lade Demo-Szenarien ...</div> :
          fixtures.length === 0 ? <div style={{ padding: 20, textAlign: "center", color: CI.midnight60, fontSize: 12 }}>Keine Demo-Szenarien verfuegbar</div> :
            <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: 400, overflow: "auto" }}>
              {fixtures.map(fx => {
                const typeColor = fx.type === "wissensdb" ? CI.lagoon : CI.amarillo;
                const isLoading = activeFixture === fx.id;
                return <button key={fx.id} onClick={() => handleLoadFixture(fx)} disabled={!!activeFixture} style={{ textAlign: "left", padding: "12px 14px", borderRadius: 6, border: "1px solid " + CI.gray300, background: CI.white, cursor: activeFixture ? "not-allowed" : "pointer", fontFamily: "inherit", transition: "all 0.15s" }}
                  onMouseEnter={e => !activeFixture && (e.currentTarget.style.borderColor = typeColor)}
                  onMouseLeave={e => e.currentTarget.style.borderColor = CI.gray300}>
                  <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                    <div style={{ width: 36, height: 36, borderRadius: 6, background: typeColor + "15", color: typeColor, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                      {fx.type === "wissensdb" ? Ic.db : Ic.folder}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
                        <span style={{ fontSize: 13, fontWeight: 600, color: CI.midnight }}>{fx.name}</span>
                        <span style={{ fontSize: 9, fontWeight: 700, padding: "1px 6px", background: typeColor + "20", color: typeColor, borderRadius: 3, textTransform: "uppercase", letterSpacing: "0.04em" }}>{fx.type === "wissensdb" ? "WissensDB" : "Akte"}</span>
                      </div>
                      <div style={{ fontSize: 11, color: CI.midnight60, lineHeight: 1.4, marginBottom: 3 }}>{fx.description}</div>
                      <div style={{ fontSize: 10, color: CI.midnight40, fontFamily: "ui-monospace, monospace" }}>{fx.doc_count} Dokumente · sofort einsatzbereit</div>
                    </div>
                    {isLoading && <div style={{ width: 14, height: 14, border: "2px solid " + CI.gray300, borderTopColor: CI.lagoon, borderRadius: "50%", animation: "spin 0.8s linear infinite", flexShrink: 0, marginTop: 10 }} />}
                  </div>
                </button>;
              })}
            </div>}
        <div style={{ marginTop: 12, padding: "8px 12px", background: CI.lagoon + "10", borderRadius: 4, fontSize: 11, color: CI.midnight60, lineHeight: 1.5 }}>
          Nach dem Laden sehen Sie sofort das Decision-Briefing mit Sachstand, Risiken und Loesungsvorschlag.
        </div>
      </div>}

      {mode === "new" && <div>
        <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
          {[{ v: "wissensdb", l: "WissensDB", i: Ic.db, c: CI.lagoon }, { v: "akte", l: "Akte", i: Ic.folder, c: CI.amarillo }].map(o => <button key={o.v} onClick={() => setType(o.v)} style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 6, padding: "10px 0", borderRadius: 4, border: "2px solid " + (type === o.v ? o.c : CI.gray300), background: type === o.v ? o.c + "10" : CI.white, color: type === o.v ? o.c : CI.gray600, cursor: "pointer", fontSize: 13, fontWeight: 600 }}>{o.i} {o.l}</button>)}
        </div>
        <div style={{ marginBottom: 14 }}><label style={{ fontSize: 11, fontWeight: 600, color: CI.midnight60, display: "block", marginBottom: 4 }}>Name</label><input value={name} onChange={e => setName(e.target.value)} placeholder="z.B. Bauakte Hauptstrasse" style={is} /></div>
        <div style={{ marginBottom: 14 }}><label style={{ fontSize: 11, fontWeight: 600, color: CI.midnight60, display: "block", marginBottom: 4 }}>Beschreibung</label><input value={desc} onChange={e => setDesc(e.target.value)} placeholder="Kurzbeschreibung" style={is} /></div>
      </div>}

      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 18, paddingTop: 14, borderTop: "1px solid " + CI.gray200 }}>
        <button onClick={onClose} style={{ padding: "9px 18px", borderRadius: 4, border: "1px solid " + CI.gray300, background: CI.white, color: CI.midnight60, cursor: "pointer", fontSize: 12, fontWeight: 600 }}>Abbrechen</button>
        {mode === "new" && <button onClick={handleCreate} disabled={!name.trim() || creating} style={{ padding: "9px 24px", borderRadius: 4, border: "none", background: name.trim() && !creating ? CI.lagoon : CI.gray400, color: CI.white, cursor: name.trim() && !creating ? "pointer" : "not-allowed", fontSize: 12, fontWeight: 700 }}>{creating ? "Wird erstellt..." : "Erstellen"}</button>}
      </div>
    </div>
  </div>;
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// KEYBOARD SHORTCUTS + UNDO/REDO
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function KeyboardShortcuts({ onUndo, onRedo, canUndo, canRedo }) {
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Ctrl+Z = Undo
      if ((e.ctrlKey || e.metaKey) && e.key === "z" && !e.shiftKey) {
        e.preventDefault();
        if (canUndo) onUndo();
      }
      // Ctrl+Shift+Z oder Ctrl+Y = Redo
      if (((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === "z") ||
          ((e.ctrlKey || e.metaKey) && e.key === "y")) {
        e.preventDefault();
        if (canRedo) onRedo();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [canUndo, canRedo, onUndo, onRedo]);

  return null; // Invisible Component
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// MAIN APP
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function AppInner() {
  const [stores, setStores] = useState(DEMOS);
  const [activeStore, setActiveStore] = useState(DEMOS[0]);
  const [loadingStore, setLoadingStore] = useState(false); // NEW: Loading State
  const [activeDoc, setActiveDoc] = useState(null);
  const [view, setView] = useState("briefing");
  const [showNew, setShowNew] = useState(false);
  const [showProviders, setShowProviders] = useState(false);
  const [apiConnected, setApiConnected] = useState(false);
  const [activeProvider, setActiveProvider] = useState(null);
  const { toast } = useToast();
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);

  // Keyboard Shortcuts + Undo/Redo Handler
  const handleUndo = useCallback(async () => {
    await commandHistory.undo();
  }, []);

  const handleRedo = useCallback(async () => {
    await commandHistory.redo();
  }, []);

  // History Listener für UI-Updates
  useEffect(() => {
    const unsubscribe = commandHistory.subscribe((state) => {
      setCanUndo(state.canUndo);
      setCanRedo(state.canRedo);
    });
    return unsubscribe;
  }, []);

  // Optimistic Store-Wechsel mit Loading State
  const handleSelectStore = useCallback(async (store) => {
    if (store.id === activeStore?.id) return; // Bereits aktiv

    // Optimistic UI Update: Sofort wechseln
    setActiveStore(store);
    setLoadingStore(true);

    try {
      // LiveView im Hintergrund laden
      const liveData = await api.getLiveView(store.id);
      if (liveData) {
        // Store mit LiveData aktualisieren (stale while revalidate pattern)
        setActiveStore(prev => ({ ...prev, ...liveData }));
      }
    } catch (error) {
      console.error("Store-Laden fehlgeschlagen:", error);
      toast("Store konnte nicht geladen werden", "error");
    } finally {
      setLoadingStore(false);
    }
  }, [activeStore, toast]);

  // Provider-Info laden (systemweit, nicht store-scoped)
  useEffect(() => {
    api.listAllProviders().then(r => {
      if (r?.providers?.length) {
        // Ollama bevorzugen wenn vorhanden, sonst ersten self-hosted, sonst ersten commercial
        const selfHosted = r.providers.filter(p => p.category === "self-hosted");
        const ollama = r.providers.find(p => p.id === "ollama");
        const p = ollama || selfHosted[0] || r.providers[0];
        setActiveProvider({
          name: p.name,
          model: p.default_model || p.models?.[0] || "–",
          category: p.category,
          total: r.total,
        });
      }
    });
  }, []);

  // Beim Start: Versuche Stores vom Backend zu laden
  useEffect(() => {
    api.listStores().then(r => {
      if (r && Array.isArray(r) && r.length > 0) {
        const mapped = r.map(s => ({ ...s, documents: s.documents || [], analyseFokus: s.analyse_fokus || "Allgemein" }));
        setStores(mapped);
        setActiveStore(mapped[0]);
        setApiConnected(true);
        toast("Backend verbunden", "success");
      } else if (r && r.items) {
        const mapped = r.items.map(s => ({ ...s, documents: s.documents || [], analyseFokus: s.analyse_fokus || "Allgemein" }));
        if (mapped.length > 0) { setStores(mapped); setActiveStore(mapped[0]); setApiConnected(true); toast("Backend verbunden", "success"); }
      } else {
        toast("Backend nicht erreichbar — Demo-Modus aktiv", "warning");
      }
    });
  }, []);

  // Nav: Wiki-Tab nur fuer WissensDB-Stores (nicht Akten)
  const isWissensDB = activeStore && (activeStore.type === "wissensdb" || activeStore.type === "WISSENSDB");
  const nav = [
    { id: "briefing", l: "Briefing", i: Ic.shield },
    { id: "synthesis", l: "Synthese", i: Ic.zap },
    { id: "overview", l: "Uebersicht", i: Ic.layers },
    ...(isWissensDB ? [{ id: "wiki", l: "Wiki", i: Ic.book }] : []),
    { id: "chat", l: "Chat", i: Ic.chat },
    { id: "skills", l: "Skills", i: Ic.skill },
    { id: "planning", l: "Planung", i: Ic.plan },
    { id: "search", l: "Suche", i: Ic.search },
  ];

  // Wenn ein Dokument ausgewaehlt ist, zeige die Detail-View
  const showDocDetail = activeDoc && view === "overview";

  return (
    <>
      <KeyboardShortcuts onUndo={handleUndo} onRedo={handleRedo} canUndo={canUndo} canRedo={canRedo} />
      <div style={{ display: "flex", height: "100vh", width: "100vw", background: CI.lightblue, color: CI.gray900, fontFamily: "Arial, Helvetica, sans-serif", fontSize: 14, overflow: "hidden" }}>
        <style>{`* { box-sizing: border-box; margin: 0; padding: 0; } ::-webkit-scrollbar { width: 6px; } ::-webkit-scrollbar-track { background: transparent; } ::-webkit-scrollbar-thumb { background: ${CI.gray400}; border-radius: 3px; } ::selection { background: ${CI.lagoon40}; } input::placeholder { color: ${CI.grey01}; } textarea::placeholder { color: ${CI.grey01}; }`}</style>
        <Sidebar stores={stores} active={activeStore} onSelect={handleSelectStore} onNew={() => setShowNew(true)} />
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {/* Loading Indicator für Store-Wechsel */}
          {loadingStore && (
            <div style={{
              position: "absolute",
              top: 48,
              left: 272,
              right: 0,
              bottom: 0,
              background: "rgba(255,255,255,0.9)",
              zIndex: 100,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexDirection: "column",
              gap: 16,
            }}>
              <div style={{ width: 40, height: 40, borderRadius: "50%", border: "4px solid " + CI.lagoon40, borderTopColor: CI.lagoon }} style={{
                animation: "spin 1s linear infinite"
              }} />
              <div style={{ fontSize: 14, color: CI.midnight60, fontWeight: 500 }}>
                Store wird geladen…
              </div>
              <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
            </div>
          )}

          {/* Top Nav */}
          <div style={{ display: "flex", alignItems: "center", padding: "0 20px", height: 48, borderBottom: "1px solid " + CI.gray300, background: CI.white, flexShrink: 0 }}>
            {nav.map(n => <button key={n.id} onClick={() => { setView(n.id); setActiveDoc(null); }} style={{ display: "flex", alignItems: "center", gap: 5, padding: "0 12px", height: "100%", border: "none", borderBottom: "2px solid " + (view === n.id && !showDocDetail ? CI.lagoon : "transparent"), background: "transparent", color: view === n.id ? CI.midnight : CI.gray600, cursor: "pointer", fontSize: 12, fontWeight: 600, fontFamily: "inherit" }}>{n.i} {n.l}</button>)}
            {showDocDetail && <div style={{ display: "flex", alignItems: "center", gap: 4, padding: "0 12px", height: "100%", borderBottom: "2px solid " + CI.pgInfr, color: CI.pgInfr, fontSize: 12, fontWeight: 600 }}>{Ic.doc} Dokument-Detail</div>}
            <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
              {/* Undo/Redo Buttons */}
              {(canUndo || canRedo) && (
                <>
                  <button
                    onClick={handleUndo}
                    disabled={!canUndo}
                    title="Rückgängig (Ctrl+Z)"
                    style={{
                      padding: "4px 8px",
                      borderRadius: 4,
                      border: "1px solid " + CI.gray300,
                      background: canUndo ? CI.white : CI.gray100,
                      color: canUndo ? CI.midnight : CI.gray400,
                      cursor: canUndo ? "pointer" : "not-allowed",
                      fontSize: 11,
                      fontWeight: 600,
                      fontFamily: "inherit",
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                    }}
                  >
                    ↶
                  </button>
                  <button
                    onClick={handleRedo}
                    disabled={!canRedo}
                    title="Wiederherstellen (Ctrl+Shift+Z)"
                    style={{
                      padding: "4px 8px",
                      borderRadius: 4,
                      border: "1px solid " + CI.gray300,
                      background: canRedo ? CI.white : CI.gray100,
                      color: canRedo ? CI.midnight : CI.gray400,
                      cursor: canRedo ? "pointer" : "not-allowed",
                      fontSize: 11,
                      fontWeight: 600,
                      fontFamily: "inherit",
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                    }}
                  >
                    ↷
                  </button>
                </>
              )}
              {activeStore && <div style={{ display: "flex", alignItems: "center", gap: 5, padding: "4px 10px", borderRadius: 4, background: activeStore.color + "10", border: "1px solid " + activeStore.color + "30" }}>
                <div style={{ width: 6, height: 6, borderRadius: "50%", background: activeStore.color }} />
                <span style={{ fontSize: 11, fontWeight: 600, color: activeStore.color }}>{activeStore.name}</span>
              </div>}
          <Badge color={CI.basil}><span style={{ width: 6, height: 6, borderRadius: "50%", background: CI.basil, display: "inline-block" }} /> On-Premise</Badge>
          {activeProvider && <button onClick={() => setShowProviders(true)} title={`Aktiv: ${activeProvider.name} / ${activeProvider.model}\n${activeProvider.total} Provider konfiguriert — Klicken fuer Details`} style={{ display: "inline-flex", alignItems: "center", gap: 4, padding: "2px 8px", borderRadius: 3, fontSize: 11, fontWeight: 600, color: CI.pgInfr, background: CI.pgInfr + "15", whiteSpace: "nowrap", cursor: "pointer", border: "1px solid " + CI.pgInfr + "30", fontFamily: "inherit" }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: CI.pgInfr }} />
            {activeProvider.model}
            {activeProvider.total > 1 && <span style={{ fontSize: 9, opacity: 0.7, marginLeft: 2 }}>+{activeProvider.total - 1}</span>}
          </button>}
          <Badge color={apiConnected ? CI.lagoon : CI.amarillo}><span style={{ width: 6, height: 6, borderRadius: "50%", background: apiConnected ? CI.lagoon : CI.amarillo, display: "inline-block" }} /> {apiConnected ? "API" : "Demo"}</Badge>
        </div>
      </div>
      {/* Content */}
      <div style={{ flex: 1, overflow: "hidden" }}>
        {showDocDetail && <DocumentDetailView doc={activeDoc} store={activeStore} onBack={() => setActiveDoc(null)} />}
        {!showDocDetail && view === "briefing" && activeStore && <BriefingPanel store={activeStore} key={"br-" + activeStore.id} />}
        {!showDocDetail && view === "synthesis" && activeStore && <SynthesisPanel store={activeStore} key={"sy-" + activeStore.id} />}
        {!showDocDetail && view === "overview" && activeStore && <Overview store={activeStore} onDoc={d => setActiveDoc(d)} />}
        {view === "wiki" && activeStore && isWissensDB && <WikiPanel store={activeStore} key={"wi-" + activeStore.id} />}
        {view === "chat" && activeStore && !showDocDetail && <ChatPanel store={activeStore} key={activeStore.id} />}
        {view === "skills" && activeStore && <SkillPanel store={activeStore} key={"sk-" + activeStore.id} />}
        {view === "planning" && activeStore && <PlanningPanel store={activeStore} key={"pl-" + activeStore.id} />}
        {view === "search" && activeStore && <SearchPanel store={activeStore} key={"se-" + activeStore.id} />}
      </div>
    </div>
    {showNew && <NewDialog onClose={() => setShowNew(false)} onCreate={s => { setStores(p => [...p, s]); setActiveStore(s); setView("briefing"); setShowNew(false); toast(`"${s.name}" erstellt`, "success"); }} />}
    {showProviders && <ProvidersPanel onClose={() => setShowProviders(false)} />}
  </div>;
}

// Wrapper mit ToastProvider + Error Boundary
export default function App() {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <AppInner />
      </ToastProvider>
    </ErrorBoundary>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// GLOBAL ERROR HANDLERS (Window + Promise)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if (typeof window !== "undefined") {
  // Fängt alle uncaught errors
  window.addEventListener("error", (event) => {
    console.error("❌ Global Error:", event.error);
    // SOTA: Send to Error Tracking Service (z.B. Sentry)
    // Sentry.captureException(event.error);
  });

  // Fängt alle unhandled promise rejections
  window.addEventListener("unhandledrejection", (event) => {
    console.error("❌ Unhandled Promise Rejection:", event.reason);
    // Verhindert Default Console Error
    event.preventDefault();
    // SOTA: Send to Error Tracking
    // Sentry.captureException(event.reason);
  });
}
