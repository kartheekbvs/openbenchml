"""
OpenBenchML Dashboard Routes
==============================
Renders the authenticated user's dashboard with aggregated statistics,
recent benchmark jobs, top leaderboard entries, and platform metrics.
Enhanced with platform stats API and activity feed.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.database.models import User, MLModel, BenchmarkJob, BenchmarkResult, Leaderboard, Dataset
from app.routes.auth import get_current_user_from_cookie
from app.config import templates
from app.services.benchmark_service import get_platform_stats

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Render the user dashboard with summary statistics.

    Aggregates model counts, benchmark totals, average accuracy, user
    rank, recent jobs, and top models from the leaderboard.
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
    top_models_data = [
        {
            "rank": entry.Leaderboard.rank,
            "model_name": entry.MLModel.model_name,
            "username": entry.User.username,
            "score": entry.Leaderboard.score,
        }
        for entry in top_models
    ]

    # ── Framework distribution for user's models ───────────────────────────
    framework_dist = (
        db.query(MLModel.framework, func.count(MLModel.id))
        .filter(MLModel.user_id == user.id)
        .group_by(MLModel.framework)
        .all()
    )
    framework_data = [{"framework": fw, "count": cnt} for fw, cnt in framework_dist]

    # ── Average latency for user's benchmarks ──────────────────────────────
    avg_latency = (
        db.query(func.avg(BenchmarkResult.latency_ms))
        .join(BenchmarkJob, BenchmarkJob.id == BenchmarkResult.job_id)
        .join(MLModel, MLModel.id == BenchmarkJob.model_id)
        .filter(MLModel.user_id == user.id, BenchmarkResult.latency_ms.isnot(None))
        .scalar()
    )
    avg_latency = round(avg_latency, 2) if avg_latency else None

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
        "avg_latency": avg_latency,
        "user_rank": user_rank,
        "recent_jobs": recent_jobs,
        "top_models": top_models_data,
        "framework_data": framework_data,
    })


# ─── JSON API Routes ──────────────────────────────────────────────────────────


@router.get("/api/dashboard/stats")
async def api_dashboard_stats(
    db: Session = Depends(get_db),
):
    """Return platform-wide statistics as JSON.

    Provides aggregated metrics about the platform including total users,
    models, benchmarks, average accuracy, etc. This is a public endpoint
    that does not require authentication.
    """
    stats = get_platform_stats(db)
    return stats


@router.get("/api/dashboard/activity")
async def api_recent_activity(
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """Return recent platform activity as JSON.

    Shows the most recent completed benchmark jobs with their results,
    useful for a real-time activity feed on the landing page.
    """
    from app.routes.auth import get_current_user_from_cookie
    # This is a public endpoint showing anonymized activity
    recent = (
        db.query(BenchmarkJob, MLModel, Dataset, BenchmarkResult)
        .join(MLModel, MLModel.id == BenchmarkJob.model_id)
        .join(Dataset, Dataset.id == BenchmarkJob.dataset_id)
        .outerjoin(BenchmarkResult, BenchmarkResult.job_id == BenchmarkJob.id)
        .filter(
            BenchmarkJob.status == "completed",
            MLModel.is_public == True,
        )
        .order_by(BenchmarkJob.finished_at.desc())
        .limit(min(limit, 50))
        .all()
    )

    activity = [
        {
            "model_name": job.MLModel.model_name,
            "framework": job.MLModel.framework,
            "dataset": job.Dataset.name,
            "accuracy": job.BenchmarkResult.accuracy if job.BenchmarkResult else None,
            "f1_score": job.BenchmarkResult.f1_score if job.BenchmarkResult else None,
            "latency_ms": job.BenchmarkResult.latency_ms if job.BenchmarkResult else None,
            "finished_at": job.BenchmarkJob.finished_at.isoformat() if job.BenchmarkJob.finished_at else None,
        }
        for job in recent
    ]

    return activity
