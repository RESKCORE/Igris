"""Tests for Stage 4: Validator (hard rules, soft checks, and seeded error detection)."""

from datetime import date, timedelta
import pytest
from app.demo_data import load_demo_data
from app.models import Dataset, DatasetRow
from app.validator.engine import validate_rows
from app.validator.rules import (
    check_date_sane,
    check_email,
    check_number_range,
    check_phone,
    check_reference,
    check_required,
    check_resource_conflicts,
    check_uniqueness,
)
from app.validator.soft_checks import StatisticalAnomalyChecker


def test_rule_req_01() -> None:
    """REQ-01: Required field present."""
    assert check_required("email", "test@example.com") is None
    assert check_required("email", "") is not None
    assert check_required("email", None) is not None
    assert check_required("email", "   ") is not None


def test_rule_eml_01() -> None:
    """EML-01: Valid email format."""
    assert check_email("email", "user@example.com") is None
    fail_res = check_email("email", "ravi@@example")
    assert fail_res is not None
    assert fail_res.rule_id == "EML-01"


def test_rule_phn_01() -> None:
    """PHN-01: Valid phone format (warning)."""
    assert check_phone("phone", "+919820011111", region="IN") is None
    fail_res = check_phone("phone", "12345", region="IN")
    assert fail_res is not None
    assert fail_res.rule_id == "PHN-01"
    assert fail_res.severity == "warning"


def test_rule_num_01() -> None:
    """NUM-01: Number within range and non-negative."""
    assert check_number_range("amount", 100, min_val=1, max_val=1000) is None
    # Negative
    neg_res = check_number_range("amount", -3000)
    assert neg_res is not None
    assert neg_res.rule_id == "NUM-01"
    # Below min
    low_res = check_number_range("amount", 0, min_val=1)
    assert low_res is not None


def test_rule_dat_01() -> None:
    """DAT-01: Valid sane date window."""
    today_str = date.today().isoformat()
    assert check_date_sane("due_date", today_str) is None
    # Year 2099 (beyond today + 365)
    future_res = check_date_sane("due_date", "2099-01-01")
    assert future_res is not None
    assert future_res.rule_id == "DAT-01"
    # Past year 1990 (before 2000)
    past_res = check_date_sane("due_date", "1990-05-15")
    assert past_res is not None


def test_rule_dup_01() -> None:
    """DUP-01: Uniqueness within dataset."""
    rows = [{"id": "INV-1"}, {"id": "INV-2"}, {"id": "INV-1"}]
    dups = check_uniqueness("id", rows)
    assert 2 in dups
    assert dups[2][0].rule_id == "DUP-01"


def test_rule_ref_01() -> None:
    """REF-01: Referenced key exists."""
    valid_ids = {"CUST-001", "CUST-002"}
    assert check_reference("customer_id", "CUST-001", valid_ids) is None
    fail_res = check_reference("customer_id", "CUST-999", valid_ids)
    assert fail_res is not None
    assert fail_res.rule_id == "REF-01"


def test_rule_cnf_01() -> None:
    """CNF-01: Booking resource conflict."""
    clean_bookings = [
        {"resource": "Room A", "slot_start": "2026-11-01T09:00:00", "slot_end": "2026-11-01T10:00:00"},
        {"resource": "Room A", "slot_start": "2026-11-01T10:00:00", "slot_end": "2026-11-01T11:00:00"},
    ]
    assert len(check_resource_conflicts(clean_bookings)) == 0

    conflicting_bookings = [
        {"resource": "Room A", "slot_start": "2026-11-01T10:00:00", "slot_end": "2026-11-01T12:00:00"},
        {"resource": "Room A", "slot_start": "2026-11-01T11:00:00", "slot_end": "2026-11-01T13:00:00"},
    ]
    conflicts = check_resource_conflicts(conflicting_bookings)
    assert 0 in conflicts and 1 in conflicts
    assert conflicts[0][0].rule_id == "CNF-01"


def test_statistical_outlier_checker() -> None:
    """AMT-ANOM-01: Ratio to customer median."""
    checker = StatisticalAnomalyChecker(outlier_ratio_threshold=8.0)
    invoices = [
        {"customer_id": "CUST-1", "amount": 1000},
        {"customer_id": "CUST-1", "amount": 1200},
        {"customer_id": "CUST-1", "amount": 1100},
        {"customer_id": "CUST-1", "amount": 95000},  # ~86x median
    ]
    issues = checker.check("invoices", invoices)
    assert 3 in issues
    assert issues[3][0].rule_id == "AMT-ANOM-01"


def test_validation_against_seeded_mock_data(test_db) -> None:
    """All seeded errors in SEEDED_ERRORS.md are flagged and clean rows are 'ok'."""
    load_demo_data(test_db, reset=True)

    # 1. Invoices assertions
    inv_ds = test_db.query(Dataset).filter(Dataset.name == "invoices").first()
    assert inv_ds is not None
    inv_rows = test_db.query(DatasetRow).filter(DatasetRow.dataset_id == inv_ds.id).all()

    inv_map = {r.data.get("invoice_id"): r for r in inv_rows}

    # Clean invoice row
    inv_101 = inv_map["INV-101"]
    assert inv_101.validation_status == "ok"
    assert len(inv_101.issues) == 0

    # INV-103: Duplicate
    dup_rows = [r for r in inv_rows if r.data.get("invoice_id") == "INV-103"]
    assert len(dup_rows) == 2
    assert any(any(i["rule_id"] == "DUP-01" for i in r.issues) for r in dup_rows)

    # INV-104: Outlier amount (AMT-ANOM-01)
    inv_104 = inv_map["INV-104"]
    assert any(i["rule_id"] == "AMT-ANOM-01" for i in inv_104.issues)

    # INV-106: Negative amount (NUM-01)
    inv_106 = inv_map["INV-106"]
    assert inv_106.validation_status == "error"
    assert any(i["rule_id"] == "NUM-01" for i in inv_106.issues)

    # INV-110: Year 2099 date (DAT-01)
    inv_110 = inv_map["INV-110"]
    assert inv_110.validation_status == "error"
    assert any(i["rule_id"] == "DAT-01" for i in inv_110.issues)

    # INV-115: Orphan customer reference (REF-01)
    inv_115 = inv_map["INV-115"]
    assert inv_115.validation_status == "error"
    assert any(i["rule_id"] == "REF-01" for i in inv_115.issues)

    # 2. Customers assertions
    cust_ds = test_db.query(Dataset).filter(Dataset.name == "customers").first()
    cust_rows = test_db.query(DatasetRow).filter(DatasetRow.dataset_id == cust_ds.id).all()
    cust_map = {r.data.get("customer_id"): r for r in cust_rows}

    # CUST-002: Malformed email (EML-01)
    c_002 = cust_map["CUST-002"]
    assert c_002.validation_status == "error"
    assert any(i["rule_id"] == "EML-01" for i in c_002.issues)

    # CUST-005: Missing email (REQ-01)
    c_005 = cust_map["CUST-005"]
    assert c_005.validation_status == "error"
    assert any(i["rule_id"] == "REQ-01" for i in c_005.issues)

    # CUST-008: Invalid phone (PHN-01 warning)
    c_008 = cust_map["CUST-008"]
    assert c_008.validation_status == "warning"
    assert any(i["rule_id"] == "PHN-01" for i in c_008.issues)

    # 3. Bookings assertions
    bk_ds = test_db.query(Dataset).filter(Dataset.name == "bookings").first()
    bk_rows = test_db.query(DatasetRow).filter(DatasetRow.dataset_id == bk_ds.id).all()
    bk_map = {r.data.get("booking_id"): r for r in bk_rows}

    # BK-302 and BK-303: Conflict (CNF-01)
    assert any(i["rule_id"] == "CNF-01" for i in bk_map["BK-302"].issues)
    assert any(i["rule_id"] == "CNF-01" for i in bk_map["BK-303"].issues)

