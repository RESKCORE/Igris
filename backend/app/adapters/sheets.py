"""Google Sheets export adapter (sandbox/demo feature).

Reads rows from SQL and pushes them into a Google spreadsheet. Requires a
service-account JSON (path or raw JSON string) in GOOGLE_SERVICE_ACCOUNT_JSON;
otherwise the export fails closed with a clear configuration error.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Dataset, DatasetRow


class SheetsNotConfigured(Exception):
    """Raised when Google Sheets integration is requested without credentials."""


def _service_account_info() -> Dict[str, Any]:
    """Resolve the service account JSON from a file path or an embedded JSON string."""
    raw = (settings.GOOGLE_SERVICE_ACCOUNT_JSON or "").strip()
    if not raw:
        raise SheetsNotConfigured("GOOGLE_SERVICE_ACCOUNT_JSON is not set.")
    candidate = Path(raw)
    if candidate.exists():
        raw = candidate.read_text(encoding="utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SheetsNotConfigured(f"GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON: {exc}")


def export_dataset_to_sheet(db: Session, dataset: Dataset) -> Dict[str, Any]:
    """Push every row of a dataset into a (new or shared) Google spreadsheet."""
    import gspread
    from google.oauth2.service_account import Credentials

    info = _service_account_info()
    credentials = Credentials.from_service_account_info(info, scopes=gspread.auth.READ_WRITE_SCOPES)
    client = gspread.authorize(credentials)

    if settings.GOOGLE_SHEET_TEST_ID:
        spreadsheet = client.open_by_key(settings.GOOGLE_SHEET_TEST_ID)
    else:
        spreadsheet = client.create(f"OpsPilot - {dataset.name}")

    worksheet = spreadsheet.get_worksheet(0)
    columns: List[str] = (dataset.schema_def or {}).get("columns", [])

    values: List[List[Any]] = [[*columns, "validation_status", "issue_count"]]
    rows = (
        db.query(DatasetRow)
        .filter(DatasetRow.dataset_id == dataset.id)
        .order_by(DatasetRow.row_index.asc())
        .all()
    )
    for row in rows:
        data = row.data or {}
        values.append([data.get(col) for col in columns] + [row.validation_status or "ok", len(row.issues or [])])

    worksheet.clear()
    worksheet.update(values=values, range_name="A1")

    return {
        "spreadsheet_title": spreadsheet.title,
        "spreadsheet_url": spreadsheet.url,
        "worksheet": worksheet.title,
        "rows_written": max(len(values) - 1, 0),
    }
