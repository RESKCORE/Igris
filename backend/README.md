# OpsPilot Backend (FastAPI + CrewAI)

OpsPilot is an agentic workflow dashboard for small business operations. An owner types a plain-language instruction; the system produces a reviewable plan; data is validated; exceptions go to a human; messages are sent through a controlled pipeline; every event is recorded in a tamper-evident audit trail. Everything is demonstrated on mock data in SIMULATION mode by default before any external action.

## Core Principles
- **The LLM only PLANS**: Deterministic Python validates, routes, executes, and logs.
- **Safety First**: Simulation mode never performs external network calls; Live mode is strictly guarded.
- **Tamper-Evident Audit**: Every state transition and data mutation writes to a cryptographic SHA-256 hash-chained log.

## Quick Start

### 1. Requirements
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or standard `pip`

### 2. Setup Virtual Environment & Install Dependencies
```bash
# Inside backend/
uv venv
# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

uv pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### 4. Run Tests
```bash
pytest
```

### 5. Start Development Server
```bash
uvicorn app.main:app --reload --port 8000
```
- Swagger UI / OpenAPI docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health check: [http://localhost:8000/health](http://localhost:8000/health)

## Stage 5: Planner (CrewAI + OpenRouter)

An owner types a plain-language instruction and `POST /runs` returns a reviewable plan.

- **Planner** (`app/planner/planner.py`): builds a **schema-only** prompt (dataset columns/types, action catalog, template names - never row contents), calls CrewAI `Agent`/`Task` with `output_pydantic=PlanSchema` over an OpenRouter free model (temperature 0, no tools, no delegation).
- **Deterministic plan guard** (`app/planner/plan_guard.py`, PRD 12.2): drops unknown actions, validates params against catalog schemas, **recomputes risk server-side** (model value ignored), strips dangling `depends_on` references, deletes cycle-blocked tasks, requires every external task to be preceded by a read/draft ancestor, and enforces `MAX_EXTERNAL_ACTIONS`.
- **Cached plans** (`app/planner/cached_plans.py`): known-good plans for the three demo scenarios (overdue invoices, order intake, booking conflicts). Used as fast path when `USE_CACHED_PLANS=true` and as automatic fallback when the LLM fails; unmatched instructions fail gracefully with `502 planner_unavailable`.
- **Routes** (`app/routes/runs.py`): `POST /runs` persists Run -> Plan(version 1) -> mirrored Task rows and writes an audited `plan_created` event; `GET /runs/{id}` returns run state plus the latest plan.

State machine: `CREATED -> PLANNED -> PLAN_APPROVED -> COMPLETED` (exceptions gate the human queue; see the pipeline table above).

## Frontend Integration (full pipeline API)

The dashboard frontend connects with `VITE_API_URL` (see `frontend/.env.example`). Startup seeds demo datasets, templates, and users, so a fresh SQLite file works out of the box.

Endpoints beyond Stage 5 (all JSON, snake_case):

| Area | Route | Purpose |
| --- | --- | --- |
| Runs | `GET /runs` | List runs (newest first) |
| Runs | `PUT /runs/{id}/plan` | Human plan edit; plan guard re-checks and bumps the version |
| Runs | `POST /runs/{id}/approve` | Records human approval + audit event |
| Exceptions | `GET /exceptions`, `POST /exceptions/{id}/resolve` | Human exception queue and decisions |
| Pipeline | `GET /runs/{id}/preview` | Drafts the outbound messages without persisting |
| Pipeline | `POST /runs/{id}/execute` | Executes external tasks through the guarded pipeline |
| Outbox | `GET /outbox` | All sent/simulated messages |
| Validation | `GET /validation` | Row-validation totals for every dataset |
| Data | `POST /datasets/{id}/sheets` | Export a dataset to Google Sheets (`gspread`, service account) |
| Audit | `GET /audit`, `GET /audit/verify`, `GET /audit/export` | Global tamper-evident trail, chain check, JSON export |

## Email delivery to your Gmail (sandbox/live)

Sandbox mode does a **real send** with every recipient rewritten to `SANDBOX_REDIRECT_TO` - safe demo of true delivery:

1. Enable 2-Step Verification on the Google account: https://myaccount.google.com/security
2. Create an **App Password** (16 chars): https://myaccount.google.com/apppasswords
3. In `backend/.env` set:
   ```ini
   SANDBOX_REDIRECT_TO=you@gmail.com
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=you@gmail.com
   SMTP_PASS=your-16-char-app-password
   SMTP_FROM=you@gmail.com
   ```
4. Start both servers (repo root: `python run_all.py`), approve the plan on **Plan**, choose **Sandbox**, click **Run** - mail lands in your Gmail inbox and every message is listed in **Outbox**.
- Without a mail provider, sandbox still records per-message `failed` statuses and returns `503 send_failed` - nothing is silently dropped.
- Live mode additionally needs `ALLOW_LIVE=true` and the confirm checkbox, and would contact true recipients.

## Owner notifications (plan created / approved)

The owner gets one email per lifecycle milestone through the same single adapter (`app/adapters/mail.py`: Web3Forms first, SMTP fallback):

1. **Plan ready** — on successful `POST /runs`, subject `Igris: New plan ready — {instruction}`, body lists every task with its server-computed risk label.
2. **Plan approved** — on `POST /runs/{id}/approve`, subject `Igris: Plan approved — {instruction}`.

Behavior and safety:

- Enable by setting `OWNER_EMAIL=you@gmail.com` in `backend/.env` (`OWNER_NOTIFY=true` is the default). Empty `OWNER_EMAIL` = complete no-op, so tests stay hermetic.
- Every attempt is audited as an `owner_notified` event (`status: delivered | failed` in the payload); delivery failures never break the API response.
- Live run timestamps (`created_at`, audit `ts`, outbox) are serialized with a `+00:00` UTC offset (`iso_utc`) so the dashboard renders your true local time.

## Google Sheets export (Data page)

`POST /datasets/{id}/sheets` writes every row plus `validation_status` / `issue_count` columns via the `gspread` service account flow:

1. Google Cloud console -> create project -> enable **Google Sheets API** + **Google Drive API**.
2. Create a **service account**, download the JSON key.
3. In `backend/.env` set either a path (`GOOGLE_SERVICE_ACCOUNT_JSON=./service-account.json`) or the raw JSON string. Optionally set `GOOGLE_SHEET_TEST_ID` to target an existing spreadsheet instead of creating a new one ("OpsPilot - {dataset}").
4. Share the target spreadsheet with the service-account email (client_email inside the JSON) as Editor.
5. On the dashboard **Data** page click **Send to Sheets** - a toast links to the spreadsheet; the export is audited as `dataset_exported`.
| Audit | `GET /audit`, `GET /audit/verify`, `GET /audit/export` | Full trail, chain verification, JSON export |
| Users | `GET /users/me`, `GET /users` | Dashboard user profile (dev bypass header) |

Execution modes (`POST /runs/{id}/execute`):
- **simulation** (default, no network): records messages in the SQL outbox with status `simulated`; run completes.
- **sandbox**: requires an approved plan and `SANDBOX_REDIRECT_TO`; every recipient is redirected there, status `sandbox`.
- **live**: requires an approved plan, `confirm=true`, `ALLOW_LIVE=true`, and a configured provider (`WEB3FORMS_ACCESS_KEY` or `SMTP_*`); otherwise it fails closed (`403 live_blocked`).

## Database (SQL only)

SQLite file (`DATABASE_URL=sqlite:///./opspilot.db`) by default; the app talks SQLAlchemy against any SQL server the URL points at. No Supabase or Neon-specific code or credentials are required or used.

