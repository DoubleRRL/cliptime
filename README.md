# Cliptime

Self-hosted AI clipper. Upload or link a long video; get vertical clips with burned-in subtitles. No watermark, no subscription.

## Quick start

**Requires:** Docker, [AssemblyAI](https://www.assemblyai.com/) API key, and Ollama or a cloud LLM key.

```bash
git clone https://github.com/DoubleRRL/cliptime.git
cd cliptime
cp .env.example .env    # set ASSEMBLY_AI_API_KEY
./start.sh
```

Equivalent: `docker compose up -d --build`

| Service | URL |
|---------|-----|
| App | http://localhost:3000 |
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |

Local/self-host mode skips sign-in.

## Minimum `.env`

```env
ASSEMBLY_AI_API_KEY=your_key
LLM=ollama:llama3.2:3b
OLLAMA_BASE_URL=http://host.docker.internal:11434/v1   # Docker → Ollama on host
```

Cloud LLM instead: set `LLM` and the matching provider key (`GOOGLE_API_KEY`, `OPENAI_API_KEY`, or `ANTHROPIC_API_KEY`). See [`.env.example`](.env.example).

## Repo layout

| Path | What it is |
|------|------------|
| `backend/` | FastAPI API + ARQ video worker |
| `frontend/` | Next.js UI and auth |
| `docker-compose.yml` | All services wired together |
| `init.sql` | Database schema |
| `start.sh` | Bootstrap script (env check + compose up + health wait) |
| `AGENTS.md` | Contributor/agent reference (architecture, conventions) |

Drop fonts in `backend/fonts/`, transitions in `backend/transitions/` — they show up in the app automatically.

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Stuck on queued | `docker compose logs -f worker` |
| LLM errors | Ollama running? Model pulled? (`ollama pull …`) |
| Changed `.env` | `docker compose up -d --build` |
| Bad DB state | `docker compose down -v` (wipes data) then up again |

## Tests

```bash
make test              # backend pytest + frontend vitest
make test-e2e          # Playwright (needs stack running)
```

## License

AGPL-3.0 — see [LICENSE](LICENSE).
