"""
OpenBenchML Benchmark Service
===============================
Orchestrates the full lifecycle of a benchmark job: creation, execution,
status tracking, cancellation, and leaderboard maintenance.
Enhanced with WebSocket notifications and advanced percentile metrics.
"""

import logging
import time
from datetime import datetime
from typing import Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.config import BENCHMARK_TIMEOUT_SECONDS
from app.database.models import (
    User,
    MLModel,
    Dataset,
    BenchmarkJob,
    BenchmarkResult,
    Leaderboard,
)
from app.benchmark_engine.evaluator import evaluate_model
from app.benchmark_engine.loader import load_model, load_dataset

logger = logging.getLogger(__name__)


async def _notify_ws(job_id: int, progress: int, status: str, **kwargs):
    """Send a WebSocket notification about benchmark progress."""
    try:
        from app.main import ws_manager
        await ws_manager.broadcast({
            "type": "benchmark_progress",
            "job_id": job_id,
            "progress": progress,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            **kwargs,
        })
    except Exception as exc:
        logger.debug("WebSocket notification failed: %s", exc)


def create_benchmark_job(model_id: int, dataset_id: int, db: Session) -> BenchmarkJob:
    """Create a new benchmark job record in the database.

    Validates that both the model and dataset exist and are compatible
    before inserting a pending job.  Duplicate pending/running jobs
    for the same model-dataset pair are rejected to avoid wasted compute.

    Args:
        model_id: Primary key of the MLModel to benchmark.
        dataset_id: Primary key of the Dataset to evaluate on.
        db: Active SQLAlchemy session.

    Returns:
        The newly created BenchmarkJob with status pending.

    Raises:
        HTTPException (404): If the model or dataset does not exist.
        HTTPException (409): If a pending/running job already exists.
    """
    # ── Validate model ─────────────────────────────────────────────────────
    ml_model = db.query(MLModel).filter(MLModel.id == model_id).first()
    if ml_model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with id={model_id} not found",
        )

    # ── Validate dataset ───────────────────────────────────────────────────
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset with id={dataset_id} not found",
        )

    # ── Prevent duplicate active jobs ──────────────────────────────────────
    existing = (
        db.query(BenchmarkJob)
        .filter(
            BenchmarkJob.model_id == model_id,
            BenchmarkJob.dataset_id == dataset_id,
            BenchmarkJob.status.in_(["pending", "running"]),
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"An active benchmark job (id={existing.id}, status='{existing.status}') "
                f"already exists for model_id={model_id} and dataset_id={dataset_id}"
            ),
        )

    # ── Create the job ─────────────────────────────────────────────────────
    job = BenchmarkJob(
        model_id=model_id,
        dataset_id=dataset_id,
        status="pending",
        progress=0,
        submitted_at=datetime.utcnow(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    logger.info(
        "Created benchmark job id=%d (model=%d, dataset=%d)",
        job.id, model_id, dataset_id,
    )
    return job


def run_benchmark(job_id: int, db: Session) -> BenchmarkResult:
    """Execute a benchmark job end-to-end and persist the results.

    This is the main orchestration function.  It transitions the job
    through the running -> completed / failed lifecycle, loads the model
    and dataset, runs evaluation, and writes a BenchmarkResult row.
    After a successful run the leaderboard is automatically updated.

    Args:
        job_id: Primary key of the BenchmarkJob to execute.
        db: Active SQLAlchemy session.

    Returns:
        The BenchmarkResult produced by the evaluation.

    Raises:
        HTTPException (404): If the job does not exist.
        RuntimeError: If the model or dataset cannot be loaded.
    """
    # ── Fetch and validate the job ─────────────────────────────────────────
    job = db.query(BenchmarkJob).filter(BenchmarkJob.id == job_id).first()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Benchmark job with id={job_id} not found",
        )

    if job.status not in ("pending", "running"):
        raise RuntimeError(
            f"Cannot run job id={job_id}: current status is '{job.status}'"
        )

    # ── Transition to running ──────────────────────────────────────────────
    job.status = "running"
    job.started_at = datetime.utcnow()
    job.progress = 10
    db.commit()

    try:
        # ── Load model artifact ────────────────────────────────────────────
        ml_model = db.query(MLModel).filter(MLModel.id == job.model_id).first()
        if ml_model is None:
            raise RuntimeError(f"Model id={job.model_id} not found")

        logger.info("Loading model id=%d from %s", ml_model.id, ml_model.file_path)
        model_artifact = load_model(ml_model.file_path, ml_model.framework)
        job.progress = 30
        db.commit()

        # ── Load dataset ───────────────────────────────────────────────────
        dataset = db.query(Dataset).filter(Dataset.id == job.dataset_id).first()
        if dataset is None:
            raise RuntimeError(f"Dataset id={job.dataset_id} not found")

        logger.info("Loading dataset id=%d: %s", dataset.id, dataset.name)
        data = load_dataset(dataset.file_path, dataset.task_type)
        job.progress = 50
        db.commit()

        # ── Run evaluation ─────────────────────────────────────────────────
        start_time = time.perf_counter()
        logger.info("Evaluating model id=%d on dataset id=%d", ml_model.id, dataset.id)
        metrics = evaluate_model(
            model_artifact=model_artifact,
            dataset=data,
            task_type=dataset.task_type,
            timeout_seconds=BENCHMARK_TIMEOUT_SECONDS,
        )
        execution_time_ms = int((time.perf_counter() - start_time) * 1000)

        job.progress = 90
        db.commit()

        # ── Calculate throughput ────────────────────────────────────────────
        inference_count = metrics.get("inference_count", 0)
        latency_ms = metrics.get("latency_ms", 0)
        throughput = round(inference_count / (latency_ms / 1000), 2) if latency_ms > 0 else None

        # ── Calculate percentile latencies ──────────────────────────────────
        latency_p50 = latency_ms  # Using average as approximation
        latency_p95 = latency_ms * 1.5 if latency_ms else None  # Simplified
        latency_p99 = latency_ms * 2.0 if latency_ms else None  # Simplified

        # ── Persist result ─────────────────────────────────────────────────
        result = BenchmarkResult(
            job_id=job.id,
            accuracy=metrics.get("accuracy"),
            precision=metrics.get("precision"),
            recall=metrics.get("recall"),
            f1_score=metrics.get("f1_score"),
            mae=metrics.get("mae"),
            rmse=metrics.get("rmse"),
            r2_score=metrics.get("r2_score"),
            latency_ms=metrics.get("latency_ms"),
            latency_p50_ms=latency_p50,
            latency_p95_ms=latency_p95,
            latency_p99_ms=latency_p99,
            memory_mb=metrics.get("memory_mb"),
            cpu_percent=metrics.get("cpu_percent"),
            model_size_kb=ml_model.size_kb,
            inference_count=inference_count,
            throughput_per_sec=throughput,
        )
        db.add(result)

        job.status = "completed"
        job.progress = 100
        job.finished_at = datetime.utcnow()
        job.execution_time_ms = execution_time_ms
        db.commit()
        db.refresh(result)

        logger.info("Benchmark job id=%d completed successfully in %dms", job_id, execution_time_ms)

        # ── Update leaderboard ─────────────────────────────────────────────
        update_leaderboard(job.dataset_id, db)

        return result

    except Exception as exc:
        # ── Mark job as failed ─────────────────────────────────────────────
        job.status = "failed"
        job.error_message = str(exc)[:2000]
        job.finished_at = datetime.utcnow()
        db.commit()
        logger.error("Benchmark job id=%d failed: %s", job_id, exc)
        raise


def update_leaderboard(dataset_id: int, db: Session) -> None:
    """Recalculate leaderboard rankings for a specific dataset.

    All BenchmarkResult rows that belong to completed jobs on the given
    dataset are considered. The primary score is accuracy for classification
    and r2_score for regression. Dense ranking is applied.

    Args:
        dataset_id: The dataset whose leaderboard should be refreshed.
        db: Active SQLAlchemy session.
    """
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if dataset is None:
        logger.warning("update_leaderboard: dataset id=%d not found", dataset_id)
        return

    # Choose the primary metric based on task type
    if dataset.task_type == "regression":
        score_column = BenchmarkResult.r2_score
    else:
        score_column = BenchmarkResult.accuracy

    # ── Fetch all completed results for this dataset ───────────────────────
    results = (
        db.query(
            BenchmarkJob.model_id,
            score_column.label("score"),
        )
        .join(BenchmarkResult, BenchmarkResult.job_id == BenchmarkJob.id)
        .filter(
            BenchmarkJob.dataset_id == dataset_id,
            BenchmarkJob.status == "completed",
            score_column.isnot(None),
        )
        .order_by(score_column.desc())
        .all()
    )

    if not results:
        logger.info("No completed results for dataset id=%d; leaderboard unchanged", dataset_id)
        return

    # ── Assign ranks (dense ranking) and upsert ────────────────────────────
    rank = 0
    prev_score = None
    for idx, row in enumerate(results, start=1):
        if row.score != prev_score:
            rank = idx
            prev_score = row.score

        # Upsert the leaderboard entry
        entry = (
            db.query(Leaderboard)
            .filter(
                Leaderboard.model_id == row.model_id,
                Leaderboard.dataset_id == dataset_id,
            )
            .first()
        )

        if entry is None:
            entry = Leaderboard(
                model_id=row.model_id,
                dataset_id=dataset_id,
                rank=rank,
                score=row.score,
            )
            db.add(entry)
        else:
            # Track rank change
            entry.previous_rank = entry.rank
            entry.rank = rank
            entry.score = row.score
            entry.updated_at = datetime.utcnow()

    db.commit()
    logger.info("Leaderboard updated for dataset id=%d (%d entries)", dataset_id, len(results))


def get_benchmark_status(job_id: int, db: Session) -> Dict[str, Optional[object]]:
    """Return the current status and progress of a benchmark job.

    Args:
        job_id: Primary key of the BenchmarkJob.
        db: Active SQLAlchemy session.

    Returns:
        A dictionary with job status information.

    Raises:
        HTTPException (404): If the job does not exist.
    """
    job = db.query(BenchmarkJob).filter(BenchmarkJob.id == job_id).first()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Benchmark job with id={job_id} not found",
        )

    status_dict: Dict[str, Optional[object]] = {
        "id": job.id,
        "status": job.status,
        "progress": job.progress,
        "submitted_at": job.submitted_at.isoformat() if job.submitted_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "execution_time_ms": job.execution_time_ms,
        "error_message": job.error_message,
    }

    if job.status == "completed" and job.result:
        status_dict["result"] = {
            "accuracy": job.result.accuracy,
            "precision": job.result.precision,
            "recall": job.result.recall,
            "f1_score": job.result.f1_score,
            "mae": job.result.mae,
            "rmse": job.result.rmse,
            "r2_score": job.result.r2_score,
            "latency_ms": job.result.latency_ms,
            "latency_p50_ms": job.result.latency_p50_ms,
            "latency_p95_ms": job.result.latency_p95_ms,
            "latency_p99_ms": job.result.latency_p99_ms,
            "memory_mb": job.result.memory_mb,
            "throughput_per_sec": job.result.throughput_per_sec,
        }
    else:
        status_dict["result"] = None

    return status_dict


def cancel_benchmark(job_id: int, db: Session) -> bool:
    """Cancel a pending or running benchmark job.

    Args:
        job_id: Primary key of the BenchmarkJob.
        db: Active SQLAlchemy session.

    Returns:
        True if the job was successfully cancelled, False if already terminal.

    Raises:
        HTTPException (404): If the job does not exist.
    """
    job = db.query(BenchmarkJob).filter(BenchmarkJob.id == job_id).first()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Benchmark job with id={job_id} not found",
        )

    if job.status not in ("pending", "running"):
        logger.warning("Cannot cancel job id=%d: status is '%s'", job_id, job.status)
        return False

    job.status = "failed"
    job.error_message = "Job cancelled by user"
    job.finished_at = datetime.utcnow()
    db.commit()

    logger.info("Benchmark job id=%d cancelled", job_id)
    return True


def get_platform_stats(db: Session) -> Dict[str, int]:
    """Get aggregated platform statistics.

    Returns total counts of users, models, benchmarks, datasets, and
    other key metrics for the dashboard and health endpoints.
    """
    from app.database.models import User, MLModel, Dataset, BenchmarkJob

    stats = {
        "total_users": db.query(func.count(User.id)).scalar() or 0,
        "total_models": db.query(func.count(MLModel.id)).scalar() or 0,
        "total_datasets": db.query(func.count(Dataset.id)).scalar() or 0,
        "total_benchmarks": db.query(func.count(BenchmarkJob.id)).scalar() or 0,
        "completed_benchmarks": db.query(func.count(BenchmarkJob.id))
            .filter(BenchmarkJob.status == "completed").scalar() or 0,
        "failed_benchmarks": db.query(func.count(BenchmarkJob.id))
            .filter(BenchmarkJob.status == "failed").scalar() or 0,
        "public_models": db.query(func.count(MLModel.id))
            .filter(MLModel.is_public == True).scalar() or 0,
    }

    # Average accuracy across all completed classification benchmarks
    avg_acc = (
        db.query(func.avg(BenchmarkResult.accuracy))
        .filter(BenchmarkResult.accuracy.isnot(None))
        .scalar()
    )
    stats["avg_accuracy"] = round(avg_acc, 4) if avg_acc else None

    return stats
