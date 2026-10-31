"""Pipeline tests: exceptions, plan approval, preview, execution guards, outbox.

Safety rules exercised here:
- Rule 1: simulation mode never performs a network call for external actions.
- Rule 2: live mode requires confirm=true AND ALLOW_LIVE=true AND an approval.
- Rule 5: audit events are append-only and verify as a chain.
"""

import pytest

from app.config import settings


class FakeSMTP:
    """Records send_message() calls without touching a network."""

    sent = []

    def __init__(self, host, port):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def starttls(self):
        pass

    def login(self, user, pw):
        pass

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


@pytest.fixture
def llm_disabled(monkeypatch):
    """Force deterministic cached-plan behavior: no network, ever, in tests."""
    monkeypatch.setattr(settings, "USE_CACHED_PLANS", False)
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")
    monkeypatch.setattr(settings, "LLM_API_KEY", "")


@pytest.fixture
def no_mail_provider(monkeypatch):
    """Hermetic guard: .env may carry real SMTP/Gmail settings; tests never send."""
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    monkeypatch.setattr(settings, "WEB3FORMS_ACCESS_KEY", "")


@pytest.fixture
def seeded_client(client):
    """TestClient with demo datasets, rows, and templates loaded."""
    resp = client.post("/datasets/demo/load")
    assert resp.status_code == 200
    return client


@pytest.fixture
def overdue_run(seeded_client):
    """A created run on the invoices dataset with a cached overseas plan."""
    resp = seeded_client.post(
        "/runs",
        json={"instruction": "Email every customer whose invoice is more than 15 days overdue", "dataset_id": "invoices"},
    )
    body = resp.json()
    run = body["run"] if "run" in body else body
    return seeded_client, run["id"]


def test_create_run_stages_exceptions(overdue_run):
    c, run_id = overdue_run
    exc = c.get("/exceptions").json()
    mine = [e for e in exc if e["run_id"] == run_id]
    assert len(mine) >= 1
    item = mine[0]
    assert item["row_ref"] and item["reason"]
    assert item["status"] == "open"


def test_resolve_exception(overdue_run):
    c, _ = overdue_run
    ex_id = c.get("/exceptions").json()[0]["id"]
    resp = c.post(f"/exceptions/{ex_id}/resolve", json={"decision": "reject", "reason": "needs human pass"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "rejected"
    assert body["resolved_by"]


def test_preview_renders_messages(overdue_run):
    c, run_id = overdue_run
    prev = c.get(f"/runs/{run_id}/preview").json()
    assert len(prev) >= 1
    first = prev[0]
    assert first["recipient"] and first["subject"] and first["body"]


def test_execute_simulation_no_network_and_completes(overdue_run, monkeypatch):
    c, run_id = overdue_run
    c.post(f"/runs/{run_id}/approve")

    def explode(*args, **kwargs):
        raise AssertionError("no network call allowed in simulation mode")

    monkeypatch.setattr("app.adapters.mail.httpx.post", explode)

    resp = c.post(f"/runs/{run_id}/execute", json={"mode": "simulation", "confirm": False})
    assert resp.status_code == 200
    msgs = resp.json()
    assert len(msgs) >= 1
    assert all(m["status"] == "simulated" for m in msgs)

    outbox = c.get("/outbox").json()
    assert len(outbox) == len(msgs)

    run_body = c.get(f"/runs/{run_id}").json()
    assert run_body["state"] == "COMPLETED"

    assert c.get(f"/runs/{run_id}/audit/verify").json()["intact"] is True


def test_execute_twice_conflicts(overdue_run):
    c, run_id = overdue_run
    c.post(f"/runs/{run_id}/approve")
    assert c.post(f"/runs/{run_id}/execute", json={"mode": "simulation"}).status_code == 200
    assert c.post(f"/runs/{run_id}/execute", json={"mode": "simulation"}).status_code == 409


def test_live_requires_confirm_allowlive_and_approved_plan(overdue_run, monkeypatch):
    c, run_id = overdue_run
    monkeypatch.setattr(settings, "ALLOW_LIVE", True)
    # Unapproved plan: even with ALLOW_LIVE and confirm, blocked.
    assert c.post(f"/runs/{run_id}/execute", json={"mode": "live", "confirm": True}).status_code == 403
    c.post(f"/runs/{run_id}/approve")
    # Missing confirm: 400.
    assert c.post(f"/runs/{run_id}/execute", json={"mode": "live", "confirm": False}).status_code == 400


def test_live_blocked_by_default(overdue_run):
    c, run_id = overdue_run
    c.post(f"/runs/{run_id}/approve")
    resp = c.post(f"/runs/{run_id}/execute", json={"mode": "live", "confirm": True})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "live_blocked"


def test_sandbox_requires_redirect_target(overdue_run, monkeypatch):
    c, run_id = overdue_run
    monkeypatch.setattr(settings, "SANDBOX_REDIRECT_TO", None)
    c.post(f"/runs/{run_id}/approve")
    assert c.post(f"/runs/{run_id}/execute", json={"mode": "sandbox", "confirm": False}).status_code == 400


def test_sandbox_delivers_real_mail_redirected(overdue_run, no_mail_provider, monkeypatch):
    c, run_id = overdue_run
    monkeypatch.setattr(settings, "SANDBOX_REDIRECT_TO", "test@example.com")
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.test")
    monkeypatch.setattr(settings, "SMTP_USER", "u")
    FakeSMTP.sent = []
    import app.adapters.mail as mail
    monkeypatch.setattr(mail.smtplib, "SMTP", FakeSMTP)
    c.post(f"/runs/{run_id}/approve")
    msgs = c.post(f"/runs/{run_id}/execute", json={"mode": "sandbox", "confirm": False}).json()
    assert all(m["recipient"] == "test@example.com" for m in msgs)
    assert all(m["original_recipient"] not in ("test@example.com", None) for m in msgs)
    assert all(m["status"] == "sandbox" for m in msgs)
    assert len(FakeSMTP.sent) == len(msgs)


def test_sandbox_reports_all_failed_without_provider(overdue_run, no_mail_provider, monkeypatch):
    c, run_id = overdue_run
    monkeypatch.setattr(settings, "SANDBOX_REDIRECT_TO", "test@example.com")
    c.post(f"/runs/{run_id}/approve")
    resp = c.post(f"/runs/{run_id}/execute", json={"mode": "sandbox", "confirm": False})
    assert resp.status_code == 503
    statuses = {m["status"] for m in c.get(f"/outbox").json() if m["run_id"] == run_id}
    assert statuses == {"failed"}


def test_sheets_export_requires_credentials(seeded_client, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_SERVICE_ACCOUNT_JSON", "")
    resp = seeded_client.post("/datasets/invoices/sheets")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "sheets_not_configured"


def test_sheets_export_audits(seeded_client, monkeypatch):
    """With a working adapter, export succeeds and returns the sheet location."""

    import app.routes.data as data_module

    monkeypatch.setattr(
        data_module,
        "export_dataset_to_sheet",
        lambda db, dataset: {
            "spreadsheet_title": f"OpsPilot - {dataset.name}",
            "spreadsheet_url": "https://docs.google.com/spreadsheets/d/fake",
            "worksheet": "Sheet1",
            "rows_written": 15,
        },
    )

    resp = seeded_client.post("/datasets/invoices/sheets")
    assert resp.status_code == 200
    body = resp.json()
    assert body["spreadsheet_url"] == "https://docs.google.com/spreadsheets/d/fake"
    assert body["rows_written"] == 15

    events = [e for e in seeded_client.get("/audit").json() if e["event_type"] == "dataset_exported"]
    assert events, "dataset_exported audit event missing"


def test_plan_payload_exposes_approval_state(overdue_run):
    c, run_id = overdue_run
    plan = c.get(f"/runs/{run_id}").json()["plan"]
    assert plan["approved"] is False
    assert c.post(f"/runs/{run_id}/approve").status_code == 200
    plan = c.get(f"/runs/{run_id}").json()["plan"]
    assert plan["approved"] is True
    assert plan["approved_by"] == "human:owner"


def test_update_plan_is_guarded_and_versioned(overdue_run):
    c, run_id = overdue_run
    plan = c.get(f"/runs/{run_id}").json()["plan"]
    tasks = [t for t in plan["tasks"] if t["action"] in ("read_sheet",)]
    resp = c.put(f"/runs/{run_id}/plan", json={"tasks": tasks})
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == 2
    assert all(t["risk"] == "read" for t in body["tasks"])


def test_global_audit_endpoints(overdue_run):
    c, run_id = overdue_run
    c.post(f"/runs/{run_id}/approve")
    c.post(f"/runs/{run_id}/execute", json={"mode": "simulation"})
    events = c.get("/audit").json()
    assert len(events) >= 5
    verify = c.get("/audit/verify").json()
    assert verify["valid"] is True
    assert verify["runs"] >= 1
    export = c.get("/audit/export")
    assert export.headers["content-type"] == "application/json"
    assert len(export.json()) == len(events)
