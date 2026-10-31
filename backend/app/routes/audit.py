"""Audit trail API endpoints."""

import csv
import io
import json
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.audit import canonical_json, verify_chain
from app.db import get_db
from app.models import AuditEvent, iso_utc

router = APIRouter(prefix="/runs", tags=["Audit"])
global_router = APIRouter(prefix="/audit", tags=["Audit"])

_EVENT_COLUMNS = [
    "id",
    "run_id",
    "sequence",
    "ts",
    "actor",
    "event_type",
    "task_id",
    "payload",
    "prev_hash",
    "hash",
]


def _event_dict(e: AuditEvent) -> Dict[str, Any]:
    """Shape a plain dict for an audit event row."""
    return {
        "id": e.id,
        "run_id": e.run_id,
        "sequence": e.sequence,
        "ts": iso_utc(e.ts),
        "actor": e.actor,
        "event_type": e.event_type,
        "task_id": e.task_id,
        "payload": e.payload,
        "prev_hash": e.prev_hash,
        "hash": e.hash,
    }


@router.get(
    "/{id}/audit",
    summary="Get audit events for a run",
)
def get_run_audit(
    id: str,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Retrieve the ordered, tamper-evident audit trail for a specific run."""
    events = (
        db.query(AuditEvent)
        .filter(AuditEvent.run_id == id)
        .order_by(AuditEvent.sequence.asc())
        .all()
    )
    return [
        {
            "id": e.id,
            "run_id": e.run_id,
            "sequence": e.sequence,
            "ts": iso_utc(e.ts),
            "actor": e.actor,
            "event_type": e.event_type,
            "task_id": e.task_id,
            "payload": e.payload,
            "prev_hash": e.prev_hash,
            "hash": e.hash,
        }
        for e in events
    ]


@router.get(
    "/{id}/audit/verify",
    summary="Verify cryptographic integrity of audit chain",
)
def verify_run_audit(
    id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Verify hash chain integrity by recalculating SHA-256 signatures."""
    result = verify_chain(db, id)
    return result


@router.get(
    "/{id}/audit/export",
    summary="Export audit trail",
)
def export_run_audit(
    id: str,
    format: str = Query("csv", description="Export format: 'csv' or 'pdf'"),
    db: Session = Depends(get_db),
) -> Response:
    """Export the run's audit trail in CSV format (or PDF in later stage)."""
    fmt = format.lower().strip()
    if fmt == "pdf":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail={
                "code": "not_implemented",
                "message": "PDF audit export is not implemented yet in Stage 2 (available in Stage 8).",
                "details": None,
            },
        )
    if fmt != "csv":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_format",
                "message": f"Unsupported export format '{format}'. Supported formats: csv, pdf.",
                "details": None,
            },
        )

    events = (
        db.query(AuditEvent)
        .filter(AuditEvent.run_id == id)
        .order_by(AuditEvent.sequence.asc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(_EVENT_COLUMNS)

    for e in events:
        writer.writerow([
            e.id,
            e.run_id,
            e.sequence,
            iso_utc(e.ts),
            e.actor,
            e.event_type,
            e.task_id or "",
            canonical_json(e.payload),
            e.prev_hash,
            e.hash,
        ])

    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=audit_{id}.csv"
        },
    )


@global_router.get(
    "",
    summary="List all audit events",
)
def list_all_audit(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """List every audit event across all runs, oldest first."""
    events = db.query(AuditEvent).order_by(AuditEvent.ts.asc(), AuditEvent.id.asc()).all()
    return [_event_dict(e) for e in events]


@global_router.get(
    "/verify",
    summary="Verify audit chain integrity for every run",
)
def verify_all_audit(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Recompute the hash chain of every run's audit trail."""
    run_ids = [row for (row,) in db.query(AuditEvent.run_id).distinct().all()]
    all_ok = True
    checked = 0
    for run_id in run_ids:
        result = verify_chain(db, run_id)
        all_ok = all_ok and bool(result.get("intact", False))
        checked += int(result.get("verified", 0) or 0)
    return {"valid": all_ok, "runs": len(run_ids), "verified": checked}


@global_router.get(
    "/export",
    summary="Export the full audit trail as JSON",
)
def export_all_audit(db: Session = Depends(get_db)) -> Response:
    """Return every audit event as a JSON export file."""
    events = db.query(AuditEvent).order_by(AuditEvent.ts.asc(), AuditEvent.id.asc()).all()
    payload = json.dumps([_event_dict(e) for e in events], indent=2, default=str)
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=audit_export.json"},
    )

