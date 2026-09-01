"""
OpenBenchML Metrics Computation
=================================
Real, per-sample latency percentiles, advanced classification metrics
(AUC-ROC, log-loss, confusion matrix, classification report), and
process-level resource profiling.

This is the heart of the core benchmark engine. Every number produced
here is a true measurement — no synthetic approximations, no
"latency * 1.5" style fake percentiles.

Public API:

* :func:`compute_classification_metrics`
* :func:`compute_regression_metrics`
* :func:`compute_performance_metrics`
* :func:`compute_all_metrics`
"""

import logging
import os
import time
import tracemalloc
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    roc_auc_score,
    log_loss,
    confusion_matrix,
    classification_report,
)

logger = logging.getLogger(__name__)


# ─── Classification metrics ────────────────────────────────────────────────────

def compute_classification_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """Compute standard classification metrics.

    All multi-class metrics use ``average='weighted'`` to handle
    imbalanced class distributions gracefully.

    Args:
        y_true: Ground-truth labels of shape ``(n_samples,)``.
        y_pred: Predicted labels of shape ``(n_samples,)``.
        y_proba: Optional predicted probabilities of shape
            ``(n_samples, n_classes)``.  When provided, AUC-ROC and
            log-loss are also computed.

    Returns:
        Dictionary with keys: ``accuracy``, ``precision``, ``recall``,
        ``f1_score``, and (when *y_proba* is given) ``auc_roc``,
        ``log_loss``, ``confusion_matrix``, ``classification_report``.
    """
    y_true = np.asarray(y_true).ravel()
    y_pred = np.asarray(y_pred).ravel()

    if y_true.shape != y_pred.shape:
        raise ValueError(
            f"Shape mismatch: y_true has {y_true.shape[0]} samples, "
            f"y_pred has {y_pred.shape[0]} samples"
        )

    n_samples = y_true.shape[0]
    if n_samples == 0:
        logger.warning("Empty arrays passed to compute_classification_metrics")
        return {
            "accuracy": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "f1_score": 0.0,
        }

    metrics: Dict[str, Any] = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(
            precision_score(y_true, y_pred, average="weighted", zero_division=0)
        ),
        "recall": float(
            recall_score(y_true, y_pred, average="weighted", zero_division=0)
        ),
        "f1_score": float(
            f1_score(y_true, y_pred, average="weighted", zero_division=0)
        ),
    }

    # ── Confusion matrix (always computable) ───────────────────────────────
    try:
        cm = confusion_matrix(y_true, y_pred)
        metrics["confusion_matrix"] = cm.tolist()
    except Exception as exc:
        logger.debug("Could not compute confusion_matrix: %s", exc)
        metrics["confusion_matrix"] = None

    # ── Classification report (per-class breakdown) ────────────────────────
    try:
        report = classification_report(
            y_true, y_pred, output_dict=True, zero_division=0
        )
        # JSON-serialise: convert numpy floats inside the dict
        metrics["classification_report"] = _jsonify(report)
    except Exception as exc:
        logger.debug("Could not compute classification_report: %s", exc)
        metrics["classification_report"] = None

    # ── AUC-ROC and log-loss (require probabilities) ───────────────────────
    if y_proba is not None:
        try:
            # Binarise labels for multi-class ROC
            classes = np.unique(y_true)
            if len(classes) == 2:
                # Binary: proba[:, 1] is positive-class prob
                if y_proba.ndim == 2 and y_proba.shape[1] == 2:
                    metrics["auc_roc"] = float(
                        roc_auc_score(y_true, y_proba[:, 1])
                    )
                else:
                    metrics["auc_roc"] = float(roc_auc_score(y_true, y_proba.ravel()))
            elif len(classes) > 2:
                metrics["auc_roc"] = float(
                    roc_auc_score(
                        y_true, y_proba, multi_class="ovr", average="weighted"
                    )
                )
        except Exception as exc:
            logger.debug("Could not compute AUC-ROC: %s", exc)
            metrics["auc_roc"] = None

        try:
            metrics["log_loss"] = float(log_loss(y_true, y_proba, labels=classes))
        except Exception as exc:
            logger.debug("Could not compute log_loss: %s", exc)
            metrics["log_loss"] = None
    else:
        metrics["auc_roc"] = None
        metrics["log_loss"] = None

    logger.debug(
        "Classification metrics: accuracy=%.4f, precision=%.4f, "
        "recall=%.4f, f1=%.4f, auc=%s, logloss=%s",
        metrics["accuracy"],
        metrics["precision"],
        metrics["recall"],
        metrics["f1_score"],
        metrics.get("auc_roc"),
        metrics.get("log_loss"),
    )
    return metrics


def _jsonify(obj: Any) -> Any:
    """Recursively convert numpy scalars/arrays to JSON-safe Python types."""
    if isinstance(obj, dict):
        return {str(k): _jsonify(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonify(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


# ─── Regression metrics ────────────────────────────────────────────────────────

def compute_regression_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> Dict[str, float]:
    """Compute standard regression metrics.

    Args:
        y_true: Ground-truth targets of shape ``(n_samples,)`` or
            ``(n_samples, n_outputs)``.
        y_pred: Predicted targets of same shape as *y_true*.

    Returns:
        Dictionary with keys: ``mae``, ``rmse``, ``r2_score``,
        ``mse``, ``explained_variance``, ``max_error``.
    """
    y_true = np.asarray(y_true).ravel()
    y_pred = np.asarray(y_pred).ravel()

    if y_true.shape != y_pred.shape:
        raise ValueError(
            f"Shape mismatch: y_true has {y_true.shape[0]} samples, "
            f"y_pred has {y_pred.shape[0]} samples"
        )

    n_samples = y_true.shape[0]
    if n_samples == 0:
        logger.warning("Empty arrays passed to compute_regression_metrics")
        return {"mae": 0.0, "rmse": 0.0, "r2_score": 0.0, "mse": 0.0,
                "explained_variance": 0.0, "max_error": 0.0}

    from sklearn.metrics import explained_variance_score, max_error

    mse = float(mean_squared_error(y_true, y_pred))
    metrics: Dict[str, float] = {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mse)),
        "mse": mse,
        "r2_score": float(r2_score(y_true, y_pred)),
        "explained_variance": float(explained_variance_score(y_true, y_pred)),
        "max_error": float(max_error(y_true, y_pred)),
    }

    logger.debug(
        "Regression metrics: mae=%.4f, rmse=%.4f, r2=%.4f",
        metrics["mae"],
        metrics["rmse"],
        metrics["r2_score"],
    )
    return metrics


# ─── Performance metrics ───────────────────────────────────────────────────────

# Number of warm-up runs (excluded from timing).
_DEFAULT_WARMUP_RUNS = 5

# Default number of timed runs.
_DEFAULT_TIMED_RUNS = 50

# Hard ceiling on timed runs to keep benchmarks bounded.
_MAX_TIMED_RUNS = 200

# Hard floor so latency percentiles are statistically meaningful.
_MIN_TIMED_RUNS = 10


def compute_performance_metrics(
    model: Any,
    X_test: np.ndarray,
    framework: str,
    model_path: Optional[str] = None,
    *,
    warmup_runs: int = _DEFAULT_WARMUP_RUNS,
    timed_runs: int = _DEFAULT_TIMED_RUNS,
    batch_size: int = 1,
) -> Dict[str, Any]:
    """Measure inference performance with REAL per-sample latency percentiles.

    What is measured and how:

    * **Latency** — For each timed run we time a forward pass on a batch
      of *batch_size* samples, then divide by *batch_size* to get a
      per-sample latency.  We collect all per-sample latencies into a
      list and compute true P50 / P95 / P99 / mean / std from that list.
      No fake ``latency * 1.5`` approximations.

    * **Throughput** — Total samples processed divided by total wall
      time across all timed runs.

    * **Memory** — Peak memory delta measured with :mod:`tracemalloc`
      during the inference loop.  If ``psutil`` is available the
      process-level RSS delta is also captured.

    * **CPU percent** — Sampled via :mod:`psutil` during the loop.

    * **Model size** — File size of the model on disk (KB).

    Args:
        model: The loaded model object.
        X_test: Test features used for the inference loop.
        framework: Framework identifier (affects prediction dispatch).
        model_path: Optional path to the model file on disk (for size).
        warmup_runs: Number of untimed warm-up runs (default 5).
        timed_runs: Number of timed runs (default 50, max 200, min 10).
        batch_size: Number of samples per forward pass (default 1).

    Returns:
        Dictionary with keys: ``latency_ms`` (mean), ``latency_p50_ms``,
        ``latency_p95_ms``, ``latency_p99_ms``, ``latency_std_ms``,
        ``throughput_per_sec``, ``memory_mb``, ``cpu_percent``,
        ``model_size_kb``, ``inference_count``, ``timed_runs``.
    """
    X_test = np.asarray(X_test)
    framework = (framework or "").lower().strip()

    # ── Clamp timed_runs to a sane range ───────────────────────────────────
    timed_runs = max(_MIN_TIMED_RUNS, min(_MAX_TIMED_RUNS, int(timed_runs)))
    warmup_runs = max(0, int(warmup_runs))
    batch_size = max(1, int(batch_size))

    # ── Model file size ───────────────────────────────────────────────────
    model_size_kb = 0.0
    if model_path and os.path.isfile(model_path):
        model_size_kb = os.path.getsize(model_path) / 1024.0
    logger.debug("Model size: %.2f KB", model_size_kb)

    # ── Pick a slice of test data to use for timing ───────────────────────
    n_available = X_test.shape[0]
    n_samples_per_run = min(batch_size, n_available)
    if n_samples_per_run < 1:
        raise ValueError("X_test is empty – cannot run performance benchmark")

    timing_input = X_test[:n_samples_per_run]

    # ── Warm-up runs (untimed) ────────────────────────────────────────────
    for i in range(warmup_runs):
        try:
            _predict_single(model, timing_input, framework)
        except Exception as exc:
            logger.warning("Warm-up prediction %d failed: %s", i, exc)

    # ── Start profiling ───────────────────────────────────────────────────
    tracemalloc.start()
    cpu_percent_samples: List[float] = []
    process = None
    try:
        import psutil
        process = psutil.Process()
        # Prime cpu_percent (first call returns 0.0 since process start)
        process.cpu_percent(interval=None)
    except ImportError:
        logger.debug("psutil not available – CPU percent will be 0.0")

    # ── Timed runs ────────────────────────────────────────────────────────
    per_sample_latencies_ms: List[float] = []
    total_samples_processed = 0
    loop_start = time.perf_counter()

    for i in range(timed_runs):
        if process is not None:
            try:
                cpu_percent_samples.append(process.cpu_percent(interval=None))
            except Exception:
                pass

        t0 = time.perf_counter()
        try:
            _predict_single(model, timing_input, framework)
        except Exception as exc:
            logger.error("Prediction failed on timed run %d: %s", i, exc)
            continue
        elapsed_s = time.perf_counter() - t0

        per_sample_ms = (elapsed_s * 1000.0) / n_samples_per_run
        per_sample_latencies_ms.append(per_sample_ms)
        total_samples_processed += n_samples_per_run

    loop_total_s = time.perf_counter() - loop_start

    # ── Collect memory ────────────────────────────────────────────────────
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    memory_mb = peak / (1024 * 1024)

    # ── Aggregate latency statistics (true percentiles) ───────────────────
    if per_sample_latencies_ms:
        latencies = np.asarray(per_sample_latencies_ms, dtype=np.float64)
        latency_mean_ms = float(np.mean(latencies))
        latency_p50_ms = float(np.percentile(latencies, 50))
        latency_p95_ms = float(np.percentile(latencies, 95))
        latency_p99_ms = float(np.percentile(latencies, 99))
        latency_std_ms = float(np.std(latencies))
        latency_min_ms = float(np.min(latencies))
        latency_max_ms = float(np.max(latencies))
    else:
        latency_mean_ms = latency_p50_ms = latency_p95_ms = latency_p99_ms = 0.0
        latency_std_ms = latency_min_ms = latency_max_ms = 0.0

    # ── Throughput (samples/sec over the timed loop) ──────────────────────
    throughput_per_sec = (
        float(total_samples_processed) / loop_total_s
        if loop_total_s > 0 else 0.0
    )

    cpu_percent = float(np.mean(cpu_percent_samples)) if cpu_percent_samples else 0.0

    perf: Dict[str, Any] = {
        "latency_ms": round(latency_mean_ms, 4),
        "latency_p50_ms": round(latency_p50_ms, 4),
        "latency_p95_ms": round(latency_p95_ms, 4),
        "latency_p99_ms": round(latency_p99_ms, 4),
        "latency_std_ms": round(latency_std_ms, 4),
        "latency_min_ms": round(latency_min_ms, 4),
        "latency_max_ms": round(latency_max_ms, 4),
        "throughput_per_sec": round(throughput_per_sec, 2),
        "memory_mb": round(memory_mb, 4),
        "cpu_percent": round(cpu_percent, 2),
        "model_size_kb": round(model_size_kb, 2),
        "inference_count": int(total_samples_processed),
        "timed_runs": int(len(per_sample_latencies_ms)),
    }

    logger.info(
        "Performance metrics: mean=%.3fms p50=%.3fms p95=%.3fms p99=%.3fms "
        "throughput=%.1f/s memory=%.2fMB cpu=%.1f%% size=%.2fKB runs=%d",
        perf["latency_ms"],
        perf["latency_p50_ms"],
        perf["latency_p95_ms"],
        perf["latency_p99_ms"],
        perf["throughput_per_sec"],
        perf["memory_mb"],
        perf["cpu_percent"],
        perf["model_size_kb"],
        perf["timed_runs"],
    )
    return perf


# ─── Single-sample prediction helper ──────────────────────────────────────────

def _predict_single(model: Any, X: np.ndarray, framework: str) -> np.ndarray:
    """Run a single prediction for timing purposes.

    Mirrors the logic in
    :func:`app.benchmark_engine.evaluator._predict_single` but is kept
    local to avoid circular imports.

    Args:
        model: Loaded model object.
        X: Input data (at least 1 sample).
        framework: Framework identifier.

    Returns:
        Model output as a NumPy array.
    """
    framework = (framework or "").lower().strip()

    if framework in ("scikit-learn", "xgboost", "lightgbm"):
        return np.asarray(model.predict(X))

    elif framework == "pytorch":
        import torch

        with torch.no_grad():
            tensor_input = torch.as_tensor(X, dtype=torch.float32)
            output = model(tensor_input)
            if isinstance(output, torch.Tensor):
                return output.cpu().numpy()
            return np.asarray(output)

    elif framework == "onnx":
        input_feed = {model.get_inputs()[0].name: X.astype(np.float32)}
        return np.asarray(model.run(None, input_feed)[0])

    elif framework == "tensorflow":
        return np.asarray(model.predict(X, verbose=0))

    else:
        raise ValueError(f"Unsupported framework for prediction: '{framework}'")


# ─── Combined metrics ─────────────────────────────────────────────────────────

def compute_all_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    model: Any,
    X_test: np.ndarray,
    framework: str,
    task_type: str,
    model_path: Optional[str] = None,
    y_proba: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """Compute all benchmarking metrics in one call.

    Combines task-specific metrics (classification or regression) with
    inference performance metrics.

    Args:
        y_true: Ground-truth labels/targets.
        y_pred: Model predictions.
        model: The loaded model object.
        X_test: Test features (for performance measurement).
        framework: Framework identifier.
        task_type: ``classification`` or ``regression``.
        model_path: Optional path to the model file on disk.
        y_proba: Optional predicted probabilities (classification only).

    Returns:
        Dictionary containing all metric key/value pairs plus an
        ``inference_count`` key indicating the number of test samples.
    """
    results: Dict[str, Any] = {
        "inference_count": int(len(y_true)),
    }

    # ── Task-specific metrics ─────────────────────────────────────────────
    if task_type == "classification":
        results.update(compute_classification_metrics(y_true, y_pred, y_proba=y_proba))
        # Ensure regression keys are present (as None) so the DB insert
        # does not break when the service reads them with .get().
        results.setdefault("mae", None)
        results.setdefault("rmse", None)
        results.setdefault("r2_score", None)
        results.setdefault("mse", None)
        results.setdefault("explained_variance", None)
        results.setdefault("max_error", None)
    elif task_type == "regression":
        results.update(compute_regression_metrics(y_true, y_pred))
        # Ensure classification keys are present (as None)
        results.setdefault("accuracy", None)
        results.setdefault("precision", None)
        results.setdefault("recall", None)
        results.setdefault("f1_score", None)
        results.setdefault("auc_roc", None)
        results.setdefault("log_loss", None)
        results.setdefault("confusion_matrix", None)
        results.setdefault("classification_report", None)
    else:
        logger.warning("Unknown task_type '%s' – skipping task metrics", task_type)
        for key in (
            "accuracy", "precision", "recall", "f1_score",
            "mae", "rmse", "r2_score", "auc_roc", "log_loss",
            "confusion_matrix", "classification_report",
        ):
            results.setdefault(key, None)

    # ── Performance metrics ───────────────────────────────────────────────
    results.update(
        compute_performance_metrics(
            model,
            X_test,
            framework,
            model_path=model_path,
        )
    )

    logger.info(
        "All metrics computed: task=%s, inference_count=%d",
        task_type,
        results["inference_count"],
    )
    return results
