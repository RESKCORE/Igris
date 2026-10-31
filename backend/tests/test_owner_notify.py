"""Owner notification + timestamp-offset tests.

Covers the new owner_notified audit event (create run + approve plan), the
shared mail adapter, and iso_utc() serialization ending in +00:00.
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
def fake_smtp(monkeypatch):
    """Force the SMTP path (clear Web3Forms from .env) behind the fake transport."""
    monkeypatch.setattr(settings, "WEB3FORMS_ACCESS_KEY", "")
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.test")
    import app.adapters.mail as mail
    monkeypatch.setattr(mail.smtplib, "SMTP", FakeSMTP)
    FakeSMTP.sent = []
    return FakeSMTP


@pytest.fixture
def owner_on(monkeypatch):
    """Enable owner notifications to a test inbox (overrides conftest no-op)."""
    monkeypatch.setattr(settings, "OWNER_EMAIL", "owner@example.com")
    monkeypatch.setattr(settings, "OWNER_NOTIFY", True)


@pytest.fixture
def seeded_client(client):
    resp = client.post("/datasets/demo/load")
    assert resp.status_code == 200
    return client


def test_create_and_approve_mail_owner_twice(seeded_client, llm_disabled, owner_on, fake_smtp):
    resp = seeded_client.post("/runs", json={"instruction": "reminder for overdue invoice payments"})
    assert resp.status_code == 200
    assert resp.json()["created_at"].endswith("+00:00")
    run_id = resp.json()["id"]

    assert len(fake_smtp.sent) == 1
    first = fake_smtp.sent[0]
    assert first["Subject"] == "Igris: New plan ready — reminder for overdue invoice payments"
    assert "CUST-001" in first.get_content()
    assert "INV-101" in first.get_content()
    assert "[read] read_sheet" not in first.get_content()

    assert seeded_client.post(f"/runs/{run_id}/approve").status_code == 200
    assert len(fake_smtp.sent) == 2
    assert fake_smtp.sent[1]["Subject"] == "Igris: Plan approved — reminder for overdue invoice payments"

    events = [e for e in seeded_client.get(f"/runs/{run_id}/audit").json() if e["event_type"] == "owner_notified"]
    assert len(events) == 2
    assert all(e["payload"]["status"] == "delivered" for e in events)
    assert all(e["payload"]["to"] == "owner@example.com" for e in events)


def test_no_owner_email_zero_mail_attempts(seeded_client, llm_disabled, fake_smtp):
    seeded_client.post("/runs", json={"instruction": "reminder for overdue invoice payments"})
    body = seeded_client.post("/runs", json={"instruction": "please confirm the new orders today"})
    seeded_client.post(f"/runs/{body.json()['id']}/approve")
    assert fake_smtp.sent == []


def test_provider_error_recorded_not_fatal(seeded_client, llm_disabled, owner_on, monkeypatch):
    """OWNER_EMAIL set but no provider: create still returns 200; audit shows failed."""
    monkeypatch.setattr(settings, "WEB3FORMS_ACCESS_KEY", "")
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    resp = seeded_client.post("/runs", json={"instruction": "reminder for overdue invoice payments"})
    assert resp.status_code == 200
    run_id = resp.json()["id"]
    events = [e for e in seeded_client.get(f"/runs/{run_id}/audit").json() if e["event_type"] == "owner_notified"]
    assert len(events) == 1
    assert events[0]["payload"]["status"] == "failed"
    assert "No live email provider configured" in events[0]["payload"]["error"]
    assert seeded_client.get(f"/runs/{run_id}/audit/verify").json()["intact"] is True


def test_runtime_timestamps_carry_utc_offset(seeded_client, llm_disabled):
    created = seeded_client.post("/runs", json={"instruction": "reminder for overdue invoice payments"}).json()
    run_id = created["id"]
    assert created["created_at"].endswith("+00:00")

    listing = [r for r in seeded_client.get("/runs").json() if r["id"] == run_id][0]
    assert listing["created_at"].endswith("+00:00")

    seeded_client.post(f"/runs/{run_id}/approve")
    assert [e for e in seeded_client.get("/audit").json() if e["run_id"] == run_id][0]["ts"].endswith("+00:00")


def test_web3forms_rejection_falls_back_to_smtp(monkeypatch):
    """Web3Forms free tier rejects server-side calls; SMTP must still deliver."""
    import httpx
    import app.adapters.mail as mail

    monkeypatch.setattr(settings, "WEB3FORMS_ACCESS_KEY", "free-tier-key")
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.test")
    monkeypatch.setattr(mail.smtplib, "SMTP", FakeSMTP)
    FakeSMTP.sent = []

    def reject(*args, **kwargs):
        raise httpx.HTTPError("bad")

    monkeypatch.setattr(mail.httpx, "post", reject)
    assert mail.send_email("s", "b", "to@example.com") == "smtp"
    assert len(FakeSMTP.sent) == 1
