"""Tamper-evident audit logger with SHA-256 cryptographic hash chain."""

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional, Set
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import AuditEvent, generate_uuid


# Fixed set of valid audit event types per PRD
EVENT_TYPES: Set[str] = {
    "plan_created",
    "plan_edited",
    "plan_approved",
    "owner_notified",
    "row_edited",
    "data_loaded",
    "data_reset",
    "dataset_exported",
    "task_validated",
    "exception_raised",
    "exception_resolved",
    "task_simulated",
    "task_executed",
    "task_blocked",
    "mode_changed",
    "live_blocked",
    "run_completed",
    "run_cancelled",
}


def canonical_json(data: Any) -> str:
    """Serialize data into a deterministic, sorted, compact JSON string."""
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
        ensure_ascii=False,
    )


def _format_timestamp(ts: Any) -> str:
    """Format timestamp into a standardized ISO 8601 UTC string."""
    if isinstance(ts, str):
        return ts
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts.isoformat()
    return str(ts)


def append_event(
    db: Session,
    run_id: str,
    actor: str,
    event_type: str,
    task_id: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> AuditEvent:
    """Append a new tamper-evident audit event to the run's hash chain.

    Computes: hash = SHA256(prev_hash + canonical_json(body))
    where prev_hash is the preceding event's hash or 'GENESIS'.
    """
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Unknown audit event type: {event_type}")

    payload_clean = payload if payload is not None else {}
    ts = datetime.now(timezone.utc)
    ts_iso = _format_timestamp(ts)

    # Fetch previous event for this run within current transaction
    prev_event = (
        db.query(AuditEvent)
        .filter(AuditEvent.run_id == run_id)
        .order_by(desc(AuditEvent.sequence))
        .first()
    )

    if prev_event is None:
        sequence = 1
        prev_hash = "GENESIS"
    else:
        sequence = prev_event.sequence + 1
        prev_hash = prev_event.hash

    body = {
        "run_id": run_id,
        "ts": ts_iso,
        "actor": actor,
        "event_type": event_type,
        "task_id": task_id,
        "payload": payload_clean,
    }

    content_to_hash = (prev_hash + canonical_json(body)).encode("utf-8")
    event_hash = hashlib.sha256(content_to_hash).hexdigest()

    event = AuditEvent(
        id=generate_uuid(),
        run_id=run_id,
        sequence=sequence,
        ts=ts,
        actor=actor,
        event_type=event_type,
        task_id=task_id,
        payload=payload_clean,
        prev_hash=prev_hash,
        hash=event_hash,
    )

    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def verify_chain(db: Session, run_id: str) -> Dict[str, Any]:
    """Verify the cryptographic integrity of the hash chain for a run.

    Recomputes SHA256(prev_hash + canonical_json(body)) in order and reports
    the first mismatch or corruption found.
    """
    events: List[AuditEvent] = (
        db.query(AuditEvent)
        .filter(AuditEvent.run_id == run_id)
        .order_by(AuditEvent.sequence.asc())
        .all()
    )

    if not events:
        return {
            "intact": True,
            "verified": 0,
            "broken_at": None,
            "event_id": None,
        }

    expected_prev_hash = "GENESIS"

    for idx, event in enumerate(events):
        if event.prev_hash != expected_prev_hash:
            return {
                "intact": False,
                "verified": idx,
                "broken_at": event.sequence,
                "event_id": event.id,
            }

        body = {
            "run_id": event.run_id,
            "ts": _format_timestamp(event.ts),
            "actor": event.actor,
            "event_type": event.event_type,
            "task_id": event.task_id,
            "payload": event.payload,
        }

        content_to_hash = (expected_prev_hash + canonical_json(body)).encode("utf-8")
        computed_hash = hashlib.sha256(content_to_hash).hexdigest()

        if event.hash != computed_hash:
            return {
                "intact": False,
                "verified": idx,
                "broken_at": event.sequence,
                "event_id": event.id,
            }

        expected_prev_hash = event.hash

    return {
        "intact": True,
        "verified": len(events),
        "broken_at": None,
        "event_id": None,
    }

