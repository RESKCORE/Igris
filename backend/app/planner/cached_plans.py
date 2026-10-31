"""Known-good cached plans for the demo scenarios (PRD 12.5).

Fallback when the LLM is slow, rate-limited, or disabled (USE_CACHED_PLANS).
Matched by cheap keyword heuristics -
  # ponytail: keyword routing suffices for the 3 demo scenarios; fuzzy/LLM routing
  # when unplanned instructions appear.
"""

from typing import Optional

from app.models import PlanSchema, TaskSchema


def _tasks(*specs) -> list:
    """Build TaskSchema list from (id, depends_on, action, params, description) tuples."""
    return [TaskSchema(id=tid, depends_on=list(deps), action=action, params=params, description=desc) for tid, deps, action, params, desc in specs]


S1_OVERDUE_INVOICES = PlanSchema(
    tasks=_tasks(
        ("t1", [], "read_sheet", {"dataset": "invoices"}, "Load the invoices dataset"),
        ("t2", ["t1"], "filter_rows", {"condition": "due_date is older than 15 days", "field": "due_date"}, "Keep overdue invoices past 15 days"),
        ("t3", ["t2"], "draft_email", {"template": "payment_reminder"}, "Draft payment reminder emails from the template"),
        ("t4", ["t3"], "send_email", {"template": "payment_reminder"}, "Send reminder emails to the customers of overdue invoices"),
        ("t5", ["t4"], "update_sheet_row", {"dataset": "invoices", "updates": {"status": "Reminded"}}, "Mark reminded invoices in the invoices sheet"),
    )
)

S2_ORDER_INTAKE = PlanSchema(
    tasks=_tasks(
        ("t1", [], "read_sheet", {"dataset": "orders"}, "Load the orders dataset"),
        ("t2", ["t1"], "draft_email", {"template": "order_confirmation"}, "Draft confirmation emails for new orders"),
        ("t3", ["t2"], "send_email", {"template": "order_confirmation"}, "Send confirmation emails to customers"),
        ("t4", ["t3"], "send_message", {"channel": "telegram", "template": "warehouse_notice"}, "Notify the warehouse on Telegram for dispatch"),
        ("t5", ["t4"], "update_sheet_row", {"dataset": "orders", "updates": {"status": "Confirmed"}}, "Mark orders as confirmed in the orders sheet"),
    )
)

S3_BOOKING_CONFLICTS = PlanSchema(
    tasks=_tasks(
        ("t1", [], "read_sheet", {"dataset": "bookings"}, "Load the bookings dataset"),
        ("t2", ["t1"], "flag_conflict", {"resource": "booking", "reason": "Double-booked resource slot"}, "Flag conflicting booking slots"),
        ("t3", ["t2"], "draft_email", {"template": "appointment_reminder"}, "Draft reminder emails for non-conflicting bookings"),
        ("t4", ["t3"], "send_email", {"template": "appointment_reminder"}, "Send booking reminders to customers"),
    )
)

_CACHED_PLANS = [
    ({"overdue", "invoice", "remind", "payment"}, S1_OVERDUE_INVOICES),
    ({"order", "confirm", "warehouse", "dispatch"}, S2_ORDER_INTAKE),
    ({"booking", "conflict", "appointment", "schedule", "slot", "notify"}, S3_BOOKING_CONFLICTS),
]

# A single keyword that clearly names a dataset/scenario makes the match decisive.
_STRONG_KEYWORDS = {"overdue", "invoice", "order", "booking", "conflict"}


def _stem(word: str) -> str:
    """Naively strip punctuation and a trailing plural s."""
    w = word.strip(".,!?;:()[]").lower()
    if len(w) > 4 and w.endswith("s"):
        w = w[:-1]  # ponytail: truncated-plural is fine for the 3 demo scenarios
    return w


def match_cached_plan(instruction: str) -> Optional[PlanSchema]:
    """Match a demo instruction to a known-good cached plan by keyword overlap."""
    stems = [s for s in (_stem(w) for w in instruction.split()) if len(s) >= 4]
    for keywords, plan in _CACHED_PLANS:
        hits = {
            k
            for k in keywords
            for s in stems
            if s == k or s.startswith(k) or k.startswith(s)
        }
        if len(hits) >= 2 or hits & _STRONG_KEYWORDS:
            return plan.model_copy(deep=True)
    return None
