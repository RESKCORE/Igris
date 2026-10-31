"""Utilities for loading and resetting seeded demo mock datasets."""

import csv
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Dict, List
from sqlalchemy.orm import Session

from app.audit import append_event
from app.auth import seed_default_users
from app.models import Dataset, DatasetRow, Submission, generate_uuid
from app.templates import seed_default_templates
from app.validator.engine import revalidate_dataset

MOCK_DATA_DIR = Path(__file__).resolve().parent / "mock_data"


def resolve_date_string(raw_val: str) -> str:
    """Resolve dynamic date offsets like OFFSET:-25 to an ISO date string."""
    val = raw_val.strip()
    if val.startswith("OFFSET:"):
        days_offset = int(val.replace("OFFSET:", "").strip())
        target_date = date.today() + timedelta(days=days_offset)
        return target_date.isoformat()
    return val


def parse_csv_file(file_path: Path) -> List[Dict[str, Any]]:
    """Read a CSV file and convert typed values and date offsets."""
    rows: List[Dict[str, Any]] = []
    with open(file_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cleaned: Dict[str, Any] = {}
            for k, v in row.items():
                if v is None:
                    cleaned[k] = None
                    continue
                val = v.strip()
                # Handle empty string
                if val == "":
                    cleaned[k] = ""
                    continue
                # Handle numeric conversion if integer or float
                try:
                    if "." in val:
                        cleaned[k] = float(val)
                    else:
                        cleaned[k] = int(val)
                    continue
                except ValueError:
                    pass

                # Handle date offsets
                if "due_date" in k or val.startswith("OFFSET:"):
                    cleaned[k] = resolve_date_string(val)
                else:
                    cleaned[k] = val
            rows.append(cleaned)
    return rows


DATASET_SCHEMAS = {
    "customers": {
        "columns": ["customer_id", "name", "email", "phone", "city"],
        "types": {"customer_id": "string", "name": "string", "email": "email", "phone": "phone", "city": "string"},
    },
    "invoices": {
        "columns": ["invoice_id", "customer_id", "amount", "due_date", "status"],
        "types": {"invoice_id": "string", "customer_id": "string", "amount": "number", "due_date": "date", "status": "string"},
    },
    "orders": {
        "columns": ["order_id", "customer_id", "sku", "qty", "price", "status"],
        "types": {"order_id": "string", "customer_id": "string", "sku": "string", "qty": "number", "price": "number", "status": "string"},
    },
    "bookings": {
        "columns": ["booking_id", "customer_id", "slot_start", "slot_end", "resource"],
        "types": {"booking_id": "string", "customer_id": "string", "slot_start": "datetime", "slot_end": "datetime", "resource": "string"},
    },
}


def load_demo_data(db: Session, reset: bool = False) -> Dict[str, Any]:
    """Load mock data into the database from CSV files."""
    seed_default_templates(db)
    seed_default_users(db)

    # Load submissions from submissions.json if present
    submissions_file = MOCK_DATA_DIR / "submissions.json"
    if submissions_file.exists():
        if reset:
            db.query(Submission).delete()
        with open(submissions_file, mode="r", encoding="utf-8") as sf:
            sub_items = json.load(sf)
            for item in sub_items:
                if not db.query(Submission).filter(
                    Submission.form_type == item["form_type"],
                    Submission.data == item["data"]
                ).first():
                    db.add(Submission(
                        id=generate_uuid(),
                        form_type=item["form_type"],
                        data=item["data"],
                        status="pending",
                    ))

    loaded_counts: Dict[str, int] = {}

    for dataset_name, schema_info in DATASET_SCHEMAS.items():
        csv_path = MOCK_DATA_DIR / f"{dataset_name}.csv"
        if not csv_path.exists():
            continue

        dataset = db.query(Dataset).filter(Dataset.name == dataset_name).first()
        if not dataset:
            dataset = Dataset(
                id=generate_uuid(),
                name=dataset_name,
                source_type="internal_sheet",
                schema_def=schema_info,
                rules_ref=dataset_name,
            )
            db.add(dataset)
            db.commit()
            db.refresh(dataset)
        elif reset:
            db.query(DatasetRow).filter(DatasetRow.dataset_id == dataset.id).delete()
            db.commit()

        # Check existing row count
        existing_rows_count = db.query(DatasetRow).filter(DatasetRow.dataset_id == dataset.id).count()
        if existing_rows_count > 0 and not reset:
            loaded_counts[dataset_name] = existing_rows_count
            continue

        raw_rows = parse_csv_file(csv_path)
        for idx, row_dict in enumerate(raw_rows):
            d_row = DatasetRow(
                id=generate_uuid(),
                dataset_id=dataset.id,
                row_index=idx,
                data=row_dict,
                validation_status="ok",
                issues=[],
            )
            db.add(d_row)

        db.commit()
        loaded_counts[dataset_name] = len(raw_rows)

    # Revalidate all datasets to populate row validation_status and issues
    for dataset_name in DATASET_SCHEMAS.keys():
        revalidate_dataset(db, dataset_name)

    event_type = "data_reset" if reset else "data_loaded"
    append_event(
        db=db,
        run_id="system_demo",
        actor="system",
        event_type=event_type,
        payload={"loaded_counts": loaded_counts, "reset": reset},
    )

    return loaded_counts

