"""Tests for Stage 3: Catalog, templates, mock data, and dataset routes."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.audit import verify_chain
import app.models  # noqa: F401
from app.catalog import ACTION_CATALOG, get_action, risk_for, catalog_prompt_text
from app.db import Base, get_db
from app.main import app
from app.models import AuditEvent, Dataset, DatasetRow, Risk
from app.templates import render, DEFAULT_TEMPLATES




def test_action_catalog() -> None:
    """Verify action catalog definitions, risk levels, and prompt text."""
    assert "read_sheet" in ACTION_CATALOG
    assert "send_email" in ACTION_CATALOG
    assert risk_for("send_email") == Risk.external
    assert risk_for("read_sheet") == Risk.read
    assert risk_for("update_sheet_row") == Risk.internal_write

    prompt_text = catalog_prompt_text()
    assert "read_sheet" in prompt_text
    assert "send_email" in prompt_text

    with pytest.raises(ValueError):
        risk_for("non_existent_action")


def test_templates_render() -> None:
    """Verify template rendering and placeholder substitution safety."""
    row = {
        "invoice_id": "INV-101",
        "customer_name": "Asha Traders",
        "amount": "12000",
        "due_date": "2026-10-15",
    }
    body_template = DEFAULT_TEMPLATES["payment_reminder"]["body"]
    rendered = render(body_template, row)
    assert "INV-101" in rendered
    assert "Asha Traders" in rendered
    assert "12000" in rendered

    # Missing placeholder must raise KeyError
    incomplete_row = {"invoice_id": "INV-101"}
    with pytest.raises(KeyError) as exc_info:
        render(body_template, incomplete_row)
    assert "Missing required placeholder" in str(exc_info.value)


def test_demo_load_and_reset(client, test_db) -> None:
    """Verify demo data load, query, patch, and reset cycle."""
    # 1. Load demo data
    res_load = client.post("/datasets/demo/load")
    assert res_load.status_code == 200
    data_loaded = res_load.json()["loaded"]
    assert "customers" in data_loaded
    assert "invoices" in data_loaded
    assert "orders" in data_loaded
    assert "bookings" in data_loaded
    assert data_loaded["customers"] >= 20
    assert data_loaded["invoices"] >= 35

    # 2. Query datasets
    res_ds = client.get("/datasets")
    assert res_ds.status_code == 200
    datasets = res_ds.json()
    assert len(datasets) >= 4
    inv_ds = next(d for d in datasets if d["name"] == "invoices")

    # 3. Query invoice rows
    res_rows = client.get(f"/datasets/{inv_ds['id']}/rows")
    assert res_rows.status_code == 200
    rows = res_rows.json()["rows"]
    assert len(rows) >= 35

    first_row = rows[0]
    first_row_id = first_row["id"]
    original_amount = first_row["data"]["amount"]

    # 4. Patch row (edits data and logs audit event)
    patch_payload = {"data": {"amount": 99999}}
    res_patch = client.patch(f"/datasets/{inv_ds['id']}/rows/{first_row_id}", json=patch_payload)
    assert res_patch.status_code == 200
    assert res_patch.json()["data"]["amount"] == 99999

    # Check audit log for row edit
    audit_events = (
        test_db.query(AuditEvent)
        .filter(AuditEvent.run_id == f"dataset_{inv_ds['name']}")
        .all()
    )
    assert len(audit_events) >= 1
    edit_event = audit_events[-1]
    assert edit_event.event_type == "row_edited"
    assert edit_event.payload["before"]["amount"] == original_amount
    assert edit_event.payload["after"]["amount"] == 99999

    # 5. Reset demo data restores original state
    res_reset = client.post("/datasets/demo/reset")
    assert res_reset.status_code == 200

    # Verify rows reset
    res_rows_after = client.get(f"/datasets/{inv_ds['id']}/rows")
    reset_first_row = res_rows_after.json()["rows"][0]
    assert reset_first_row["data"]["amount"] == original_amount
