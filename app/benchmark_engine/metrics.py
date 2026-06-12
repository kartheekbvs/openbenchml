"""
OpenBenchML Metrics Computation
=================================
All metric calculations for benchmarking ML models: classification,
regression, and inference performance (latency, memory, CPU, model size).

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
from typing import Any, Dict, Optional

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)

logger = logging.getLogger(__name__)


# ─── Classification metrics ────────────────────────────────────────────────────

def compute_classification_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> Dict[str, float]:
    """Compute standard classification metrics.

    All multi-class metrics use ``average='weighted'`` to handle
    imbalanced class distributions gracefully.

    Args:
        y_true: Ground-truth labels of shape ``(n_samples,)``.
        y_pred: Predicted labels of shape ``(n_samples,)``.

    Returns:
        Dictionary with keys: ``accuracy``, ``precision``, ``recall``,
        ``f1_score``.  All values are floats in the range ``[0, 1]``.
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

    metrics: Dict[str, float] = {
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

    logger.debug(
        "Classification metrics: accuracy=%.4f, precision=%.4f, "
        "recall=%.4f, f1=%.4f",
        metrics["accuracy"],
        metrics["precision"],
        metrics["recall"],
        metrics["f1_score"],
    )
    return metrics


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
        Dictionary with keys: ``mae``, ``rmse``, ``r2_score``.
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
        return {"mae": 0.0, "rmse": 0.0, "r2_score": 0.0}

    mse = mean_squared_error(y_true, y_pred)
    metrics: Dict[str, float] = {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mse)),
        "r2_score": float(r2_score(y_true, y_pred)),
    }

    logger.debug(
        "Regression metrics: mae=%.4f, rmse=%.4f, r2=%.4f",
        metrics["mae"],
        metrics["rmse"],
        metrics["r2_score"],
    )
    return metrics


# ─── Performance metrics ───────────────────────────────────────────────────────

def compute_performance_metrics(
    model: Any,
    X_test: np.ndarray,
    framework: str,
    model_path: Optional[str] = None,
) -> Dict[str, float]:
    """Measure inference performance: latency, memory, CPU, and model size.

    **Latency** is the average wall-clock time over ``n_runs`` forward
    passes.  A warm-up run is performed first and excluded from the
    average.  For very slow models the number of runs is reduced to 1.

    **Memory** is the peak memory delta measured with :mod:`tracemalloc`
    during the inference loop.  If ``psutil`` is available the process-
    level RSS delta is also captured as a fallback.

    **CPU percent** is sampled via :mod:`psutil` during the inference
    loop.  If psutil is unavailable the value is ``0.0``.

    **Model size** is the file size of the model on disk (in KB).  If
    *model_path* is not provided or the file does not exist, the value
    is ``0.0``.

    Args:
        model: The loaded model object.
        X_test: Test features used for the inference loop.
        framework: Framework identifier (affects prediction dispatch).
        model_path: Optional path to the model file on disk (for size).

    Returns:
        Dictionary with keys: ``latency_ms``, ``memory_mb``,
        ``cpu_percent``, ``model_size_kb``.
    """
    X_test = np.asarray(X_test)
    framework = framework.lower().strip()

    # ── Model file size ───────────────────────────────────────────────────
    model_size_kb = 0.0
    if model_path and os.path.isfile(model_path):
        model_size_kb = os.path.getsize(model_path) / 1024.0
    logger.debug("Model size: %.2f KB", model_size_kb)

    # ── Determine number of runs ──────────────────────────────────────────
    n_runs = 100
    n_samples = min(X_test.shape[0], 1)
    single_input = X_test[:n_samples]

    # Warm-up run to let the runtime JIT-compile / warm caches.
    try:
        _predict_single(model, single_input, framework)
    except Exception as exc:
        logger.warning("Warm-up prediction failed: %s", exc)

    # ── Start profiling ───────────────────────────────────────────────────
    tracemalloc.start()
    cpu_percent_samples: list[float] = []
    process = None
    try:
        import psutil
        process = psutil.Process()
    except ImportError:
        logger.debug("psutil not available – CPU percent will be 0.0")

    latencies: list[float] = []

    for i in range(n_runs):
        if process is not None:
            try:
                cpu_percent_samples.append(process.cpu_percent(interval=None))
            except Exception:
                pass

        t0 = time.perf_counter()
        try:
            _predict_single(model, single_input, framework)
        except Exception as exc:
            logger.error("Prediction failed on run %d: %s", i, exc)
            continue
        elapsed = time.perf_counter() - t0
        latencies.append(elapsed)

    # ── Collect memory ────────────────────────────────────────────────────
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    memory_mb = peak / (1024 * 1024)

    # ── Aggregate ─────────────────────────────────────────────────────────
    if latencies:
        avg_latency_s = sum(latencies) / len(latencies)
        latency_ms = avg_latency_s * 1000.0
    else:
        latency_ms = 0.0

    cpu_percent = float(np.mean(cpu_percent_samples)) if cpu_percent_samples else 0.0

    perf: Dict[str, float] = {
        "latency_ms": round(latency_ms, 4),
        "memory_mb": round(memory_mb, 4),
        "cpu_percent": round(cpu_percent, 2),
        "model_size_kb": round(model_size_kb, 2),
    }

    logger.info(
        "Performance metrics: latency=%.2f ms, memory=%.2f MB, "
        "cpu=%.1f%%, size=%.2f KB",
        perf["latency_ms"],
        perf["memory_mb"],
        perf["cpu_percent"],
        perf["model_size_kb"],
    )
    return perf


# ─── Single-sample prediction helper ──────────────────────────────────────────

def _predict_single(model: Any, X: np.ndarray, framework: str) -> np.ndarray:
    """Run a single prediction for timing purposes.

    This mirrors the logic in
    :func:`app.benchmark_engine.evaluator._predict_single` but is kept
    local to avoid circular imports.

    Args:
        model: Loaded model object.
        X: Input data (at least 1 sample).
        framework: Framework identifier.

    Returns:
        Model output as a NumPy array.
    """
    framework = framework.lower().strip()

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

    Returns:
        Dictionary containing all metric key/value pairs plus an
        ``inference_count`` key indicating the number of test samples.
    """
    results: Dict[str, Any] = {
        "inference_count": int(len(y_true)),
    }

    # ── Task-specific metrics ─────────────────────────────────────────────
    if task_type == "classification":
        results.update(compute_classification_metrics(y_true, y_pred))
        # Ensure regression keys are present (as None) so the DB insert
        # does not break when the service reads them with .get().
        results.setdefault("mae", None)
        results.setdefault("rmse", None)
        results.setdefault("r2_score", None)
    elif task_type == "regression":
        results.update(compute_regression_metrics(y_true, y_pred))
        # Ensure classification keys are present (as None)
        results.setdefault("accuracy", None)
        results.setdefault("precision", None)
        results.setdefault("recall", None)
        results.setdefault("f1_score", None)
    else:
        logger.warning("Unknown task_type '%s' – skipping task metrics", task_type)
        for key in (
            "accuracy", "precision", "recall", "f1_score",
            "mae", "rmse", "r2_score",
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
