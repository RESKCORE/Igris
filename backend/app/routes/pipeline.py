"""Exception queue, outbox, preview, execute, and validation-summary routes.

Deterministic Python does the routing and execution. The LLM never sends or
writes anything: simulation/sandbox status is recorded in SQL, and live mode
only runs behind the mode+confirm+approval guard with a configured provider.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.adapters.mail import DeliveryError, send_email
from app.audit import append_event
from app.config import settings
from app.db import get_db
from app.models import (
    Dataset,
    DatasetRow,
    ExceptionItem,
    ExceptionResolveRequest,
    ExceptionStatus,
    Outbox,
    Plan,
    Run,
    RunExecuteRequest,
    RunState,
    Task,
    TaskStatus,
    Template,
    iso_utc,
    utc_now,
)
from app.templates import render_template

router = APIRouter(tags=["Pipeline"])


# ==========================================
# Exception queue
# ==========================================

@router.get("/exceptions", summary="List human-review exceptions")
def list_exceptions(
    run_id: Optional[str] = None,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List exception items, optionally filtered by run, newest first."""
    query = db.query(ExceptionItem).order_by(ExceptionItem.created_at.desc())
    if run_id:
        query = query.filter(ExceptionItem.run_id == run_id)
    return [_exception_dict(e) for e in query.all()]


@router.post("/exceptions/{id}/resolve", summary="Resolve an exception")
def resolve_exception(
    id: str,
    payload: ExceptionResolveRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Record the human decision on an exception and audit it (append-only)."""
    item = db.query(ExceptionItem).filter(ExceptionItem.id == id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "exception_not_found", "message": f"Exception '{id}' not found."},
        )

    status_map = {"approve": "approved", "fix": "fixed", "reject": "rejected"}
    new_status = status_map.get(payload.decision.lower())
    if new_status not in ExceptionStatus._value2member_map_:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "invalid_decision",
                "message": "decision must be one of: approve, fix, reject.",
            },
        )

    item.status = new_status
    item.resolution = {
        **(item.resolution or {}),  # keep suggested_fix and any prior context
        "decision": payload.decision,
        "reason": payload.reason,
    }
    item.resolved_by = "human:owner"
    item.resolved_at = utc_now()
    db.commit()

    append_event(
        db=db,
        run_id=item.run_id,
        actor=item.resolved_by or "human:owner",
        event_type="exception_resolved",
        payload={
            "exception_id": item.id,
            "row_ref": item.row_ref,
            "decision": payload.decision,
            "reason": payload.reason,
        },
    )
    return _exception_dict(item)


def _exception_dict(item: ExceptionItem) -> Dict[str, Any]:
    """Shape a plain dict for an exception row."""
    return {
        "id": item.id,
        "run_id": item.run_id,
        "task_id": item.task_id,
        "row_ref": item.row_ref,
        "reason": item.reason,
        "raw_data": item.raw_data or {},
        "suggested_fix": (item.resolution or {}).get("suggested_fix"),
        "status": item.status,
        "resolved_by": item.resolved_by,
        "created_at": iso_utc(item.created_at),
    }


# ==========================================
# Validation summary
# ==========================================

@router.get("/validation", summary="Global row-validation counts")
def get_validation_summary(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Count rows per validation status across all datasets."""
    rows = db.query(DatasetRow).all()
    counts: Dict[str, int] = {"passed": 0, "warnings": 0, "errors": 0}
    for row in rows:
        s = row.validation_status or "ok"
        if s == "ok":
            counts["passed"] += 1
        elif s == "warning":
            counts["warnings"] += 1
        elif s == "error":
            counts["errors"] += 1
    counts["total"] = len(rows)
    return counts


# ==========================================
# Outbox & preview
# ==========================================

@router.get("/outbox", summary="List all outbox messages")
def list_outbox(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """List every recorded external communication, newest first."""
    rows = db.query(Outbox).order_by(Outbox.created_at.desc()).all()
    return [_outbox_dict(m) for m in rows]


def _outbox_dict(m: Outbox) -> Dict[str, Any]:
    """Shape a plain dict for an outbox row."""
    return {
        "id": m.id,
        "run_id": m.run_id,
        "task_id": m.task_id,
        "channel": m.channel,
        "recipient": m.recipient,
        "original_recipient": m.original_recipient,
        "subject": m.subject,
        "body": m.body,
        "mode": m.mode,
        "status": m.status,
        "created_at": iso_utc(m.created_at),
    }


@router.get("/runs/{run_id}/preview", summary="Preview messages a run would send")
def get_preview(run_id: str, db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Render the outbound messages for the run's plan without persisting them."""
    run = _get_run(db, run_id)
    drafts = _draft_messages(db, run)
    now = iso_utc(utc_now())
    return [
        {
            "id": f"preview-{run.id}-{i}",
            "channel": d["channel"],
            "recipient": d["recipient"],
            "subject": d["subject"],
            "body": d["body"],
            "mode": run.mode,
            "status": "simulated",
            "created_at": now,
        }
        for i, d in enumerate(drafts, start=1)
    ]


@router.post("/runs/{run_id}/execute", summary="Execute the run's external actions")
def execute_run(
    run_id: str,
    payload: RunExecuteRequest,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Run the plan's external tasks through the guarded messaging pipeline."""
    run = _get_run(db, run_id)

    if run.state == RunState.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "already_executed", "message": "This run has already been executed."},
        )

    mode = payload.mode.value if payload.mode else run.mode

    sent: List[Dict[str, Any]] = []
    if mode != "simulation":
        plan = _latest_plan(db, run)
        if plan is None or plan.approved_by is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "approval_required",
                    "message": f"{mode.capitalize()} mode requires an approved plan.",
                },
            )
    if mode == "live":
        if not payload.confirm:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "confirm_required", "message": "Live mode requires confirm=true."},
            )
        if not settings.ALLOW_LIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "live_blocked",
                    "message": "Live mode is disabled by ALLOW_LIVE=false.",
                },
            )
    if mode == "sandbox":
        if not settings.SANDBOX_REDIRECT_TO:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "sandbox_redirect_not_configured",
                    "message": "Set SANDBOX_REDIRECT_TO before using sandbox mode.",
                },
            )

    drafts = _draft_messages(db, run)

    plan = _latest_plan(db, run)
    if plan is not None:
        for t in (
            db.query(Task)
            .filter(Task.run_id == run.id, Task.plan_version == plan.version)
            .all()
        ):
            t.status = TaskStatus.simulated.value
            db.add(t)

    external_task_id = _first_external_task_id(db, run)
    failed = 0
    for i, draft in enumerate(drafts, start=1):
        outbox = Outbox(
            run_id=run.id,
            task_id=str(external_task_id or ""),
            idempotency_key=f"{run.id}:{i}:{draft['recipient']}",
            channel=draft["channel"],
            recipient=draft["recipient"],
            original_recipient=draft["recipient"],
            subject=draft["subject"],
            body=draft["body"],
            mode=mode,
            status="simulated",
        )

        if mode == "sandbox":
            # Every recipient is rewritten to the configured safe inbox, then delivered.
            outbox.recipient = settings.SANDBOX_REDIRECT_TO
            try:
                _deliver(outbox)
                outbox.status = "sandbox"
            except HTTPException as exc:
                outbox.status = "failed"
                outbox.body = f"{outbox.body}\n\n[delivery error] {exc.detail['message']}"
        elif mode == "live":
            try:
                _deliver(outbox)
                outbox.status = "sent"
            except HTTPException as exc:
                outbox.status = "failed"
                outbox.body = f"{outbox.body}\n\n[delivery error] {exc.detail['message']}"

        db.add(outbox)
        db.flush()
        if outbox.status == "failed":
            failed += 1
        sent.append(_outbox_dict(outbox))

    append_event(
        db=db,
        run_id=run.id,
        actor="executor",
        event_type="task_executed",
        payload={
            "mode": mode,
            "count": len(sent),
            "delivered": len(sent) - failed,
            "failed": failed,
            "recipients": [m["recipient"] for m in sent],
            "external_delivery": mode in ("sandbox", "live"),
        },
    )

    if sent and failed == len(sent):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "send_failed",
                "message": "No message could be delivered. Check WEB3FORMS_ACCESS_KEY or SMTP_* settings.",
            },
        )

    run.state = RunState.COMPLETED.value
    db.commit()
    append_event(
        db=db,
        run_id=run.id,
        actor="executor",
        event_type="run_completed",
        payload={"mode": mode, "message_count": len(sent)},
    )

    return sent


def _deliver(outbox: Outbox) -> None:
    """Perform a real live send via the shared mail adapter. Only the executor guard reaches this.

    Fails closed: without a configured provider nothing is sent.
    """
    try:
        send_email(
            subject=outbox.subject or "OpsPilot notification",
            body=outbox.body,
            to=outbox.recipient,
        )
    except DeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "send_failed", "message": str(exc)},
        )


# ==========================================
# Draft generation (deterministic)
# ==========================================

def _get_run(db: Session, run_id: str) -> Run:
    """Fetch a run or raise 404."""
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "run_not_found", "message": f"Run '{run_id}' not found."},
        )
    return run


def _latest_plan(db: Session, run: Run) -> Optional[Plan]:
    """Return the highest-version plan for a run."""
    return (
        db.query(Plan)
        .filter(Plan.run_id == run.id)
        .order_by(Plan.version.desc())
        .first()
    )


def _first_external_task_id(db: Session, run: Run) -> Optional[str]:
    """Task id of the first external-risk task in the latest plan version."""
    plan = _latest_plan(db, run)
    for t in (plan.tasks or [] if plan else []):
        if t.get("risk") == "external":
            return t.get("id")
    return None


_DATASET_TEMPLATE_FALLBACK = {
    "invoices": "payment_reminder",
    "bookings": "appointment_reminder",
    "orders": "order_confirmation",
}


def _draft_messages(db: Session, run: Run) -> List[Dict[str, Any]]:
    """Render outbound message drafts from the run's dataset and plan templates.

    Deterministic: template + trusted validated row data only. Rows that fail
    validation or lack a template variable are skipped, never guessed.
    """
    plan = _latest_plan(db, run)
    tasks = plan.tasks or [] if plan else []
    ext = [t for t in tasks if t.get("risk") == "external"]
    if not ext:
        return []

    channel = "email" if any(t.get("action") == "send_email" for t in ext) else "message"
    template_name = next((t["params"].get("template") for t in ext if t.get("params", {}).get("template")), None)
    inline_subject = next((t["params"].get("subject") for t in ext if t.get("params", {}).get("subject")), None)
    inline_body = next((t["params"].get("body") for t in ext if t.get("params", {}).get("body")), None)

    # Choose the dataset: run's dataset, else the first read_sheet task's dataset.
    dataset = None
    if run.dataset_id:
        dataset = (
            db.query(Dataset)
            .filter((Dataset.id == run.dataset_id) | (Dataset.name == run.dataset_id))
            .first()
        )
    if dataset is None:
        read_param = next((t["params"].get("dataset") for t in tasks if t.get("action") == "read_sheet"), None)
        if read_param:
            dataset = (
                db.query(Dataset)
                .filter((Dataset.id == read_param) | (Dataset.name == read_param))
                .first()
            )
    if dataset is None:
        return []

    template_name = template_name or _DATASET_TEMPLATE_FALLBACK.get(dataset.name)
    template = db.query(Template).filter(Template.name == template_name).first() if template_name else None
    if template:
        subj_tpl, body_tpl = template.subject, template.body
    elif inline_body:
        subj_tpl, body_tpl = inline_subject, inline_body  # inline overrides from the plan
    else:
        return []  # nothing sendable without a template or inline body

    rows = (
        db.query(DatasetRow)
        .filter(DatasetRow.dataset_id == dataset.id, DatasetRow.validation_status == "ok")
        .order_by(DatasetRow.row_index.asc())
        .limit(settings.MAX_EXTERNAL_ACTIONS)
        .all()
    )
    customers = _customer_contact_map(db)

    drafts: List[Dict[str, Any]] = []
    for row in rows:
        context = dict(row.data)
        cust_id = context.get("customer_id")
        if cust_id and cust_id in customers:
            merged = dict(customers[cust_id])
            merged.update(context)
            context = merged

        recipient = context.get("email") if channel == "email" else context.get("phone") or context.get("customer_id")
        if not recipient:
            continue

        try:
            subject, body = render_template(subj_tpl or inline_subject, body_tpl, context)
        except KeyError:
            continue  # missing placeholder: skip rather than send a broken message

        drafts.append({"channel": channel, "recipient": str(recipient), "subject": subject, "body": body})
    if len(drafts) > settings.MAX_EXTERNAL_ACTIONS:
        drafts = drafts[: settings.MAX_EXTERNAL_ACTIONS]
    return drafts


def _customer_contact_map(db: Session) -> Dict[str, Dict[str, Any]]:
    """Map customer_id -> merged customer row for joining contact fields."""
    ds = db.query(Dataset).filter(Dataset.name == "customers").first()
    if not ds:
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for r in db.query(DatasetRow).filter(DatasetRow.dataset_id == ds.id).all():
        data = dict(r.data or {})
        cid = data.get("customer_id")
        if cid:
            data["customer_name"] = data.get("customer_name") or data.get("name")
            out[str(cid)] = data
    return out
