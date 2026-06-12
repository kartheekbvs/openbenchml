"""
OpenBenchML Benchmark Execution Routes
=========================================
Handles benchmark job creation, execution, results display, model
comparison, and JSON API access.  HTML routes require cookie-based
authentication; API routes return JSON without auth for public data.
"""

import logging
from typing import Optional, List

from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session, joinedload

from app.database.db import get_db
from app.database.models import MLModel, Dataset, BenchmarkJob, BenchmarkResult
from app.services.benchmark_service import (
    create_benchmark_job,
    run_benchmark,
    get_benchmark_status,
    cancel_benchmark,
)
from app.routes.auth import get_current_user_from_cookie
from app.config import templates

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Status colour mapping for template rendering ──────────────────────────────
STATUS_COLORS = {
    "pending": "warning",    # yellow
    "running": "info",       # blue
    "completed": "success",  # green
    "failed": "danger",      # red
}


# ─── HTML Page Routes ─────────────────────────────────────────────────────────


@router.get("/benchmark", response_class=HTMLResponse)
async def benchmark_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Render the benchmark submission form.

    Populates two dropdowns: the current user's models and all available
    datasets.  Unauthenticated visitors are redirected to the login page.
    """
    user = await get_current_user_from_cookie(request, db)
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    models: List[MLModel] = (
        db.query(MLModel)
        .filter(MLModel.user_id == user.id)
        .order_by(MLModel.created_at.desc())
        .all()
    )
    datasets: List[Dataset] = (
        db.query(Dataset)
        .order_by(Dataset.name.asc())
        .all()
    )

    return templates.TemplateResponse("benchmark.html", {
        "request": request,
        "user": user,
        "models": models,
        "datasets": datasets,
    })


@router.post("/benchmark", response_class=HTMLResponse)
async def benchmark_submit(
    request: Request,
    model_id: int = Form(...),
    dataset_id: int = Form(...),
    db: Session = Depends(get_db),
):
    """Handle benchmark form submission.

    Creates a pending job via ``create_benchmark_job``, then immediately
    executes it synchronously with ``run_benchmark``.  On success the user
    is redirected to the results page; on failure the form is re-rendered
    with an error message.
    """
    user = await get_current_user_from_cookie(request, db)
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    # ── Verify the model belongs to the user ──────────────────────────────
    model: Optional[MLModel] = (
        db.query(MLModel).filter(MLModel.id == model_id, MLModel.user_id == user.id).first()
    )
    if model is None:
        datasets = db.query(Dataset).order_by(Dataset.name.asc()).all()
        return templates.TemplateResponse("benchmark.html", {
            "request": request,
            "user": user,
            "models": db.query(MLModel).filter(MLModel.user_id == user.id).all(),
            "datasets": datasets,
            "error": "Invalid model selected. Please choose one of your models.",
        })

    # ── Create and run the benchmark job ──────────────────────────────────
    try:
        job = create_benchmark_job(model_id=model_id, dataset_id=dataset_id, db=db)
        logger.info("Benchmark job id=%d created, starting execution", job.id)
        run_benchmark(job_id=job.id, db=db)
    except HTTPException as exc:
        logger.warning("Benchmark submission failed: %s", exc.detail)
        datasets = db.query(Dataset).order_by(Dataset.name.asc()).all()
        return templates.TemplateResponse("benchmark.html", {
            "request": request,
            "user": user,
            "models": db.query(MLModel).filter(MLModel.user_id == user.id).all(),
            "datasets": datasets,
            "error": exc.detail,
        })
    except RuntimeError as exc:
        logger.error("Benchmark execution failed for job: %s", exc)
        # Job was created but execution failed – redirect to results so user sees error
        if 'job' in dir():
            return RedirectResponse(url=f"/results/{job.id}", status_code=303)
        datasets = db.query(Dataset).order_by(Dataset.name.asc()).all()
        return templates.TemplateResponse("benchmark.html", {
            "request": request,
            "user": user,
            "models": db.query(MLModel).filter(MLModel.user_id == user.id).all(),
            "datasets": datasets,
            "error": f"Benchmark execution failed: {exc}",
        })
    except Exception as exc:
        logger.error("Unexpected benchmark error: %s", exc)
        datasets = db.query(Dataset).order_by(Dataset.name.asc()).all()
        return templates.TemplateResponse("benchmark.html", {
            "request": request,
            "user": user,
            "models": db.query(MLModel).filter(MLModel.user_id == user.id).all(),
            "datasets": datasets,
            "error": "An unexpected error occurred. Please try again.",
        })

    return RedirectResponse(url=f"/results/{job.id}", status_code=303)


@router.get("/jobs", response_class=HTMLResponse)
async def jobs_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Render a list of the current user's benchmark jobs.

    Each row shows job id, model name, dataset name, status (with colour
    coding), submitted_at, and finished_at timestamps.
    """
    user = await get_current_user_from_cookie(request, db)
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    jobs: List[BenchmarkJob] = (
        db.query(BenchmarkJob)
        .join(MLModel, MLModel.id == BenchmarkJob.model_id)
        .filter(MLModel.user_id == user.id)
        .options(
            joinedload(BenchmarkJob.model),
            joinedload(BenchmarkJob.dataset),
        )
        .order_by(BenchmarkJob.submitted_at.desc())
        .all()
    )

    # Build display rows with colour mapping
    job_rows = [
        {
            "id": j.id,
            "model_name": j.model.model_name if j.model else "Unknown",
            "dataset_name": j.dataset.name if j.dataset else "Unknown",
            "status": j.status,
            "status_color": STATUS_COLORS.get(j.status, "secondary"),
            "submitted_at": j.submitted_at,
            "finished_at": j.finished_at,
        }
        for j in jobs
    ]

    logger.debug("Fetched %d jobs for user=%s", len(job_rows), user.username)

    return templates.TemplateResponse("jobs.html", {
        "request": request,
        "user": user,
        "job_rows": job_rows,
    })


@router.get("/results/{job_id}", response_class=HTMLResponse)
async def results_page(
    request: Request,
    job_id: int,
    db: Session = Depends(get_db),
):
    """Render detailed benchmark results for a single job.

    Displays all metrics in a card layout: accuracy, precision, recall,
    f1_score, mae, rmse, r2_score, latency_ms, memory_mb, cpu_percent,
    and model_size_kb.  If the job is not yet complete the status is
    shown instead.
    """
    user = await get_current_user_from_cookie(request, db)
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    job: Optional[BenchmarkJob] = (
        db.query(BenchmarkJob)
        .options(
            joinedload(BenchmarkJob.model),
            joinedload(BenchmarkJob.dataset),
            joinedload(BenchmarkJob.result),
        )
        .filter(BenchmarkJob.id == job_id)
        .first()
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Benchmark job not found")

    # Enforce access control: only the model owner can view results
    if job.model and job.model.user_id != user.id:
        raise HTTPException(status_code=403, detail="You do not have access to this job")

    result: Optional[BenchmarkResult] = job.result

    # Build metric cards for the template (only include non-None values)
    metric_cards = []
    if result:
        metric_defs = [
            ("Accuracy", result.accuracy, "{:.4f}"),
            ("Precision", result.precision, "{:.4f}"),
            ("Recall", result.recall, "{:.4f}"),
            ("F1 Score", result.f1_score, "{:.4f}"),
            ("MAE", result.mae, "{:.4f}"),
            ("RMSE", result.rmse, "{:.4f}"),
            ("R\u00b2 Score", result.r2_score, "{:.4f}"),
            ("Latency", result.latency_ms, "{:.1f} ms"),
            ("Memory", result.memory_mb, "{:.1f} MB"),
            ("CPU Usage", result.cpu_percent, "{:.1f}%"),
            ("Model Size", result.model_size_kb, "{:.1f} KB"),
        ]
        for label, value, fmt in metric_defs:
            if value is not None:
                try:
                    formatted = fmt.format(value)
                except (ValueError, TypeError):
                    formatted = str(value)
                metric_cards.append({"label": label, "value": formatted})

    return templates.TemplateResponse("results.html", {
        "request": request,
        "user": user,
        "job": job,
        "result": result,
        "metric_cards": metric_cards,
        "status_color": STATUS_COLORS.get(job.status, "secondary"),
    })


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(
    request: Request,
    job_id: int,
    db: Session = Depends(get_db),
):
    """Cancel a pending or running benchmark job.

    Only the model owner may cancel a job.  On success or if the job is
    already in a terminal state the user is redirected back to /jobs.
    """
    user = await get_current_user_from_cookie(request, db)
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    job: Optional[BenchmarkJob] = (
        db.query(BenchmarkJob)
        .options(joinedload(BenchmarkJob.model))
        .filter(BenchmarkJob.id == job_id)
        .first()
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Benchmark job not found")

    # Enforce ownership
    if job.model and job.model.user_id != user.id:
        raise HTTPException(status_code=403, detail="You can only cancel your own jobs")

    try:
        cancelled = cancel_benchmark(job_id=job_id, db=db)
        if cancelled:
            logger.info("Job id=%d cancelled by user=%s", job_id, user.username)
        else:
            logger.info("Job id=%d could not be cancelled (terminal state)", job_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error cancelling job id=%d: %s", job_id, exc)
        raise HTTPException(status_code=500, detail="Failed to cancel job")

    return RedirectResponse(url="/jobs", status_code=303)


@router.get("/compare", response_class=HTMLResponse)
async def compare_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Render the model comparison form.

    Shows dropdowns to select 2-3 models from the user's library.  If
    comparison data is present in the query string the results are
    rendered alongside the form.
    """
    user = await get_current_user_from_cookie(request, db)
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    models: List[MLModel] = (
        db.query(MLModel)
        .filter(MLModel.user_id == user.id)
        .order_by(MLModel.model_name.asc())
        .all()
    )

    return templates.TemplateResponse("compare.html", {
        "request": request,
        "user": user,
        "models": models,
        "comparison_data": None,
    })


@router.post("/compare", response_class=HTMLResponse)
async def compare_submit(
    request: Request,
    db: Session = Depends(get_db),
    model_id_1: int = Form(...),
    model_id_2: int = Form(...),
    model_id_3: Optional[int] = Form(None),
):
    """Handle model comparison form submission.

    Fetches the best (highest accuracy / r2_score) completed result for
    each selected model and renders a side-by-side comparison table.
    """
    user = await get_current_user_from_cookie(request, db)
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    model_ids = [model_id_1, model_id_2]
    if model_id_3 is not None:
        model_ids.append(model_id_3)

    # Deduplicate in case the same model is selected twice
    model_ids = list(dict.fromkeys(model_ids))

    models: List[MLModel] = (
        db.query(MLModel)
        .filter(MLModel.user_id == user.id)
        .order_by(MLModel.model_name.asc())
        .all()
    )

    # ── Fetch best result per model ───────────────────────────────────────
    comparison_rows = []
    for mid in model_ids:
        ml_model = db.query(MLModel).filter(MLModel.id == mid).first()
        if ml_model is None:
            continue

        # Get the best result: prefer highest accuracy for classification,
        # highest r2_score for regression; fall back to latest completed job
        best_result: Optional[BenchmarkResult] = (
            db.query(BenchmarkResult)
            .join(BenchmarkJob, BenchmarkJob.id == BenchmarkResult.job_id)
            .filter(
                BenchmarkJob.model_id == mid,
                BenchmarkJob.status == "completed",
            )
            .order_by(BenchmarkResult.accuracy.desc().nullslast())
            .first()
        )

        comparison_rows.append({
            "model_id": mid,
            "model_name": ml_model.model_name,
            "framework": ml_model.framework,
            "result": best_result,
        })

    logger.debug(
        "Comparison submitted by user=%s with %d models",
        user.username, len(comparison_rows),
    )

    return templates.TemplateResponse("compare.html", {
        "request": request,
        "user": user,
        "models": models,
        "comparison_data": comparison_rows,
    })


# ─── JSON API Routes ──────────────────────────────────────────────────────────


@router.get("/api/jobs", response_class=JSONResponse)
async def api_list_jobs(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Return a JSON list of all benchmark jobs, optionally filtered by status.

    Accepts an optional ``status`` query parameter (pending, running,
    completed, failed).  Each entry includes job metadata and the
    associated model/dataset names.
    """
    query = (
        db.query(BenchmarkJob)
        .options(joinedload(BenchmarkJob.model), joinedload(BenchmarkJob.dataset))
    )

    if status:
        valid_statuses = ("pending", "running", "completed", "failed")
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. Valid: {', '.join(valid_statuses)}",
            )
        query = query.filter(BenchmarkJob.status == status)

    jobs: List[BenchmarkJob] = query.order_by(BenchmarkJob.submitted_at.desc()).all()

    return [
        {
            "id": j.id,
            "model_id": j.model_id,
            "model_name": j.model.model_name if j.model else None,
            "dataset_id": j.dataset_id,
            "dataset_name": j.dataset.name if j.dataset else None,
            "status": j.status,
            "progress": j.progress,
            "submitted_at": j.submitted_at.isoformat() if j.submitted_at else None,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "finished_at": j.finished_at.isoformat() if j.finished_at else None,
            "error_message": j.error_message,
        }
        for j in jobs
    ]


@router.get("/api/results/{job_id}", response_class=JSONResponse)
async def api_get_results(
    job_id: int,
    db: Session = Depends(get_db),
):
    """Return JSON benchmark results for a single job.

    Includes all ML metrics, regression metrics, and performance
    metrics.  Returns 404 if the job or result does not exist.
    """
    job: Optional[BenchmarkJob] = (
        db.query(BenchmarkJob)
        .options(
            joinedload(BenchmarkJob.model),
            joinedload(BenchmarkJob.dataset),
            joinedload(BenchmarkJob.result),
        )
        .filter(BenchmarkJob.id == job_id)
        .first()
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Benchmark job not found")

    response_data = {
        "job_id": job.id,
        "model_id": job.model_id,
        "model_name": job.model.model_name if job.model else None,
        "dataset_id": job.dataset_id,
        "dataset_name": job.dataset.name if job.dataset else None,
        "status": job.status,
        "progress": job.progress,
        "submitted_at": job.submitted_at.isoformat() if job.submitted_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "error_message": job.error_message,
        "metrics": None,
    }

    if job.result:
        response_data["metrics"] = {
            "accuracy": job.result.accuracy,
            "precision": job.result.precision,
            "recall": job.result.recall,
            "f1_score": job.result.f1_score,
            "mae": job.result.mae,
            "rmse": job.result.rmse,
            "r2_score": job.result.r2_score,
            "latency_ms": job.result.latency_ms,
            "memory_mb": job.result.memory_mb,
            "cpu_percent": job.result.cpu_percent,
            "model_size_kb": job.result.model_size_kb,
            "inference_count": job.result.inference_count,
        }

    return response_data
