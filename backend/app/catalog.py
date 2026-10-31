"""Action catalog defining allowed plan actions, risk levels, and parameter schemas."""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel, Field

from app.models import Risk


class ReadSheetParams(BaseModel):
    dataset: str = Field(description="Name of the dataset to read (e.g., 'invoices', 'customers')")


class FilterRowsParams(BaseModel):
    condition: str = Field(description="Filter condition description (e.g., 'days overdue > 15')")
    field: Optional[str] = Field(default=None, description="Field name to filter on")
    operator: Optional[str] = Field(default=None, description="Filter operator: >, <, ==, !=")
    value: Optional[Any] = Field(default=None, description="Filter threshold value")


class UpdateSheetRowParams(BaseModel):
    dataset: str = Field(description="Target dataset name")
    row_id: Optional[str] = Field(default=None, description="Row ID to update")
    updates: Dict[str, Any] = Field(default_factory=dict, description="Key-value mapping of field updates")


class AppendSheetRowParams(BaseModel):
    dataset: str = Field(description="Target dataset name")
    data: Dict[str, Any] = Field(default_factory=dict, description="Row data to insert")


class DraftEmailParams(BaseModel):
    template: str = Field(description="Template name to render (e.g., 'payment_reminder')")
    recipient_field: Optional[str] = Field(default="email", description="Field containing recipient email")


class SendEmailParams(BaseModel):
    template: Optional[str] = Field(default=None, description="Template identifier used")
    recipient: Optional[str] = Field(default=None, description="Recipient email address")
    subject: Optional[str] = Field(default=None, description="Email subject")
    body: Optional[str] = Field(default=None, description="Email body content")


class SendMessageParams(BaseModel):
    channel: str = Field(default="telegram", description="Messaging channel: 'telegram', 'slack', or 'whatsapp'")
    template: Optional[str] = Field(default=None, description="Template identifier used")
    recipient: Optional[str] = Field(default=None, description="Target recipient chat ID or handle")
    message: Optional[str] = Field(default=None, description="Message text content")


class FlagConflictParams(BaseModel):
    resource: Optional[str] = Field(default=None, description="Resource identifier with conflict")
    reason: Optional[str] = Field(default=None, description="Conflict explanation")


class RequestHumanInputParams(BaseModel):
    prompt: str = Field(description="Question or input prompt for the human operator")


class GenerateSummaryParams(BaseModel):
    title: Optional[str] = Field(default=None, description="Title of summary report")


@dataclass(frozen=True)
class ActionDefinition:
    """Action metadata definition."""
    name: str
    risk: Risk
    label: str
    description: str
    params_schema: Type[BaseModel]


# Fixed catalog mapping per PRD 6.6.1
ACTION_CATALOG: Dict[str, ActionDefinition] = {
    "read_sheet": ActionDefinition(
        name="read_sheet",
        risk=Risk.read,
        label="Read Sheet",
        description="Load rows from a dataset",
        params_schema=ReadSheetParams,
    ),
    "filter_rows": ActionDefinition(
        name="filter_rows",
        risk=Risk.read,
        label="Filter Rows",
        description="Filter rows by safe condition",
        params_schema=FilterRowsParams,
    ),
    "update_sheet_row": ActionDefinition(
        name="update_sheet_row",
        risk=Risk.internal_write,
        label="Update Sheet Row",
        description="Update a row or cell in an internal dataset",
        params_schema=UpdateSheetRowParams,
    ),
    "append_sheet_row": ActionDefinition(
        name="append_sheet_row",
        risk=Risk.internal_write,
        label="Append Sheet Row",
        description="Append a new row to an internal dataset",
        params_schema=AppendSheetRowParams,
    ),
    "draft_email": ActionDefinition(
        name="draft_email",
        risk=Risk.internal_write,
        label="Draft Email",
        description="Generate email text from a template and row data",
        params_schema=DraftEmailParams,
    ),
    "send_email": ActionDefinition(
        name="send_email",
        risk=Risk.external,
        label="Send Email",
        description="Send an email to an external recipient",
        params_schema=SendEmailParams,
    ),
    "send_message": ActionDefinition(
        name="send_message",
        risk=Risk.external,
        label="Send Message",
        description="Send Telegram, Slack, or WhatsApp notification",
        params_schema=SendMessageParams,
    ),
    "flag_conflict": ActionDefinition(
        name="flag_conflict",
        risk=Risk.internal_write,
        label="Flag Conflict",
        description="Mark a scheduling or resource conflict",
        params_schema=FlagConflictParams,
    ),
    "request_human_input": ActionDefinition(
        name="request_human_input",
        risk=Risk.read,
        label="Request Human Input",
        description="Ask the owner a clarifying question or approval",
        params_schema=RequestHumanInputParams,
    ),
    "generate_summary": ActionDefinition(
        name="generate_summary",
        risk=Risk.internal_write,
        label="Generate Summary",
        description="Produce a run summary report",
        params_schema=GenerateSummaryParams,
    ),
}


def get_action(name: str) -> Optional[ActionDefinition]:
    """Retrieve action definition by name from the catalog."""
    return ACTION_CATALOG.get(name)


def risk_for(name: str) -> Risk:
    """Return the server-authoritative risk level for an action name."""
    action = ACTION_CATALOG.get(name)
    if not action:
        raise ValueError(f"Unknown action: '{name}' is not in the action catalog.")
    return action.risk


def catalog_prompt_text() -> str:
    """Render catalog into a concise instruction text for the planner prompt."""
    lines = ["Available Actions in the Catalog:"]
    for action in ACTION_CATALOG.values():
        lines.append(
            f"- `{action.name}` (risk: {action.risk.value}): {action.description}. "
            f"Parameters: {list(action.params_schema.model_fields.keys())}"
        )
    return "\n".join(lines)

