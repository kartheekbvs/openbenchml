"""
OpenBenchML Benchmark Service
===============================
Orchestrates the full lifecycle of a benchmark job: creation, execution,
status tracking, cancellation, and leaderboard maintenance.

Key design decisions:

* **Real-time progress** — Each major phase (model load, dataset load,
  prediction, metrics) commits a new progress value to the DB and
  pushes a WebSocket notification. Clients subscribed to
  ``/ws/benchmark`` see live updates.

* **Dataset resolution** — Built-in datasets have ``file_path = None``;
  we resolve them via their lowercase ``name`` field instead. Custom
  datasets use ``file_path`` directly.

* **Real percentile latencies** — All latency percentiles come straight
  from the metrics module (per-sample timing); we never synthesise
  them here.
"""

import asyncio
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


def _notify_ws_sync(job_id: int, progress: int, status: str, **kwargs):
    """Synchronous wrapper around :func:`_notify_ws`.

    Used inside the (synchronous) ``run_benchmark`` function. We try
    to schedule the coroutine on the running event loop; if no loop is
    running (e.g. when invoked from Celery) the notification is dropped
    silently.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_notify_ws(job_id, progress, status, **kwargs))
        else:
            loop.run_until_complete(_notify_ws(job_id, progress, status, **kwargs))
    except RuntimeError:
        # No event loop in this thread — skip WS notification.
        pass
    except Exception as exc:
        logger.debug("WS sync notify failed: %s", exc)


def _resolve_dataset_source(dataset: Dataset) -> str:
    """Decide what to pass to :func:`load_dataset`.

    For built-in datasets (``is_builtin=True`` or ``file_path=None``)
    we use the lowercased dataset name, which matches the keys in the
    loader's ``_BUILTIN_DATASETS`` registry. For custom datasets we
    pass the file path.
    """
    if dataset.file_path:
        return dataset.file_path
    # Built-in: use the dataset name (lowercased & normalised)
    return (dataset.name or "").lower().replace("-", "_").replace(" ", "_")


def create_benchmark_job(model_id: int, dataset_id: int, db: Session) -> BenchmarkJob:
    """Create a new benchmark job record in the database.

    Validates that both the model and dataset exist and are compatible
    before inserting a pending job. Duplicate pending/running jobs for
    the same model-dataset pair are rejected to avoid wasted compute.
    """
    ml_model = db.query(MLModel).filter(MLModel.id == model_id).first()
    if ml_model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with id={model_id} not found",
        )

    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset with id={dataset_id} not found",
        )

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

    Phase-by-phase progress is committed to the DB and broadcast over
    WebSocket so clients can show a live progress bar.
    """
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
    job.progress = 5
    db.commit()
    _notify_ws_sync(job_id, 5, "running", message="Starting benchmark")

    try:
        # ── Load model artifact ────────────────────────────────────────────
        ml_model = db.query(MLModel).filter(MLModel.id == job.model_id).first()
        if ml_model is None:
            raise RuntimeError(f"Model id={job.model_id} not found")

        logger.info("Loading model id=%d from %s", ml_model.id, ml_model.file_path)
        model_artifact = load_model(ml_model.file_path, ml_model.framework)
        job.progress = 20
        db.commit()
        _notify_ws_sync(job_id, 20, "running", message="Model loaded")

        # ── Load dataset ───────────────────────────────────────────────────
        dataset = db.query(Dataset).filter(Dataset.id == job.dataset_id).first()
        if dataset is None:
            raise RuntimeError(f"Dataset id={job.dataset_id} not found")

        dataset_source = _resolve_dataset_source(dataset)
        if not dataset_source:
            raise RuntimeError(
                f"Dataset '{dataset.name}' has no file_path and is not a "
                f"recognised built-in dataset"
            )

        logger.info(
            "Loading dataset id=%d (source=%s, task=%s)",
            dataset.id, dataset_source, dataset.task_type,
        )
        data = load_dataset(dataset_source, task_type=dataset.task_type)
        job.progress = 40
        db.commit()
        _notify_ws_sync(job_id, 40, "running", message="Dataset loaded")

        # ── Run evaluation ─────────────────────────────────────────────────
        start_time = time.perf_counter()
        logger.info("Evaluating model id=%d on dataset id=%d", ml_model.id, dataset.id)
        _notify_ws_sync(job_id, 50, "running", message="Running predictions")
        metrics = evaluate_model(
            model_artifact=model_artifact,
            dataset=data,
            task_type=dataset.task_type,
            timeout_seconds=BENCHMARK_TIMEOUT_SECONDS,
            model_path=ml_model.file_path,
        )
        execution_time_ms = int((time.perf_counter() - start_time) * 1000)

        job.progress = 85
        db.commit()
        _notify_ws_sync(job_id, 85, "running", message="Metrics computed")

        # ── Persist result ─────────────────────────────────────────────────
        result = BenchmarkResult(
            job_id=job.id,
            # Classification metrics
            accuracy=metrics.get("accuracy"),
            precision=metrics.get("precision"),
            recall=metrics.get("recall"),
            f1_score=metrics.get("f1_score"),
            # Advanced classification metrics
            auc_roc=metrics.get("auc_roc"),
            log_loss=metrics.get("log_loss"),
            confusion_matrix=metrics.get("confusion_matrix"),
            classification_report=metrics.get("classification_report"),
            # Regression metrics
            mae=metrics.get("mae"),
            rmse=metrics.get("rmse"),
            r2_score=metrics.get("r2_score"),
            # Performance metrics (REAL percentiles from metrics module)
            latency_ms=metrics.get("latency_ms"),
            latency_p50_ms=metrics.get("latency_p50_ms"),
            latency_p95_ms=metrics.get("latency_p95_ms"),
            latency_p99_ms=metrics.get("latency_p99_ms"),
            memory_mb=metrics.get("memory_mb"),
            cpu_percent=metrics.get("cpu_percent"),
            model_size_kb=ml_model.size_kb,
            inference_count=metrics.get("inference_count", 0),
            throughput_per_sec=metrics.get("throughput_per_sec"),
        )
        db.add(result)

        job.status = "completed"
        job.progress = 100
        job.finished_at = datetime.utcnow()
        job.execution_time_ms = execution_time_ms
        db.commit()
        db.refresh(result)

        logger.info(
            "Benchmark job id=%d completed in %dms (acc=%s, p95=%.3fms, throughput=%.1f/s)",
            job_id,
            execution_time_ms,
            metrics.get("accuracy"),
            metrics.get("latency_p95_ms", 0.0),
            metrics.get("throughput_per_sec", 0.0),
        )
        _notify_ws_sync(
            job_id, 100, "completed",
            message="Benchmark completed",
            accuracy=metrics.get("accuracy"),
            latency_p95_ms=metrics.get("latency_p95_ms"),
        )

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
        _notify_ws_sync(
            job_id, job.progress or 0, "failed",
            message=f"Failed: {str(exc)[:200]}",
        )
        raise


def update_leaderboard(dataset_id: int, db: Session) -> None:
    """Recalculate leaderboard rankings for a specific dataset.

    All BenchmarkResult rows that belong to completed jobs on the given
    dataset are considered. The primary score is accuracy for
    classification and r2_score for regression. Dense ranking is
    applied and rank changes are tracked via ``previous_rank``.
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
            entry.previous_rank = entry.rank
            entry.rank = rank
            entry.score = row.score
            entry.updated_at = datetime.utcnow()

    db.commit()
    logger.info("Leaderboard updated for dataset id=%d (%d entries)", dataset_id, len(results))

    # ── Broadcast leaderboard update over WebSocket ────────────────────────
    try:
        from app.main import ws_manager
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(ws_manager.broadcast({
                "type": "leaderboard_update",
                "dataset_id": dataset_id,
                "dataset_name": dataset.name if dataset else None,
                "timestamp": datetime.utcnow().isoformat(),
                "entries": len(results),
            }))
    except Exception as exc:
        logger.debug("Leaderboard WS broadcast failed: %s", exc)


def get_benchmark_status(job_id: int, db: Session) -> Dict[str, Optional[object]]:
    """Return the current status and progress of a benchmark job."""
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
            "auc_roc": job.result.auc_roc,
            "log_loss": job.result.log_loss,
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
    """Cancel a pending or running benchmark job."""
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
    """Get aggregated platform statistics."""
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
