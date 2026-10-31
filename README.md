# Igris — OpsPilot

Agentic workflow dashboard for small business operations. An owner types a plain-language instruction; the LLM produces a reviewable plan; deterministic Python validates, routes, executes, and logs; exceptions go to a human; every event is recorded in a tamper-evident hash-chained audit trail. Everything runs on mock data in **simulation mode by default**.

**Core principle:** the LLM only plans. No agent has tools that send, write, or delete anything — only the executor, through its guard, can cause side effects. Full spec: [docs/PRD-v2-smb-workflow-agent.md](docs/PRD-v2-smb-workflow-agent.md).

## Stack

- **Backend** — Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (SQLite by default), CrewAI planner (Gemini via OpenRouter fallback)
- **Frontend** — TypeScript + Vite (TanStack Start), shadcn/ui
- **Tests** — pytest (backend), vitest (frontend)
- **Run both** — `run_all.py` one-command launcher with smoke mode

## Quick start

### One command (both servers)

```bash
python run_all.py            # backend + frontend, Ctrl+C stops both
python run_all.py --smoke    # start, verify health, exit
```

### Manual

**Backend** (Python 3.11+):

```bash
cd backend
python -m venv .venv && .venv\Scripts\Activate.ps1   # or source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                                # then edit settings
uvicorn app.main:app --reload --port 8000
```

- Swagger UI: http://localhost:8000/docs
- Health check: http://localhost:8000/health

**Frontend**:

```bash
cd frontend
bun install        # or npm install
bun run dev        # http://localhost:8080
```

Set `VITE_API_URL` in `frontend/.env` to point at the backend.

## Configuration

All config comes from `backend/.env` (see `backend/.env.example`):

- `DATABASE_URL` — SQLite file locally; any SQL server URL for deployment
- `MODE=simulation` / `ALLOW_LIVE=false` — live external actions require simulation off, `ALLOW_LIVE=true`, explicit confirmation, and a recorded human approval event; sandbox redirects all messages via `SANDBOX_REDIRECT_TO`
- `OPENROUTER_API_KEY` + `LLM_MODEL` — planner LLM (free models supported); `USE_CACHED_PLANS=true` uses known-good plans without an LLM
- Optional integrations: Gmail SMTP, Telegram, Google Sheets, Web3Forms owner notifications

## Layout

```
backend/    FastAPI app (app/), tests, planner, audit chain, .env.example
frontend/   dashboard UI (Vite + TanStack + shadcn/ui)
docs/       PRD v2 (full product spec)
data/       seeded demo dataset notes
run_all.py  single-command launcher (backend + frontend)
```

## Tests

```bash
cd backend && .venv\Scripts\Activate.ps1; pytest
cd frontend && bun run test
```

Safety tests enforce: no network calls in simulation, guarded live mode, server-side risk recomputation, unknown actions dropped, append-only audit, and datasets never injected into planner prompts.
