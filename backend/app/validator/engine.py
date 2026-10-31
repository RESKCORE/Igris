"""Validation engine orchestrating hard rules and soft anomaly checks."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import yaml
from sqlalchemy.orm import Session

from app.models import Dataset, DatasetRow
from app.validator.rules import (
    Issue,
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

RULES_FILE = Path(__file__).resolve().parent.parent / "mock_data" / "rules.yaml"


class ValidationEngine:
    """Configurable rule engine driven by rules.yaml and soft checkers."""

    def __init__(self, rules_path: Optional[Path] = None):
        self.rules_path = rules_path or RULES_FILE
        self.rules: Dict[str, Any] = {}
        self.soft_checker = StatisticalAnomalyChecker(outlier_ratio_threshold=8.0)
        self.load_rules()

    def load_rules(self) -> None:
        """Load YAML rule specifications into memory."""
        if self.rules_path.exists():
            with open(self.rules_path, mode="r", encoding="utf-8") as f:
                self.rules = yaml.safe_load(f) or {}

    def validate_rows(
        self,
        dataset_name: str,
        rows: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[str, List[Issue]]]:
        """Validate an array of rows and return status ('ok', 'warning', 'error') and issues for each."""
        dataset_spec = self.rules.get(dataset_name, {})
        fields_spec = dataset_spec.get("fields", {})
        ds_rules = dataset_spec.get("dataset_rules", [])

        row_issues: List[List[Issue]] = [[] for _ in rows]
        ctx = context or {}

        # 1. Field-level deterministic validation
        for idx, row in enumerate(rows):
            for field_name, f_spec in fields_spec.items():
                val = row.get(field_name)

                # REQ-01: Required check
                if f_spec.get("required", False):
                    req_iss = check_required(field_name, val)
                    if req_iss:
                        row_issues[idx].append(req_iss)

                # Skip further type checks if value is absent
                if val is None or val == "":
                    continue

                f_type = f_spec.get("type")
                if f_type == "email":
                    iss = check_email(field_name, val)
                    if iss:
                        row_issues[idx].append(iss)
                elif f_type == "phone":
                    region = f_spec.get("region", "IN")
                    iss = check_phone(field_name, val, region=region)
                    if iss:
                        row_issues[idx].append(iss)
                elif f_type == "number":
                    min_val = f_spec.get("min")
                    max_val = f_spec.get("max")
                    iss = check_number_range(field_name, val, min_val=min_val, max_val=max_val)
                    if iss:
                        row_issues[idx].append(iss)
                elif f_type == "date":
                    not_after = f_spec.get("not_after", 365)
                    not_before_year = f_spec.get("not_before_year", 2000)
                    iss = check_date_sane(field_name, val, not_after_days=not_after, not_before_year=not_before_year)
                    if iss:
                        row_issues[idx].append(iss)

                # REF-01: Foreign key validation
                ref_spec = f_spec.get("reference")
                if ref_spec:
                    target_dataset = ref_spec.get("dataset")
                    valid_refs: Set[Any] = ctx.get(f"valid_ids_{target_dataset}", set())
                    if valid_refs:
                        ref_iss = check_reference(field_name, val, valid_refs)
                        if ref_iss:
                            row_issues[idx].append(ref_iss)

        # 2. Dataset-level uniqueness checks (DUP-01)
        for r in ds_rules:
            if r.get("type") == "unique":
                for u_field in r.get("fields", []):
                    dup_issues = check_uniqueness(u_field, rows)
                    for r_idx, isss in dup_issues.items():
                        row_issues[r_idx].extend(isss)

            elif r.get("type") == "resource_conflict":
                res_field = r.get("resource_field", "resource")
                start_field = r.get("start_field", "slot_start")
                end_field = r.get("end_field", "slot_end")
                cnf_issues = check_resource_conflicts(
                    rows,
                    resource_field=res_field,
                    start_field=start_field,
                    end_field=end_field,
                )
                for r_idx, isss in cnf_issues.items():
                    row_issues[r_idx].extend(isss)

        # 3. Advisory soft checks
        soft_issues = self.soft_checker.check(dataset_name, rows, context=ctx)
        for r_idx, isss in soft_issues.items():
            row_issues[r_idx].extend(isss)

        # 4. Synthesize final validation status per row
        results: List[Tuple[str, List[Issue]]] = []
        for issues in row_issues:
            if any(i.severity == "error" for i in issues):
                status = "error"
            elif any(i.severity == "warning" for i in issues):
                status = "warning"
            else:
                status = "ok"
            results.append((status, issues))

        return results


engine = ValidationEngine()


def validate_rows(
    dataset_name: str,
    rows: List[Dict[str, Any]],
    context: Optional[Dict[str, Any]] = None,
) -> List[Tuple[str, List[Issue]]]:
    """Public helper to validate row data dictionaries against rules.yaml."""
    return engine.validate_rows(dataset_name, rows, context)


def revalidate_dataset(db: Session, dataset_id_or_name: str) -> None:
    """Revalidate all rows belonging to a dataset in the database."""
    dataset = (
        db.query(Dataset)
        .filter((Dataset.id == dataset_id_or_name) | (Dataset.name == dataset_id_or_name))
        .first()
    )
    if not dataset:
        return

    # Fetch reference IDs for cross-dataset verification if needed (e.g., customers)
    context: Dict[str, Any] = {}
    if dataset.name == "invoices" or dataset.name == "orders" or dataset.name == "bookings":
        cust_ds = db.query(Dataset).filter(Dataset.name == "customers").first()
        if cust_ds:
            c_rows = db.query(DatasetRow).filter(DatasetRow.dataset_id == cust_ds.id).all()
            valid_ids = {str(r.data.get("customer_id")).strip() for r in c_rows if r.data.get("customer_id")}
            context["valid_ids_customers"] = valid_ids

    rows = (
        db.query(DatasetRow)
        .filter(DatasetRow.dataset_id == dataset.id)
        .order_by(DatasetRow.row_index.asc())
        .all()
    )
    if not rows:
        return

    raw_dicts = [r.data for r in rows]
    results = validate_rows(dataset.name, raw_dicts, context)

    for r_obj, (v_status, issues) in zip(rows, results):
        r_obj.validation_status = v_status
        r_obj.issues = [i.model_dump() for i in issues]

    db.commit()

