"""
OpenBenchML Celery Worker
==========================
Celery task queue for asynchronous benchmark execution.

The ``run_benchmark`` task offloads the heavy evaluation work to a
Celery worker process so that the FastAPI web server remains
responsive.  Each task creates its own database session, calls the
benchmark service, and returns a result dictionary.

Usage
-----
Start the worker from the project root::

    celery -A app.workers.celery_worker worker --loglevel=info

Public API
----------

* :func:`get_celery_app` – retrieve the Celery application instance
* :func:`run_benchmark`   – Celery task that executes a benchmark job
"""

import logging
from typing import Any, Dict, Optional

from celery import Celery

from app.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND
from app.database.db import SessionLocal
from app.services.benchmark_service import run_benchmark as _run_benchmark

logger = logging.getLogger(__name__)

# ─── Celery application instance ───────────────────────────────────────────────

_celery_app: Optional[Celery] = None


def get_celery_app() -> Celery:
    """Return (and lazily create) the Celery application instance.

    The app is configured with the broker and result backend URLs from
    :mod:`app.config`.  Serialisation is set to JSON for portability.

    Returns:
        The shared :class:`celery.Celery` instance.
    """
    global _celery_app
    if _celery_app is None:
        _celery_app = Celery(
            "openbenchml",
            broker=CELERY_BROKER_URL,
            backend=CELERY_RESULT_BACKEND,
        )
        _celery_app.conf.update(
            # Use JSON serialisation for all message types.
            task_serializer="json",
            result_serializer="json",
            accept_content=["json"],
            # Timeouts
            task_soft_time_limit=600,   # 10 min soft limit
            task_time_limit=900,        # 15 min hard limit
            # Results
            result_expires=3600,        # Results kept for 1 hour
            # Concurrency
            worker_prefetch_multiplier=1,
            worker_max_tasks_per_child=50,
            # Reliability
            task_acks_late=True,
            task_reject_on_worker_lost=True,
        )
        logger.info(
            "Celery app created (broker=%s, backend=%s)",
            CELERY_BROKER_URL,
            CELERY_RESULT_BACKEND,
        )
    return _celery_app


# ─── Initialise the app at import time so ``celery -A`` can find it ────────────

celery = get_celery_app()


# ─── Benchmark task ────────────────────────────────────────────────────────────

@celery.task(
    name="run_benchmark",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
    track_started=True,
)
def run_benchmark(self: Any, job_id: int) -> Dict[str, Any]:
    """Execute a benchmark job asynchronously via Celery.

    This task is the bridge between the web API and the benchmark
    service.  It creates its own short-lived database session, calls
    :func:`app.services.benchmark_service.run_benchmark`, and returns
    the result as a plain dictionary (Celery serialises the return
    value as JSON).

    If a transient error occurs (e.g. database connection issue) the
    task is retried up to ``max_retries`` times with an exponential
    back-off.

    Args:
        self: The Celery task instance (injected because ``bind=True``).
        job_id: Primary key of the :class:`BenchmarkJob` to execute.

    Returns:
        A dictionary containing the benchmark result metrics with keys
        such as ``accuracy``, ``precision``, ``recall``, ``f1_score``,
        ``latency_ms``, ``memory_mb``, etc.

    Raises:
        Exception: Re-raised after all retries are exhausted.
    """
    logger.info("Celery task run_benchmark started for job_id=%d", job_id)

    db = SessionLocal()
    try:
        result = _run_benchmark(job_id, db)

        # Convert the SQLAlchemy model to a plain dict for JSON
        # serialisation.  The BenchmarkResult model has simple scalar
        # columns so a manual mapping is reliable.
        result_dict = _result_to_dict(result)
        logger.info(
            "Celery task run_benchmark completed for job_id=%d", job_id
        )
        return result_dict

    except Exception as exc:
        logger.error(
            "Celery task run_benchmark failed for job_id=%d: %s",
            job_id,
            exc,
        )
        # Retry on potentially transient errors (DB connection, etc.).
        # Do not retry on application-level errors (404, validation).
        from fastapi import HTTPException

        if isinstance(exc, HTTPException):
            # HTTPExceptions are application-level; don't retry.
            return {
                "error": str(exc.detail),
                "status_code": exc.status_code,
                "job_id": job_id,
            }

        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error(
                "Max retries exceeded for job_id=%d", job_id
            )
            raise

    finally:
        db.close()


# ─── Helper functions ──────────────────────────────────────────────────────────

def _result_to_dict(result: Any) -> Dict[str, Any]:
    """Convert a :class:`BenchmarkResult` ORM object to a plain dict.

    This is necessary because Celery serialises return values as JSON,
    and SQLAlchemy model instances are not JSON-serialisable by
    default.

    Args:
        result: A :class:`app.database.models.BenchmarkResult` instance.

    Returns:
        A dictionary with all result columns as key/value pairs.
    """
    return {
        "id": result.id,
        "job_id": result.job_id,
        "accuracy": result.accuracy,
        "precision": result.precision,
        "recall": result.recall,
        "f1_score": result.f1_score,
        "mae": result.mae,
        "rmse": result.rmse,
        "r2_score": result.r2_score,
        "latency_ms": result.latency_ms,
        "memory_mb": result.memory_mb,
        "cpu_percent": result.cpu_percent,
        "model_size_kb": result.model_size_kb,
        "inference_count": result.inference_count,
        "created_at": result.created_at.isoformat() if result.created_at else None,
    }
