# Product Requirements Document (v2, Expanded)

## OpsPilot: Agentic Workflow Dashboard for Small Business Operations
*(working title; rename freely)*

| | |
|---|---|
| **Version** | 2.0 (hackathon build, expanded) |
| **Date** | 31 Oct 2026 |
| **Owner** | Reddy Santosh Kumar |
| **Status** | Ready for build |
| **Supersedes** | PRD v1.0 |

### What changed from v1
- Added a concrete explanation of the **repetitive tasks** the product targets, with a task taxonomy.
- Added the **owner dashboard concept** (plan, store in sheets, send mail from one place) and how it maps to the safety-first design.
- Added an explicit **Demo Mode Strategy** (mock data, simulation, sandbox, guarded live) and what judges need to see.
- Expanded data model, state machines, validation catalog, UI specs, test cases, build plan and demo script.

---

## Table of Contents
1. Overview and Context
2. The Problem in Detail: Repetitive Tasks
3. Product Concept: The Owner Dashboard
4. Demo Mode Strategy
5. Users and Use Cases
6. Functional Requirements
7. Non-Functional Requirements
8. Tech Stack
9. System Architecture and Design
10. Data Model
11. API Specification
12. Agent (CrewAI) Specification
13. Validation Specification
14. Execution and Safety Specification
15. Audit Trail Specification
16. Integration Specifications
17. UI/UX Specification
18. Mock Data Specification
19. Security, Privacy and Safety
20. Testing and Acceptance Criteria
21. Build Plan and Milestones
22. Risks and Mitigations
23. Demo Script
24. Judging Alignment
25. Open Questions
26. Future Scope

---

## 1. Overview and Context

### 1.1 Problem statement (as given)
Small businesses manage repetitive tasks across forms, spreadsheets, email and messaging platforms, often leading to delays and manual errors. Build an AI workflow agent that converts plain-language instructions into a reviewable sequence of tasks, validates input data, routes exceptions to a human, and records an audit trail. Demonstrate the workflow on mock business data before allowing any external action.

### 1.2 Product vision
A dashboard where a small business owner **describes work in plain language** and gets back a **reviewable plan**. The agent validates the data, pauses on anything doubtful, asks a human, stores results in sheet-style tables, drafts and sends messages through a controlled pipeline, and records everything it does. It proves itself on mock data first, and it never takes an external action without explicit human approval.

### 1.3 Core design principle
**The LLM plans; deterministic code validates, routes, executes and logs.**

The model never directly sends, writes or deletes anything. It emits a structured plan. Everything after that (validation, routing, execution, logging) is plain, testable Python. This is what makes the system trustworthy for a business and defensible to judges.

### 1.4 Goals
| ID | Goal |
|---|---|
| G1 | Convert a plain-language instruction into a structured, ordered task plan |
| G2 | Let a human review, edit and approve the plan before anything runs |
| G3 | Validate input data and catch common errors automatically |
| G4 | Route exceptions and uncertain items to a human decision queue |
| G5 | Record a tamper-evident audit trail of every event |
| G6 | Demonstrate the full flow on mock data in simulation mode before any external action |
| G7 | Provide a single dashboard for planning, data storage (sheet-style) and sending messages |
| G8 | Show credible integration paths for Sheets, email, forms and messaging |

### 1.5 Non-goals (this version)
- Multi-tenant SaaS, billing, self-signup
- Fully autonomous execution without approval
- Large-scale data (target: hundreds of rows)
- Custom model training
- Production WhatsApp Business onboarding
- Using real customer data

### 1.6 Success metrics
| Metric | Target |
|---|---|
| Schema-valid plan from test instructions | At least 90% |
| Seeded hard-rule errors caught | 100% |
| Seeded soft anomalies caught | At least 80% |
| External actions executed without approval | **0** |
| State changes present in audit log | 100% |
| Tamper detection on modified audit row | 100% |
| End-to-end demo duration | Under 3 minutes |
| A first-time viewer understands the product | Within 30 seconds of the demo start |

---

## 2. The Problem in Detail: Repetitive Tasks

### 2.1 What "repetitive tasks" means
In a small business, the owner or one or two staff members repeat the same admin steps every day, **copying information between tools by hand**: a form, a spreadsheet, an inbox, a chat app. The tools do not talk to each other, so a person acts as the glue. That is the source of delays and manual errors.

**The universal pattern:**
```
Something arrives (form / email / message)
   -> a person reads it
   -> checks it
   -> copies it into a sheet
   -> sends a follow-up email or message
   -> updates a status
   -> (repeat tomorrow)
```

### 2.2 Task taxonomy
| Category | Examples | Where errors occur |
|---|---|---|
| **Intake** | Orders from forms, customer enquiries, booking requests, leave requests | Typos, missing fields, duplicates |
| **Recording** | Copying data into orders, clients, invoices or attendance sheets | Wrong column, overwritten rows |
| **Follow-up** | Payment reminders, appointment reminders, order confirmations, thank-you messages | Forgotten, duplicated, sent to wrong person |
| **Monitoring** | Overdue invoices, low stock, double-booked slots | Noticed too late |
| **Reporting** | Weekly summary emails, daily sales recap | Stale or inconsistent numbers |

### 2.3 Examples by business type
**Retail / online shop**
| Task | Manual work | Typical error |
|---|---|---|
| Order intake | Reads each order, types into the orders sheet | Typos, missed orders |
| Order confirmation | Emails or messages every customer | Forgotten or wrong recipient |
| Stock alerts | Checks sheet, messages supplier | Noticed late |
| Payment follow-up | Scans for unpaid invoices, writes reminders | Reminder to someone who already paid |

**Clinic / salon / tutoring center**
| Task | Manual work | Typical error |
|---|---|---|
| Appointment reminders | Reviews tomorrow's bookings, messages each person | Missed reminders, no-shows |
| Double-booking check | Eyeballs the calendar sheet | Two clients, one slot |
| New client onboarding | Copies form data into the client sheet | Wrong phone number, missing field |
| Post-visit follow-up | Sends thank-you or feedback request | Skipped when busy |

**Small agency / freelancer**
| Task | Manual work | Typical error |
|---|---|---|
| Invoice tracking | Updates tracker, emails reminders | Wrong amount, late chasing |
| Lead intake | Copies enquiries into a CRM sheet | Lost leads |
| Client reports | Pulls numbers, writes the email | Inconsistent data |

### 2.4 Why existing solutions fall short
1. **Tools do not connect.** Forms, Sheets, Gmail and chat apps are separate.
2. **Rule-based automation is brittle.** It needs setup and breaks on messy data.
3. **Owners do not trust full automation.** A wrong message to a real customer is costly.
4. **No record.** When something goes wrong, nobody can say who did what.

### 2.5 How the product answers each pain
| Pain | Product response |
|---|---|
| "I need to chase unpaid invoices" | Owner types it in plain words; agent builds the step list |
| "I made a typo / sent it twice" | Validator catches bad emails, duplicates, odd amounts |
| "I'm unsure about this customer" | Exception goes to a human instead of the agent guessing |
| "Did we actually send that?" | Audit trail shows every action and who approved it |
| "I'm afraid to automate customer messages" | Simulation mode shows everything first; nothing leaves without approval |

---

## 3. Product Concept: The Owner Dashboard

### 3.1 The idea
One dashboard where the owner can:
1. **Plan** the work by typing instructions in plain language.
2. **Store** business information in sheet-style tables (customers, invoices, orders, bookings).
3. **Send** emails and messages directly from the dashboard.

### 3.2 Critical design decision: nothing sends directly
A dashboard that sends a message the moment you click is just an email tool. The problem statement asks for review, validation, exception handling and audit. Therefore **every send passes through the same pipeline**:

```
Owner instruction
   -> Plan (editable)
   -> Approval
   -> Validation
   -> Exception handling (human)
   -> Pre-execution summary
   -> Execute in selected mode (simulation / sandbox / live)
   -> Audit log
```

The "Send" button on the dashboard is therefore a "Run" button for an approved plan. Even a one-off email goes through a one-task plan, keeping the audit trail complete.

### 3.3 Dashboard modules
| Module | Purpose |
|---|---|
| **Command bar** | Plain-language instruction input with example chips |
| **Data workspace** | Spreadsheet-style grids for each dataset, inline edit, validation badges per row |
| **Plan board** | Current plan with risk-coloured tasks, edit, approve |
| **Exception inbox** | Items needing a human decision |
| **Outbox** | Every email/message, marked Simulated, Sandbox or Sent |
| **Audit timeline** | Full history, verify integrity, export |
| **Mode switch** | Simulation (default), Sandbox, Live (guarded), with a persistent banner |

### 3.4 Where "sheets" live
- **Primary store:** Supabase tables, rendered in the UI as an editable grid that looks and feels like a spreadsheet.
- **Optional mirror:** one real Google Sheet owned by you, kept in sync through `gspread`, shown to prove sheet integration. This is a P1 enhancement, not a dependency.

---

## 4. Demo Mode Strategy

### 4.1 Do we need real data?
**No.** The problem statement explicitly asks for demonstration on mock business data before any external action. Mock data plus simulated sending is the expected approach.

### 4.2 Three execution modes
| Mode | Behavior | Use in hackathon |
|---|---|---|
| **Simulation** (default) | No network call. Emails/messages are written to the in-app outbox, labelled "SIMULATED" | Main demo |
| **Sandbox** | Real API call, but to targets you own. Recipients are rewritten to a test address; subject prefixed `[SANDBOX -> original]` | One short proof-it-works moment |
| **Live** | Real recipients. Requires explicit confirm flag plus a recorded human approval | Shown as a guarded switch; confirmation modal displayed, then cancelled |

### 4.3 Recommended demo composition
1. **Main demo (about 2.5 minutes):** mock data, seeded errors, simulation outbox.
2. **Sandbox proof (about 20 seconds):** one real email arriving in your own inbox or Mailtrap.
3. **Live guard (about 10 seconds):** show the confirmation requirement and cancel.

### 4.4 What judges need to see versus what is optional
| Must see | Optional |
|---|---|
| Plain language to plan | Real Gmail send |
| Editable plan and approval | Google Sheets mirror |
| Validation catching seeded errors | Telegram or WhatsApp |
| Exception queue with human decisions | Scheduled runs |
| Simulation with zero external calls | Reviewer agent |
| Tamper-evident audit trail | PDF audit export |

---

## 5. Users and Use Cases

### 5.1 Personas
| Persona | Description | Needs |
|---|---|---|
| **Owner (primary)** | Runs a small shop, clinic, tuition center or agency; not technical | Plain-language control, stay in charge, avoid mistakes |
| **Staff operator** | Handles daily admin | Clear exception queue, quick fix-and-approve |
| **Auditor / reviewer** | Owner, accountant or judge | Complete, trustworthy history |

### 5.2 User stories
| ID | As a... | I want to... | So that... |
|---|---|---|---|
| US-1 | Owner | Type "Email customers whose invoices are over 15 days overdue" | I don't process the sheet by hand |
| US-2 | Owner | See the plan as steps before anything happens | I catch mistakes early |
| US-3 | Owner | Edit or remove steps | The agent does exactly what I mean |
| US-4 | Staff | See which rows are invalid and why | I fix them quickly |
| US-5 | Staff | Approve, fix or reject each exception | Risky items never slip through |
| US-6 | Owner | Run everything in simulation first | I see the result with zero risk |
| US-7 | Owner | Switch to a real action only after explicit confirmation | Nothing goes out by accident |
| US-8 | Auditor | View and export a complete log | I can prove what happened |
| US-9 | Auditor | Verify the log was not altered | I can trust it |
| US-10 | Owner | Be asked a question when my instruction is unclear | The agent doesn't guess |
| US-11 | Owner | View and edit my business data in a spreadsheet-style grid | I keep my information in one place |
| US-12 | Owner | See every message the system sent or would send | I stay informed |

### 5.3 Demo scenarios
| # | Scenario | Instruction | Highlights |
|---|---|---|---|
| S1 | Overdue invoices | "Email every customer whose invoice is more than 15 days overdue and log it in the tracker." | Filtering, bulk external action, logging |
| S2 | Order intake | "Check new form submissions, add valid ones to the orders sheet, and notify the warehouse." | Validation, exception routing, messaging |
| S3 | Appointment follow-up | "Send reminders for tomorrow's bookings and flag double-booked slots." | Conflict detection, escalation |

---

## 6. Functional Requirements

Priority: **P0** = must have, **P1** = should have, **P2** = stretch.

### 6.1 Instruction intake and planning
| ID | Requirement | Pri |
|---|---|---|
| FR-1.1 | User submits free-text instruction and selects a dataset | P0 |
| FR-1.2 | System produces a `Plan`: ordered `Task` objects with action, params, dependencies and risk | P0 |
| FR-1.3 | Planner may only use actions from the fixed **action catalog** | P0 |
| FR-1.4 | Plan must pass schema validation; retry once on failure, then show a clear error | P0 |
| FR-1.5 | If the instruction is ambiguous, return a clarifying question instead of a plan | P1 |
| FR-1.6 | Server recomputes each task's `risk` from the catalog, ignoring the model's value | P0 |
| FR-1.7 | Plan edits create a new plan version | P1 |
| FR-1.8 | Each task includes a plain-English description for non-technical users | P1 |
| FR-1.9 | Provide example instruction chips for S1, S2, S3 | P1 |

### 6.2 Plan review
| ID | Requirement | Pri |
|---|---|---|
| FR-2.1 | Show plan as a table: action, parameters, risk badge, dependencies, description | P0 |
| FR-2.2 | User can edit parameters, remove a task, reorder independent tasks | P0 |
| FR-2.3 | Plan must be approved before validation and execution proceed | P0 |
| FR-2.4 | Show "what this plan will touch" summary (datasets, channels, counts) | P1 |

### 6.3 Data workspace (sheet-style storage)
| ID | Requirement | Pri |
|---|---|---|
| FR-3.1 | Display datasets (customers, invoices, orders, bookings) as editable grids | P0 |
| FR-3.2 | Rows show validation badges (OK, warning, error) | P1 |
| FR-3.3 | Edits to data are audit-logged with before/after values | P0 |
| FR-3.4 | Import mock data from CSV with one click ("Load demo data") | P0 |
| FR-3.5 | Reset demo data to the seeded state | P0 |
| FR-3.6 | Optional mirror to a real Google Sheet | P1 |

### 6.4 Validation
| ID | Requirement | Pri |
|---|---|---|
| FR-4.1 | **Hard rules** run deterministically (required, type, email, phone, range, date, duplicates) | P0 |
| FR-4.2 | **Soft checks** (LLM-assisted) flag anomalies with a confidence score | P1 |
| FR-4.3 | Soft checks may only flag, never modify data | P0 |
| FR-4.4 | Each failure records rule id, field, offending value, severity, suggested fix | P0 |
| FR-4.5 | Rules configurable per dataset in a rules file | P1 |

### 6.5 Exception routing and human review
| ID | Requirement | Pri |
|---|---|---|
| FR-5.1 | Any hard-rule failure creates an exception and halts that item only; others continue | P0 |
| FR-5.2 | Soft flags below the confidence threshold create exceptions | P1 |
| FR-5.3 | Exception cards show issue, raw data, suggested fix; actions: Approve as-is, Fix and approve, Reject | P0 |
| FR-5.4 | Resolution records who, when and why | P0 |
| FR-5.5 | Rejected items excluded from execution and listed in the run report | P0 |
| FR-5.6 | Bulk actions for repeated identical exceptions | P2 |

### 6.6 Execution
| ID | Requirement | Pri |
|---|---|---|
| FR-6.1 | Three modes: simulation, sandbox, live; default simulation | P0 |
| FR-6.2 | Simulation writes external tasks to the outbox; no network call | P0 |
| FR-6.3 | Pre-execution summary (for example "12 emails, 3 sheet updates, 1 message") | P0 |
| FR-6.4 | Live mode requires confirm flag and a recorded human approval | P0 |
| FR-6.5 | Sandbox rewrites recipients and prefixes subjects | P1 |
| FR-6.6 | Per-run cap on external actions (default 20) | P1 |
| FR-6.7 | Failed tasks retried with backoff (max 2), then escalated as exceptions | P1 |
| FR-6.8 | Tasks respect `depends_on` ordering | P0 |
| FR-6.9 | Idempotency: re-running a completed task does not duplicate its effect | P1 |

### 6.6.1 Action catalog (v1)
| Action | Risk | Description |
|---|---|---|
| `read_sheet` | read | Load rows from a dataset |
| `filter_rows` | read | Filter by condition |
| `update_sheet_row` | internal_write | Update a row or cell |
| `append_sheet_row` | internal_write | Add a row |
| `draft_email` | internal_write | Generate email text from a template |
| `send_email` | external | Send an email |
| `send_message` | external | Send Telegram, Slack or WhatsApp message |
| `flag_conflict` | internal_write | Mark a scheduling conflict |
| `request_human_input` | read | Ask the owner a question |
| `generate_summary` | internal_write | Produce a run summary |

### 6.7 Messaging and templates
| ID | Requirement | Pri |
|---|---|---|
| FR-7.1 | Email and message templates with placeholders (`{{customer_name}}`, `{{amount}}`, `{{due_date}}`) | P0 |
| FR-7.2 | Agent drafts the message from the template and row data; owner can preview each | P0 |
| FR-7.3 | Preview shows exact recipient, subject and body before execution | P0 |
| FR-7.4 | Optional tone setting (polite, firm, friendly) for drafted text | P2 |

### 6.8 Audit trail
| ID | Requirement | Pri |
|---|---|---|
| FR-8.1 | Append-only event log; no update or delete endpoints | P0 |
| FR-8.2 | Log: plan created/edited/approved, data edited, task validated, exception raised/resolved, task executed (with mode), mode changed, run completed | P0 |
| FR-8.3 | Each event includes actor, timestamp, task id, before/after payload | P0 |
| FR-8.4 | Events are hash-chained | P0 |
| FR-8.5 | "Verify integrity" recomputes the chain and reports the first broken event | P0 |
| FR-8.6 | Export audit as CSV (P0) and PDF (P1) | P0/P1 |

### 6.9 Integrations and triggers
| ID | Requirement | Pri |
|---|---|---|
| FR-9.1 | Every integration is an adapter with `simulate()`, `sandbox()`, `live()` | P0 |
| FR-9.2 | Spreadsheet: Supabase tables (P0), Google Sheets via service account (P1) | P0/P1 |
| FR-9.3 | Email: outbox (P0), Mailpit/Mailtrap and Gmail SMTP sandbox (P1) | P0/P1 |
| FR-9.4 | Forms: in-app intake form (P0), Google Forms via linked Sheet (P2) | P0/P2 |
| FR-9.5 | Messaging: outbox (P0), Telegram (P1), Slack (P2), WhatsApp sandbox (P2) | P0/P1/P2 |
| FR-9.6 | Secrets only via environment variables or secret stores | P0 |
| FR-9.7 | Manual run (P0), webhook trigger (P2), scheduled run (P2) | P0/P2 |

---

## 7. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Safety** | No external side effect without passing the executor guard; guard covered by automated tests |
| **Reliability** | Planner failures degrade gracefully; one bad row never crashes a run |
| **Performance** | Plan in under 15 s; validate 500 rows in under 3 s |
| **Security** | HTTPS, restricted CORS, Supabase JWT, least-privilege service accounts |
| **Privacy** | Mock data only; PII masked in logs |
| **Observability** | Structured logs with `run_id` and `task_id` |
| **Testability** | Validator, router, audit chain, executor guard unit-tested |
| **Usability** | A non-technical person can complete S1 without instructions |
| **Accessibility** | Keyboard navigable, sufficient contrast, labels on controls |
| **Cost** | Entire stack on free tiers |

---

## 8. Tech Stack

### 8.1 Summary
| Layer | Choice | Why |
|---|---|---|
| **Frontend** | Lovable (React, TypeScript, Tailwind, shadcn/ui) | Fast UI generation, clean components, native Supabase integration |
| **Backend API** | **FastAPI** (Python 3.11+), Pydantic v2 | Typed contracts, auto OpenAPI for Lovable, async |
| **Agent framework** | **CrewAI** (planner, optional reviewer) | Structured agent orchestration with Pydantic outputs |
| **LLM** | Gemini free tier via CrewAI `LLM` (LiteLLM); swappable | Free, JSON output |
| **Database** | Supabase PostgreSQL | Free tier, realtime, RLS |
| **Auth** | Supabase Auth (JWT verified in FastAPI) | No custom auth |
| **Background work** | FastAPI `BackgroundTasks`; APScheduler for schedules | No extra infra |
| **Sheets** | Supabase grid (primary), `gspread` mirror (optional) | Simple, free |
| **Email** | SMTP (`smtplib`), Mailpit/Mailtrap, Gmail SMTP | Free, safe sandbox |
| **Messaging** | `httpx` to Telegram/Slack/WhatsApp APIs | Lightweight |
| **Validation** | Pydantic, YAML rule engine, `email-validator`, `phonenumbers` | Deterministic |
| **PDF export** | ReportLab | Free |
| **Testing** | pytest, FastAPI TestClient | |
| **Dev environment** | Antigravity (primary), OpenCode (parallel), Git/GitHub | |
| **Deployment** | FastAPI on Render/Railway; Lovable hosting or Vercel; Supabase cloud | Free tiers |

### 8.2 Division of work between tools
| Tool | Owns |
|---|---|
| Antigravity | `backend/app/` core (planner, validator, executor, audit) |
| OpenCode | `backend/tests/`, mock data generation, docs |
| Lovable | `frontend/` screens built against the OpenAPI schema |
| Supabase | Schema, RLS policies, realtime |

### 8.3 Practical notes
- Lovable runs in the cloud, so FastAPI needs a public URL (Render/Railway, or Cloudflare Tunnel/ngrok in development). Enable CORS for the frontend origin.
- Free Render instances sleep; hit `/health` a minute before presenting.
- CrewAI requires a recent Python (3.10 to 3.13); pin it in a virtual environment.
- Give Lovable the `/openapi.json` and sample JSON payloads so the UI matches the real contract.

---

## 9. System Architecture and Design

### 9.1 Architecture
```
+------------------+      HTTPS / JSON       +-----------------------------+
|  Lovable UI      | <---------------------> |  FastAPI                    |
|  Dashboard       |                         |  Routes + JWT auth          |
|                  |   Supabase Realtime     +--------------+--------------+
+--------+---------+ <------------------+                  |
         |                              |                  v
         |        +---------------------+------+   +---------------------------+
         +------> | Supabase Postgres + Auth   |<--| Core services             |
                  | datasets, runs, plans,     |   | Planner (CrewAI)          |
                  | tasks, exceptions, audit,  |   | Validator                 |
                  | outbox, submissions        |   | Router                    |
                  +----------------------------+   | Executor (mode guard)     |
                                                   | Audit logger (hash chain) |
                                                   +-------------+-------------+
                                                                 |
                                       Adapters: Sheets | Email | Forms | Messaging
                                       (each: simulate / sandbox / live)
```

### 9.2 Repository layout
```
opspilot/
  backend/
    app/
      main.py
      config.py              # MODE, caps, SANDBOX_REDIRECT_TO
      auth.py                # Supabase JWT verification
      models.py              # Task, Plan, ExceptionItem, AuditEvent
      catalog.py             # action catalog + risk levels
      planner.py             # CrewAI crew
      templates.py           # message templates
      validator/
        rules.py  engine.py  soft_checks.py
      router.py
      executor.py            # mode guard
      audit.py               # hash chain + verify
      adapters/
        base.py  sheets.py  email.py  messaging.py  forms.py
      routes/
        runs.py  exceptions.py  audit.py  intake.py  data.py  health.py
      mock_data/
        customers.csv  invoices.csv  orders.csv  bookings.csv  rules.yaml
    tests/
    requirements.txt
  frontend/                  # Lovable project (synced to GitHub)
  docs/
    PRD.md  demo-script.md
  .env.example
```

### 9.3 Run lifecycle
```
CREATED -> PLANNED -> PLAN_APPROVED -> VALIDATING -> AWAITING_EXCEPTIONS
        -> READY_TO_EXECUTE -> EXECUTING -> COMPLETED
                                     \-> FAILED
Any state -> CANCELLED
```
Task status: `pending_review` > `approved` > `validated` | `flagged` > `simulated` | `executed` | `rejected` | `failed`.

### 9.4 Sequence: Scenario S1 (overdue invoices)
1. Owner types the instruction; API creates a run.
2. Planner reads the dataset schema and action catalog, returns a plan: `read_sheet(invoices)` > `filter_rows(overdue>15d)` > `draft_email(template=payment_reminder)` > `send_email` > `update_sheet_row(status=Reminded)`.
3. Server enforces catalog and recomputes risk (`send_email` = external).
4. Owner edits (for example changes 15 to 20 days) and approves.
5. Validator runs on the filtered rows; failures become exceptions.
6. Owner resolves exceptions.
7. Pre-execution summary: "9 emails (simulated), 9 sheet updates".
8. Execute in simulation; outbox fills; tracker updates; audit logs each step.

---

## 10. Data Model

| Table | Key fields |
|---|---|
| `datasets` | id, name, source_type, schema (JSONB), rules_ref |
| `dataset_rows` | id, dataset_id, data (JSONB), validation_status, updated_at |
| `runs` | id, instruction, dataset_id, mode, state, created_by, created_at |
| `plans` | id, run_id, version, tasks (JSONB), clarifying_question, approved_by, approved_at |
| `tasks` | id, run_id, plan_version, action, params (JSONB), description, depends_on, risk, status |
| `validation_results` | id, run_id, task_id, row_ref, rule_id, severity, field, value, suggested_fix |
| `exceptions` | id, run_id, task_id, row_ref, reason, raw_data (JSONB), status, resolution, resolved_by, resolved_at |
| `templates` | id, name, channel, subject, body |
| `outbox` | id, run_id, task_id, channel, recipient, original_recipient, subject, body, mode, created_at |
| `submissions` | id, form_type, data (JSONB), status, created_at |
| `audit_events` | id, run_id, ts, actor, event_type, task_id, payload (JSONB), prev_hash, hash |

Row-level security: users see only their own runs and datasets. `audit_events` is insert-only.

---

## 11. API Specification

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness |
| GET | `/datasets` | List datasets |
| GET | `/datasets/{id}/rows` | Read rows |
| PATCH | `/datasets/{id}/rows/{row_id}` | Edit a row (audited) |
| POST | `/datasets/demo/load` | Load seeded demo data |
| POST | `/datasets/demo/reset` | Reset to seeded state |
| POST | `/runs` | Create run from instruction; returns plan or clarifying question |
| GET | `/runs/{id}` | Run status, plan, summary |
| PATCH | `/runs/{id}/plan` | Edit plan (new version) |
| POST | `/runs/{id}/approve` | Approve plan; starts validation |
| GET | `/runs/{id}/validation` | Validation report |
| GET | `/runs/{id}/exceptions` | Exception queue |
| POST | `/exceptions/{id}/resolve` | `{decision: approve|fix|reject, fixed_data?, reason}` |
| GET | `/runs/{id}/preview` | Pre-execution summary and message previews |
| POST | `/runs/{id}/execute` | `{mode, confirm}`; live requires `confirm=true` |
| GET | `/runs/{id}/outbox` | Simulated/sandbox/sent messages |
| GET | `/runs/{id}/audit` | Audit events |
| GET | `/runs/{id}/audit/verify` | Integrity check result |
| GET | `/runs/{id}/audit/export?format=csv|pdf` | Export |
| POST | `/intake/{form_type}` | Form submission |
| GET | `/templates` and POST `/templates` | Manage templates |

Error format: `{"error": {"code": "...", "message": "...", "details": {...}}}`.

---

## 12. Agent (CrewAI) Specification

### 12.1 Planner
- **Input:** instruction, dataset schema, action catalog with parameter schemas, available templates.
- **Output:** `Plan` Pydantic model via `output_pydantic`.
- **Settings:** temperature 0; no tools that can write or send; `allow_delegation=False`.
- **Behavior:** use only catalog actions; set `clarifying_question` when ambiguous; include a plain-English description for each task.

### 12.2 Server-side post-processing (non-negotiable)
1. Drop unknown actions.
2. Recompute `risk` from the catalog.
3. Verify `depends_on` references exist and the graph has no cycles.
4. Ensure every `external` task is preceded by a `read` or `draft` task.
5. Enforce the per-run external action cap.

### 12.3 Reviewer agent (P1)
Read-only. Receives drafted messages and flagged rows; returns flags with confidence (for example tone too aggressive, amount unusual). Output feeds the exception queue.

### 12.4 Prompt-injection stance
The planner sees the **schema** and the owner's instruction, never raw cell contents. Row data is treated purely as data and is never interpreted as instructions. The action catalog bounds what any plan can do.

### 12.5 Demo resilience
Cache known-good plans for S1, S2 and S3 as a fallback if the LLM is slow or rate-limited during the demo.

---

## 13. Validation Specification

### 13.1 Hard rule catalog
| Rule ID | Check | Severity |
|---|---|---|
| REQ-01 | Required field present | Error |
| EML-01 | Email format valid | Error |
| PHN-01 | Phone format valid (region IN) | Warning |
| NUM-01 | Number within allowed range, not negative | Error |
| DAT-01 | Date valid and within sane window | Error |
| DUP-01 | Duplicate key (for example invoice_id) | Error |
| REF-01 | Referenced customer exists | Error |
| CNF-01 | Booking slot conflict | Error |

### 13.2 Soft checks (advisory, with confidence)
| Check | Example |
|---|---|
| Amount outlier | Amount 8x or more the customer's median |
| Tone check | Draft reads too aggressive for a first reminder |
| Ambiguity | Customer name matches two records |

### 13.3 Rules file example
```yaml
dataset: invoices
fields:
  customer_email: {type: email, required: true}
  amount: {type: number, min: 1, max: 1000000}
  due_date: {type: date, not_after: today+365d}
dataset_rules:
  - id: DUP-01
    type: unique
    fields: [invoice_id]
  - id: AMT-ANOM-01
    type: outlier
    field: amount
    method: ratio_to_customer_median
    threshold: 8
```

### 13.4 Routing rules
- Hard failure -> exception, item halted.
- Soft flag with confidence below threshold -> exception.
- Plan contains `external` task -> always requires plan approval and pre-execution confirmation.
- Ambiguous instruction -> clarifying question, no plan.

---

## 14. Execution and Safety Specification

### 14.1 Executor guard (pseudocode)
```python
def execute(task, mode, confirmed, approvals):
    if task.status != "validated":
        raise Blocked("Task not validated")
    adapter = ADAPTERS[task.action]
    if task.risk != "external":
        return adapter.run(task)                  # internal, still audited
    if mode == "simulation":
        return adapter.simulate(task)             # outbox only
    if mode == "sandbox":
        return adapter.sandbox(task)              # recipients rewritten
    if mode == "live":
        if not (confirmed and approvals.has("live_execution", task.run_id)):
            raise Blocked("Live action needs confirmation and approval")
        return adapter.live(task)
```

### 14.2 Safety controls
| Control | Detail |
|---|---|
| Default mode | Simulation |
| Recipient rewrite | `SANDBOX_REDIRECT_TO` replaces every recipient in sandbox |
| Action cap | Default 20 external actions per run |
| Idempotency key | `run_id + task_id + row_ref` prevents double sends |
| Kill switch | "Cancel run" stops further tasks and logs it |
| Environment lock | Live mode disabled unless `ALLOW_LIVE=true` in the environment |

---

## 15. Audit Trail Specification

### 15.1 Event schema
| Field | Example |
|---|---|
| `event_id`, `run_id`, `ts` | |
| `actor` | `agent`, `validator`, `executor`, `human:owner` |
| `event_type` | `plan_created`, `plan_approved`, `row_edited`, `exception_raised`, `exception_resolved`, `task_simulated`, `mode_changed`, `live_blocked` |
| `task_id` | `t3` |
| `payload` | before/after, reason, mode |
| `prev_hash`, `hash` | SHA-256 chain |

### 15.2 Hash chain
```
hash_n = SHA256( hash_{n-1} + canonical_json(event_n) )     # first uses "GENESIS"
```
Verification walks events in order, recomputes hashes, and reports the first mismatch.

### 15.3 Demo moment
Edit one audit row directly in the database, click **Verify integrity**, and show it failing at the exact event.

---

## 16. Integration Specifications

| Integration | Simulation | Sandbox | Live |
|---|---|---|---|
| **Sheets** | Supabase grid | Owned Google Sheet via `gspread` service account | Same, real data |
| **Email** | Outbox row | Mailpit/Mailtrap, or Gmail SMTP to your own address with recipient rewrite | Gmail SMTP/API to real recipients |
| **Forms** | In-app form to `/intake` | Google Form to linked Sheet, polled | Same |
| **Messaging** | Outbox row | Telegram bot to a test chat; Slack test webhook | WhatsApp (Twilio/Meta) to opted-in numbers |

### 16.1 Setup notes
- **Google Sheets:** enable Sheets API, create a service account, share the Sheet with its email, store the key as a secret.
- **Gmail SMTP:** enable 2FA, create an app password, host `smtp.gmail.com`, port 587, STARTTLS.
- **Mailtrap/Mailpit:** use their SMTP credentials for a safe visible inbox.
- **Telegram:** create a bot via BotFather, store the token, message the bot once to get `chat_id`.
- **WhatsApp:** Twilio sandbox (recipients must opt in); treat as optional.

### 16.2 Adapter interface
```python
class Adapter(Protocol):
    def simulate(self, task: Task) -> Result: ...
    def sandbox(self, task: Task) -> Result: ...
    def live(self, task: Task) -> Result: ...
```

---

## 17. UI/UX Specification

### 17.1 Global elements
- **Mode banner** (always visible): green "SIMULATION: nothing leaves this system", amber "SANDBOX", red "LIVE".
- **Run state chip** showing the current lifecycle state.
- **Risk badges:** grey (read), blue (internal write), orange (external).

### 17.2 Screens
| # | Screen | Contents | Key interactions |
|---|---|---|---|
| 1 | **Dashboard home** | Command bar, example chips, recent runs, data summary tiles | Type instruction, click chip |
| 2 | **Plan board** | Editable task table, descriptions, risk badges, dependency lines | Edit, remove, approve |
| 3 | **Data workspace** | Tabs per dataset, editable grid, row validation badges, Load/Reset demo data | Inline edit |
| 4 | **Validation report** | Counts, per-rule breakdown, links to exceptions | Drill down |
| 5 | **Exception inbox** | Cards with issue, raw row, suggested fix, reason field | Approve / Fix / Reject |
| 6 | **Pre-execution review** | Summary counts, message previews (recipient, subject, body), mode selector | Run, cancel |
| 7 | **Outbox** | Messages with status labels Simulated / Sandbox / Sent | Filter, inspect |
| 8 | **Audit timeline** | Chronological events, actor icons, filters | Verify, Export |
| 9 | **Intake form** | Sample order form posting to `/intake` | Submit |

### 17.3 UX rules
- External actions are always visually distinct.
- Live actions require a confirmation modal that restates the count and channel.
- Empty, loading and error states are designed for every screen.
- Plain language in all labels; avoid jargon such as "DAG" or "idempotency".

### 17.4 Lovable prompt starter
> Build a dashboard called OpsPilot for small business owners. Include: a command bar for plain-language instructions with example chips; a plan board table with editable tasks, risk badges and Approve; a spreadsheet-style data workspace with tabs for Customers, Invoices, Orders and Bookings and a "Load demo data" button; an exception inbox with cards (issue, raw row, suggested fix, Approve / Fix & approve / Reject); a pre-execution review screen with message previews and a mode selector (Simulation default, Sandbox, Live with confirmation modal); an outbox with Simulated/Sandbox/Sent labels; and an audit timeline with Verify integrity and Export buttons. Show a persistent mode banner. Call the REST API at `VITE_API_URL` using the attached OpenAPI schema. Use Tailwind and shadcn/ui with a clean, professional style.

---

## 18. Mock Data Specification

### 18.1 Business theme
Choose one for coherence (recommended: small retail shop, or tuition center/clinic). Use clearly fictional names and `example.com` addresses.

### 18.2 Datasets
| Dataset | Approx rows | Key columns |
|---|---|---|
| `customers` | 25 | customer_id, name, email, phone, city |
| `invoices` | 40 | invoice_id, customer_id, amount, due_date, status |
| `orders` | 30 | order_id, customer_id, sku, qty, price, status |
| `bookings` | 25 | booking_id, customer_id, slot_start, slot_end, resource |
| `submissions` | 10 | form_type, data (raw form entries) |

### 18.3 Seeded errors (per dataset, deliberate)
| Error type | Example |
|---|---|
| Malformed email | `ravi@@example` |
| Missing required field | Blank email |
| Duplicate record | Same `invoice_id` twice |
| Negative amount | `-3000` |
| Outlier amount | 950,000 where the customer's norm is about 9,000 |
| Bad date | Due date in year 2099 |
| Orphan reference | Invoice for a nonexistent customer |
| Slot conflict | Two bookings, same resource, overlapping time |
| Ambiguous name | Two customers named "Kiran" |

### 18.4 Sample rows
| invoice_id | customer | email | amount | due_date | Seeded issue |
|---|---|---|---|---|---|
| INV-101 | Asha Traders | asha@example.com | 12,000 | 2026-09-30 | None (overdue) |
| INV-102 | Ravi Stores | ravi@@example | 8,500 | 2026-10-05 | Malformed email |
| INV-103 | Meena Boutique | meena@example.com | 9,000 | 2026-10-01 | Duplicate |
| INV-103 | Meena Boutique | meena@example.com | 9,000 | 2026-10-01 | Duplicate |
| INV-104 | Kiran Mart | kiran@example.com | 950,000 | 2026-10-10 | Outlier amount |
| INV-105 | Lakshmi Clinic | (blank) | 4,200 | 2026-09-28 | Missing email |
| INV-106 | Suresh Foods | suresh@example.com | -3,000 | 2026-10-12 | Negative amount |

---

## 19. Security, Privacy and Safety

| Risk | Control |
|---|---|
| Unintended external action | Executor guard, default simulation, live needs confirm + approval, `ALLOW_LIVE` env lock, action cap |
| Prompt injection via data | Planner sees schema not cell contents; catalog bounds actions; data never treated as instructions |
| LLM invents actions or lowers risk | Server-side catalog enforcement and risk recomputation |
| Secrets leak | `.env` gitignored, platform secret stores, no keys in Lovable prompts or repo |
| Log tampering | Hash chain, insert-only policy |
| Unauthorized access | Supabase JWT, RLS, restricted CORS |
| Emailing real people during development | Sandbox redirect, mock data only |
| PII exposure | Fictional data, masked logs |

---

## 20. Testing and Acceptance Criteria

### 20.1 Test plan
| Area | Tests |
|---|---|
| Validator | One test per rule (pass and fail) using seeded data |
| Planner | 10 instructions; assert schema validity and catalog-only actions |
| Post-processing | Unknown actions dropped; risk recomputed; cycles rejected |
| Router | Failures create exceptions; clean rows continue |
| Executor guard | Live without confirm is blocked; simulation never touches the network (mocked adapter) |
| Audit | Chain verifies; modifying any row breaks verification |
| API | Happy and error paths per endpoint |
| Idempotency | Re-executing a task does not duplicate an outbox entry |
| UI smoke | S1 completes end to end |

### 20.2 Acceptance criteria (demo gate)
1. S1 produces an editable plan that a human can approve.
2. All seeded errors are flagged with a clear reason.
3. Exceptions can be fixed, approved or rejected, and each decision appears in the audit log.
4. A simulation run produces an outbox and **zero** external network calls.
5. Attempting live mode without confirmation is rejected and logged.
6. Audit verification passes on a clean run and fails after a manual DB edit.
7. Audit export downloads as CSV.
8. Data edits in the workspace appear in the audit log with before/after values.
9. "Reset demo data" restores the seeded state.

---

## 21. Build Plan and Milestones

Time shares are proportional; map them to your actual deadline.

| Phase | Scope | Share | Owner tool |
|---|---|---|---|
| **M1 Foundation** | Repo, Supabase schema, models, mock data, audit logger | 15% | Antigravity |
| **M2 Brain** | Action catalog, CrewAI planner, server-side enforcement, cached fallback plans | 15% | Antigravity |
| **M3 Safety core** | Validator, router, exceptions, executor guard, simulation adapters, templates | 25% | Antigravity |
| **M3b Tests** | Validator, guard and audit tests, seeded-data fixtures | parallel | OpenCode |
| **M4 API** | Endpoints, auth, error format | 10% | Antigravity |
| **M5 UI** | Dashboard screens wired to API | 20% | Lovable |
| **M6 Integrations** | Sheets mirror, email sandbox, Telegram | 10% | Antigravity |
| **M7 Polish** | Audit export, tamper demo, S2 and S3, rehearsal | 5% | All |

**Cut order if short on time:** WhatsApp, Slack, Google Forms, Gmail API, reviewer agent, scheduled runs, PDF export.
**Never cut:** validator, exception queue, audit trail, simulation guard.

---

## 22. Risks and Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| CrewAI output unstable or slow | Medium | Temperature 0, `output_pydantic`, one retry, cached plans |
| Free-tier backend cold start | Medium | Warm `/health` before demo |
| LLM rate limits | Medium | Cache plans, short prompts, second provider key ready |
| Lovable UI mismatches API | Medium | Provide OpenAPI and sample payloads upfront |
| Integration setup consumes time | High | Simulation first; sandbox only after core is done |
| Two coding agents conflict | Low | Separate directory ownership, branches, small commits |
| Demo data too clean | Medium | Seed errors deliberately |
| Scope creep | High | Hold to P0 list until acceptance criteria pass |
| Live demo failure | Medium | Pre-recorded backup video, cached plans, local fallback |

---

## 23. Demo Script (about 3 minutes)

| Time | Step |
|---|---|
| 0:00 | One-sentence pitch: "Plain-language instruction in, reviewable and auditable workflow out; nothing external without approval." |
| 0:20 | Show the Data workspace with demo data; point at a few visibly messy rows |
| 0:35 | Type the S1 instruction; show the generated plan; edit one task |
| 1:00 | Approve; validator flags the malformed email, duplicate, outlier and negative amount |
| 1:25 | In the exception inbox: fix one, reject one, approve one |
| 1:50 | Pre-execution review: message previews and counts; run in **simulation**; open the outbox |
| 2:10 | Audit timeline; click **Verify integrity** (pass); tamper with one DB row; verify again (fail at exact event) |
| 2:35 | Sandbox: send one real email to your own inbox; show it arriving with the `[SANDBOX]` prefix |
| 2:50 | Switch to Live: show the confirmation requirement and cancel |
| 3:00 | Close: summarise safety guarantees |

Backup plan: a pre-recorded video of the same flow, and cached plans if the LLM is unavailable.

---

## 24. Judging Alignment

| Problem-statement requirement | Where it is satisfied |
|---|---|
| Converts plain-language instructions to a reviewable task sequence | Command bar, planner, editable plan board |
| Validates input data | Hard rules plus soft checks; validation report |
| Routes exceptions to a human | Exception inbox with approve, fix, reject |
| Records an audit trail | Hash-chained log, verify, export |
| Demonstrates on mock data before external action | Seeded mock datasets; simulation by default; sandbox and guarded live |
| Works across forms, spreadsheets, email, messaging | In-app forms, sheet-style grids, email and messaging adapters |

Extra differentiators: tamper-evident audit, recipient-rewrite sandbox, server-side risk enforcement, prompt-injection stance.

---

## 25. Open Questions
1. Hackathon deadline and submission format (video, repo, live demo)?
2. Business vertical for the mock data (retail, clinic, tuition center)?
3. LLM provider and key to be used at demo time?
4. PDF audit export required, or is CSV enough?
5. Solo build or team (affects parallel work split)?

---

## 26. Future Scope
- Plain-English policy rules ("never email customers after 8 pm")
- Undo and rollback for internal writes
- Role-based approvals (owner vs staff)
- Multi-tenant workspaces
- Native WhatsApp Business onboarding
- Template marketplace for common small-business workflows
- Bi-directional Google Sheets sync
- Analytics on time saved and errors prevented
