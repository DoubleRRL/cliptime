# Repository Guidelines

Cliptime is a self-hosted AI clipper (FastAPI + ARQ worker + Next.js). Long-form video in; transcribed, segmented by an LLM, rendered as vertical clips with subtitles.

## Root files

| Path | Purpose |
|------|---------|
| `docker-compose.yml` | Runs frontend, backend API, ARQ worker, PostgreSQL, Redis |
| `init.sql` | PostgreSQL schema (tasks, clips, sources + Better Auth tables) |
| `.env.example` | Environment template — copy to `.env` |
| `start.sh` | Creates `.env` if missing, builds stack, waits on `/health` |
| `Makefile` | `make test`, `make test-backend`, `make test-frontend`, `make test-e2e` |
| `README.md` | Human quickstart and troubleshooting |

## `backend/`

| Path | Purpose |
|------|---------|
| `src/main_refactored.py` | FastAPI app entry (use this, not legacy `main.py`) |
| `src/api/routes/` | HTTP handlers (`tasks`, `media`, `models`, `admin`, …) |
| `src/services/` | Business logic (`task_service`, `video_service`) |
| `src/repositories/` | Raw SQL via asyncpg (no ORM for app tables) |
| `src/workers/` | ARQ worker (`process_video_task`, progress via Redis → SSE) |
| `src/ai.py` | LLM clip selection; signal-first path for Ollama |
| `src/video_utils.py` | Clip render, crop, subtitles, face/speaker layout |
| `fonts/`, `transitions/` | Drop-in `.ttf` / `.mp4` assets (auto-listed by API) |
| `migrations/` | SQL migrations applied outside `init.sql` on existing DBs |
| `tests/` | `unit/` and `integration/` pytest suites |

Local run: `uv sync` → `uvicorn src.main_refactored:app --reload --port 8000` + `arq src.workers.tasks.WorkerSettings` (needs Postgres, Redis, ffmpeg).

## `frontend/`

| Path | Purpose |
|------|---------|
| `src/app/` | Next.js App Router pages and API proxies to backend |
| `src/components/` | UI (`console/` = main clip workspace) |
| `src/lib/` | Shared helpers, auth, API clients |
| `prisma/` | Better Auth schema and migrations |
| `e2e/` | Playwright smoke tests |

Local run: `bun install` → `bun run dev` (port 3000).

## Flow

```
Browser → Next.js (:3000) → FastAPI (:8000) → Redis → ARQ worker
                              ↓                      ↓
                         PostgreSQL ←────────────────┘
```

Task `POST` returns immediately; worker processes async; frontend uses SSE for progress.

## Commands

```bash
docker compose up -d --build    # full stack
docker compose logs -f worker   # clip pipeline debug
make test                       # backend + frontend unit tests
```

## Code style

- Python: 4 spaces, `snake_case`, type hints where useful; `uv` not pip.
- TypeScript: 2 spaces, `PascalCase` components, `@/*` imports.
- Lint: `cd frontend && bun run lint`.

## Tests

- Backend: `cd backend && uv run pytest`
- Frontend: `cd frontend && bun run test:coverage` and `bun run test:e2e`
- CI: `.github/workflows/tests.yml`

## Commits & PRs

Prefer `type(scope): summary` (e.g. `feat(backend): add clip re-render`). PRs: what/why, env impact, screenshots for UI, verification steps.

## Secrets

Never commit `.env`. Required: `ASSEMBLY_AI_API_KEY` plus cloud LLM key **or** `LLM=ollama:*` with Ollama reachable from the worker container (`OLLAMA_BASE_URL`).
