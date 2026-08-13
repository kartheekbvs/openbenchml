"""
OpenBenchML Competitions Routes
=================================
Kaggle-style competitions: list, create, view, submit, leaderboard.

A competition is bound to a dataset; users submit an existing model
which is benchmarked on the competition's dataset; the score is taken
from the benchmark result and the per-competition leaderboard is
maintained.
"""
import logging
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Request, Depends, HTTPException, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy import func, desc
from sqlalchemy.orm import Session, joinedload

from app.database.db import get_db
from app.database.models import (
    Competition, CompetitionSubmission, MLModel, Dataset, User,
    BenchmarkJob, BenchmarkResult, Notification,
)
from app.services.benchmark_service import create_benchmark_job, run_benchmark
from app.routes.auth import get_current_user_from_cookie
from app.config import templates

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _slugify(title: str) -> str:
    """Convert a title to a URL-safe slug."""
    slug = re.sub(r"[^a-zA-Z0-9\s-]", "", title.lower()).strip()
    slug = re.sub(r"[\s-]+", "-", slug)
    return slug or "competition"


def _refresh_competition_status(comp: Competition, db: Session) -> None:
    """Update the in-memory status of a competition based on current time."""
    now = datetime.utcnow()
    if now < comp.starts_at:
        new_status = "upcoming"
    elif comp.starts_at <= now < comp.ends_at:
        new_status = "live"
    else:
        new_status = "ended"
    if comp.status != new_status:
        comp.status = new_status
        db.commit()


def _extract_score(result: BenchmarkResult, metric: str) -> Optional[float]:
    """Pull a metric value from a BenchmarkResult; returns None if missing."""
    if result is None:
        return None
    return getattr(result, metric, None)


def _recompute_competition_leaderboard(comp: Competition, db: Session) -> None:
    """Mark the best submission per (user OR team) for this competition.

    Higher is better for accuracy / f1 / auc / r2.
    Lower is better for rmse / mae / latency_ms.
    """
    subs = (
        db.query(CompetitionSubmission)
        .filter(
            CompetitionSubmission.competition_id == comp.id,
            CompetitionSubmission.score.isnot(None),
        )
        .all()
    )
    # Group by user_id (ignore team for now — could extend)
    best_by_user: Dict[int, CompetitionSubmission] = {}
    for s in subs:
        uid = s.user_id
        cur = best_by_user.get(uid)
        if cur is None:
            best_by_user[uid] = s
            continue
        if _is_better(s.score, cur.score, comp.evaluation_metric):
            best_by_user[uid] = s

    # Reset all is_best flags then re-set
    for s in subs:
        s.is_best = False
    for s in best_by_user.values():
        s.is_best = True
    db.commit()


def _is_better(new: float, old: float, metric: str) -> bool:
    """Return True if *new* is a better score than *old* for the metric."""
    lower_is_better = metric in ("rmse", "mae", "latency_ms", "log_loss")
    if lower_is_better:
        return new < old
    return new > old


def _broadcast_notification(
    db: Session,
    user_id: int,
    ntype: str,
    title: str,
    body: str = "",
    link: str = "",
):
    """Persist a notification and broadcast it over WebSocket."""
    try:
        n = Notification(
            user_id=user_id, type=ntype, title=title, body=body, link=link,
        )
        db.add(n)
        db.commit()
        db.refresh(n)
    except Exception as exc:
        db.rollback()
        logger.warning("Could not persist notification: %s", exc)
        return None

    # Best-effort WebSocket push
    try:
        from app.main import ws_manager
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(ws_manager.broadcast({
                "type": "notification",
                "user_id": user_id,
                "notification_type": ntype,
                "title": title,
                "body": body,
                "link": link,
                "created_at": datetime.utcnow().isoformat(),
            }))
    except Exception as exc:
        logger.debug("WS notification broadcast failed: %s", exc)

    return n


# ─── HTML Page Routes ─────────────────────────────────────────────────────────


@router.get("/competitions", response_class=HTMLResponse)
async def competitions_list_page(
    request: Request,
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """List all competitions, optionally filtered by status."""
    user = await get_current_user_from_cookie(request, db)

    query = db.query(Competition)
    if status:
        valid = ("upcoming", "live", "ended")
        if status not in valid:
            raise HTTPException(status_code=400, detail=f"Invalid status '{status}'")
        query = query.filter(Competition.status == status)

    competitions = query.order_by(Competition.starts_at.desc()).all()

    # Refresh statuses
    for c in competitions:
        _refresh_competition_status(c, db)

    return templates.TemplateResponse("competitions.html", {
        "request": request,
        "user": user,
        "competitions": competitions,
        "filter_status": status,
        "now": datetime.utcnow(),
    })


@router.get("/competitions/create", response_class=HTMLResponse)
async def competition_create_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Render the competition creation form (admin-only)."""
    user = await get_current_user_from_cookie(request, db)
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can create competitions")

    datasets = db.query(Dataset).order_by(Dataset.name.asc()).all()
    return templates.TemplateResponse("competition_form.html", {
        "request": request,
        "user": user,
        "datasets": datasets,
    })


@router.post("/competitions/create")
async def competition_create_submit(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    rules: str = Form(""),
    prize: str = Form(""),
    dataset_id: int = Form(...),
    evaluation_metric: str = Form("accuracy"),
    starts_at: str = Form(...),
    ends_at: str = Form(...),
    max_submissions_per_user: int = Form(10),
    db: Session = Depends(get_db),
):
    """Handle competition creation."""
    user = await get_current_user_from_cookie(request, db)
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can create competitions")

    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")

    valid_metrics = ("accuracy", "f1_score", "auc_roc", "r2_score",
                     "rmse", "mae", "latency_ms", "log_loss")
    if evaluation_metric not in valid_metrics:
        raise HTTPException(status_code=400, detail=f"Invalid metric")

    try:
        starts_dt = datetime.fromisoformat(starts_at)
        ends_dt = datetime.fromisoformat(ends_at)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    if ends_dt <= starts_dt:
        raise HTTPException(status_code=400, detail="End date must be after start date")

    slug = _slugify(title)
    # Make slug unique
    base_slug = slug
    suffix = 1
    while db.query(Competition).filter(Competition.slug == slug).first():
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    now = datetime.utcnow()
    status_val = "upcoming" if now < starts_dt else ("live" if now < ends_dt else "ended")

    comp = Competition(
        title=title.strip(),
        slug=slug,
        description=description.strip(),
        rules=rules.strip() or None,
        prize=prize.strip() or None,
        dataset_id=dataset_id,
        evaluation_metric=evaluation_metric,
        task_type=dataset.task_type,
        starts_at=starts_dt,
        ends_at=ends_dt,
        status=status_val,
        max_submissions_per_user=max_submissions_per_user,
        created_by=user.id,
    )
    db.add(comp)
    db.commit()
    db.refresh(comp)
    logger.info("Competition created: id=%d, slug=%s", comp.id, comp.slug)

    return RedirectResponse(url=f"/competitions/{comp.slug}", status_code=303)


@router.get("/competitions/{slug}", response_class=HTMLResponse)
async def competition_detail_page(
    request: Request,
    slug: str,
    db: Session = Depends(get_db),
):
    """Render a competition's detail page with leaderboard and discussion."""
    user = await get_current_user_from_cookie(request, db)

    comp = db.query(Competition).filter(Competition.slug == slug).first()
    if comp is None:
        raise HTTPException(status_code=404, detail="Competition not found")

    _refresh_competition_status(comp, db)

    # Build leaderboard: best submission per user, ordered by score
    submissions = (
        db.query(CompetitionSubmission)
        .filter(
            CompetitionSubmission.competition_id == comp.id,
            CompetitionSubmission.is_best == True,
            CompetitionSubmission.score.isnot(None),
        )
        .order_by(
            CompetitionSubmission.score.desc()
            if comp.evaluation_metric not in ("rmse", "mae", "latency_ms", "log_loss")
            else CompetitionSubmission.score.asc()
        )
        .all()
    )

    leaderboard_rows = []
    for idx, s in enumerate(submissions, start=1):
        leaderboard_rows.append({
            "rank": idx,
            "user_id": s.user_id,
            "username": s.user.username if s.user else "Unknown",
            "model_id": s.model_id,
            "model_name": s.model.model_name if s.model else "Unknown",
            "score": s.score,
            "submitted_at": s.submitted_at,
        })

    # User's own submissions to this competition
    user_subs = []
    if user:
        user_subs = (
            db.query(CompetitionSubmission)
            .filter(
                CompetitionSubmission.competition_id == comp.id,
                CompetitionSubmission.user_id == user.id,
            )
            .order_by(CompetitionSubmission.submitted_at.desc())
            .all()
        )

    # User's models eligible for submission
    user_models = []
    if user:
        user_models = (
            db.query(MLModel)
            .filter(MLModel.user_id == user.id)
            .order_by(MLModel.created_at.desc())
            .all()
        )

    # ── Comments (rendered server-side, no JS needed) ─────────────────────
    from app.database.models import Comment
    from sqlalchemy.orm import joinedload as _joinedload
    comments = (
        db.query(Comment)
        .filter(
            Comment.competition_id == comp.id,
            Comment.parent_id.is_(None),
        )
        .options(_joinedload(Comment.author))
        .order_by(Comment.is_pinned.desc(), Comment.created_at.asc())
        .all()
    )

    # Pre-fetch replies for each top-level comment (one extra query per
    # comment; fine for low-volume competition discussions).
    comment_rows = []
    for c in comments:
        replies = (
            db.query(Comment)
            .filter(Comment.parent_id == c.id)
            .options(_joinedload(Comment.author))
            .order_by(Comment.created_at.asc())
            .all()
        )
        comment_rows.append({
            "id": c.id,
            "author_username": c.author.username if c.author else "Unknown",
            "body": c.body,
            "created_at": c.created_at,
            "is_pinned": c.is_pinned,
            "replies": [
                {
                    "id": r.id,
                    "author_username": r.author.username if r.author else "Unknown",
                    "body": r.body,
                    "created_at": r.created_at,
                }
                for r in replies
            ],
        })

    return templates.TemplateResponse("competition_detail.html", {
        "request": request,
        "user": user,
        "comp": comp,
        "leaderboard_rows": leaderboard_rows,
        "user_submissions": user_subs,
        "user_models": user_models,
        "comments": comment_rows,
        "time_to_end": (comp.ends_at - datetime.utcnow()).total_seconds() if comp.status == "live" else None,
    })


@router.post("/competitions/{slug}/submit")
async def competition_submit(
    request: Request,
    slug: str,
    model_id: int = Form(...),
    submission_note: str = Form(""),
    db: Session = Depends(get_db),
):
    """Submit a model to a competition.

    Creates a benchmark job for the model on the competition's dataset
    and registers a CompetitionSubmission. Recomputes the per-competition
    leaderboard afterwards.
    """
    user = await get_current_user_from_cookie(request, db)
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    comp = db.query(Competition).filter(Competition.slug == slug).first()
    if comp is None:
        raise HTTPException(status_code=404, detail="Competition not found")

    _refresh_competition_status(comp, db)
    if comp.status != "live":
        raise HTTPException(status_code=400, detail=f"Competition is {comp.status}, not live")

    # Validate model ownership
    ml_model = (
        db.query(MLModel)
        .filter(MLModel.id == model_id, MLModel.user_id == user.id)
        .first()
    )
    if ml_model is None:
        raise HTTPException(status_code=404, detail="Model not found or not owned by you")

    # Check submission count limit
    existing_count = (
        db.query(CompetitionSubmission)
        .filter(
            CompetitionSubmission.competition_id == comp.id,
            CompetitionSubmission.user_id == user.id,
        )
        .count()
    )
    if existing_count >= comp.max_submissions_per_user:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {comp.max_submissions_per_user} submissions reached",
        )

    # Create benchmark job and run it
    try:
        job = create_benchmark_job(model_id=ml_model.id, dataset_id=comp.dataset_id, db=db)
        run_benchmark(job_id=job.id, db=db)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Competition submission benchmark failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Benchmark failed: {exc}")

    # Fetch the result and compute score
    result = job.result
    score = _extract_score(result, comp.evaluation_metric) if result else None

    submission = CompetitionSubmission(
        competition_id=comp.id,
        user_id=user.id,
        model_id=ml_model.id,
        benchmark_job_id=job.id,
        score=score,
        submission_note=submission_note.strip() or None,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    # Recompute leaderboard
    _recompute_competition_leaderboard(comp, db)

    # Notify the user
    _broadcast_notification(
        db, user.id, "submission_received",
        f"Submission received for {comp.title}",
        body=f"Score ({comp.evaluation_metric}): {score}",
        link=f"/competitions/{comp.slug}",
    )

    logger.info(
        "Competition submission: comp=%s user=%s model=%s score=%s",
        comp.slug, user.username, ml_model.model_name, score,
    )

    return RedirectResponse(url=f"/competitions/{comp.slug}", status_code=303)


# ─── JSON API Routes ──────────────────────────────────────────────────────────


@router.get("/api/competitions", response_class=JSONResponse)
async def api_list_competitions(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """List competitions as JSON."""
    query = db.query(Competition)
    if status:
        query = query.filter(Competition.status == status)
    comps = query.order_by(Competition.starts_at.desc()).all()
    return [
        {
            "id": c.id,
            "title": c.title,
            "slug": c.slug,
            "description": c.description,
            "dataset_id": c.dataset_id,
            "evaluation_metric": c.evaluation_metric,
            "task_type": c.task_type,
            "starts_at": c.starts_at.isoformat(),
            "ends_at": c.ends_at.isoformat(),
            "status": c.status,
            "max_submissions_per_user": c.max_submissions_per_user,
        }
        for c in comps
    ]


@router.get("/api/competitions/{slug}", response_class=JSONResponse)
async def api_get_competition(
    slug: str,
    db: Session = Depends(get_db),
):
    """Get competition detail as JSON, including the leaderboard."""
    comp = db.query(Competition).filter(Competition.slug == slug).first()
    if comp is None:
        raise HTTPException(status_code=404, detail="Competition not found")

    _refresh_competition_status(comp, db)

    submissions = (
        db.query(CompetitionSubmission)
        .filter(
            CompetitionSubmission.competition_id == comp.id,
            CompetitionSubmission.is_best == True,
            CompetitionSubmission.score.isnot(None),
        )
        .all()
    )

    lower_is_better = comp.evaluation_metric in ("rmse", "mae", "latency_ms", "log_loss")
    submissions.sort(key=lambda s: s.score, reverse=not lower_is_better)

    leaderboard = [
        {
            "rank": idx,
            "user_id": s.user_id,
            "username": s.user.username if s.user else "Unknown",
            "model_id": s.model_id,
            "model_name": s.model.model_name if s.model else "Unknown",
            "score": s.score,
            "submitted_at": s.submitted_at.isoformat(),
        }
        for idx, s in enumerate(submissions, start=1)
    ]

    return {
        "id": comp.id,
        "title": comp.title,
        "slug": comp.slug,
        "description": comp.description,
        "rules": comp.rules,
        "prize": comp.prize,
        "dataset_id": comp.dataset_id,
        "evaluation_metric": comp.evaluation_metric,
        "task_type": comp.task_type,
        "starts_at": comp.starts_at.isoformat(),
        "ends_at": comp.ends_at.isoformat(),
        "status": comp.status,
        "max_submissions_per_user": comp.max_submissions_per_user,
        "leaderboard": leaderboard,
        "total_submissions": (
            db.query(CompetitionSubmission)
            .filter(CompetitionSubmission.competition_id == comp.id)
            .count()
        ),
        "unique_participants": (
            db.query(CompetitionSubmission.user_id)
            .filter(CompetitionSubmission.competition_id == comp.id)
            .distinct().count()
        ),
    }


@router.get("/api/competitions/{slug}/leaderboard", response_class=JSONResponse)
async def api_competition_leaderboard(
    slug: str,
    db: Session = Depends(get_db),
):
    """Return just the leaderboard for a competition (live-updates friendly)."""
    comp = db.query(Competition).filter(Competition.slug == slug).first()
    if comp is None:
        raise HTTPException(status_code=404, detail="Competition not found")

    submissions = (
        db.query(CompetitionSubmission)
        .filter(
            CompetitionSubmission.competition_id == comp.id,
            CompetitionSubmission.is_best == True,
            CompetitionSubmission.score.isnot(None),
        )
        .all()
    )

    lower_is_better = comp.evaluation_metric in ("rmse", "mae", "latency_ms", "log_loss")
    submissions.sort(key=lambda s: s.score, reverse=not lower_is_better)

    return [
        {
            "rank": idx,
            "user_id": s.user_id,
            "username": s.user.username if s.user else "Unknown",
            "model_id": s.model_id,
            "model_name": s.model.model_name if s.model else "Unknown",
            "score": s.score,
            "submitted_at": s.submitted_at.isoformat(),
        }
        for idx, s in enumerate(submissions, start=1)
    ]
