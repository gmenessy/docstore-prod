"""
Test-Suite für den Agentischen Document Store.
Testet: Extraktion, Chunking, NER, Suche, API-Endpunkte.
"""
import asyncio
import json
import sys
import tempfile
from pathlib import Path

# Projekt-Root zum Path hinzufügen
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Test 1: Chunking
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_chunking():
    from app.ingestion.chunker import chunk_text, estimate_tokens

    print("\n═══ Test: Adaptives Chunking ═══")

    # Langer deutscher Text
    text = """
Die Digitalisierungsstrategie der Stadt Freiburg umfasst fünf zentrale Handlungsfelder.
Das erste Handlungsfeld betrifft die Einführung der E-Akte in allen Verwaltungsbereichen.
Die Umsetzung soll bis Ende 2025 abgeschlossen sein.

Das zweite Handlungsfeld fokussiert sich auf die Online-Zugänge für Bürgerinnen und Bürger.
Gemäß dem Onlinezugangsgesetz (OZG) müssen alle Verwaltungsleistungen digital verfügbar sein.
Der aktuelle Umsetzungsstand liegt bei 67 Prozent der priorisierten Leistungen.

Das dritte Handlungsfeld behandelt die IT-Infrastruktur und den Glasfaserausbau.
Der Kreis Breisgau-Hochschwarzwald beteiligt sich an der Kofinanzierung.
Das Budget für das Haushaltsjahr 2025 beträgt insgesamt 3,2 Millionen Euro.
Davon werden 800.000 Euro durch Fördermittel des Landes Baden-Württemberg gedeckt.

Die DSGVO-Compliance wird durch regelmäßige Audits und Datenschutz-Folgenabschätzungen sichergestellt.
Der Datenschutzbeauftragte, Herr Dr. Müller, koordiniert die Maßnahmen.
    """.strip()

    chunks = chunk_text(text, max_tokens=100, overlap=20)

    print(f"  Eingabe: {len(text)} Zeichen, ~{estimate_tokens(text)} Tokens")
    print(f"  Ergebnis: {len(chunks)} Chunks")

    for chunk in chunks:
        print(f"    Chunk {chunk.index}: {chunk.token_count} Tokens, {len(chunk.content)} Zeichen")
        print(f"      → {chunk.content[:80]}…")

    assert len(chunks) > 1, "Sollte mehrere Chunks erzeugen"
    assert all(c.token_count > 0 for c in chunks), "Alle Chunks sollten Token haben"
    print("  ✓ Chunking bestanden")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Test 2: NER (Entitäten-Extraktion)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_ner():
    from app.ingestion.ner import extract_entities

    print("\n═══ Test: Entitäten-Extraktion (NER v2) ═══")

    text = """
    Der Beschluss des Gemeinderats vom 22. Juni 2025 sieht eine Beschleunigung
    der Digitalisierung vor. Herr Dr. Müller hat die Genehmigung am 15. März 2025
    erteilt. Frau Weber koordiniert die Umsetzung in der Verwaltung.
    Die DSGVO-Compliance wird sichergestellt. Stadt Freiburg investiert
    in Barrierefreiheit und Infrastruktur. Prof. Schmidt leitet das
    BSI-Grundschutz-Audit. Der Antrag auf Förderung wurde eingereicht.
    Die Verordnung zur digitalen Barrierefreiheit tritt am 01.01.2026 in Kraft.
    Das Budget beträgt 3,2 Mio Euro. Kontakt: mueller@freiburg.de
    Gemäß § 12 Abs. 3 GemO ist der Beschluss rechtskräftig.
    Telefon: +49 761 201-0. IBAN: DE89370400440532013000.
    """

    entities = extract_entities(text)

    print(f"  Personen: {[e['value'] for e in entities.personen]}")
    print(f"  Daten: {[e['value'] for e in entities.daten]}")
    print(f"  Fachbegriffe: {len(entities.fachbegriffe)} gefunden")
    print(f"  Orte: {[e['value'] for e in entities.orte]}")
    print(f"  PII: {[e['type'] + ':' + e['value'][:20] for e in entities.pii]}")
    print(f"  Geldbetraege: {[e['value'] for e in entities.geldbetraege]}")
    print(f"  Gesetze: {[e['value'] for e in entities.gesetze]}")
    print(f"  GESAMT: {entities.total_count} Entitaeten")

    assert len(entities.personen) > 0, "Sollte Personen finden"
    assert len(entities.daten) > 0, "Sollte Daten finden"
    assert len(entities.fachbegriffe) > 0, "Sollte Fachbegriffe finden"
    assert any("DSGVO" in e["value"] for e in entities.fachbegriffe), "Sollte DSGVO finden"
    assert len(entities.pii) > 0, "Sollte PII finden (E-Mail, Telefon, IBAN)"
    assert len(entities.geldbetraege) > 0, "Sollte Geldbetraege finden"
    assert len(entities.gesetze) > 0, "Sollte Gesetze finden"
    print("  ✓ NER v2 bestanden")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Test 3: Hybrid-Suche
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_search():
    from app.search.engine import HybridSearchEngine

    print("\n═══ Test: Hybrid-Suche ═══")

    engine = HybridSearchEngine()

    # Test-Chunks hinzufügen
    chunks = [
        {
            "id": "c1", "document_id": "d1", "document_title": "Digitalisierung.pdf",
            "store_id": "s1", "store_name": "Test-Store",
            "content": "Die Digitalisierungsstrategie umfasst fünf Handlungsfelder für die Verwaltung.",
            "chunk_index": 0, "file_type": "pdf", "tags": ["Strategie"],
        },
        {
            "id": "c2", "document_id": "d1", "document_title": "Digitalisierung.pdf",
            "store_id": "s1", "store_name": "Test-Store",
            "content": "Das Budget für Infrastruktur beträgt 3,2 Millionen Euro im Haushaltsjahr.",
            "chunk_index": 1, "file_type": "pdf", "tags": ["Budget"],
        },
        {
            "id": "c3", "document_id": "d2", "document_title": "Bauantrag.pdf",
            "store_id": "s2", "store_name": "Bauakte",
            "content": "Der Bauantrag für die Sanierung des Gebäudes wurde genehmigt.",
            "chunk_index": 0, "file_type": "pdf", "tags": ["Bau"],
        },
        {
            "id": "c4", "document_id": "d2", "document_title": "Bauantrag.pdf",
            "store_id": "s2", "store_name": "Bauakte",
            "content": "Die DSGVO Datenschutz-Folgenabschätzung für das Bauprojekt liegt vor.",
            "chunk_index": 1, "file_type": "pdf", "tags": ["Datenschutz"],
        },
    ]

    engine.add_chunks(chunks)
    engine.rebuild_index()

    # Test: Hybrid-Suche
    results = engine.search("Digitalisierung Verwaltung", search_type="hybrid")
    print(f"  Suche 'Digitalisierung Verwaltung': {len(results)} Treffer")
    for r in results:
        print(f"    Score {r.score:.3f} │ {r.document_title} │ Chunk {r.chunk_index}")
    assert len(results) > 0, "Sollte Treffer finden"
    assert results[0].document_title == "Digitalisierung.pdf", "Bestes Ergebnis sollte Digitalisierung sein"

    # Test: BM25-Suche
    results_bm25 = engine.search("Budget Infrastruktur", search_type="bm25")
    print(f"  Suche 'Budget Infrastruktur' (BM25): {len(results_bm25)} Treffer")
    assert len(results_bm25) > 0

    # Test: Store-Filter
    results_filtered = engine.search("Datenschutz", store_id="s2")
    print(f"  Suche 'Datenschutz' (Store s2): {len(results_filtered)} Treffer")
    assert all(r.store_id == "s2" for r in results_filtered)

    # Test: Leere Suche
    results_empty = engine.search("xyznonexistent")
    assert len(results_empty) == 0

    print("  ✓ Hybrid-Suche bestanden")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Test 4: Intelligence-Services
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_intelligence():
    from app.services.intelligence import (
        generate_summary, extract_key_takeaways, fuse_knowledge, distill_facts,
    )

    print("\n═══ Test: Intelligence-Services ═══")

    texts = [
        "Die Digitalisierungsstrategie umfasst fünf Handlungsfelder. Das Budget beträgt 3,2 Millionen Euro. Die Umsetzung erfolgt bis Ende 2025. Der Beschluss wurde am 22. Juni gefasst.",
        "Die IT-Infrastruktur basiert auf einem hybriden Ansatz. On-Premise-Server für sensible Daten. Förderung durch das Land in Höhe von 800.000 Euro. BSI-Grundschutz wird eingehalten.",
        "Der Bauantrag wurde am 03. April 2025 eingereicht. Die Kosten betragen 1,5 Millionen Euro. Denkmalschutz-Auflagen sind zu beachten. Statik-Gutachten liegt vor.",
    ]

    # Zusammenfassung
    summary = generate_summary(texts)
    print(f"  Zusammenfassung: {summary[:120]}…")
    assert len(summary) > 50, "Zusammenfassung sollte substantiell sein"

    # Key Takeaways
    takeaways = extract_key_takeaways(texts)
    print(f"  Key Takeaways: {len(takeaways)} Punkte")
    for t in takeaways[:5]:
        print(f"    → {t['takeaway']} ({t['count']}×)")
    assert len(takeaways) > 0

    # Fusion
    fusion = fuse_knowledge(texts)
    print(f"  Fusion: {len(fusion['common_themes'])} gemeinsame Themen, Coverage {fusion['coverage']:.2f}")
    assert "common_themes" in fusion

    # Destillierung
    facts = distill_facts(texts)
    print(f"  Destillierte Fakten: {len(facts)}")
    for f in facts[:3]:
        print(f"    → [{f['type']}] {f['text'][:80]}…")
    assert len(facts) > 0

    print("  ✓ Intelligence-Services bestanden")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Test 5: Dokumenten-Extraktion
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_extractor():
    from app.ingestion.extractor import DocumentExtractor

    print("\n═══ Test: Dokumenten-Extraktion ═══")

    ext = DocumentExtractor()

    # Test: Markdown
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False, encoding="utf-8") as f:
        f.write("# Test-Dokument\n\nDies ist ein **Test** mit einer Tabelle:\n\n| Spalte A | Spalte B |\n|----------|----------|\n| Wert 1 | Wert 2 |\n\n![Bild](test.png)")
        f.flush()
        result = ext.extract(Path(f.name))

    print(f"  Markdown: {len(result.text)} Zeichen, Tabellen={result.has_tables}, Bilder={result.has_images}")
    assert result.has_tables, "Sollte Tabelle erkennen"
    assert result.has_images, "Sollte Bild erkennen"

    # Test: Plaintext
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False, encoding="utf-8") as f:
        f.write("Einfacher Text ohne besondere Formatierung.\nZweite Zeile.")
        f.flush()
        result = ext.extract(Path(f.name))

    print(f"  TXT: {len(result.text)} Zeichen")
    assert len(result.text) > 10

    # Test: Unsupported
    result = ext.extract(Path("test.xyz"))
    assert len(result.errors) > 0
    print(f"  Unsupported: {result.errors[0]}")

    print("  ✓ Extraktion bestanden")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Test 6: API-Endpunkte (Integration)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def test_api():
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.core.database import init_db

    print("\n═══ Test: API-Endpunkte ═══")

    await init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:

        # Health-Check
        r = await client.get("/health")
        assert r.status_code == 200
        print(f"  GET /health → {r.status_code}")

        # Store erstellen
        r = await client.post("/api/v1/stores", json={
            "name": "Test-WissensDB",
            "type": "wissensdb",
            "description": "Test-Sammlung für Unit-Tests",
            "analyse_fokus": "Qualitätssicherung",
        })
        assert r.status_code == 201
        store = r.json()
        store_id = store["id"]
        print(f"  POST /stores → {r.status_code}, ID={store_id}")

        # Store abrufen
        r = await client.get(f"/api/v1/stores/{store_id}")
        assert r.status_code == 200
        assert r.json()["name"] == "Test-WissensDB"
        print(f"  GET /stores/{store_id} → {r.status_code}")

        # Store aktualisieren
        r = await client.patch(f"/api/v1/stores/{store_id}", json={
            "analyse_fokus": "Neuer Fokus",
        })
        assert r.status_code == 200
        assert r.json()["analyse_fokus"] == "Neuer Fokus"
        print(f"  PATCH /stores/{store_id} → {r.status_code}")

        # Alle Stores auflisten
        r = await client.get("/api/v1/stores")
        assert r.status_code == 200
        stores = r.json()
        assert len(stores) >= 1
        print(f"  GET /stores → {r.status_code}, {len(stores)} Store(s)")

        # Dokument hochladen (Markdown)
        md_content = """# Test-Dokument

Die Digitalisierungsstrategie der Stadt Freiburg umfasst fünf Handlungsfelder.
Herr Dr. Müller hat am 15. März 2025 die Genehmigung erteilt.
Das Budget beträgt 3,2 Millionen Euro.

| Maßnahme | Status |
|----------|--------|
| E-Akte | In Umsetzung |
| OZG | Abgeschlossen |

Die DSGVO-Compliance wird durch regelmäßige Audits sichergestellt.
"""
        r = await client.post(
            f"/api/v1/documents/{store_id}/upload-sync",
            files={"file": ("test-dokument.md", md_content.encode(), "text/markdown")},
        )
        assert r.status_code == 200
        upload_result = r.json()
        doc_id = upload_result.get("document_id", "")
        print(f"  POST /documents/{store_id}/upload-sync → {r.status_code}, DocID={doc_id}")

        # Dokumente auflisten
        r = await client.get(f"/api/v1/documents/{store_id}")
        assert r.status_code == 200
        docs_resp = r.json()
        docs = docs_resp.get("items", docs_resp)  # Handle paginated or flat
        doc_count = len(docs) if isinstance(docs, list) else docs_resp.get("total", 0)
        print(f"  GET /documents/{store_id} → {r.status_code}, {doc_count} Dok(s)")

        # Dokument-Detail
        if doc_id:
            r = await client.get(f"/api/v1/documents/detail/{doc_id}")
            assert r.status_code == 200
            detail = r.json()
            print(f"  GET /documents/detail/{doc_id} → {r.status_code}")
            print(f"    Chunks: {detail['chunk_count']}, Entitäten: {len(detail['entities'])}")
            print(f"    Tabellen: {detail['has_tables']}, Bilder: {detail['has_images']}")

        # Suche
        r = await client.post("/api/v1/search", json={
            "query": "Digitalisierung DSGVO",
            "search_type": "hybrid",
        })
        assert r.status_code == 200
        search_result = r.json()
        print(f"  POST /search 'Digitalisierung DSGVO' → {search_result['total_results']} Treffer, {search_result['execution_time_ms']:.1f}ms")

        # Live-View
        r = await client.get(f"/api/v1/stores/{store_id}/live-view")
        assert r.status_code == 200
        lv = r.json()
        print(f"  GET /stores/{store_id}/live-view → {r.status_code}")
        print(f"    Zusammenfassung: {lv['summary'][:80]}…")
        print(f"    Takeaways: {len(lv['key_takeaways'])}")
        print(f"    Stats: {lv['stats']}")

        # ═══ NEUE MODULE: Chat, Skills, Planung ═══
        print("\n  ─── Chat (Store-isoliert) ───")

        # Chat: Nachricht senden
        r = await client.post(f"/api/v1/stores/{store_id}/chat", json={
            "message": "Was steht zur Digitalisierung in den Dokumenten?",
        })
        assert r.status_code == 200
        chat = r.json()
        assert chat["store_id"] == store_id
        assert chat["store_name"] == "Test-WissensDB"
        assert "provider" in chat
        assert "model" in chat
        session_id = chat["session_id"]
        print(f"  POST /chat → {r.status_code}, Session={session_id[:8]}…, Provider={chat['provider']}/{chat['model']}")
        print(f"    Antwort: {chat['answer']['content'][:80]}…")
        print(f"    Quellen: {len(chat['answer']['sources'])}, Kontext-Docs: {chat['context_documents']}")

        # Chat: Zweite Nachricht in gleicher Session
        r = await client.post(f"/api/v1/stores/{store_id}/chat", json={
            "message": "Welche Personen werden erwähnt?",
            "session_id": session_id,
        })
        assert r.status_code == 200
        assert r.json()["session_id"] == session_id
        print(f"  POST /chat (Session) → {r.status_code}")

        # Chat: Verlauf abrufen
        r = await client.get(f"/api/v1/stores/{store_id}/chat/history/{session_id}")
        assert r.status_code == 200
        history = r.json()
        msg_count = history.get("total", history.get("count", len(history.get("items", []))))
        assert msg_count >= 4  # 2 user + 2 assistant
        print(f"  GET /chat/history → {msg_count} Nachrichten")

        # Chat: LLM-Provider auflisten
        r = await client.get(f"/api/v1/stores/{store_id}/chat/providers")
        assert r.status_code == 200
        providers = r.json()
        assert len(providers["providers"]) >= 5
        print(f"  GET /chat/providers → {len(providers['providers'])} Provider: {[p['id'] for p in providers['providers']]}")

        print("\n  ─── Skills (Store-isoliert) ───")

        # Skills: Katalog abrufen
        r = await client.get(f"/api/v1/stores/{store_id}/skills")
        assert r.status_code == 200
        skills = r.json()
        assert len(skills["skills"]) >= 6
        print(f"  GET /skills → {len(skills['skills'])} Skills verfügbar")

        # Skills: Anonymisierung ausführen
        r = await client.post(f"/api/v1/stores/{store_id}/skills/execute-sync", json={
            "skill_id": "anon",
            "parameters": {"scope": "Alle Dokumente", "entities": "Personen"},
        })
        assert r.status_code == 200
        anon_result = r.json()
        assert anon_result["step"] == "done"
        print(f"  POST /skills/execute-sync (anon) → {r.status_code}")
        print(f"    Ergebnis: {anon_result['result'].get('total_replacements', 0)} Ersetzungen")

        # Skills: Blog-Beitrag generieren
        r = await client.post(f"/api/v1/stores/{store_id}/skills/execute-sync", json={
            "skill_id": "blog",
            "parameters": {"title": "Digitalisierung", "tone": "informativ", "length": "300"},
        })
        assert r.status_code == 200
        print(f"  POST /skills/execute-sync (blog) → {r.status_code}")

        # Skills: Ausführungshistorie
        r = await client.get(f"/api/v1/stores/{store_id}/skills/executions")
        assert r.status_code == 200
        assert r.json()["count"] >= 2
        print(f"  GET /skills/executions → {r.json()['count']} Ausführungen")

        print("\n  ─── Planung (Store-isoliert) ───")

        # Planung: Tasks abrufen (automatische Extraktion)
        r = await client.get(f"/api/v1/stores/{store_id}/planning/tasks")
        assert r.status_code == 200
        plan = r.json()
        assert plan["count"] >= 1
        print(f"  GET /planning/tasks → {plan['count']} Maßnahmen extrahiert")
        if plan["tasks"]:
            t = plan["tasks"][0]
            print(f"    Erste Maßnahme: {t['title']} (Quelle: {t['source_document']})")

        # Planung: Manuelle Maßnahme hinzufügen
        r = await client.post(f"/api/v1/stores/{store_id}/planning/tasks", json={
            "title": "Test-Maßnahme: API-Prüfung",
            "description": "Automatisierter Test",
            "priority": "hoch",
            "due_date": "Q1 2026",
            "assignee": "CI/CD",
        })
        assert r.status_code == 201
        new_task = r.json()
        task_id = new_task["id"]
        print(f"  POST /planning/tasks → {r.status_code}, ID={task_id}")

        # Planung: Task-Status aktualisieren (Kanban-Move)
        r = await client.patch(f"/api/v1/stores/{store_id}/planning/tasks/{task_id}", json={
            "status": "active",
            "assignee": "Projektteam",
        })
        assert r.status_code == 200
        assert r.json()["status"] == "active"
        print(f"  PATCH /planning/tasks/{task_id} → Status: active")

        # Planung: Task löschen
        r = await client.delete(f"/api/v1/stores/{store_id}/planning/tasks/{task_id}")
        assert r.status_code == 204
        print(f"  DELETE /planning/tasks/{task_id} → {r.status_code}")

        # ═══ PRIO 3: Web-Scraper, Storage, Versionierung, Task-Deps ═══
        print("\n  ─── Storage-Management ───")

        r = await client.get("/api/v1/system/storage")
        assert r.status_code == 200
        storage = r.json()
        print(f"  GET /system/storage → App: {storage['app_used_mb']} MB, Stores: {storage['stores_count']}")

        r = await client.get(f"/api/v1/stores/{store_id}/storage")
        assert r.status_code == 200
        print(f"  GET /stores/.../storage → {r.json()['used_mb']} MB / {r.json()['limit_mb']} MB")

        r = await client.post("/api/v1/system/cleanup?max_age_days=30")
        assert r.status_code == 200
        print(f"  POST /system/cleanup → {r.json()['deleted_files']} Dateien geloescht")

        print("\n  ─── Dokument-Versionierung ───")

        # Zweites Dokument mit gleichem Namen hochladen = Version 2
        md_v2 = "# Test-Dokument V2\n\nAktualisierte Version mit neuen Informationen.\nDie Digitalisierung wurde beschleunigt."
        r = await client.post(
            f"/api/v1/documents/{store_id}/upload-sync",
            files={"file": ("test-dokument.md", md_v2.encode(), "text/markdown")},
        )
        assert r.status_code == 200
        doc_v2_id = r.json().get("document_id", "")
        print(f"  POST /upload (gleicher Name) → {r.status_code}, V2 DocID={doc_v2_id}")

        # Versionshistorie abrufen
        if doc_v2_id:
            r = await client.get(f"/api/v1/documents/detail/{doc_v2_id}/versions")
            assert r.status_code == 200
            versions = r.json()
            print(f"  GET /versions → {versions['total_versions']} Version(en)")

        print("\n  ─── Task-Abhaengigkeiten ───")

        # Task A erstellen
        r = await client.post(f"/api/v1/stores/{store_id}/planning/tasks", json={
            "title": "Task A: Konzept erstellen",
            "priority": "hoch",
        })
        assert r.status_code == 201
        task_a_id = r.json()["id"]
        print(f"  POST Task A → {task_a_id}")

        # Task B abhaengig von A
        r = await client.post(f"/api/v1/stores/{store_id}/planning/tasks", json={
            "title": "Task B: Umsetzung (abhaengig von A)",
            "priority": "mittel",
            "depends_on": [task_a_id],
        })
        assert r.status_code == 201
        task_b = r.json()
        assert task_a_id in task_b["depends_on"]
        assert task_b["blocked_by_count"] >= 1
        print(f"  POST Task B → depends_on=[{task_a_id}], blocked={task_b['blocked_by_count']}")

        # Aufraeumen
        await client.delete(f"/api/v1/stores/{store_id}/planning/tasks/{task_a_id}")
        await client.delete(f"/api/v1/stores/{store_id}/planning/tasks/{task_b['id']}")

        # ═══ PRIO 4: Export + NER v2 ═══
        print("\n  ─── Export (PPTX, DOCX, PDF) ───")

        # PPTX Export
        r = await client.get(f"/api/v1/stores/{store_id}/export/pptx")
        assert r.status_code == 200
        assert len(r.content) > 1000
        assert "presentationml" in r.headers.get("content-type", "")
        print(f"  GET /export/pptx → {r.status_code}, {len(r.content) // 1024} KB")

        # DOCX Export
        r = await client.get(f"/api/v1/stores/{store_id}/export/docx?sections=Zusammenfassung,Quellen")
        assert r.status_code == 200
        assert len(r.content) > 1000
        print(f"  GET /export/docx → {r.status_code}, {len(r.content) // 1024} KB")

        # PDF Export
        r = await client.get(f"/api/v1/stores/{store_id}/export/pdf")
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"
        print(f"  GET /export/pdf → {r.status_code}, {len(r.content) // 1024} KB, PDF header OK")

        print("\n  ─── NER v2 (Re-Analyse) ───")

        # NER Re-Extraktion (Regex-Modus)
        r = await client.post(f"/api/v1/stores/{store_id}/reanalyze-ner?use_llm=false")
        assert r.status_code == 200
        ner = r.json()
        print(f"  POST /reanalyze-ner (regex) → {ner['entities_extracted']} Entitaeten aus {ner['documents_processed']} Dok(s)")

        # ═══ WIKI (WissensDB v2) ═══
        print("\n  ─── Wiki (WissensDB v2) ───")

        # Wiki-Seiten listen (sollte nach Ingestion bereits Seiten haben durch Fallback)
        r = await client.get(f"/api/v1/stores/{store_id}/wiki/pages")
        assert r.status_code == 200
        wiki_pages = r.json()
        print(f"  GET /wiki/pages → {wiki_pages['total']} Seiten")

        # Wiki-Ingest manuell ausloesen (LLM-Fallback wird greifen da kein LLM verfuegbar)
        # Wir brauchen ein Dokument — hole erstes
        r = await client.get(f"/api/v1/documents/{store_id}")
        docs = r.json()["items"]
        if docs:
            doc_id = docs[0]["id"]
            r = await client.post(f"/api/v1/stores/{store_id}/wiki/ingest/{doc_id}", json={})
            assert r.status_code == 200
            ingest_result = r.json()
            print(f"  POST /wiki/ingest/{{doc}} → {ingest_result.get('pages_created', 0)} neu, {ingest_result.get('pages_updated', 0)} aktualisiert")

        # Wiki-Seiten nach Ingest
        r = await client.get(f"/api/v1/stores/{store_id}/wiki/pages")
        assert r.status_code == 200
        wiki_pages = r.json()
        print(f"  GET /wiki/pages (nach Ingest) → {wiki_pages['total']} Seiten")
        assert wiki_pages['total'] > 0, "Wiki sollte mindestens eine Seite haben nach Ingest"

        # Einzelne Wiki-Seite abrufen
        if wiki_pages["pages"]:
            slug = wiki_pages["pages"][0]["slug"]
            r = await client.get(f"/api/v1/stores/{store_id}/wiki/pages/{slug}")
            assert r.status_code == 200
            page = r.json()
            print(f"  GET /wiki/pages/{slug} → '{page['title']}', {len(page.get('content_md', ''))} Zeichen")

        # Wiki-Lint
        r = await client.post(f"/api/v1/stores/{store_id}/wiki/lint")
        assert r.status_code == 200
        lint = r.json()
        print(f"  POST /wiki/lint → {lint['total_pages']} Seiten, {lint['issues_found']} Hinweise")
        print(f"    Summary: {lint['summary']}")

        # Wiki-Query
        r = await client.post(f"/api/v1/stores/{store_id}/wiki/query",
                              json={"question": "Was steht zur Digitalisierung?"})
        assert r.status_code == 200
        qresult = r.json()
        print(f"  POST /wiki/query → {len(qresult.get('pages_used', []))} Seiten genutzt, Antwort {len(qresult.get('answer', ''))} Zeichen")

        # Save-Answer: Chat-Antwort als Wiki-Seite
        r = await client.post(f"/api/v1/stores/{store_id}/wiki/save-answer",
                              json={"question": "Was ist DSGVO?",
                                    "answer": "Datenschutz-Grundverordnung: regelt Umgang mit personenbezogenen Daten.",
                                    "title": "DSGVO Uebersicht"})
        assert r.status_code == 200
        save_result = r.json()
        print(f"  POST /wiki/save-answer → slug='{save_result['slug']}', created={save_result['created']}")

        # Wiki-Log
        r = await client.get(f"/api/v1/stores/{store_id}/wiki/log")
        assert r.status_code == 200
        log_data = r.json()
        print(f"  GET /wiki/log → {log_data['total']} Operationen")

        # ═══ WIKI-WARTUNG → PLANNING-TASKS (Iteration 3) ═══
        print("\n  ─── Wiki-Wartung → Planning-Tasks ───")

        # Tasks vorher zaehlen
        r = await client.get(f"/api/v1/stores/{store_id}/planning/tasks")
        assert r.status_code == 200
        before_total = r.json()["count"]
        print(f"  GET /planning/tasks (gesamt, vorher) → {before_total} Tasks")

        # Lint-to-Tasks ausloesen
        r = await client.post(f"/api/v1/stores/{store_id}/planning/wiki-lint-to-tasks")
        assert r.status_code == 200
        lint_tasks = r.json()
        print(f"  POST /planning/wiki-lint-to-tasks → {lint_tasks['created']} neue Tasks aus {lint_tasks['total_issues']} Issues")
        print(f"    Lint-Summary: {lint_tasks['lint_summary']}")

        # Zweiter Lauf: Dedup sollte greifen
        r = await client.post(f"/api/v1/stores/{store_id}/planning/wiki-lint-to-tasks")
        assert r.status_code == 200
        lint_tasks2 = r.json()
        print(f"  POST /planning/wiki-lint-to-tasks (2. Lauf) → {lint_tasks2['created']} neu, {lint_tasks2['skipped']} uebersprungen (Dedup)")
        assert lint_tasks2['skipped'] == lint_tasks['created'], f"Dedup defekt: erwartet {lint_tasks['created']} skips, bekam {lint_tasks2['skipped']}"

        # Filter: nur Wiki-Wartungs-Tasks
        r = await client.get(f"/api/v1/stores/{store_id}/planning/tasks?category=wiki-maintenance")
        assert r.status_code == 200
        wiki_tasks = r.json()
        print(f"  GET /planning/tasks?category=wiki-maintenance → {wiki_tasks['count']} Tasks")
        if wiki_tasks['count'] > 0:
            sample = wiki_tasks['tasks'][0]
            assert sample['source_document'].startswith('wiki-lint:'), "Filter defekt: sollte nur wiki-lint-Tasks liefern"
            print(f"    Beispiel: '{sample['title']}' (Prio: {sample['priority']}, Quelle: {sample['source_document']})")

        # Filter: nur Dokument-Tasks
        r = await client.get(f"/api/v1/stores/{store_id}/planning/tasks?category=documents")
        assert r.status_code == 200
        doc_tasks = r.json()
        print(f"  GET /planning/tasks?category=documents → {doc_tasks['count']} Tasks")
        for t in doc_tasks['tasks']:
            assert not t['source_document'].startswith('wiki-lint:'), "Filter defekt: dokuemnt-Tasks sollten keine wiki-lint enthalten"


        # Suche-Stats
        r = await client.get("/api/v1/search/stats")
        assert r.status_code == 200
        print(f"\n  GET /search/stats → Index: {r.json()['index_size']} Chunks")

        # System-Info
        r = await client.get("/api/v1/system/info")
        assert r.status_code == 200
        print(f"  GET /system/info → {r.status_code}")

        # Aufräumen: Store löschen
        r = await client.delete(f"/api/v1/stores/{store_id}")
        assert r.status_code == 204
        print(f"  DELETE /stores/{store_id} → {r.status_code}")

    print("  ✓ API-Tests bestanden")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Runner
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    print("╔═══════════════════════════════════════════════╗")
    print("║  Agentischer Document Store – Test-Suite      ║")
    print("╚═══════════════════════════════════════════════╝")

    passed = 0
    failed = 0

    tests = [
        ("Chunking", test_chunking),
        ("NER", test_ner),
        ("Hybrid-Suche", test_search),
        ("Intelligence", test_intelligence),
        ("Extraktion", test_extractor),
    ]

    for name, test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"\n  ✗ {name} FEHLGESCHLAGEN: {e}")
            failed += 1

    # Async API-Tests
    try:
        asyncio.run(test_api())
        passed += 1
    except Exception as e:
        print(f"\n  ✗ API-Tests FEHLGESCHLAGEN: {e}")
        import traceback
        traceback.print_exc()
        failed += 1

    print(f"\n{'═' * 50}")
    print(f"  Ergebnis: {passed} bestanden, {failed} fehlgeschlagen")
    print(f"{'═' * 50}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
