"""Run lifecycle routes: create, list, review, edit, and approve plans."""

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
    ExceptionStatus,
    Plan,
    PlanSchema,
    Run,
    RunCreateRequest,
    RunResponse,
    RunState,
    Task,
    TaskSchema,
    TaskStatus,
    iso_utc,
    utc_now,
)
from app.planner.planner import PlannerResult, PlannerUnavailable, run_planner
from app.planner.plan_guard import enforce_plan
from app.templates import Template

router = APIRouter(prefix="/runs", tags=["Runs"])


@router.post("", response_model=RunResponse, summary="Create a run from a plain-language instruction")
def create_run(payload: RunCreateRequest, db: Session = Depends(get_db)) -> RunResponse:
    """Plan the instruction, enforce the plan guard, persist Plan+Tasks, and audit."""
    instruction = (payload.instruction or "").strip()
    if not instruction:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "instruction_required", "message": "Instruction must not be empty."},
        )

    dataset: Optional[Dataset] = None
    if payload.dataset_id:
        dataset = (
            db.query(Dataset)
            .filter((Dataset.id == payload.dataset_id) | (Dataset.name == payload.dataset_id))
            .first()
        )
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "dataset_not_found", "message": f"Dataset '{payload.dataset_id}' not found."},
            )
    dataset_schemas = {dataset.name: dataset.schema_def} if dataset else {
        d.name: d.schema_def for d in db.query(Dataset).all()
    }
    templates = [{"name": t.name, "channel": t.channel} for t in db.query(Template).all()]

    try:
        result = run_planner(instruction, dataset_schemas, templates)
    except PlannerUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "planner_unavailable", "message": str(exc)},
        )

    return _persist_planned_run(db, instruction, result, dataset.id if dataset else None)


@router.get("", summary="List runs (newest first)")
def list_runs(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """List all runs in creation order (newest first), without plans attached."""
    runs = db.query(Run).order_by(Run.created_at.desc()).all()
    return [_run_dict(r) for r in runs]


def _run_dict(run: Run) -> Dict[str, Any]:
    """Shape a plain dict for a run row."""
    return {
        "id": run.id,
        "instruction": run.instruction,
        "dataset_id": run.dataset_id,
        "mode": run.mode,
        "state": run.state,
        "created_by": run.created_by,
        "created_at": iso_utc(run.created_at),
        "updated_at": iso_utc(run.updated_at),
    }


@router.get("/{run_id}", response_model=RunResponse, summary="Get run status, plan, and summary")
def get_run(run_id: str, db: Session = Depends(get_db)) -> RunResponse:
    """Return a run with its latest plan version attached."""
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "run_not_found", "message": f"Run '{run_id}' not found."},
        )
    plan_row = (
        db.query(Plan).filter(Plan.run_id == run.id).order_by(Plan.version.desc()).first()
    )
    plan_schema = None
    if plan_row:
        plan_schema = PlanSchema(
            version=plan_row.version,
            clarifying_question=plan_row.clarifying_question,
            tasks=[
                TaskSchema.model_validate(t)
                for t in (plan_row.tasks or [])
            ],
            approved=plan_row.approved_by is not None,
            approved_by=plan_row.approved_by,
        )
    return _run_response(run, plan_schema)


@router.put("/{run_id}/plan", summary="Human-edited plan revision (re-guarded)")
def update_plan(
    run_id: str,
    payload: PlanSchema,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Store an owner-edited plan as a new version after the plan guard re-checks it."""
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "run_not_found", "message": f"Run '{run_id}' not found."},
        )

    guarded, dropped = enforce_plan(payload, max_external=settings.MAX_EXTERNAL_ACTIONS)
    if not guarded.tasks:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "plan_empty",
                "message": "Edited plan has no valid tasks after guard enforcement.",
                "details": dropped,
            },
        )

    latest = (
        db.query(Plan).filter(Plan.run_id == run.id).order_by(Plan.version.desc()).first()
    )
    new_version = (latest.version if latest else 0) + 1
    plan_row = Plan(
        run_id=run.id,
        version=new_version,
        tasks=[t.model_dump() for t in guarded.tasks],
        clarifying_question=guarded.clarifying_question,
        approved_by=None,
    )
    db.add(plan_row)
    _mirror_tasks(db, run.id, new_version, guarded.tasks)

    append_event(
        db=db,
        run_id=run.id,
        actor="human:owner",
        event_type="plan_edited",
        payload={"version": new_version, "task_count": len(guarded.tasks), "dropped": dropped},
    )
    run.state = RunState.PLANNED.value if run.state in (RunState.PLAN_APPROVED.value,) else run.state
    db.commit()

    return _plan_dict(plan_row)


@router.post("/{run_id}/approve", summary="Approve the latest plan version")
def approve_plan(run_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Record the human approval for the latest plan version and audit it."""
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "run_not_found", "message": f"Run '{run_id}' not found."},
        )

    plan = (
        db.query(Plan).filter(Plan.run_id == run.id).order_by(Plan.version.desc()).first()
    )
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "plan_missing", "message": "Run has no plan to approve."},
        )

    if plan.approved_by is None:
        plan.approved_by = run.created_by or "human:owner"
        plan.approved_at = utc_now()
        run.state = RunState.PLAN_APPROVED.value
        append_event(
            db=db,
            run_id=run.id,
            actor=plan.approved_by,
            event_type="plan_approved",
            payload={"version": plan.version, "task_count": len(plan.tasks or [])},
        )
        db.commit()
        db.refresh(plan)
        _notify_owner(
            db,
            run.id,
            subject=f"Igris: Plan approved — {run.instruction}",
            body=(
                f"Hello,\n\n"
                f"Demo note: this notification normally goes to the admin, but it is "
                f"rewritten here to treat YOU as a customer for demo purposes.\n\n"
                f"{_demo_customer_blurb(db)}\n\n"
                f"Good news — your payment reminder for the invoice shown above has "
                f"been approved and will be sent to you shortly."
            ),
        )

    return _plan_dict(plan)


def _plan_dict(plan: Plan) -> Dict[str, Any]:
    """Shape a plain dict for a stored plan row."""
    return {
        "run_id": plan.run_id,
        "version": plan.version,
        "tasks": plan.tasks or [],
        "clarifying_question": plan.clarifying_question,
        "approved": plan.approved_by is not None,
        "approved_by": plan.approved_by,
    }


def _persist_planned_run(
    db: Session,
    instruction: str,
    result: PlannerResult,
    dataset_id: Optional[str],
) -> RunResponse:
    """Persist run, plan, mirrored task rows, and the plan_created audit event."""
    run = Run(
        instruction=instruction,
        dataset_id=dataset_id,
        mode=settings.MODE,
        state=RunState.PLANNED.value if (result.plan and result.plan.tasks) else RunState.CREATED.value,
    )
    db.add(run)
    db.flush()

    plan_schema = result.plan or PlanSchema(tasks=[], clarifying_question=None)
    plan_row = Plan(
        run_id=run.id,
        version=1,
        tasks=[t.model_dump() for t in plan_schema.tasks],
        clarifying_question=plan_schema.clarifying_question,
    )
    db.add(plan_row)

    for t in plan_schema.tasks:
        db.add(
            Task(
                run_id=run.id,
                plan_version=1,
                action=t.action,
                params=t.params,
                description=t.description,
                depends_on=t.depends_on,
                risk=t.risk.value if t.risk else "read",
                status=TaskStatus.pending_review.value,
            )
        )

    append_event(
        db=db,
        run_id=run.id,
        actor="planner:crewai",
        event_type="plan_created",
        payload={
            "source": result.source,
            "task_count": len(plan_schema.tasks),
            "dropped": result.dropped,
            "clarifying_question": plan_schema.clarifying_question,
            "model": settings.LLM_MODEL if result.source != "cached" else "cached_plans",
            "note": result.note,
        },
    )

    # Route validation errors on the run's dataset to the human exception queue.
    if dataset_id:
        _stage_dataset_exceptions(db, run.id, dataset_id)

    db.commit()
    db.refresh(run)
    _notify_owner(
        db,
        run.id,
        subject=f"Igris: New plan ready — {instruction}",
        body=(
            f"Hello,\n\n"
            f"Demo note: this notification normally goes to the admin, but it is "
            f"rewritten here to treat YOU as a customer for demo purposes.\n\n"
            f"{_demo_customer_blurb(db)}\n\n"
            f"No action is needed from you right now."
        ),
    )
    return _run_response(run, PlanSchema(version=1, clarifying_question=plan_schema.clarifying_question, tasks=plan_schema.tasks))


def _mirror_tasks(db: Session, run_id: str, plan_version: int, tasks: List[TaskSchema]) -> None:
    """Persist mirrored Task rows for a plan version."""
    for t in tasks:
        db.add(
            Task(
                run_id=run_id,
                plan_version=plan_version,
                action=t.action,
                params=t.params,
                description=t.description,
                depends_on=t.depends_on,
                risk=t.risk.value if t.risk else "read",
                status=TaskStatus.pending_review.value,
            )
        )


def _stage_dataset_exceptions(db: Session, run_id: str, dataset_id: str) -> None:
    """Create human-review exception items for every error row in the run's dataset."""
    dataset = (
        db.query(Dataset)
        .filter((Dataset.id == dataset_id) | (Dataset.name == dataset_id))
        .first()
    )
    if not dataset:
        return

    error_rows = (
        db.query(DatasetRow)
        .filter(DatasetRow.dataset_id == dataset.id, DatasetRow.validation_status == "error")
        .order_by(DatasetRow.row_index.asc())
        .limit(settings.MAX_EXTERNAL_ACTIONS)
        .all()
    )

    first_col = next(iter((dataset.schema_def or {}).get("columns", [])), None)
    for row in error_rows:
        issues = row.issues or []
        suggestion = next(
            (i.get("suggested_fix") for i in issues if i.get("suggested_fix")), None
        )
        item = ExceptionItem(
            run_id=run_id,
            row_ref=str(row.data.get(first_col, row.id)) if first_col else row.id,
            reason="; ".join(str(i.get("message")) for i in issues),
            raw_data=dict(row.data),
            resolution={"suggested_fix": suggestion} if suggestion else None,
            status=ExceptionStatus.open.value,
        )
        db.add(item)
        db.flush()
        append_event(
            db=db,
            run_id=run_id,
            actor="system",
            event_type="exception_raised",
            task_id=None,
            payload={"exception_id": item.id, "row_ref": item.row_ref, "reason": item.reason},
        )


def _run_response(run: Run, plan_schema: Optional[PlanSchema]) -> RunResponse:
    """Shape a RunResponse from ORM rows."""
    return RunResponse(
        id=run.id,
        instruction=run.instruction,
        dataset_id=run.dataset_id,
        mode=run.mode,
        state=run.state,
        created_by=run.created_by,
        created_at=iso_utc(run.created_at) or "",
        updated_at=iso_utc(run.updated_at) or "",
        plan=plan_schema,
        summary=None,
    )


def _demo_customer_blurb(db: Session) -> str:
    """Demo-only customer view: map the reader to a mock customer ID and overdue invoice.

    # ponytail: demo personalization only; swap for a real recipient mapper if mail ever goes true-customer.
    """
    invoice_row: Optional[DatasetRow] = None
    inv_ds = db.query(Dataset).filter(Dataset.name == "invoices").first()
    if inv_ds:
        today = utc_now().date().isoformat()
        rows = (
            db.query(DatasetRow)
            .filter(DatasetRow.dataset_id == inv_ds.id)
            .order_by(DatasetRow.row_index.asc())
            .all()
        )
        for r in rows:
            d = r.data or {}
            if (d.get("status", "") or "").lower() == "unpaid" and (d.get("due_date") or "") < today:
                invoice_row = r
                break
        invoice_row = invoice_row or next(iter(rows), None)
    if invoice_row is None or not invoice_row.data:
        return "Customer ID: CUST-001\nInvoice: INV-101 — ₹12000, status Unpaid"

    data = dict(invoice_row.data)
    cust_row: Optional[DatasetRow] = None
    cust_ds = db.query(Dataset).filter(Dataset.name == "customers").first()
    if cust_ds:
        for r in (
            db.query(DatasetRow)
            .filter(DatasetRow.dataset_id == cust_ds.id)
            .order_by(DatasetRow.row_index.asc())
            .all()
        ):
            if (r.data or {}).get("customer_id") == data.get("customer_id"):
                cust_row = r
                break

    lines = [f"Your customer record (from our demo database):"]
    if cust_row and cust_row.data:
        cd = cust_row.data
        lines.append(
            f"Customer ID: {cd.get('customer_id')} — {cd.get('name')}, "
            f"email: {cd.get('email')}, city: {cd.get('city')}"
        )
    else:
        lines.append(f"Customer ID: {data.get('customer_id')}")
    lines.append(
        f"Invoice: {data.get('invoice_id')} — ₹{data.get('amount')}, "
        f"due {data.get('due_date')}, status {data.get('status')}"
    )
    lines.append("This invoice is past its due date — a payment reminder is on its way to you.")
    return "\n".join(lines)


def _notify_owner(db: Session, run_id: str, subject: str, body: str) -> None:
    """Best-effort owner notification; every attempt is audited as owner_notified.

    No-ops without OWNER_NOTIFY/OWNER_EMAIL so tests and unconfigured
    deployments stay hermetic. Delivery failures are recorded and swallowed —
    they must never break the API response.
    """
    if not (settings.OWNER_NOTIFY and settings.OWNER_EMAIL):
        return
    payload: Dict[str, Any] = {"subject": subject, "to": settings.OWNER_EMAIL, "provider": None}
    try:
        payload["provider"] = send_email(subject=subject, body=body, to=settings.OWNER_EMAIL)
        payload["status"] = "delivered"
    except DeliveryError as exc:
        payload["status"] = "failed"
        payload["error"] = str(exc)
    append_event(
        db=db,
        run_id=run_id,
        actor="system",
        event_type="owner_notified",
        payload=payload,
    )
