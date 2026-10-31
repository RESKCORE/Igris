"""Tests for audit logger and tamper-evident cryptographic hash chain."""

import pytest
from app.audit import append_event, verify_chain
from app.models import AuditEvent


def test_audit_chain_ten_events(test_db) -> None:
    """Chain verifies cleanly on a sequence of 10 events."""
    run_id = "test-run-1"
    for i in range(1, 11):
        append_event(
            db=test_db,
            run_id=run_id,
            actor="test_actor",
            event_type="plan_created" if i == 1 else "task_simulated",
            task_id=f"task_{i}",
            payload={"step": i, "status": "ok"},
        )

    verification = verify_chain(test_db, run_id)
    assert verification["intact"] is True
    assert verification["verified"] == 10
    assert verification["broken_at"] is None
    assert verification["event_id"] is None


def test_audit_chain_tamper_detection(test_db) -> None:
    """Editing any event's payload directly in the database causes verification failure."""
    run_id = "test-run-tamper"
    events = []
    for i in range(1, 6):
        e = append_event(
            db=test_db,
            run_id=run_id,
            actor="test_actor",
            event_type="task_executed",
            task_id=f"task_{i}",
            payload={"count": i},
        )
        events.append(e)

    # Tamper with the 3rd event directly via raw SQL / session update
    tampered_event = test_db.query(AuditEvent).filter(
        AuditEvent.run_id == run_id,
        AuditEvent.sequence == 3,
    ).first()
    assert tampered_event is not None
    tampered_event.payload = {"count": 9999, "tampered": True}
    test_db.commit()

    # Re-verify chain; it must fail at sequence 3
    verification = verify_chain(test_db, run_id)
    assert verification["intact"] is False
    assert verification["verified"] == 2
    assert verification["broken_at"] == 3
    assert verification["event_id"] == tampered_event.id


def test_independent_runs_have_separate_chains(test_db) -> None:
    """Events from two distinct runs have independent chains starting with GENESIS."""
    run_a = "run-alpha"
    run_b = "run-beta"

    e_a1 = append_event(test_db, run_a, "actor_a", "plan_created")
    e_a2 = append_event(test_db, run_a, "actor_a", "plan_approved")

    e_b1 = append_event(test_db, run_b, "actor_b", "plan_created")
    e_b2 = append_event(test_db, run_b, "actor_b", "plan_approved")

    assert e_a1.prev_hash == "GENESIS"
    assert e_a1.sequence == 1
    assert e_a2.prev_hash == e_a1.hash
    assert e_a2.sequence == 2

    assert e_b1.prev_hash == "GENESIS"
    assert e_b1.sequence == 1
    assert e_b2.prev_hash == e_b1.hash
    assert e_b2.sequence == 2

    assert verify_chain(test_db, run_a)["intact"] is True
    assert verify_chain(test_db, run_b)["intact"] is True


def test_audit_routes(client, test_db) -> None:
    """Verify HTTP endpoints for audit log, verification, and export."""
    run_id = "test-route-run"
    for i in range(1, 4):
        append_event(
            test_db,
            run_id,
            "tester",
            "task_validated",
            task_id=f"t_{i}",
            payload={"row": i},
        )

    # 1. GET /runs/{id}/audit
    res = client.get(f"/runs/{run_id}/audit")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 3
    assert data[0]["sequence"] == 1
    assert data[0]["prev_hash"] == "GENESIS"

    # 2. GET /runs/{id}/audit/verify
    res_verify = client.get(f"/runs/{run_id}/audit/verify")
    assert res_verify.status_code == 200
    assert res_verify.json()["intact"] is True
    assert res_verify.json()["verified"] == 3

    # 3. GET /runs/{id}/audit/export?format=csv
    res_csv = client.get(f"/runs/{run_id}/audit/export?format=csv")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "sequence,ts,actor,event_type" in res_csv.text

    # 4. GET /runs/{id}/audit/export?format=pdf (returns 501 for Stage 2)
    res_pdf = client.get(f"/runs/{run_id}/audit/export?format=pdf")
    assert res_pdf.status_code == 501
    assert res_pdf.json()["error"]["code"] == "not_implemented"
