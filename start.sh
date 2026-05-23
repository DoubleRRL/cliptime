#!/bin/bash

# SupoClip - Quick Start Script
# Starts the full Docker stack: frontend, backend, worker, postgres, redis

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================"
echo "  SupoClip - AI Video Clipping Tool"
echo "============================================"
echo ""

# Create .env from template if missing
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo -e "${YELLOW}No .env found — copying from .env.example${NC}"
        cp .env.example .env
        echo "Edit .env and set ASSEMBLY_AI_API_KEY (required) and your LLM settings."
        echo ""
    else
        echo -e "${RED}Error: .env file not found and no .env.example to copy.${NC}"
        exit 1
    fi
fi

# Load env for checks (ignore comments / export issues)
set -a
# shellcheck disable=SC1091
source .env
set +a

if [ -z "${ASSEMBLY_AI_API_KEY:-}" ]; then
    echo -e "${YELLOW}Warning: ASSEMBLY_AI_API_KEY is not set in .env${NC}"
    echo "Transcription will fail until you add a key from https://www.assemblyai.com/"
    echo ""
fi

if [ -z "${OPENAI_API_KEY:-}" ] && [ -z "${GOOGLE_API_KEY:-}" ] && [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    if [[ "${LLM:-}" == ollama:* ]]; then
        echo -e "${GREEN}LLM: ${LLM} (local Ollama)${NC}"
        # Docker containers must reach the host Ollama process
        if [[ "${OLLAMA_BASE_URL:-}" == *"localhost"* ]]; then
            echo -e "${YELLOW}Tip: For Docker on Mac/Windows, set in .env:${NC}"
            echo "  OLLAMA_BASE_URL=http://host.docker.internal:11434/v1"
            echo ""
        fi
        if command -v ollama &>/dev/null; then
            MODEL_TAG="${LLM#ollama:}"
            if ! ollama list 2>/dev/null | grep -q "${MODEL_TAG}"; then
                echo -e "${YELLOW}Model '${MODEL_TAG}' not found locally. Run:${NC}"
                echo "  ollama pull ${MODEL_TAG}"
                echo ""
            fi
        fi
    else
        echo -e "${YELLOW}Warning: No AI provider API key is set in .env${NC}"
        echo "Set OPENAI_API_KEY, GOOGLE_API_KEY, ANTHROPIC_API_KEY, or LLM=ollama:<model>"
        echo ""
    fi
fi

if [ -z "${BACKEND_AUTH_SECRET:-}" ] || [ "${BACKEND_AUTH_SECRET}" = "change_me_backend_auth_secret" ]; then
    echo -e "${YELLOW}Warning: BACKEND_AUTH_SECRET is unset or still the placeholder.${NC}"
    echo "Frontend → backend auth may fail until you set a random secret in .env"
    echo ""
fi

if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running!${NC}"
    echo "Start Docker Desktop and try again."
    exit 1
fi

if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

echo -e "${GREEN}Building and starting Docker containers...${NC}"
echo "(First run can take several minutes)"
echo ""

$DOCKER_COMPOSE up -d --build

echo ""
echo -e "${GREEN}Waiting for services to become healthy...${NC}"

wait_for_url() {
    local name="$1"
    local url="$2"
    local max_attempts="${3:-30}"
    local attempt=1
    while [ "$attempt" -le "$max_attempts" ]; do
        if curl -sf "$url" > /dev/null 2>&1; then
            echo -e "  ${GREEN}✓${NC} $name"
            return 0
        fi
        sleep 2
        attempt=$((attempt + 1))
    done
    echo -e "  ${YELLOW}✗${NC} $name (not ready — check logs)"
    return 1
}

BACKEND_OK=0
FRONTEND_OK=0
wait_for_url "Backend API" "http://localhost:8000/health" 45 && BACKEND_OK=1 || true
wait_for_url "Frontend" "http://localhost:3000/" 45 && FRONTEND_OK=1 || true

echo ""
echo "Services:"
echo "  - Frontend:   http://localhost:3000"
echo "  - Backend:    http://localhost:8000"
echo "  - API docs:   http://localhost:8000/docs"
echo "  - Postgres:   localhost:5432"
echo "  - Redis:      localhost:6379"
echo ""
echo "Containers: frontend, backend, worker, postgres, redis"
echo ""
echo "Useful commands:"
echo "  $DOCKER_COMPOSE ps"
echo "  $DOCKER_COMPOSE logs -f worker    # clip processing / AI"
echo "  $DOCKER_COMPOSE logs -f backend"
echo "  $DOCKER_COMPOSE down"
echo ""

if [ "$BACKEND_OK" -eq 1 ] && [ -f backend/scripts/smoke_dual_tier.py ]; then
    echo "Running offline AI smoke check..."
    if $DOCKER_COMPOSE run --rm --no-deps \
        -v "$SCRIPT_DIR/backend/scripts:/app/scripts" \
        -v "$SCRIPT_DIR/backend/src:/app/src" \
        backend .venv/bin/python /app/scripts/smoke_dual_tier.py; then
        echo -e "${GREEN}AI smoke check passed.${NC}"
    else
        echo -e "${YELLOW}AI smoke check had warnings (see above). Stack may still work.${NC}"
    fi
    echo ""
fi

if [ "$BACKEND_OK" -eq 1 ] && [ "$FRONTEND_OK" -eq 1 ]; then
    echo -e "${GREEN}Ready to test!${NC}"
    echo "  1. Open http://localhost:3000"
    echo "  2. Sign up / log in"
    echo "  3. Upload a video (or paste a URL)"
    echo "  4. Choose caption template: OpusClip Style"
    echo "  5. Watch progress: $DOCKER_COMPOSE logs -f worker"
elif [ "$BACKEND_OK" -eq 1 ]; then
    echo -e "${YELLOW}Backend is up; frontend still starting. Open http://localhost:3000 in a minute.${NC}"
else
    echo -e "${YELLOW}Some services are not healthy yet:${NC}"
    echo "  $DOCKER_COMPOSE logs -f"
fi

echo ""
echo "============================================"
