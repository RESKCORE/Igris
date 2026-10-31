# OpsPilot Backend: Rules for the coding agent

## Product in one paragraph
OpsPilot is an agentic workflow dashboard for small business operations. An owner types a plain-language instruction; the system produces a reviewable plan; data is validated; exceptions go to a human; messages are sent through a controlled pipeline; every event is recorded in a tamper-evident audit trail. Everything is demonstrated on mock data, in SIMULATION mode by default, before any external action. Full spec: docs/PRD-v2-smb-workflow-agent.md. Read it before starting a stage.

## Non-negotiable architecture principle
The LLM only PLANS. Deterministic Python VALIDATES, ROUTES, EXECUTES and LOGS. No LLM or CrewAI agent may have a tool that sends, writes or deletes anything. Only the executor, through its guard, may cause side effects.

## Stack (do not substitute)
- Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (sync is fine), Alembic optional
- Database: DATABASE_URL env var. SQLite for local dev, Supabase PostgreSQL in deployment. Code must work on both.
- CrewAI for the planner (and optional reviewer) only; LLM via CrewAI `LLM` (Gemini by default, model name from env var LLM_MODEL), temperature 0
- Validation helpers: email-validator, phonenumbers
- httpx for outbound HTTP, smtplib for email, gspread for Google Sheets (sandbox/live only)
- pytest + FastAPI TestClient for tests
- No C++ code or C++-dependent suggestions.
- Free and open-source tooling only.

## Conventions
- Package layout exactly as in the PRD section 9.2 under backend/app/.
- Type hints everywhere. Pydantic models for all request/response bodies.
- API JSON uses snake_case. Error format: {"error": {"code": str, "message": str, "details": object}}.
- Config only through app/config.py reading environment variables (pydantic-settings). Provide .env.example. Never hardcode secrets.
- Every state change writes an audit event via app/audit.py. No exceptions.
- Defaults: MODE=simulation, ALLOW_LIVE=false, MAX_EXTERNAL_ACTIONS=20, SANDBOX_REDIRECT_TO unset.
- Small, focused modules. Docstrings on public functions. No dead code.
- After each stage: run `pytest`, start `uvicorn app.main:app --reload`, and confirm /health and /docs work.

## Safety rules (tests must enforce these)
1. Simulation mode never performs a network call for external actions.
2. Live mode requires BOTH confirm=true AND ALLOW_LIVE=true AND a recorded human approval event.
3. The server recomputes each task's risk from the catalog and ignores the model's value.
4. Unknown actions in a plan are dropped and logged.
5. Audit events are append-only: no update or delete code path exists.
6. Row data from datasets is never interpreted as instructions and never inserted into the planner prompt (only the schema is).

## Definition of done for any stage
Code runs, tests pass, endpoints documented in /docs, README section updated, and a short summary of what was built and what is next.
