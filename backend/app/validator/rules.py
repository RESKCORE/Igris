"""Deterministic hard validation rules for OpsPilot."""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set
import email_validator
from pydantic import BaseModel
import phonenumbers


class Issue(BaseModel):
    """Validation issue found on a specific field or row."""
    rule_id: str
    field: Optional[str] = None
    value: Any = None
    severity: str = "error"  # "error" or "warning"
    message: str
    suggested_fix: Optional[str] = None


def check_required(field: str, val: Any) -> Optional[Issue]:
    """REQ-01: Verify required field is present and non-empty."""
    if val is None or (isinstance(val, str) and not val.strip()):
        return Issue(
            rule_id="REQ-01",
            field=field,
            value=val,
            severity="error",
            message=f"Mandatory field '{field}' is missing or empty.",
            suggested_fix="Provide a valid non-empty value.",
        )
    return None


def check_email(field: str, val: Any) -> Optional[Issue]:
    """EML-01: Verify email format is syntactically valid."""
    if val is None or val == "":
        return None  # Let check_required handle missing values
    try:
        email_validator.validate_email(str(val).strip(), check_deliverability=False)
        return None
    except email_validator.EmailNotValidError as exc:
        return Issue(
            rule_id="EML-01",
            field=field,
            value=val,
            severity="error",
            message=f"Invalid email syntax: {str(exc)}",
            suggested_fix="Correct the email syntax to username@domain.com.",
        )


def check_phone(field: str, val: Any, region: str = "IN") -> Optional[Issue]:
    """PHN-01: Verify phone number format (severity warning)."""
    if val is None or val == "":
        return None
    try:
        parsed = phonenumbers.parse(str(val).strip(), region)
        if not phonenumbers.is_valid_number(parsed):
            return Issue(
                rule_id="PHN-01",
                field=field,
                value=val,
                severity="warning",
                message=f"Phone number '{val}' is not a valid recognized number for region {region}.",
                suggested_fix="Ensure valid 10-digit number with standard country code.",
            )
        return None
    except Exception as exc:
        return Issue(
            rule_id="PHN-01",
            field=field,
            value=val,
            severity="warning",
            message=f"Failed to parse phone number: {str(exc)}",
            suggested_fix="Provide valid standard phone digits.",
        )


def check_number_range(
    field: str,
    val: Any,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
    disallow_negative: bool = True,
) -> Optional[Issue]:
    """NUM-01: Verify number is non-negative and within configured range."""
    if val is None or val == "":
        return None
    try:
        num = float(val)
    except (ValueError, TypeError):
        return Issue(
            rule_id="NUM-01",
            field=field,
            value=val,
            severity="error",
            message=f"Field '{field}' must be a numeric value.",
            suggested_fix="Convert value to a valid number.",
        )

    if disallow_negative and num < 0:
        return Issue(
            rule_id="NUM-01",
            field=field,
            value=val,
            severity="error",
            message=f"Negative value '{num}' is not allowed for '{field}'.",
            suggested_fix=f"Use absolute positive amount {abs(num)}.",
        )

    if min_val is not None and num < min_val:
        return Issue(
            rule_id="NUM-01",
            field=field,
            value=val,
            severity="error",
            message=f"Value {num} is below minimum allowed {min_val}.",
            suggested_fix=f"Increase value to at least {min_val}.",
        )

    if max_val is not None and num > max_val:
        return Issue(
            rule_id="NUM-01",
            field=field,
            value=val,
            severity="error",
            message=f"Value {num} exceeds maximum allowed {max_val}.",
            suggested_fix=f"Reduce value to at most {max_val}.",
        )

    return None


def check_date_sane(
    field: str,
    val: Any,
    not_after_days: int = 365,
    not_before_year: int = 2000,
) -> Optional[Issue]:
    """DAT-01: Verify date is valid and within a reasonable timeline window."""
    if val is None or val == "":
        return None

    parsed_date: Optional[date] = None
    val_str = str(val).strip()

    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed_date = datetime.strptime(val_str.split("T")[0], "%Y-%m-%d").date()
            break
        except ValueError:
            continue

    if not parsed_date:
        return Issue(
            rule_id="DAT-01",
            field=field,
            value=val,
            severity="error",
            message=f"Date '{val}' is not in a valid recognized format (expected YYYY-MM-DD).",
            suggested_fix="Format date as YYYY-MM-DD.",
        )

    today = date.today()
    max_allowed = today + timedelta(days=not_after_days)

    if parsed_date.year < not_before_year:
        return Issue(
            rule_id="DAT-01",
            field=field,
            value=val,
            severity="error",
            message=f"Date {parsed_date} is too far in the past (before year {not_before_year}).",
            suggested_fix=f"Provide a recent valid date after {not_before_year}.",
        )

    if parsed_date > max_allowed:
        return Issue(
            rule_id="DAT-01",
            field=field,
            value=val,
            severity="error",
            message=f"Date {parsed_date} exceeds maximum sane future limit ({max_allowed}).",
            suggested_fix=f"Adjust date to be within {not_after_days} days of today.",
        )

    return None


def check_uniqueness(field: str, rows: List[Dict[str, Any]]) -> Dict[int, List[Issue]]:
    """DUP-01: Identify rows containing duplicate primary or candidate keys."""
    issues_by_row: Dict[int, List[Issue]] = {}
    seen_values: Dict[Any, int] = {}

    for idx, row in enumerate(rows):
        val = row.get(field)
        if val is None or val == "":
            continue
        val_str = str(val).strip()
        if val_str in seen_values:
            first_idx = seen_values[val_str]
            iss = Issue(
                rule_id="DUP-01",
                field=field,
                value=val,
                severity="error",
                message=f"Duplicate key '{val}' in field '{field}' (previously seen at row {first_idx + 1}).",
                suggested_fix=f"Assign a unique '{field}' identifier.",
            )
            issues_by_row.setdefault(idx, []).append(iss)
        else:
            seen_values[val_str] = idx

    return issues_by_row


def check_reference(
    field: str,
    val: Any,
    valid_keys: Set[Any],
) -> Optional[Issue]:
    """REF-01: Verify foreign key reference exists in parent dataset."""
    if val is None or val == "":
        return None
    val_str = str(val).strip()
    if val_str not in valid_keys:
        return Issue(
            rule_id="REF-01",
            field=field,
            value=val,
            severity="error",
            message=f"Referenced ID '{val}' does not exist in target dataset.",
            suggested_fix="Select or link an existing customer record.",
        )
    return None


def check_resource_conflicts(
    rows: List[Dict[str, Any]],
    resource_field: str = "resource",
    start_field: str = "slot_start",
    end_field: str = "slot_end",
) -> Dict[int, List[Issue]]:
    """CNF-01: Detect booking time overlaps on the same resource."""
    issues_by_row: Dict[int, List[Issue]] = {}
    parsed_slots: List[Dict[str, Any]] = []

    for idx, row in enumerate(rows):
        res = row.get(resource_field)
        s_val = row.get(start_field)
        e_val = row.get(end_field)
        if not (res and s_val and e_val):
            continue

        try:
            s_dt = datetime.fromisoformat(str(s_val).replace("Z", "+00:00"))
            e_dt = datetime.fromisoformat(str(e_val).replace("Z", "+00:00"))
            parsed_slots.append({"idx": idx, "resource": str(res).strip(), "start": s_dt, "end": e_dt})
        except Exception:
            continue

    # Compare each pair for overlap on the same resource
    for i in range(len(parsed_slots)):
        for j in range(i + 1, len(parsed_slots)):
            slot_a = parsed_slots[i]
            slot_b = parsed_slots[j]

            if slot_a["resource"] == slot_b["resource"]:
                # Overlap condition: max(start_a, start_b) < min(end_a, end_b)
                if max(slot_a["start"], slot_b["start"]) < min(slot_a["end"], slot_b["end"]):
                    idx_a = slot_a["idx"]
                    idx_b = slot_b["idx"]

                    iss_a = Issue(
                        rule_id="CNF-01",
                        field=resource_field,
                        value=slot_a["resource"],
                        severity="error",
                        message=(
                            f"Scheduling overlap on '{slot_a['resource']}' "
                            f"between [{slot_a['start']} - {slot_a['end']}] and row {idx_b + 1}."
                        ),
                        suggested_fix="Reschedule to a non-conflicting time slot.",
                    )
                    iss_b = Issue(
                        rule_id="CNF-01",
                        field=resource_field,
                        value=slot_b["resource"],
                        severity="error",
                        message=(
                            f"Scheduling overlap on '{slot_b['resource']}' "
                            f"between [{slot_b['start']} - {slot_b['end']}] and row {idx_a + 1}."
                        ),
                        suggested_fix="Reschedule to a non-conflicting time slot.",
                    )
                    issues_by_row.setdefault(idx_a, []).append(iss_a)
                    issues_by_row.setdefault(idx_b, []).append(iss_b)

    return issues_by_row

