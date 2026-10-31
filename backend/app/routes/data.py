"""Dataset workspace routes for viewing and editing data tables."""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.adapters.sheets import SheetsNotConfigured, export_dataset_to_sheet
from app.audit import append_event
from app.db import get_db
from app.demo_data import load_demo_data
from app.models import Dataset, DatasetRow, DatasetRowUpdate, iso_utc
from app.validator.engine import revalidate_dataset

router = APIRouter(prefix="/datasets", tags=["Data Workspace"])


@router.get("", summary="List all business datasets")
def list_datasets(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """List all registered spreadsheet-style datasets."""
    datasets = db.query(Dataset).all()
    return [
        {
            "id": d.id,
            "name": d.name,
            "source_type": d.source_type,
            "schema": d.schema_def,
            "rules_ref": d.rules_ref,
            "created_at": iso_utc(d.created_at),
            "updated_at": iso_utc(d.updated_at),
        }
        for d in datasets
    ]


@router.get("/{id}/rows", summary="Get data rows for a dataset")
def get_dataset_rows(id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Retrieve all rows for a dataset by ID or name, including validation status."""
    dataset = db.query(Dataset).filter((Dataset.id == id) | (Dataset.name == id)).first()
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "dataset_not_found", "message": f"Dataset '{id}' not found."},
        )

    rows = (
        db.query(DatasetRow)
        .filter(DatasetRow.dataset_id == dataset.id)
        .order_by(DatasetRow.row_index.asc())
        .all()
    )

    return {
        "dataset_id": dataset.id,
        "dataset_name": dataset.name,
        "rows": [
            {
                "id": r.id,
                "dataset_id": r.dataset_id,
                "row_index": r.row_index,
                "data": r.data,
                "validation_status": r.validation_status or "ok",
                "issues": r.issues or [],
                "updated_at": iso_utc(r.updated_at),
            }
            for r in rows
        ],
    }


@router.patch("/{id}/rows/{row_id}", summary="Edit a dataset row")
def update_dataset_row(
    id: str,
    row_id: str,
    payload: DatasetRowUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update row values and write an audited 'row_edited' event with before/after diff."""
    dataset = db.query(Dataset).filter((Dataset.id == id) | (Dataset.name == id)).first()
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "dataset_not_found", "message": f"Dataset '{id}' not found."},
        )

    row = (
        db.query(DatasetRow)
        .filter(DatasetRow.id == row_id, DatasetRow.dataset_id == dataset.id)
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "row_not_found", "message": f"Row '{row_id}' not found in dataset '{dataset.name}'."},
        )

    before_data = dict(row.data)
    merged_data = dict(row.data)
    merged_data.update(payload.data)
    row.data = merged_data

    db.commit()
    db.refresh(row)

    # Revalidate dataset to update status and issues
    revalidate_dataset(db, dataset.id)
    db.refresh(row)

    # Record tamper-evident audit event
    append_event(
        db=db,
        run_id=f"dataset_{dataset.name}",
        actor="human:owner",
        event_type="row_edited",
        payload={
            "dataset_id": dataset.id,
            "dataset_name": dataset.name,
            "row_id": row.id,
            "before": before_data,
            "after": merged_data,
        },
    )

    return {
        "id": row.id,
        "dataset_id": row.dataset_id,
        "data": row.data,
        "validation_status": row.validation_status,
        "issues": row.issues,
        "updated_at": iso_utc(row.updated_at),
    }


@router.post("/demo/load", summary="Load seeded mock data")
def load_demo_mock_data(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Load mock CSV data into datasets if not already loaded."""
    counts = load_demo_data(db=db, reset=False)
    return {"status": "ok", "loaded": counts}


@router.post("/demo/reset", summary="Reset mock data to seeded state")
def reset_demo_mock_data(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Reset datasets back to their initial seeded state."""
    counts = load_demo_data(db=db, reset=True)
    return {"status": "ok", "reset": counts}


@router.post("/{id}/sheets", summary="Export a dataset to Google Sheets")
def export_dataset_sheets(id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Push all rows of a dataset into a Google spreadsheet and audit the export."""
    dataset = db.query(Dataset).filter((Dataset.id == id) | (Dataset.name == id)).first()
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "dataset_not_found", "message": f"Dataset '{id}' not found."},
        )

    try:
        result = export_dataset_to_sheet(db, dataset)
    except SheetsNotConfigured as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "sheets_not_configured", "message": str(exc)},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "sheets_export_failed", "message": f"Google Sheets export failed: {exc}"},
        )

    append_event(
        db=db,
        run_id=f"dataset_{dataset.name}",
        actor="human:owner",
        event_type="dataset_exported",
        payload={
            "dataset_id": dataset.id,
            "dataset_name": dataset.name,
            "rows_written": result["rows_written"],
            "spreadsheet_url": result["spreadsheet_url"],
        },
    )
    return result

