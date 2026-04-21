# ═══════════════════════════════════════════════════════════════
# Agentischer Document Store — Makefile
# Haeufige Operationen fuer Development & Deployment
# ═══════════════════════════════════════════════════════════════

.PHONY: help init build up down restart logs test backup restore \
        shell-backend shell-db clean prune pull ps health llm-pull \
        up-traefik up-monitoring logs-traefik grafana-password

# Default target
help:
	@echo "Agentischer Document Store — Make Targets"
	@echo ""
	@echo "  Setup:"
	@echo "    make init           .env aus .env.example erstellen"
	@echo "    make build          Docker-Images bauen"
	@echo "    make llm-pull       Ollama-Modell herunterladen (llama3.2)"
	@echo ""
	@echo "  Betrieb:"
	@echo "    make up             Services starten (Basic)"
	@echo "    make up-llm         Mit Ollama-LLM"
	@echo "    make up-full        Alle Services (LLM + Worker + Vectors)"
	@echo "    make down           Services stoppen"
	@echo "    make restart        Services neu starten"
	@echo "    make ps             Status aller Services"
	@echo "    make health         Healthcheck-Status"
	@echo ""
	@echo "  Logs & Debug:"
	@echo "    make logs           Alle Logs (follow)"
	@echo "    make logs-backend   Nur Backend-Logs"
	@echo "    make shell-backend  Shell im Backend-Container"
	@echo "    make shell-db       psql in der Datenbank"
	@echo ""
	@echo "  Daten:"
	@echo "    make backup         Vollsicherung (DB + Files)"
	@echo "    make restore TS=... Restore eines Backups"
	@echo "    make test           API-Tests ausfuehren"
	@echo ""
	@echo "  Erweiterungen:"
	@echo "    make up-traefik       Mit Traefik-Reverse-Proxy (HTTPS)"
	@echo "    make up-monitoring    Prometheus + Grafana Dashboards"
	@echo ""
	@echo "  Wartung:"
	@echo "    make pull           Neue Images holen"
	@echo "    make clean          Volumes behalten, Container entfernen"
	@echo "    make prune          ALLES entfernen (Achtung, Datenverlust!)"

init:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		chmod 600 .env; \
		echo ".env wurde aus .env.example erstellt."; \
		echo "Bitte POSTGRES_PASSWORD und DOCSTORE_API_KEY setzen."; \
	else \
		echo ".env existiert bereits."; \
	fi

build:
	docker compose build --pull

up:
	docker compose up -d
	@echo ""
	@echo "Services gestartet. Frontend: http://localhost"
	@echo "API-Docs:  http://localhost/api/v1/docs (wenn aktiviert)"
	@echo "Health:    http://localhost/health"

up-llm:
	docker compose --profile llm up -d

up-full:
	docker compose --profile llm --profile worker --profile vectors up -d

down:
	docker compose down

restart:
	docker compose restart

ps:
	docker compose ps

health:
	@echo "─── Backend ───"
	@curl -sf http://localhost/health | head -20 || echo "Backend nicht erreichbar"
	@echo ""
	@echo "─── Container-Status ───"
	@docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Health}}"

logs:
	docker compose logs -f

logs-backend:
	docker compose logs -f backend

logs-frontend:
	docker compose logs -f frontend

shell-backend:
	docker compose exec backend /bin/bash

shell-db:
	docker compose exec postgres psql -U docstore -d docstore

backup:
	@bash scripts/backup.sh

restore:
	@if [ -z "$(TS)" ]; then \
		echo "Usage: make restore TS=20260417-140530"; \
		exit 1; \
	fi
	@bash scripts/restore.sh $(TS)

test:
	docker compose exec backend python -m tests.test_all

llm-pull:
	@echo "Ollama-Modelle herunterladen..."
	docker compose --profile llm up -d ollama
	@sleep 5
	docker compose exec ollama ollama pull llama3.2
	docker compose exec ollama ollama pull nomic-embed-text
	@echo "Modelle bereit."

pull:
	docker compose pull

up-traefik:
	@if [ -z "$$(grep DOCSTORE_DOMAIN .env 2>/dev/null)" ]; then \
		echo "FEHLER: DOCSTORE_DOMAIN in .env setzen (z.B. docstore.example.com)"; \
		exit 1; \
	fi
	docker compose -f docker-compose.yml -f deploy/traefik/docker-compose.traefik.yml up -d
	@echo ""
	@echo "Traefik aktiv. HTTPS ueber: https://$$(grep DOCSTORE_DOMAIN .env | cut -d= -f2)"

up-monitoring:
	docker compose -f docker-compose.yml -f deploy/monitoring/docker-compose.monitoring.yml up -d
	@echo ""
	@echo "Grafana:    http://localhost:3000 (admin/\$${GRAFANA_ADMIN_PASSWORD})"
	@echo "Prometheus: http://localhost:9090"

logs-traefik:
	docker compose -f docker-compose.yml -f deploy/traefik/docker-compose.traefik.yml logs -f traefik

grafana-password:
	@PASS=$$(openssl rand -hex 16); \
		echo "GRAFANA_ADMIN_PASSWORD=$$PASS" >> .env; \
		echo "Neues Grafana-Admin-Passwort gesetzt: $$PASS"

clean:
	docker compose down --remove-orphans

prune:
	@read -p "ALLE Daten werden geloescht (DB, Uploads, Outputs). Fortfahren? (ja/nein): " confirm && [ "$$confirm" = "ja" ]
	docker compose down -v --remove-orphans
