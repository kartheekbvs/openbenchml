"""
OpenBenchML Dashboard Routes
==============================
Renders the authenticated user's dashboard with aggregated statistics,
recent benchmark jobs, and top leaderboard entries.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.database.models import User, MLModel, BenchmarkJob, BenchmarkResult, Leaderboard
from app.routes.auth import get_current_user_from_cookie
from app.config import templates

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Render the user dashboard with summary statistics.

    Aggregates model counts, benchmark totals, average accuracy, user
    rank, recent jobs, and top models from the leaderboard.  If the
    visitor is not authenticated they are redirected to the login page.
    """
    # ── Authentication gate ────────────────────────────────────────────────
    user: Optional[User] = await get_current_user_from_cookie(request, db)
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    # ── Total models owned by this user ────────────────────────────────────
    total_models = (
        db.query(func.count(MLModel.id))
        .filter(MLModel.user_id == user.id)
        .scalar()
    ) or 0

    # ── Total benchmark jobs for this user's models ────────────────────────
    total_benchmarks = (
        db.query(func.count(BenchmarkJob.id))
        .join(MLModel, MLModel.id == BenchmarkJob.model_id)
        .filter(MLModel.user_id == user.id)
        .scalar()
    ) or 0

    # ── Average accuracy across this user's completed results ──────────────
    avg_accuracy = (
        db.query(func.avg(BenchmarkResult.accuracy))
        .join(BenchmarkJob, BenchmarkJob.id == BenchmarkResult.job_id)
        .join(MLModel, MLModel.id == BenchmarkJob.model_id)
        .filter(MLModel.user_id == user.id, BenchmarkResult.accuracy.isnot(None))
        .scalar()
    )
    avg_accuracy = round(avg_accuracy, 4) if avg_accuracy is not None else None

    # ── User's best rank on any leaderboard entry ──────────────────────────
    user_rank_entry = (
        db.query(func.min(Leaderboard.rank))
        .join(MLModel, MLModel.id == Leaderboard.model_id)
        .filter(MLModel.user_id == user.id, Leaderboard.rank.isnot(None))
        .scalar()
    )
    user_rank = user_rank_entry if user_rank_entry is not None else "N/A"

    # ── Recent benchmark jobs (last 10) for this user ──────────────────────
    recent_jobs = (
        db.query(BenchmarkJob)
        .join(MLModel, MLModel.id == BenchmarkJob.model_id)
        .filter(MLModel.user_id == user.id)
        .order_by(BenchmarkJob.submitted_at.desc())
        .limit(10)
        .all()
    )

    # ── Top 5 models from the global leaderboard ──────────────────────────
    top_models = (
        db.query(Leaderboard, MLModel, User)
        .join(MLModel, MLModel.id == Leaderboard.model_id)
        .join(User, User.id == MLModel.user_id)
        .filter(Leaderboard.rank.isnot(None))
        .order_by(Leaderboard.rank.asc())
        .limit(5)
        .all()
    )
    # Flatten into a list of dicts for easy template access
    top_models_data = [
        {
            "rank": entry.Leaderboard.rank,
            "model_name": entry.MLModel.model_name,
            "username": entry.User.username,
            "score": entry.Leaderboard.score,
        }
        for entry in top_models
    ]

    logger.debug(
        "Dashboard stats for %s: models=%d, benchmarks=%d, avg_acc=%s, rank=%s",
        user.username, total_models, total_benchmarks, avg_accuracy, user_rank,
    )

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "total_models": total_models,
        "total_benchmarks": total_benchmarks,
        "avg_accuracy": avg_accuracy,
        "user_rank": user_rank,
        "recent_jobs": recent_jobs,
        "top_models": top_models_data,
    })
