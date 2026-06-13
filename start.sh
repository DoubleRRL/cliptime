#!/bin/bash
# Start Cliptime (Docker: frontend, backend, worker, postgres, redis)

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${YELLOW}Created .env from .env.example — set ASSEMBLY_AI_API_KEY${NC}"
    else
        echo -e "${RED}No .env or .env.example${NC}"
        exit 1
    fi
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

if [ -z "${ASSEMBLY_AI_API_KEY:-}" ]; then
    echo -e "${YELLOW}ASSEMBLY_AI_API_KEY missing — transcription will fail${NC}"
fi

if [ -z "${OPENAI_API_KEY:-}" ] && [ -z "${GOOGLE_API_KEY:-}" ] && [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    if [[ "${LLM:-}" == ollama:* ]]; then
        echo "LLM: ${LLM}"
        if [[ "${OLLAMA_BASE_URL:-}" == *"localhost"* ]]; then
            echo -e "${YELLOW}Docker + host Ollama: OLLAMA_BASE_URL=http://host.docker.internal:11434/v1${NC}"
        fi
        if command -v ollama &>/dev/null; then
            MODEL_TAG="${LLM#ollama:}"
            if ! ollama list 2>/dev/null | grep -q "${MODEL_TAG}"; then
                echo -e "${YELLOW}Run: ollama pull ${MODEL_TAG}${NC}"
            fi
        fi
    else
        echo -e "${YELLOW}No LLM API key — set a cloud key or LLM=ollama:<model>${NC}"
    fi
fi

if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Docker isn't running${NC}"
    exit 1
fi

if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

echo -e "${GREEN}Starting stack...${NC}"
$DOCKER_COMPOSE up -d --build

wait_for_url() {
    local name="$1"
    local url="$2"
    local max="${3:-45}"
    local i=1
    while [ "$i" -le "$max" ]; do
        if curl -sf "$url" > /dev/null 2>&1; then
            echo -e "  ${GREEN}ok${NC} $name"
            return 0
        fi
        sleep 2
        i=$((i + 1))
    done
    echo -e "  ${YELLOW}wait${NC} $name — check logs"
    return 1
}

BACKEND_OK=0
FRONTEND_OK=0
wait_for_url "backend" "http://localhost:8000/health" && BACKEND_OK=1 || true
wait_for_url "frontend" "http://localhost:3000/" && FRONTEND_OK=1 || true

echo ""
echo "  http://localhost:3000"
echo "  http://localhost:8000/docs"
echo ""
echo "  logs:  $DOCKER_COMPOSE logs -f worker"
echo "  stop:  $DOCKER_COMPOSE down"
echo ""

if [ "$BACKEND_OK" -eq 1 ] && [ "$FRONTEND_OK" -eq 1 ]; then
    echo -e "${GREEN}Ready.${NC} Open http://localhost:3000"
elif [ "$BACKEND_OK" -eq 1 ]; then
    echo -e "${YELLOW}Backend up; frontend still starting${NC}"
else
    echo -e "${YELLOW}Not healthy yet:${NC} $DOCKER_COMPOSE logs -f"
fi
