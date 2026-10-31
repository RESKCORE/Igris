"""Message and email templates with placeholder rendering."""

import re
from typing import Any, Dict, Optional, Tuple
from sqlalchemy.orm import Session

from app.models import Template, generate_uuid


# Default system templates
DEFAULT_TEMPLATES = {
    "payment_reminder": {
        "channel": "email",
        "subject": "Payment Reminder: Invoice {{invoice_id}} for {{customer_name}}",
        "body": (
            "Dear {{customer_name}},\n\n"
            "This is a friendly reminder that invoice {{invoice_id}} for ₹{{amount}} "
            "was due on {{due_date}} and is currently overdue. "
            "Please arrange for the payment at your earliest convenience.\n\n"
            "If you have already paid, please ignore this email.\n\n"
            "Warm regards,\n"
            "Accounts Team, Shree Ganesh Retail"
        ),
    },
    "order_confirmation": {
        "channel": "email",
        "subject": "Order Confirmation: {{order_id}}",
        "body": (
            "Dear {{customer_name}},\n\n"
            "Thank you for your order #{{order_id}}. We have received your order for "
            "{{qty}} unit(s) of {{sku}} totaling ₹{{price}}.\n\n"
            "Status: {{status}}.\n\n"
            "Warm regards,\n"
            "Customer Support, Shree Ganesh Retail"
        ),
    },
    "appointment_reminder": {
        "channel": "email",
        "subject": "Reminder: Booking {{booking_id}} for {{resource}}",
        "body": (
            "Dear {{customer_name}},\n\n"
            "This is a reminder for your upcoming appointment (Booking: {{booking_id}}) "
            "for {{resource}} scheduled from {{slot_start}} to {{slot_end}}.\n\n"
            "Warm regards,\n"
            "Scheduling Team, Shree Ganesh Retail"
        ),
    },
    "warehouse_notice": {
        "channel": "telegram",
        "subject": "Warehouse Dispatch Alert: {{order_id}}",
        "body": (
            "📦 Dispatch Alert: Order {{order_id}} confirmed!\n"
            "Customer: {{customer_name}}\n"
            "SKU: {{sku}} | Qty: {{qty}} | Total: ₹{{price}}\n"
            "Please prepare package for shipping."
        ),
    },
}

PLACEHOLDER_PATTERN = re.compile(r"\{\{([a-zA-Z0-9_]+)\}\}")


def render(template_text: str, row: Dict[str, Any]) -> str:
    """Safely substitute {{placeholder}} variables with values from row dictionary.

    Raises KeyError if a required placeholder is missing or None in the row data.
    """
    def replacer(match: re.Match) -> str:
        var_name = match.group(1)
        if var_name not in row or row[var_name] is None:
            raise KeyError(f"Missing required placeholder value for '{{{{{var_name}}}}}'")
        return str(row[var_name])

    return PLACEHOLDER_PATTERN.sub(replacer, template_text)


def render_template(
    subject_template: Optional[str],
    body_template: str,
    row: Dict[str, Any],
) -> Tuple[Optional[str], str]:
    """Render both subject and body with the given row data dictionary."""
    rendered_subject = render(subject_template, row) if subject_template else None
    rendered_body = render(body_template, row)
    return rendered_subject, rendered_body


def seed_default_templates(db: Session) -> None:
    """Populate default templates in the database if not present."""
    for name, data in DEFAULT_TEMPLATES.items():
        existing = db.query(Template).filter(Template.name == name).first()
        if not existing:
            template = Template(
                id=generate_uuid(),
                name=name,
                channel=data["channel"],
                subject=data["subject"],
                body=data["body"],
            )
            db.add(template)
    db.commit()
