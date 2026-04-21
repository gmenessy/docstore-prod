#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Agentischer Document Store — Installations-Skript
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Farbige Ausgabe
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[FEHLER]${NC} $*" >&2; exit 1; }

# ═══ 1. System-Pruefung ═══
info "1/6 System-Anforderungen pruefen..."

command -v docker >/dev/null || error "Docker ist nicht installiert. Siehe https://docs.docker.com/engine/install/"
docker compose version >/dev/null 2>&1 || error "Docker Compose v2 fehlt."

DOCKER_VERSION=$(docker version --format '{{.Server.Version}}' 2>/dev/null || echo "unknown")
info "    Docker: $DOCKER_VERSION"

# RAM-Check (mind. 4 GB)
if command -v free >/dev/null; then
    RAM_GB=$(free -g | awk '/^Mem:/ {print $2}')
    if [ "$RAM_GB" -lt 4 ]; then
        warn "    Nur ${RAM_GB}GB RAM verfuegbar. Empfohlen sind 4GB+ (16GB mit LLM)."
    else
        info "    RAM: ${RAM_GB}GB"
    fi
fi

# Plattenplatz (mind. 20 GB frei)
DISK_GB=$(df -BG . | awk 'NR==2 {gsub("G",""); print $4}')
if [ "$DISK_GB" -lt 20 ]; then
    warn "    Nur ${DISK_GB}GB freier Plattenplatz. Empfohlen sind 20GB+."
else
    info "    Platte: ${DISK_GB}GB frei"
fi

# ═══ 2. .env einrichten ═══
info "2/6 Konfiguration..."

if [ ! -f .env ]; then
    cp .env.example .env
    chmod 600 .env
    info "    .env erstellt."

    # Passwoerter generieren
    if command -v openssl >/dev/null; then
        PG_PASS=$(openssl rand -hex 24)
        API_KEY=$(openssl rand -hex 32)
        sed -i "s|<HIER-STARKES-PASSWORT-EINSETZEN>|${PG_PASS}|g" .env
        sed -i "s|<HIER-API-KEY-EINSETZEN>|${API_KEY}|g" .env
        info "    Passwort und API-Key generiert."
        echo ""
        warn "    API-Key (bitte sicher aufbewahren):"
        echo ""
        echo "    ${API_KEY}"
        echo ""
    else
        warn "    openssl nicht gefunden. Bitte .env manuell bearbeiten!"
    fi
else
    info "    .env existiert bereits, wird nicht ueberschrieben."
fi

# ═══ 3. Images bauen ═══
info "3/6 Docker-Images bauen (kann einige Minuten dauern)..."

# Proxy-Args aus Environment uebernehmen
BUILD_ARGS=""
[ -n "${HTTP_PROXY:-}" ]  && BUILD_ARGS="$BUILD_ARGS --build-arg HTTP_PROXY=$HTTP_PROXY"
[ -n "${HTTPS_PROXY:-}" ] && BUILD_ARGS="$BUILD_ARGS --build-arg HTTPS_PROXY=$HTTPS_PROXY"

# shellcheck disable=SC2086
docker compose build --pull $BUILD_ARGS

# ═══ 4. Scripts ausfuehrbar machen ═══
info "4/6 Scripts vorbereiten..."
chmod +x scripts/*.sh

# ═══ 5. Services starten ═══
info "5/6 Services starten..."
docker compose up -d

# ═══ 6. Health-Check ═══
info "6/6 Services starten, warte auf Healthcheck..."
echo ""

MAX_WAIT=120
COUNTER=0
while [ $COUNTER -lt $MAX_WAIT ]; do
    if docker compose ps --format json 2>/dev/null | grep -q '"Health":"healthy"'; then
        HEALTHY_COUNT=$(docker compose ps --format json 2>/dev/null | grep -c '"Health":"healthy"' || echo 0)
        info "    ${HEALTHY_COUNT} Services healthy..."
        if [ "$HEALTHY_COUNT" -ge 3 ]; then
            break
        fi
    fi
    sleep 5
    COUNTER=$((COUNTER + 5))
done

echo ""
info "═══ Installation abgeschlossen ═══"
echo ""
echo "Frontend:    http://localhost"
echo "API-Status:  http://localhost/health"
echo ""
echo "Weitere Befehle:"
echo "  make ps       # Container-Status"
echo "  make logs     # Live-Logs"
echo "  make health   # Healthcheck"
echo "  make backup   # Backup erstellen"
echo "  make down     # Stoppen"
echo ""
warn "Wichtig: .env nach /etc/default/docstore kopieren wenn systemd-Integration gewuenscht:"
echo "  sudo cp .env /etc/default/docstore"
echo "  sudo chmod 600 /etc/default/docstore"
