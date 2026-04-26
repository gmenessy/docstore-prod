#!/bin/bash
# Automatisches Test-Coverage Reporting

set -e

echo "=========================================="
echo "Test-Coverage Analysis & Reporting"
echo "=========================================="
echo ""

# Farben
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Prüfe ob pytest und coverage installiert sind
echo -e "${BLUE}Prüfe Dependencies...${NC}"
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}pytest nicht gefunden. Installiere...${NC}"
    pip install pytest pytest-cov pytest-asyncio
fi

echo -e "${GREEN}✓ Dependencies vorhanden${NC}"
echo ""

# ─── Test-Execution ───
echo -e "${BLUE}Führe Tests mit Coverage aus...${NC}"
echo ""

# Tests mit Coverage ausführen
docker compose exec -T backend python -m pytest \
    tests/ \
    --cov=app \
    --cov-report=term-missing \
    --cov-report=html:htmlcov \
    --cov-report=json:coverage.json \
    --asyncio-mode=auto \
    -v \
    --tb=short \
    --maxfail=5 \
    | tee test_results.log

TEST_EXIT_CODE=${PIPESTATUS[0]}

echo ""
echo "=========================================="
echo "Test-Coverage Report"
echo "=========================================="
echo ""

# Coverage JSON auslesen
if [ -f "coverage.json" ]; then
    TOTAL_COVERAGE=$(python -c "import json; print(json.load(open('coverage.json'))['totals']['percent_covered'])")
    echo -e "Total Coverage: ${BLUE}${TOTAL_COVERAGE}%${NC}"
    echo ""

    # Coverage pro Modul
    echo -e "${BLUE}Coverage pro Modul:${NC}"
    python << 'EOFPYTHON'
import json
from pathlib import Path

coverage = json.load(open("coverage.json"))

# Module mit < 80% Coverage hervorheben
for filename, data in coverage['files'].items():
    pct = data['summary']['percent_covered']
    if pct < 80:
        print(f"  ❌ {filename}: {pct:.1f}%")
    elif pct < 90:
        print(f"  ⚠️  {filename}: {pct:.1f}%")
    else:
        print(f"  ✅ {filename}: {pct:.1f}%")
EOFPYTHON

    echo ""

    # Prüfen ob 80% erreicht wurden
    COVERAGE_INT=$(echo "$TOTAL_COVERAGE" | cut -d. -f1)
    if [ "$COVERAGE_INT" -ge 80 ]; then
        echo -e "${GREEN}✅ Coverage-Ziel erreicht: ${TOTAL_COVERAGE}% >= 80%${NC}"
        EXIT_CODE=0
    else
        echo -e "${YELLOW}⚠️  Coverage-Ziel nicht erreicht: ${TOTAL_COVERAGE}% < 80%${NC}"
        echo "Weitere Tests erforderlich"
        EXIT_CODE=1
    fi

else
    echo -e "${RED}Coverage Report nicht gefunden${NC}"
    EXIT_CODE=1
fi

echo ""

# Test-Results analysieren
echo -e "${BLUE}Test-Results:${NC}"
PASSED=$(grep -c "PASSED" test_results.log || echo "0")
FAILED=$(grep -c "FAILED" test_results.log || echo "0")
ERRORS=$(grep -c "ERROR" test_results.log || echo "0")
TOTAL=$(grep -c "test_" test_results.log || echo "0")

echo "  Passed: $PASSED"
echo "  Failed: $FAILED"
echo "  Errors: $ERRORS"
echo "  Total:  $TOTAL"

if [ "$FAILED" -gt 0 ] || [ "$ERRORS" -gt 0 ]; then
    echo -e "${RED}✗ Einige Tests fehlgeschlagen${NC}"
    EXIT_CODE=1
else
    echo -e "${GREEN}✓ Alle Tests bestanden${NC}"
fi

echo ""

# ─── Detailed Report ───
echo -e "${BLUE}Detaillierter Coverage-Report:${NC}"
echo ""
echo "HTML-Report: htmlcov/index.html"
echo "JSON-Report: coverage.json"
echo ""

# Top-3 Module mit niedrigster Coverage identifizieren
if [ -f "coverage.json" ]; then
    echo -e "${YELLOW}Module mit niedrigster Coverage (Top 3):${NC}"
    python << 'EOFPYTHON'
import json

coverage = json.load(open("coverage.json"))

# Module nach Coverage sortieren
modules = []
for filename, data in coverage['files'].items():
    pct = data['summary']['percent_covered']
    modules.append((filename, pct))

modules.sort(key=lambda x: x[1])  # Aufsteigend sortieren

for i, (filename, pct) in enumerate(modules[:3]):
    print(f"  {i+1}. {filename}: {pct:.1f}%")
EOFPYTHON

    echo ""
fi

# ─── Recommendations ───
echo -e "${BLUE}Empfehlungen:${NC}"

if [ "$COVERAGE_INT" -lt 80 ]; then
    cat << 'EOF'
  1. Füge weitere Tests für Module mit < 80% Coverage hinzu
  2. Implementiere Edge-Case Tests
  3. Füge Integration-Tests hinzu
  4. Teste Error-Handling und Exceptions
EOF
elif [ "$COVERAGE_INT" -lt 90 ]; then
    cat << 'EOF'
  1. Füge Tests für Boundary Conditions hinzu
  2. Implementiere Performance-Tests
  3. Teste Concurrent Operations
EOF
else
    cat << 'EOF'
  1. Fokus auf Security-Tests
  2. Implementiere End-to-End Tests
  3. Füge Stress-Tests hinzu
EOF
fi

echo ""

# ─── System-Health Check ───
echo -e "${BLUE}System-Health Check:${NC}"

# API-Health prüfen
HEALTH=$(curl -s http://localhost:8000/health | jq -r '.status' 2>/dev/null || echo "unknown")

if [ "$HEALTH" = "healthy" ]; then
    echo -e "  ${GREEN}✓ API Status: healthy${NC}"
else
    echo -e "  ${YELLOW}⚠️  API Status: $HEALTH${NC}"
fi

# Database-Connection prüfen
DB_OK=$(docker compose exec -T postgres pg_isready -U docstore 2>/dev/null | grep -c "accepting" || echo "0")

if [ "$DB_OK" -gt 0 ]; then
    echo -e "  ${GREEN}✓ Database: connected${NC}"
else
    echo -e "  ${RED}✗ Database: not connected${NC}"
fi

echo ""

# ─── Summary ───
echo "=========================================="
if [ "$EXIT_CODE" -eq 0 ]; then
    echo -e "${GREEN}✓ Test-Coverage Analyse erfolgreich${NC}"
else
    echo -e "${YELLOW}⚠️  Test-Coverage Verbesserung erforderlich${NC}"
fi
echo "=========================================="
echo ""

exit $EXIT_CODE
