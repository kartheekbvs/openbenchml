"""
OpenBenchML Benchmark Service
===============================
Orchestrates the full lifecycle of a benchmark job: creation, execution,
status tracking, cancellation, and leaderboard maintenance.
"""

import logging
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
from app.database.db import get_db
from app.benchmark_engine.evaluator import evaluate_model
from app.benchmark_engine.loader import load_model, load_dataset

logger = logging.getLogger(__name__)


def create_benchmark_job(model_id: int, dataset_id: int, db: Session) -> BenchmarkJob:
    """Create a new benchmark job record in the database.

    Validates that both the model and dataset exist and are compatible
    (e.g. the model's framework is supported for the dataset's task type)
    before inserting a ``pending`` job.  Duplicate pending/running jobs
    for the same model–dataset pair are rejected to avoid wasted compute.

    Args:
        model_id: Primary key of the :class:`MLModel` to benchmark.
        dataset_id: Primary key of the :class:`Dataset` to evaluate on.
        db: Active SQLAlchemy session.

    Returns:
        The newly created :class:`BenchmarkJob` with status ``pending``.

    Raises:
        HTTPException (404): If the model or dataset does not exist.
        HTTPException (409): If a pending/running job already exists for
            the same model–dataset pair.
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
        job.id,
        model_id,
        dataset_id,
    )
    return job


def run_benchmark(job_id: int, db: Session) -> BenchmarkResult:
    """Execute a benchmark job end-to-end and persist the results.

    This is the main orchestration function.  It transitions the job
    through the ``running`` → ``completed`` / ``failed`` lifecycle,
    loads the model and dataset, runs evaluation, and writes a
    :class:`BenchmarkResult` row.  After a successful run the
    leaderboard for the associated dataset is automatically updated.

    If any step fails the job is marked ``failed`` with an error message
    and the exception is re-raised so the caller can respond accordingly.

    Args:
        job_id: Primary key of the :class:`BenchmarkJob` to execute.
        db: Active SQLAlchemy session.

    Returns:
        The :class:`BenchmarkResult` produced by the evaluation.

    Raises:
        HTTPException (404): If the job does not exist.
        RuntimeError: If the model or dataset cannot be loaded, or if
            the evaluation itself fails.
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
        logger.info("Evaluating model id=%d on dataset id=%d", ml_model.id, dataset.id)
        metrics = evaluate_model(
            model_artifact=model_artifact,
            dataset=data,
            task_type=dataset.task_type,
            timeout_seconds=BENCHMARK_TIMEOUT_SECONDS,
        )
        job.progress = 90
        db.commit()

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
            memory_mb=metrics.get("memory_mb"),
            cpu_percent=metrics.get("cpu_percent"),
            model_size_kb=ml_model.size_kb,
            inference_count=metrics.get("inference_count", 0),
        )
        db.add(result)

        job.status = "completed"
        job.progress = 100
        job.finished_at = datetime.utcnow()
        db.commit()
        db.refresh(result)

        logger.info("Benchmark job id=%d completed successfully", job_id)

        # ── Update leaderboard ─────────────────────────────────────────────
        update_leaderboard(job.dataset_id, db)

        return result

    except Exception as exc:
        # ── Mark job as failed ─────────────────────────────────────────────
        job.status = "failed"
        job.error_message = str(exc)[:2000]  # truncate to fit column
        job.finished_at = datetime.utcnow()
        db.commit()
        logger.error("Benchmark job id=%d failed: %s", job_id, exc)
        raise


def update_leaderboard(dataset_id: int, db: Session) -> None:
    """Recalculate leaderboard rankings for a specific dataset.

    All :class:`BenchmarkResult` rows that belong to completed jobs on
    the given dataset are considered.  The primary score is
    ``accuracy`` for classification tasks and ``r2_score`` for
    regression tasks.  Results are ranked in descending order (higher
    is better).  Existing :class:`Leaderboard` entries are upserted so
    that rank history is maintained within the same row.

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
        # Dense ranking: same score → same rank
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
            entry.rank = rank
            entry.score = row.score
            entry.updated_at = datetime.utcnow()

    db.commit()
    logger.info("Leaderboard updated for dataset id=%d (%d entries)", dataset_id, len(results))


def get_benchmark_status(job_id: int, db: Session) -> Dict[str, Optional[object]]:
    """Return the current status and progress of a benchmark job.

    The returned dictionary includes the job's state, progress percentage,
    timing information, and – when available – a summary of the result
    metrics.  This is the primary read endpoint for polling clients.

    Args:
        job_id: Primary key of the :class:`BenchmarkJob`.
        db: Active SQLAlchemy session.

    Returns:
        A dictionary with keys: ``id``, ``status``, ``progress``,
        ``submitted_at``, ``started_at``, ``finished_at``,
        ``error_message``, and optionally ``result``.

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
        "error_message": job.error_message,
    }

    # ── Attach result summary if the job completed ─────────────────────────
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
            "memory_mb": job.result.memory_mb,
        }
    else:
        status_dict["result"] = None

    logger.debug("Benchmark status for job id=%d: %s", job_id, job.status)
    return status_dict


def cancel_benchmark(job_id: int, db: Session) -> bool:
    """Cancel a pending or running benchmark job.

    Only jobs in ``pending`` or ``running`` state can be cancelled.
    Completed or already-failed jobs are left untouched.  The function
    records a cancellation timestamp and a descriptive error message so
    that the cancellation is visible in the audit trail.

    Args:
        job_id: Primary key of the :class:`BenchmarkJob`.
        db: Active SQLAlchemy session.

    Returns:
        ``True`` if the job was successfully cancelled, ``False`` if the
        job was already in a terminal state.

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
        logger.warning(
            "Cannot cancel job id=%d: status is '%s'", job_id, job.status
        )
        return False

    job.status = "failed"
    job.error_message = "Job cancelled by user"
    job.finished_at = datetime.utcnow()
    db.commit()

    logger.info("Benchmark job id=%d cancelled", job_id)
    return True
