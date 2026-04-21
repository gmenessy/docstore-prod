# syntax=docker/dockerfile:1.6
# ═══════════════════════════════════════════════════════════════
# Agentischer Document Store — Frontend Dockerfile (Production)
# Multi-Stage: Node Build → nginx Serve mit Reverse-Proxy
# ═══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────
# Stage 1: Build — Vite kompiliert React-App
# ─────────────────────────────────────────────────
FROM node:20-alpine AS builder

ARG HTTP_PROXY=""
ARG HTTPS_PROXY=""
ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    npm_config_proxy=${HTTP_PROXY} \
    npm_config_https_proxy=${HTTPS_PROXY}

WORKDIR /build

# Dependencies zuerst (Layer-Cache)
COPY package.json ./
RUN npm install --no-audit --no-fund

# Source-Code + Build
COPY vite.config.js index.html ./
COPY src/ ./src/
RUN npm run build


# ─────────────────────────────────────────────────
# Stage 2: Serve — nginx mit Reverse-Proxy
# ─────────────────────────────────────────────────
FROM nginx:1.27-alpine AS runtime

LABEL org.opencontainers.image.title="Agentischer Document Store Frontend" \
      org.opencontainers.image.version="1.0.0"

# nginx-Konfiguration
RUN rm -f /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Runtime-Config-Templating
# Der envsubst-Aufruf beim Start ersetzt __API_BASE__ und __API_KEY__
# in der index.html mit Umgebungsvariablen.
COPY --from=builder /build/dist /usr/share/nginx/html

# Start-Skript: Runtime-Config einsetzen, dann nginx starten
COPY entrypoint.sh /docker-entrypoint.d/40-config-template.sh
RUN chmod +x /docker-entrypoint.d/40-config-template.sh

# Non-root User (nginx laeuft schon als nginx-User intern)
EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost/ > /dev/null 2>&1 || exit 1
