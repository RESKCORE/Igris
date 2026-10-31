"""SQLAlchemy database models and Pydantic schemas for OpsPilot."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Boolean,
    Text,
    JSON,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from pydantic import BaseModel, ConfigDict, Field

from app.db import Base


# ==========================================
# Enumerations
# ==========================================

class Risk(str, Enum):
    """Task risk levels defining execution boundaries."""
    read = "read"
    internal_write = "internal_write"
    external = "external"


class TaskStatus(str, Enum):
    """Lifecycle status of an individual task."""
    pending_review = "pending_review"
    approved = "approved"
    validated = "validated"
    flagged = "flagged"
    simulated = "simulated"
    executed = "executed"
    rejected = "rejected"
    failed = "failed"
    blocked = "blocked"


class RunState(str, Enum):
    """Overall state machine states for a run."""
    CREATED = "CREATED"
    PLANNED = "PLANNED"
    PLAN_APPROVED = "PLAN_APPROVED"
    VALIDATING = "VALIDATING"
    AWAITING_EXCEPTIONS = "AWAITING_EXCEPTIONS"
    READY_TO_EXECUTE = "READY_TO_EXECUTE"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Mode(str, Enum):
    """System execution modes."""
    simulation = "simulation"
    sandbox = "sandbox"
    live = "live"


class ExceptionStatus(str, Enum):
    """Status for human exception items."""
    open = "open"
    approved = "approved"
    fixed = "fixed"
    rejected = "rejected"


class UserRole(str, Enum):
    """Dashboard user roles."""
    owner = "owner"
    staff = "staff"
    auditor = "auditor"


def utc_now() -> datetime:
    """Return timezone-aware current UTC time."""
    return datetime.now(timezone.utc)


def iso_utc(dt: Optional[datetime]) -> Optional[str]:
    """Serialize a datetime as ISO-8601 UTC; naive values are tagged UTC.

    SQLite hands back naive datetimes even for timezone-aware columns, so raw
    .isoformat() emits offset-less strings. Tagging them UTC keeps the offset
    present so clients render the owner's true local time.
    """
    if dt is None:
        return None
    aware = dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    return aware.isoformat()


def generate_uuid() -> str:
    """Generate a UUID4 hex string."""
    return uuid.uuid4().hex


# ==========================================
# SQLAlchemy Models
# ==========================================

class Dataset(Base):
    """Metadata and schema definition for business datasets."""
    __tablename__ = "datasets"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    name = Column(String(128), unique=True, nullable=False, index=True)
    source_type = Column(String(64), default="internal_sheet")  # internal_sheet, google_sheet
    schema_def = Column(JSON, nullable=False, default=dict)  # column names and types
    rules_ref = Column(String(128), nullable=True)  # reference key in rules.yaml
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    rows = relationship("DatasetRow", back_populates="dataset", cascade="all, delete-orphan")


class DatasetRow(Base):
    """Individual data row inside a dataset."""
    __tablename__ = "dataset_rows"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    dataset_id = Column(String(64), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    row_index = Column(Integer, nullable=True)
    data = Column(JSON, nullable=False, default=dict)
    validation_status = Column(String(32), default="ok")  # ok, warning, error
    issues = Column(JSON, nullable=True, default=list)  # list of issue dicts
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    dataset = relationship("Dataset", back_populates="rows")


class Run(Base):
    """Workflow execution run initialized from user instruction."""
    __tablename__ = "runs"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    instruction = Column(Text, nullable=False)
    dataset_id = Column(String(64), nullable=True, index=True)
    mode = Column(String(32), default=Mode.simulation.value)
    state = Column(String(32), default=RunState.CREATED.value, index=True)
    created_by = Column(String(128), default="human:owner")
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    plans = relationship("Plan", back_populates="run", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="run", cascade="all, delete-orphan")
    exceptions = relationship("ExceptionItem", back_populates="run", cascade="all, delete-orphan")
    validation_results = relationship("ValidationResult", back_populates="run", cascade="all, delete-orphan")
    outbox = relationship("Outbox", back_populates="run", cascade="all, delete-orphan")


class Plan(Base):
    """Versioned plan generated by the planner and reviewable by human."""
    __tablename__ = "plans"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    run_id = Column(String(64), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, default=1)
    tasks = Column(JSON, nullable=False, default=list)  # list of task dicts
    clarifying_question = Column(Text, nullable=True)
    approved_by = Column(String(128), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    run = relationship("Run", back_populates="plans")


class Task(Base):
    """Concrete task item within a plan version."""
    __tablename__ = "tasks"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    run_id = Column(String(64), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_version = Column(Integer, default=1)
    action = Column(String(64), nullable=False)
    params = Column(JSON, nullable=False, default=dict)
    description = Column(Text, nullable=False)
    depends_on = Column(JSON, nullable=False, default=list)  # list of task IDs
    risk = Column(String(32), default=Risk.read.value)
    status = Column(String(32), default=TaskStatus.pending_review.value)
    result = Column(JSON, nullable=True)
    retry_count = Column(Integer, default=0)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    run = relationship("Run", back_populates="tasks")


class ValidationResult(Base):
    """Recorded validation failure or warning for a run."""
    __tablename__ = "validation_results"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    run_id = Column(String(64), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(String(64), nullable=True)
    row_ref = Column(String(64), nullable=True)
    rule_id = Column(String(64), nullable=False)
    severity = Column(String(32), nullable=False)  # error, warning
    field = Column(String(64), nullable=True)
    value = Column(Text, nullable=True)
    suggested_fix = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    run = relationship("Run", back_populates="validation_results")


class ExceptionItem(Base):
    """Exception routed to human operator for review and decision."""
    __tablename__ = "exceptions"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    run_id = Column(String(64), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(String(64), nullable=True)
    row_ref = Column(String(64), nullable=True)
    reason = Column(Text, nullable=False)
    raw_data = Column(JSON, nullable=False, default=dict)
    status = Column(String(32), default=ExceptionStatus.open.value)
    resolution = Column(JSON, nullable=True)  # decision, fixed_data, reason
    resolved_by = Column(String(128), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    run = relationship("Run", back_populates="exceptions")


class Template(Base):
    """Reusable message and notification templates."""
    __tablename__ = "templates"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    name = Column(String(128), unique=True, nullable=False, index=True)
    channel = Column(String(32), default="email")  # email, telegram, sms
    subject = Column(String(256), nullable=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)


class Outbox(Base):
    """Sent or simulated external communications log."""
    __tablename__ = "outbox"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    run_id = Column(String(64), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(String(64), nullable=False)
    row_ref = Column(String(64), nullable=True)
    idempotency_key = Column(String(128), unique=True, nullable=True, index=True)
    channel = Column(String(32), default="email")
    recipient = Column(String(256), nullable=False)
    original_recipient = Column(String(256), nullable=True)
    subject = Column(String(256), nullable=True)
    body = Column(Text, nullable=False)
    mode = Column(String(32), default=Mode.simulation.value)
    status = Column(String(32), default="simulated")  # simulated, sent, failed
    created_at = Column(DateTime(timezone=True), default=utc_now)

    run = relationship("Run", back_populates="outbox")


class Submission(Base):
    """Raw form submissions for intake processing."""
    __tablename__ = "submissions"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    form_type = Column(String(64), nullable=False, index=True)  # order, contact, appointment
    data = Column(JSON, nullable=False, default=dict)
    status = Column(String(32), default="pending")  # pending, processed, invalid
    created_at = Column(DateTime(timezone=True), default=utc_now)


class User(Base):
    """Dashboard user account for role-based operations and audits."""
    __tablename__ = "users"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    email = Column(String(256), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    role = Column(String(32), default=UserRole.owner.value)
    created_at = Column(DateTime(timezone=True), default=utc_now)


class AuditEvent(Base):
    """Append-only, tamper-evident hash-chained audit log."""
    __tablename__ = "audit_events"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    run_id = Column(String(64), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    ts = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    actor = Column(String(128), nullable=False)
    event_type = Column(String(64), nullable=False, index=True)
    task_id = Column(String(64), nullable=True)
    payload = Column(JSON, nullable=False, default=dict)
    prev_hash = Column(String(64), nullable=False)
    hash = Column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_run_sequence"),
    )


# ==========================================
# Pydantic Schemas
# ==========================================

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Any] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class HealthResponse(BaseModel):
    status: str
    mode: str
    database: Optional[str] = None
    llm_configured: Optional[bool] = None


class TaskParam(BaseModel):
    model_config = ConfigDict(extra="allow")


class TaskSchema(BaseModel):
    id: Optional[str] = None
    action: str
    params: Dict[str, Any] = Field(default_factory=dict)
    description: str
    depends_on: List[str] = Field(default_factory=list)
    risk: Optional[Risk] = None
    status: Optional[TaskStatus] = TaskStatus.pending_review


class PlanSchema(BaseModel):
    tasks: List[TaskSchema] = Field(default_factory=list)
    clarifying_question: Optional[str] = None
    version: Optional[int] = 1
    # Approval is recorded through the human queue; the planner never sets these.
    approved: Optional[bool] = None
    approved_by: Optional[str] = None


class RunCreateRequest(BaseModel):
    instruction: str
    dataset_id: Optional[str] = None


class RunResponse(BaseModel):
    id: str
    instruction: str
    dataset_id: Optional[str]
    mode: str
    state: str
    created_by: str
    created_at: str  # iso_utc(...) — offset-pinned so clients render local time
    updated_at: str  # iso_utc(...)
    plan: Optional[PlanSchema] = None
    summary: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class RunExecuteRequest(BaseModel):
    mode: Optional[Mode] = Mode.simulation
    confirm: Optional[bool] = False


class ExceptionResolveRequest(BaseModel):
    decision: str  # approve, fix, reject
    fixed_data: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None


class DatasetRowUpdate(BaseModel):
    data: Dict[str, Any]


class TemplateCreate(BaseModel):
    name: str
    channel: str = "email"
    subject: Optional[str] = None
    body: str


class SubmissionCreate(BaseModel):
    form_type: str
    data: Dict[str, Any]


class UserRead(BaseModel):
    id: str
    email: str
    name: str
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


