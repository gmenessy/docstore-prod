# Agentischer Document Store

**Akte & WissensDB** — DSGVO-konforme Dokumentenverwaltung mit KI-gestuetzter Wiki-Pflege fuer kommunale Verwaltung.

---

## Ueberblick

Dieses System verwaltet zwei Arten von Dokument-Sammlungen:

- **Akten** — Immutable Rohquellen mit Hybrid-Suche (BM25 + Semantic), RAG-Chat und Skills (PPTX/DOCX-Generierung, Anonymisierung, Massnahmen-Extraktion)
- **WissensDB** — Akten plus ein durch LLM gepflegtes Wiki. Jedes neue Dokument fuehrt zu automatischen Updates der Wiki-Seiten. Lint findet Orphans, Widersprueche und fehlende Konzepte. Issues werden automatisch zu Planning-Tasks in der Kategorie "Wiki-Wartung".

### Kern-Features

- **On-Premise**: Laeuft ohne Cloud-Abhaengigkeiten
- **DSGVO-konform**: PII-Anonymisierung, rollenbasiertes Auth, kein Tracking
- **Mandantenfaehig**: Jede Sammlung ist ein isoliertes Oekosystem
- **Hybrid-RAG**: BM25 + Semantic-Search, optional mit Embeddings-Cache
- **GenAI-integriert**: 5 von 6 Skills nutzen LLM (Ollama, OpenAI, Anthropic, Mistral)
- **Wiki-Pattern**: Kompilierte Synthese statt Rohdokument-RAG
- **Multi-Turn-Chat**: Konversations-Kontext ueber Sitzungen hinweg
- **47 API-Endpunkte**: REST + SSE-Streaming
- **Deutschsprachig**: UI, OCR (tesseract-deu), LLM-Prompts

---

## Systemanforderungen

**Minimal (ohne Ollama)**
- 2 CPU-Kerne
- 4 GB RAM
- 20 GB Plattenplatz
- Docker Engine 24+ und Docker Compose v2

**Empfohlen (mit lokalem LLM)**
- 8 CPU-Kerne
- 16 GB RAM
- 100 GB Plattenplatz (Modelle + Daten)
- Optional: NVIDIA-GPU (fuer grosse Modelle)

**Unterstuetzte Betriebssysteme**
- Linux (Ubuntu 22.04+, RHEL 9+, Debian 12+)
- Windows mit WSL2
- macOS mit Docker Desktop

---

## Schnellstart

```bash
# 1. Repository bereitstellen
cd /opt
tar xzf docstore-prod.tar.gz
cd docstore-prod

# 2. Konfiguration erzeugen
make init
# .env bearbeiten: POSTGRES_PASSWORD und DOCSTORE_API_KEY setzen!
nano .env
chmod 600 .env

# 3. Bauen und starten
make build
make up

# 4. Verifizieren
make health
# Sollte zeigen: postgres=healthy, redis=healthy, backend=healthy, frontend=healthy
```

Die Anwendung ist jetzt erreichbar unter **http://localhost**.

### Mit lokalem LLM (Ollama)

```bash
# Ollama-Profil aktivieren und Modelle laden
make up-llm
make llm-pull   # laedt llama3.2 und nomic-embed-text

# Oder alles auf einmal (LLM + Worker + Vectors)
make up-full
```

---

## Architektur

```
                ┌──────────────────────────────────────┐
                │         Browser (Nutzer)             │
                └──────────────┬───────────────────────┘
                               │ HTTPS
                               ▼
                ┌──────────────────────────────────────┐
                │  nginx (Frontend-Container, Port 80) │
                │  - Serves React-App (dist/)          │
                │  - Reverse-Proxy zu Backend          │
                │  - Security-Headers, Gzip, Cache     │
                └──────────────┬───────────────────────┘
                               │ /api/v1/* und /health
                               ▼
                ┌──────────────────────────────────────┐
                │  FastAPI Backend (Port 8000)         │
                │  - Uvicorn mit 2 Workern             │
                │  - Non-Root, Healthcheck             │
                │  - 47 Endpunkte                      │
                └──────┬──────────────┬───────┬────────┘
                       │              │       │
             ┌─────────▼──────┐  ┌────▼────┐  ▼
             │  PostgreSQL 16 │  │ Redis 7 │  Ollama (optional)
             │  - Primaer-DB  │  │ - Celery│  - LLM intern
             │  - pg_trgm     │  │ - Cache │
             └────────────────┘  └─────────┘
```

### Services im Detail

| Service   | Image               | Port      | Zweck                                    |
|-----------|---------------------|-----------|------------------------------------------|
| frontend  | (selbst-gebaut)     | 80        | React-SPA + nginx-Reverse-Proxy          |
| backend   | (selbst-gebaut)     | 8000      | FastAPI-App, 47 REST-Endpunkte           |
| postgres  | postgres:16-alpine  | 5432      | Primaere Datenbank                       |
| redis     | redis:7-alpine      | 6379      | Celery-Broker + Cache                    |
| worker    | (selbst-gebaut)     | -         | Celery-Worker (Profil: worker)           |
| ollama    | ollama/ollama       | 11434     | LLM-Server (Profil: llm)                 |
| qdrant    | qdrant/qdrant       | 6333      | Vector-DB (Profil: vectors)              |

---

## Konfiguration

Alle Einstellungen in `.env`. Siehe `.env.example` fuer vollstaendige Dokumentation.

**Kritische Variablen**

- `POSTGRES_PASSWORD` — mindestens 16 Zeichen, vor dem ersten Start setzen
- `DOCSTORE_API_KEY` — API-Token fuer alle Aufrufe. Generierung: `openssl rand -hex 32`
- `DOCSTORE_API_KEY_REQUIRED` — `true` in Produktion, niemals deaktivieren
- `FRONTEND_PORT` — Default 80. Fuer HTTPS einen Reverse-Proxy davor (Traefik, nginx, Caddy)

**Port-Bindings**

Default-Konfiguration bindet nur das Frontend (Port 80) extern. Backend, Datenbank und Redis sind nur ueber localhost erreichbar — das ist bewusst so.

```ini
FRONTEND_PORT=80                    # extern
BACKEND_PORT=127.0.0.1:8000         # nur localhost
POSTGRES_PORT=127.0.0.1:5432        # nur localhost
REDIS_PORT=127.0.0.1:6379           # nur localhost
```

**Storage-Limits**

```ini
MAX_STORE_SIZE_MB=5000      # pro Sammlung
MAX_TOTAL_SIZE_MB=50000     # gesamt
FILE_TTL_DAYS=365           # 0 = unbegrenzt
```

**Corporate Proxy**

Fuer Umgebungen hinter einem Proxy (z.B. Komm.ONE):

```ini
HTTP_PROXY=http://proxy.example.com:3128
HTTPS_PROXY=http://proxy.example.com:3128
NO_PROXY=localhost,127.0.0.1,postgres,redis,ollama,qdrant
```

Beim Bau der Images wird der Proxy uebernommen:

```bash
docker compose build \
  --build-arg HTTP_PROXY=$HTTP_PROXY \
  --build-arg HTTPS_PROXY=$HTTPS_PROXY
```

---

## Betrieb

### Ueblicher Workflow

```bash
make up         # Starten
make ps         # Status pruefen
make logs       # Logs mitlesen
make health     # Healthcheck
make down       # Stoppen (Daten bleiben)
```

### Backup & Restore

**Backup (automatisch)**

Per Cronjob alle 6 Stunden:
```cron
0 */6 * * * cd /opt/docstore-prod && make backup >> /var/log/docstore-backup.log 2>&1
```

Das Skript sichert:
- PostgreSQL-Dump (pg_dump custom format, komprimiert)
- Uploads und generierte Outputs (tar.gz)
- Konfiguration (docker-compose.yml, scripts/, nginx.conf — ohne .env!)

Alte Backups aelter als `RETENTION_DAYS` (Default 30) werden automatisch entfernt.

**Restore**

```bash
# Verfuegbare Backups anzeigen
bash scripts/restore.sh
# zeigt: 20260417-060000, 20260417-120000, ...

# Restore eines bestimmten Backups
make restore TS=20260417-120000
# oder: bash scripts/restore.sh 20260417-120000
```

### Updates

```bash
cd /opt/docstore-prod

# 1. Backup
make backup

# 2. Neue Version ueberschreiben
tar xzf /tmp/docstore-prod-v1.1.tar.gz --strip-components=1

# 3. Rebuild und Neustart (rolling update nicht moeglich bei Single-Node)
make build
docker compose up -d

# 4. Verifizieren
make health
```

### Logs

Logs aller Container:
```bash
docker compose logs --since 1h
```

Logs in Datei:
```bash
docker compose logs --no-color > /var/log/docstore-$(date +%F).log
```

---

## Sicherheits-Hardening

Diese Checkliste vor dem produktiven Einsatz durchgehen.

### Pflicht

- [ ] **`.env` schuetzen**: `chmod 600 .env`, nicht in Git committen
- [ ] **Starke Passwoerter**: `POSTGRES_PASSWORD` und `DOCSTORE_API_KEY` mit `openssl rand -hex 32` erzeugt
- [ ] **HTTPS aktivieren**: Reverse-Proxy (Traefik, nginx, Caddy) davor, der TLS terminiert
- [ ] **Firewall**: Nur Port 80/443 extern. Direkte DB-/Redis-/Backend-Ports gesperrt
- [ ] **API-Key erforderlich**: `DOCSTORE_API_KEY_REQUIRED=true`
- [ ] **Backup verifizieren**: Restore mindestens einmal im Dev-Env testen

### Empfohlen

- [ ] **Fail2ban** konfigurieren fuer Schutz gegen Brute-Force auf API-Keys
- [ ] **Log-Rotation**: `/etc/logrotate.d/docker-container` fuer Container-Logs
- [ ] **Monitoring**: Prometheus scraped `/health`-Endpunkt, Alert bei `status != healthy`
- [ ] **Updates**: Regelmaessig `docker compose pull` und Images neu bauen (Patches)
- [ ] **Netzwerk-Segmentierung**: Eigenes Docker-Netzwerk (ist Default), keine Verbindung zu `host` Network
- [ ] **Resource-Limits**: `BACKEND_MEM_LIMIT` in `.env` auf System-RAM anpassen

### Audit

- [ ] **DSGVO-Dokumentation**: Auftragsverarbeitung, Verzeichnis der Verarbeitungstaetigkeiten
- [ ] **Pen-Test** des Deployments durch qualifiziertes Personal
- [ ] **BSI-IT-Grundschutz**-Konformitaet pruefen (fuer kommunale Verwaltung)

---

## Troubleshooting

### Backend startet nicht — Healthcheck schlaegt fehl

```bash
docker compose logs backend --tail 50
```

Typische Ursachen:
- **`POSTGRES_PASSWORD` leer** — `.env` pruefen
- **DB noch nicht ready** — Healthcheck-Start-Period auf 60s erhoehen
- **Port 8000 belegt** — `BACKEND_PORT=127.0.0.1:8001` setzen

### Frontend zeigt "Backend nicht erreichbar"

```bash
# Backend aus Frontend-Container pingen
docker compose exec frontend wget -qO- http://backend:8000/health
```

Wenn keine Antwort: Backend-Logs pruefen, siehe oben.

### Uploads schlagen fehl mit "413 Request Entity Too Large"

nginx-Limit zu niedrig. In `frontend/nginx.conf`:
```nginx
client_max_body_size 200M;  # war 100M
```

Dann: `docker compose build frontend && docker compose up -d frontend`

### Celery-Worker laeuft nicht

```bash
docker compose --profile worker ps
docker compose logs worker --tail 30
```

Haeufig: `DOCSTORE_REDIS_URL` nicht erreichbar. Pruefen:
```bash
docker compose exec worker redis-cli -h redis ping
```

### Ollama-Modell nicht geladen

```bash
docker compose exec ollama ollama list
docker compose exec ollama ollama pull llama3.2
```

Falls Proxy-Probleme: Ollama nutzt eigene Proxy-Env. In `docker-compose.yml` beim `ollama`-Service ergaenzen:
```yaml
environment:
  HTTPS_PROXY: ${HTTPS_PROXY}
```

### Alle Daten zuruecksetzen (Dev-Umgebung)

```bash
make prune     # ACHTUNG: loescht alle Volumes!
make init
make build
make up
```

---

## Entwicklung

### Local-Dev ohne Docker

**Backend**

```bash
cd docstore-prod
python -m venv .venv
source .venv/bin/activate
pip install -e .
pip install asyncpg uvicorn pydantic-settings httpx celery redis slowapi
# SQLite als DB (kein Docker noetig):
export DOCSTORE_DATABASE_URL="sqlite+aiosqlite:///./data/docstore.db"
export DOCSTORE_API_KEY_REQUIRED=false
uvicorn app.main:app --reload
```

**Frontend**

```bash
cd docstore-prod/frontend
npm install
npm run dev
# http://localhost:5173, proxied zu http://localhost:8000
```

### Tests

```bash
# Im Container:
make test

# Lokal:
cd docstore-prod
python -m tests.test_all
```

---

## API-Dokumentation

Alle Endpunkte sind unter `/api/v1/...` erreichbar. Interaktive Docs unter `/api/v1/docs` (wenn aktiviert).

### Store-Management
- `GET/POST/PATCH/DELETE /stores` — Sammlungen verwalten
- `GET /stores/{id}/live-view` — Zusammenfassung mit Fakten, Takeaways, NER

### Dokumente
- `POST /documents/{store_id}/upload-sync` — Upload (sync, < 50 MB)
- `POST /documents/{store_id}/upload-async` — Upload (via Celery)
- `GET /documents/{store_id}` — Auflistung
- `GET /documents/detail/{doc_id}` — Details mit Chunks + Entitaeten

### Chat (RAG)
- `POST /stores/{id}/chat` — RAG-Anfrage mit Multi-Turn-Kontext
- `GET /stores/{id}/chat/providers` — Verfuegbare LLM-Provider

### Skills
- `GET /stores/{id}/skills` — Katalog (pptx, docx, blog, press, anon, planning)
- `POST /stores/{id}/skills/execute-sync` — Skill ausfuehren

### Planung
- `GET /stores/{id}/planning/tasks?category=wiki-maintenance|documents` — Gefiltert
- `POST /stores/{id}/planning/extract` — Neu extrahieren
- `POST /stores/{id}/planning/wiki-lint-to-tasks` — Lint-Issues → Tasks

### Wiki (nur WissensDB)
- `POST /stores/{id}/wiki/ingest/{doc_id}` — Dokument in Wiki integrieren
- `POST /stores/{id}/wiki/query` — Frage an Wiki
- `POST /stores/{id}/wiki/lint` — Health-Check
- `POST /stores/{id}/wiki/save-answer` — Chat-Antwort als Wiki-Seite
- `GET /stores/{id}/wiki/pages` / `/pages/{slug}` / `/log` — Lesen

---

## Lizenz & Support

Siehe `LICENSE` im Repository. Fuer Support und Anpassungen wenden Sie sich an das KI-Plattform-Team.

---

## Erweiterungen

Das Kern-Deployment laeuft auf HTTP Port 80 mit minimalem Stack. Fuer Produktion gibt es optionale Erweiterungen die per Overlay-Compose aktiviert werden.

### Traefik Reverse-Proxy mit HTTPS

**Fuer Public-facing Deployments.** Traefik terminiert TLS, holt automatisch Let's-Encrypt-Zertifikate, leitet HTTP auf HTTPS um und erzwingt Security-Headers.

```bash
# .env ergaenzen
echo "DOCSTORE_DOMAIN=docstore.example.com" >> .env
echo "TRAEFIK_ACME_EMAIL=admin@example.com" >> .env

# Traefik-Dashboard-Passwort generieren
htpasswd -nb admin SecretPass | sed -e 's/\$/\$\$/g' >> .env
# Value als TRAEFIK_DASHBOARD_AUTH eintragen

# Starten (Port 80/443 mussten frei sein)
make up-traefik
```

Enthaltene Middlewares (`deploy/traefik/dynamic.yml`):
- Security-Headers: HSTS, X-Frame-Options, CSP, Referrer-Policy
- Rate-Limiting: 100 req/min generell, 60 req/min fuer `/api/`
- TLS-Hardening: min. TLSv1.2, moderne Cipher-Suites, Perfect Forward Secrecy
- Optional: IP-Whitelist fuer internes Netz (`corporate-only`)

**Fuer Custom-Certs** (z.B. Wildcard von interner CA): Zertifikate in `deploy/traefik/certs/` ablegen und `TRAEFIK_USE_CUSTOM_CERTS=true` setzen.

### Monitoring: Prometheus + Grafana

Sammelt Metriken von Backend, PostgreSQL, Redis und Host. Dashboards werden automatisch provisioniert.

```bash
# Grafana-Admin-Passwort generieren
make grafana-password

# Monitoring-Stack starten
make up-monitoring
```

- Grafana: http://localhost:3000 (Login: `admin` / Passwort aus `.env`)
- Prometheus: http://localhost:9090

Enthaltene Services:
- `prometheus` — Scrape-Config fuer alle Services
- `grafana` — mit automatisch provisionierter Datasource und "Docstore Uebersicht" Dashboard (CPU, RAM, Disk, API Requests, Latency p95/p99, PG-Verbindungen, Redis-Memory)
- `node-exporter` — Host-Metriken
- `postgres-exporter` / `redis-exporter` — Service-spezifische Metriken

### CI/CD

Das Paket enthaelt Pipeline-Konfigurationen fuer:

- **GitHub Actions** (`.github/workflows/ci.yml`): Tests, Security-Scan (Trivy), Multi-Arch-Build (amd64+arm64), Push zu ghcr.io, Release-Tarball auf Tags
- **GitLab CI** (`.gitlab-ci.yml`): Vergleichbar, mit SSH-Deploy-Stages fuer Staging/Production und Corporate-Proxy-Support

Required Secrets (GitHub):
- automatisches `GITHUB_TOKEN` fuer Container-Registry

Required Variables (GitLab):
- `STAGING_HOST`, `STAGING_SSH_PRIVATE_KEY`
- `PROD_HOST`, `PROD_SSH_PRIVATE_KEY`
- `CI_HTTP_PROXY`, `CI_HTTPS_PROXY` (optional)

### Systemd-Integration (Bare-Metal)

Fuer Deployments ohne Container-Orchestrator: `systemd/`-Units fuer:

- `docstore.service` — startet `docker compose up -d` beim Boot, sauberes Shutdown
- `docstore-backup.service` + `docstore-backup.timer` — automatische Backups alle 6 Stunden

```bash
sudo cp systemd/*.{service,timer} /etc/systemd/system/
sudo cp .env /etc/default/docstore
sudo chmod 600 /etc/default/docstore
sudo systemctl daemon-reload
sudo systemctl enable --now docstore.service docstore-backup.timer
```
