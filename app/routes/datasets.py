"""
OpenBenchML Dataset Routes
============================
Provides browsable HTML pages and a JSON API for the platform's built-in
benchmark datasets.  Datasets are read-only — they are seeded via
``database.seed`` and are not user-uploadable in the current version.
"""

import logging
from collections import defaultdict
from typing import Optional, Dict, List

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session, joinedload

from app.database.db import get_db
from app.database.models import Dataset, BenchmarkJob, BenchmarkResult
from app.routes.auth import get_current_user_from_cookie
from app.config import templates

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
    db: Session = Depends(get_db),
):
    """Render a detailed view for a single dataset.

    Shows full metadata (description, task type, sample/feature counts,
    difficulty) together with recent benchmark jobs that used this
    dataset, so users can gauge how models typically perform.
    """
    user = await get_current_user_from_cookie(request, db)

    dataset: Optional[Dataset] = (
        db.query(Dataset)
        .filter(Dataset.id == dataset_id)
        .first()
    )
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")

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
        "Dataset detail: id=%d, name='%s', recent_jobs=%d",
        dataset_id, dataset.name, len(recent_jobs),
    )

    return templates.TemplateResponse("dataset_detail.html", {
        "request": request,
        "user": user,
        "dataset": dataset,
        "recent_jobs": recent_jobs,
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
