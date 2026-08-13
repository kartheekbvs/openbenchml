"""
OpenBenchML Dataset Routes
============================
Provides browsable HTML pages and a JSON API for the platform's built-in
benchmark datasets.  Datasets are read-only — they are seeded via
``database.seed`` and are not user-uploadable in the current version.

The dataset detail page (``/datasets/{id}``) includes a ``df.head(N)``
style preview that reads the first N rows of the underlying CSV (or
the sklearn Bunch for built-ins).  The row count comes from the
``?rows=`` query parameter (default 5, clamped to 1..100).  The form
uses a normal ``<form method="GET">`` — no vanilla JavaScript.
"""

import logging
from collections import defaultdict
from typing import Optional, Dict, List, Any

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session, joinedload

from app.database.db import get_db
from app.database.models import Dataset, BenchmarkJob, BenchmarkResult, MLModel
from app.routes.auth import get_current_user_from_cookie
from app.config import templates
from app.services.dataset_preview_service import (
    get_dataset_preview,
    DEFAULT_PREVIEW_ROWS,
    clamp_rows,
)
from app.services.sample_models_service import find_sample_model_for_dataset

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── HTML Page Routes ─────────────────────────────────────────────────────────


@router.get("/datasets", response_class=HTMLResponse)
async def datasets_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Render the datasets listing page.

    Datasets are grouped by difficulty level (beginner, intermediate,
    advanced) so users can progressively work through more challenging
    benchmarks.  Each card shows name, task type, sample count, feature
    count, and difficulty badge.
    """
    user = await get_current_user_from_cookie(request, db)

    datasets: List[Dataset] = (
        db.query(Dataset)
        .order_by(Dataset.difficulty, Dataset.name)
        .all()
    )

    # ── Group by difficulty ───────────────────────────────────────────────
    grouped: Dict[str, List[Dataset]] = defaultdict(list)
    for ds in datasets:
        grouped[ds.difficulty].append(ds)

    # Ensure the expected keys exist even when empty
    for level in ("beginner", "intermediate", "advanced"):
        grouped.setdefault(level, [])

    logger.debug("Fetched %d datasets across %d difficulty levels", len(datasets), len(grouped))

    return templates.TemplateResponse("datasets.html", {
        "request": request,
        "user": user,
        "grouped_datasets": dict(grouped),
    })


@router.get("/datasets/{dataset_id}", response_class=HTMLResponse)
async def dataset_detail_page(
    request: Request,
    dataset_id: int,
    rows: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Render a detailed view for a single dataset.

    Shows full metadata (description, task type, sample/feature counts,
    difficulty) together with:

    * A ``df.head(N)`` style preview table of the first N rows
      (controllable via the ``?rows=`` query parameter, default 5,
      clamped to 1..100).  For CSV datasets the file is read directly;
      for sklearn built-ins the Bunch is materialised.
    * Recent benchmark jobs that used this dataset, so users can gauge
      how models typically perform.
    * A "Run Sample Benchmark" button — runs a real benchmark using
      the platform's pre-trained sample model for this dataset so any
      visitor (even logged-out) can see real numbers immediately.
    """
    user = await get_current_user_from_cookie(request, db)

    dataset: Optional[Dataset] = (
        db.query(Dataset)
        .filter(Dataset.id == dataset_id)
        .first()
    )
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # ── df.head(N) preview (no vanilla JS — pure server-side) ────────────
    requested_rows = clamp_rows(rows)
    preview: Dict[str, Any] = get_dataset_preview(dataset, requested_rows)

    # ── Find a sample pre-trained model for this dataset (if any) ────────
    sample_model: Optional[MLModel] = find_sample_model_for_dataset(dataset, db)

    # ── Recent completed benchmarks for this dataset ──────────────────────
    recent_jobs: List[BenchmarkJob] = (
        db.query(BenchmarkJob)
        .options(
            joinedload(BenchmarkJob.result),
            joinedload(BenchmarkJob.model),
        )
        .filter(
            BenchmarkJob.dataset_id == dataset_id,
            BenchmarkJob.status == "completed",
        )
        .order_by(BenchmarkJob.finished_at.desc())
        .limit(20)
        .all()
    )

    logger.debug(
        "Dataset detail: id=%d, name='%s', preview_rows=%d, recent_jobs=%d",
        dataset_id, dataset.name, preview.get("total_rows_loaded", 0), len(recent_jobs),
    )

    return templates.TemplateResponse("dataset_detail.html", {
        "request": request,
        "user": user,
        "dataset": dataset,
        "recent_jobs": recent_jobs,
        "preview": preview,
        "preview_rows": requested_rows,
        "sample_model": sample_model,
    })


# ─── JSON API Routes ──────────────────────────────────────────────────────────


@router.get("/api/datasets", response_class=JSONResponse)
async def api_list_datasets(
    task_type: Optional[str] = None,
    difficulty: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Return a JSON list of all datasets.

    Optional query parameters:
      - ``task_type``: filter by task type (classification, regression, clustering)
      - ``difficulty``: filter by difficulty (beginner, intermediate, advanced)
    """
    query = db.query(Dataset)

    if task_type:
        query = query.filter(Dataset.task_type == task_type)

    if difficulty:
        valid_difficulties = {"beginner", "intermediate", "advanced"}
        if difficulty not in valid_difficulties:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid difficulty '{difficulty}'. Valid: {', '.join(sorted(valid_difficulties))}",
            )
        query = query.filter(Dataset.difficulty == difficulty)

    datasets: List[Dataset] = query.order_by(Dataset.name).all()

    return [
        {
            "id": ds.id,
            "name": ds.name,
            "task_type": ds.task_type,
            "description": ds.description,
            "samples": ds.samples,
            "features": ds.features,
            "difficulty": ds.difficulty,
            "is_builtin": ds.is_builtin,
            "created_at": ds.created_at.isoformat() if ds.created_at else None,
        }
        for ds in datasets
    ]


@router.get("/api/datasets/{dataset_id}/preview", response_class=JSONResponse)
async def api_dataset_preview(
    dataset_id: int,
    rows: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Return the first ``rows`` rows of a dataset as JSON (df.head(N)).

    Useful for programmatic inspection of a dataset without rendering
    the HTML page.  Row count is clamped to 1..100 (default 5).
    """
    dataset: Optional[Dataset] = (
        db.query(Dataset).filter(Dataset.id == dataset_id).first()
    )
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")

    n = clamp_rows(rows)
    preview = get_dataset_preview(dataset, n)
    return {
        "dataset_id": dataset.id,
        "dataset_name": dataset.name,
        "requested_rows": n,
        "returned_rows": preview.get("total_rows_loaded", 0),
        "total_rows_in_file": preview.get("total_rows_in_file"),
        "source": preview.get("source"),
        "file_name": preview.get("file_name"),
        "columns": preview.get("columns", []),
        "rows": preview.get("rows", []),
        "error": preview.get("error"),
    }
