#!/bin/bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "=== XWiki Stack Setup ==="

# Check prerequisites
echo "[1/5] Checking prerequisites..."
command -v docker >/dev/null 2>&1 || { echo "ERROR: docker not found"; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "ERROR: docker compose not found"; exit 1; }

if [ ! -f .env ]; then
    echo "ERROR: .env file not found. Copy .env.example to .env and fill in values."
    exit 1
fi

# Create data directories
echo "[2/5] Creating data directories..."
mkdir -p data/postgres data/xwiki data/anythingllm

# Build custom images
echo "[3/5] Building custom images..."
docker compose build

# Pull external images
echo "[4/5] Pulling external images..."
docker compose pull db xwiki anythingllm

# Start stack
echo "[5/5] Starting stack..."
docker compose up -d

echo ""
echo "=== Stack started! ==="
echo ""
echo "Services starting up (XWiki takes ~2 min for first run):"
echo "  XWiki:       http://$(hostname -I | awk '{print $1}'):${XWIKI_PORT:-8085}"
echo "  Bridge API:  http://$(hostname -I | awk '{print $1}'):${BRIDGE_PORT:-8090}/docs"
echo "  AutoDoc API: http://$(hostname -I | awk '{print $1}'):${AUTODOC_PORT:-8091}/docs"
echo "  AnythingLLM: http://$(hostname -I | awk '{print $1}'):${ANYTHINGLLM_PORT:-3001}"
echo ""
echo "Check status: docker compose ps"
echo "View logs:    docker compose logs -f"
