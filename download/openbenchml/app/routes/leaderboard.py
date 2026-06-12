"""
OpenBenchML Leaderboard Routes
================================
Renders global and specialised leaderboards (by score, speed, size)
with optional dataset filtering.  Includes a JSON API endpoint for
programmatic access.
"""

import logging
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Request, Depends, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc

from app.database.db import get_db
from app.database.models import Leaderboard, MLModel, Dataset, User, BenchmarkJob, BenchmarkResult
from app.routes.auth import get_current_user_from_cookie
from app.config import templates

logger = logging.getLogger(__name__)

router = APIRouter()


def _build_leaderboard_query(db: Session, dataset_id: Optional[int] = None):
    """Build the base leaderboard query with model, user, and dataset joins.

    Returns a query that selects (Leaderboard, MLModel, User, Dataset)
    tuples.  An optional ``dataset_id`` filter narrows results to a
    single dataset.
    """
    query = (
        db.query(Leaderboard, MLModel, User, Dataset)
        .join(MLModel, MLModel.id == Leaderboard.model_id)
        .join(User, User.id == MLModel.user_id)
        .join(Dataset, Dataset.id == Leaderboard.dataset_id)
        .filter(Leaderboard.rank.isnot(None))
    )
    if dataset_id is not None:
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if dataset is None:
            raise HTTPException(
                status_code=404,
                detail=f"Dataset with id={dataset_id} not found",
            )
        query = query.filter(Leaderboard.dataset_id == dataset_id)
    return query


def _build_rows(
    db: Session,
    dataset_id: Optional[int] = None,
    order_by=None,
    current_user_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Execute the leaderboard query and return a list of row dicts.

    Joins with BenchmarkResult to include latency_ms and model_size_kb
    for the best result of each model+dataset pair.  The ``order_by``
    parameter controls sort order (defaults to rank ascending).
    """
    query = _build_leaderboard_query(db, dataset_id=dataset_id)
    if order_by is not None:
        query = query.order_by(order_by)
    else:
        query = query.order_by(Leaderboard.rank.asc())

    entries = query.all()
    rows: List[Dict[str, Any]] = []

    for entry in entries:
        lb, model, user, dataset = (
            entry.Leaderboard, entry.MLModel, entry.User, entry.Dataset
        )

        # Fetch latency and size from latest completed result for this model+dataset
        best_result: Optional[BenchmarkResult] = (
            db.query(BenchmarkResult)
            .join(
                BenchmarkJob,
                BenchmarkJob.id == BenchmarkResult.job_id,
            )
            .filter(
                BenchmarkJob.model_id == model.id,
                BenchmarkJob.dataset_id == dataset.id,
                BenchmarkJob.status == "completed",
            )
            .order_by(BenchmarkResult.accuracy.desc().nullslast())
            .first()
        )

        rows.append({
            "rank": lb.rank,
            "model_name": model.model_name,
            "model_id": model.id,
            "owner": user.username,
            "owner_id": user.id,
            "dataset": dataset.name,
            "dataset_id": dataset.id,
            "score": lb.score,
            "latency_ms": best_result.latency_ms if best_result else None,
            "model_size_kb": best_result.model_size_kb if best_result else None,
            "is_current_user": user.id == current_user_id if current_user_id else False,
        })

    return rows


# ─── HTML Page Routes ─────────────────────────────────────────────────────────


@router.get("/leaderboard", response_class=HTMLResponse)
async def leaderboard_page(
    request: Request,
    dataset_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Render the global leaderboard with optional dataset filtering.

    The table displays Rank, Model Name, Owner, Dataset, Score, Latency,
    and Size.  The current user's entries are highlighted so they can
    quickly find their own rankings.
    """
    user = await get_current_user_from_cookie(request, db)
    current_user_id = user.id if user else None

    try:
        rows = _build_rows(db, dataset_id=dataset_id, current_user_id=current_user_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Leaderboard query failed: %s", exc)
        rows = []

    # Available datasets for the filter dropdown
    datasets: List[Dataset] = db.query(Dataset).order_by(Dataset.name.asc()).all()

    logger.debug(
        "Leaderboard rendered: %d entries, dataset_id=%s",
        len(rows), dataset_id,
    )

    return templates.TemplateResponse("leaderboard.html", {
        "request": request,
        "user": user,
        "rows": rows,
        "datasets": datasets,
        "selected_dataset_id": dataset_id,
        "sort_mode": "score",
    })


@router.get("/leaderboard/fastest", response_class=HTMLResponse)
async def leaderboard_fastest(
    request: Request,
    dataset_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Render a leaderboard variant sorted by latency (fastest first).

    Only models with a recorded latency_ms value are included.  The
    result set is ordered by latency_ms ascending.
    """
    user = await get_current_user_from_cookie(request, db)
    current_user_id = user.id if user else None

    # Start from the base leaderboard, then join to BenchmarkResult for sort
    query = _build_leaderboard_query(db, dataset_id=dataset_id)
    query = (
        query
        .join(BenchmarkResult, BenchmarkResult.job_id == Leaderboard.id, isouter=True)
        .filter(BenchmarkResult.latency_ms.isnot(None))
        .order_by(BenchmarkResult.latency_ms.asc())
    )

    entries = query.all()
    rows: List[Dict[str, Any]] = []

    for entry in entries:
        lb, model, user_obj, dataset = (
            entry.Leaderboard, entry.MLModel, entry.User, entry.Dataset
        )
        best_result: Optional[BenchmarkResult] = (
            db.query(BenchmarkResult)
            .join(BenchmarkJob, BenchmarkJob.id == BenchmarkResult.job_id)
            .filter(
                BenchmarkJob.model_id == model.id,
                BenchmarkJob.dataset_id == dataset.id,
                BenchmarkJob.status == "completed",
            )
            .order_by(BenchmarkResult.latency_ms.asc())
            .first()
        )
        rows.append({
            "rank": lb.rank,
            "model_name": model.model_name,
            "model_id": model.id,
            "owner": user_obj.username,
            "owner_id": user_obj.id,
            "dataset": dataset.name,
            "dataset_id": dataset.id,
            "score": lb.score,
            "latency_ms": best_result.latency_ms if best_result else None,
            "model_size_kb": best_result.model_size_kb if best_result else None,
            "is_current_user": user_obj.id == current_user_id if current_user_id else False,
        })

    datasets: List[Dataset] = db.query(Dataset).order_by(Dataset.name.asc()).all()

    return templates.TemplateResponse("leaderboard.html", {
        "request": request,
        "user": user,
        "rows": rows,
        "datasets": datasets,
        "selected_dataset_id": dataset_id,
        "sort_mode": "fastest",
    })


@router.get("/leaderboard/smallest", response_class=HTMLResponse)
async def leaderboard_smallest(
    request: Request,
    dataset_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Render a leaderboard variant sorted by model size (smallest first).

    Only models with a recorded model_size_kb value are included.  The
    result set is ordered by model_size_kb ascending.
    """
    user = await get_current_user_from_cookie(request, db)
    current_user_id = user.id if user else None

    query = _build_leaderboard_query(db, dataset_id=dataset_id)
    query = (
        query
        .join(BenchmarkResult, BenchmarkResult.job_id == Leaderboard.id, isouter=True)
        .filter(BenchmarkResult.model_size_kb.isnot(None))
        .order_by(BenchmarkResult.model_size_kb.asc())
    )

    entries = query.all()
    rows: List[Dict[str, Any]] = []

    for entry in entries:
        lb, model, user_obj, dataset = (
            entry.Leaderboard, entry.MLModel, entry.User, entry.Dataset
        )
        best_result: Optional[BenchmarkResult] = (
            db.query(BenchmarkResult)
            .join(BenchmarkJob, BenchmarkJob.id == BenchmarkResult.job_id)
            .filter(
                BenchmarkJob.model_id == model.id,
                BenchmarkJob.dataset_id == dataset.id,
                BenchmarkJob.status == "completed",
            )
            .order_by(BenchmarkResult.model_size_kb.asc())
            .first()
        )
        rows.append({
            "rank": lb.rank,
            "model_name": model.model_name,
            "model_id": model.id,
            "owner": user_obj.username,
            "owner_id": user_obj.id,
            "dataset": dataset.name,
            "dataset_id": dataset.id,
            "score": lb.score,
            "latency_ms": best_result.latency_ms if best_result else None,
            "model_size_kb": best_result.model_size_kb if best_result else None,
            "is_current_user": user_obj.id == current_user_id if current_user_id else False,
        })

    datasets: List[Dataset] = db.query(Dataset).order_by(Dataset.name.asc()).all()

    return templates.TemplateResponse("leaderboard.html", {
        "request": request,
        "user": user,
        "rows": rows,
        "datasets": datasets,
        "selected_dataset_id": dataset_id,
        "sort_mode": "smallest",
    })


# ─── JSON API Routes ──────────────────────────────────────────────────────────


@router.get("/api/leaderboard", response_class=JSONResponse)
async def api_leaderboard(
    dataset_id: Optional[int] = Query(None),
    sort_by: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Return leaderboard data as JSON with optional filters.

    Query parameters:
        dataset_id  – filter to a single dataset
        sort_by     – "score" (default), "latency", or "size"
        limit       – maximum rows to return (default 50, max 200)
    """
    valid_sorts = {"score", "latency", "size"}
    if sort_by and sort_by not in valid_sorts:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort_by '{sort_by}'. Valid: {', '.join(sorted(valid_sorts))}",
        )

    try:
        query = _build_leaderboard_query(db, dataset_id=dataset_id)

        # ── Apply sort order ──────────────────────────────────────────────
        if sort_by == "latency":
            query = (
                query
                .join(BenchmarkResult, BenchmarkResult.job_id == Leaderboard.id, isouter=True)
                .filter(BenchmarkResult.latency_ms.isnot(None))
                .order_by(BenchmarkResult.latency_ms.asc())
            )
        elif sort_by == "size":
            query = (
                query
                .join(BenchmarkResult, BenchmarkResult.job_id == Leaderboard.id, isouter=True)
                .filter(BenchmarkResult.model_size_kb.isnot(None))
                .order_by(BenchmarkResult.model_size_kb.asc())
            )
        else:
            query = query.order_by(Leaderboard.rank.asc())

        entries = query.limit(limit).all()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("API leaderboard query failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch leaderboard data")

    results: List[Dict[str, Any]] = []
    for entry in entries:
        lb, model, user_obj, dataset = (
            entry.Leaderboard, entry.MLModel, entry.User, entry.Dataset
        )

        best_result: Optional[BenchmarkResult] = (
            db.query(BenchmarkResult)
            .join(BenchmarkJob, BenchmarkJob.id == BenchmarkResult.job_id)
            .filter(
                BenchmarkJob.model_id == model.id,
                BenchmarkJob.dataset_id == dataset.id,
                BenchmarkJob.status == "completed",
            )
            .order_by(BenchmarkResult.accuracy.desc().nullslast())
            .first()
        )

        results.append({
            "rank": lb.rank,
            "model_name": model.model_name,
            "model_id": model.id,
            "owner": user_obj.username,
            "dataset": dataset.name,
            "dataset_id": dataset.id,
            "score": lb.score,
            "latency_ms": best_result.latency_ms if best_result else None,
            "model_size_kb": best_result.model_size_kb if best_result else None,
            "accuracy": best_result.accuracy if best_result else None,
            "f1_score": best_result.f1_score if best_result else None,
            "r2_score": best_result.r2_score if best_result else None,
            "updated_at": lb.updated_at.isoformat() if lb.updated_at else None,
        })

    return results
