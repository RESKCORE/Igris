"""Advisory soft checks and statistical anomaly detection for OpsPilot."""

from statistics import median
from typing import Any, Dict, List, Optional, Protocol
from app.validator.rules import Issue


class SoftCheckResult:
    """Outcome of an advisory soft validation check."""
    def __init__(
        self,
        rule_id: str,
        field: str,
        value: Any,
        confidence: float,
        message: str,
        suggested_fix: Optional[str] = None,
    ):
        self.rule_id = rule_id
        self.field = field
        self.value = value
        self.confidence = confidence
        self.message = message
        self.suggested_fix = suggested_fix

    def to_issue(self) -> Issue:
        """Convert soft result into a standard validation Issue."""
        return Issue(
            rule_id=self.rule_id,
            field=self.field,
            value=self.value,
            severity="warning",
            message=f"[Confidence {int(self.confidence * 100)}%] {self.message}",
            suggested_fix=self.suggested_fix,
        )


class SoftChecker(Protocol):
    """Extensible interface for heuristic or LLM-based soft checkers."""

    def check(
        self,
        dataset_name: str,
        rows: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[int, List[Issue]]:
        """Analyze rows and return per-row advisory issues."""
        ...


class StatisticalAnomalyChecker:
    """Deterministic statistical soft checker for numeric outliers and ambiguous text."""

    def __init__(self, outlier_ratio_threshold: float = 8.0):
        self.outlier_ratio_threshold = outlier_ratio_threshold

    def check(
        self,
        dataset_name: str,
        rows: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[int, List[Issue]]:
        issues_by_row: Dict[int, List[Issue]] = {}

        if dataset_name == "invoices":
            # Group amounts by customer_id to calculate customer-specific median
            customer_amounts: Dict[str, List[float]] = {}
            for row in rows:
                c_id = str(row.get("customer_id", "")).strip()
                amt_val = row.get("amount")
                if c_id and amt_val is not None:
                    try:
                        amt = float(amt_val)
                        if amt > 0:
                            customer_amounts.setdefault(c_id, []).append(amt)
                    except (ValueError, TypeError):
                        pass

            customer_medians: Dict[str, float] = {
                c_id: median(amts) for c_id, amts in customer_amounts.items() if amts
            }

            for idx, row in enumerate(rows):
                c_id = str(row.get("customer_id", "")).strip()
                amt_val = row.get("amount")
                if not (c_id and amt_val is not None and c_id in customer_medians):
                    continue

                try:
                    amt = float(amt_val)
                    med = customer_medians[c_id]
                    if med > 0 and (amt / med) >= self.outlier_ratio_threshold:
                        res = SoftCheckResult(
                            rule_id="AMT-ANOM-01",
                            field="amount",
                            value=amt,
                            confidence=0.95,
                            message=(
                                f"Amount ₹{amt:,.2f} is an extreme outlier "
                                f"({amt / med:.1f}x the customer median ₹{med:,.2f})."
                            ),
                            suggested_fix=f"Review invoice amount against historical orders for customer {c_id}.",
                        )
                        issues_by_row.setdefault(idx, []).append(res.to_issue())
                except (ValueError, TypeError):
                    continue

        elif dataset_name == "customers":
            # Heuristic check for ambiguous customer first names
            first_names: Dict[str, List[int]] = {}
            for idx, row in enumerate(rows):
                name = str(row.get("name", "")).strip()
                if name:
                    first = name.split()[0].title()
                    first_names.setdefault(first, []).append(idx)

            for first, indices in first_names.items():
                if len(indices) > 1:
                    for idx in indices:
                        c_name = rows[idx].get("name")
                        res = SoftCheckResult(
                            rule_id="AMB-NAME-01",
                            field="name",
                            value=c_name,
                            confidence=0.85,
                            message=f"Ambiguous customer name '{c_name}': multiple customers share first name '{first}'.",
                            suggested_fix="Verify full name, email, or customer ID before executing actions.",
                        )
                        issues_by_row.setdefault(idx, []).append(res.to_issue())

        return issues_by_row

