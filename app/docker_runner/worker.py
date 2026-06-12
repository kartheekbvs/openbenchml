#!/usr/bin/env python3
"""
OpenBenchML Container Worker
==============================
This script runs **inside** the Docker container during a benchmark job.

It reads configuration from environment variables (injected by
:class:`DockerRunner`), loads the model and dataset, runs the
evaluation, and prints the result as a single JSON object to stdout.

Environment Variables
---------------------
``MODEL_PATH``
    Absolute path to the model file inside the container (mounted
    read-only from the host).
``FRAMEWORK``
    ML framework identifier (e.g. ``"scikit-learn"``).
``DATASET_NAME``
    Name of a built-in dataset (e.g. ``"iris"``) or the container path
    to a custom dataset file.
``TASK_TYPE``
    Optional task type override (``"classification"`` or
    ``"regression"``).

Exit Codes
----------
0
    Evaluation completed successfully; JSON result is on stdout.
1
    Evaluation failed; error details are printed to stderr.
"""

import json
import os
import sys
import traceback
from typing import Any, Dict, Optional


def main() -> None:
    """Entry point for the container worker.

    Orchestrates the following steps:

    1. Read and validate environment variables.
    2. Load the ML model using the benchmark engine loader.
    3. Load the dataset using the benchmark engine loader.
    4. Run the evaluation using the benchmark engine evaluator.
    5. Print the result as JSON to stdout.
    6. Exit with code 0 on success, 1 on failure.

    All exceptions are caught and reported to stderr as JSON so that
    the host-side :class:`DockerRunner` can diagnose failures from
    container logs.
    """
    # ── Step 1: Read environment variables ─────────────────────────────────
    model_path = os.environ.get("MODEL_PATH", "")
    framework = os.environ.get("FRAMEWORK", "")
    dataset_name = os.environ.get("DATASET_NAME", "")
    task_type = os.environ.get("TASK_TYPE") or None

    # Validate required variables.
    missing = []
    if not model_path:
        missing.append("MODEL_PATH")
    if not framework:
        missing.append("FRAMEWORK")
    if not dataset_name:
        missing.append("DATASET_NAME")

    if missing:
        _fail(f"Missing required environment variable(s): {', '.join(missing)}")

    # ── Step 2: Load the model ─────────────────────────────────────────────
    try:
        from app.benchmark_engine.loader import load_model
        model_artifact = load_model(model_path, framework)
    except ImportError:
        # Inside the container the app package may not be on sys.path.
        # Fall back to standalone imports for the minimal worker image.
        try:
            import joblib
            model_artifact = joblib.load(model_path)
        except Exception as exc:
            _fail(f"Failed to load model from '{model_path}': {exc}")
    except Exception as exc:
        _fail(f"Failed to load model from '{model_path}': {exc}")

    # ── Step 3: Load the dataset ───────────────────────────────────────────
    try:
        from app.benchmark_engine.loader import load_dataset
        dataset = load_dataset(dataset_name, task_type=task_type)
    except ImportError:
        # Fallback for the minimal container: attempt to load the dataset
        # with built-in sklearn loaders.
        try:
            dataset = _load_dataset_standalone(dataset_name, task_type)
        except Exception as exc:
            _fail(f"Failed to load dataset '{dataset_name}': {exc}")
    except Exception as exc:
        _fail(f"Failed to load dataset '{dataset_name}': {exc}")

    # ── Step 4: Run the evaluation ─────────────────────────────────────────
    try:
        from app.benchmark_engine.evaluator import evaluate_model
        results = evaluate_model(
            model_artifact=model_artifact,
            dataset=dataset,
            task_type=task_type or dataset.get("task_type"),
            timeout_seconds=int(os.environ.get("BENCHMARK_TIMEOUT", "300")),
        )
    except ImportError:
        # Fallback: run a minimal evaluation directly.
        try:
            results = _evaluate_standalone(
                model_artifact, dataset, task_type or dataset.get("task_type", "classification")
            )
        except Exception as exc:
            _fail(f"Evaluation failed: {exc}")
    except Exception as exc:
        _fail(f"Evaluation failed: {exc}")

    # ── Step 5: Print result as JSON to stdout ─────────────────────────────
    # Convert any non-serialisable values before printing.
    serialisable = _make_json_safe(results)
    try:
        output = json.dumps(serialisable, indent=2)
    except (TypeError, ValueError) as exc:
        _fail(f"Failed to serialise results to JSON: {exc}")

    sys.stdout.write(output + "\n")
    sys.stdout.flush()

    # ── Step 6: Exit successfully ──────────────────────────────────────────
    sys.exit(0)


# ─── Standalone dataset loader (minimal fallback) ──────────────────────────────

def _load_dataset_standalone(
    dataset_name: str,
    task_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Load a built-in sklearn dataset without importing from the app package.

    This is the fallback path for the minimal Docker worker image that
    only has scikit-learn, numpy, and pandas installed.

    Args:
        dataset_name: Name of a built-in dataset or path to a file.
        task_type: Optional task type (``classification`` or
            ``regression``).

    Returns:
        Dataset dictionary with ``X_train``, ``X_test``, ``y_train``,
        ``y_test``, ``task_type``, and ``feature_names`` keys.

    Raises:
        ValueError: If the dataset cannot be loaded.
    """
    from sklearn.datasets import load_iris, load_wine, load_breast_cancer, load_digits
    from sklearn.model_selection import train_test_split
    import numpy as np

    _builtin = {
        "iris": load_iris,
        "wine": load_wine,
        "breast_cancer": load_breast_cancer,
        "digits": load_digits,
    }

    normalised = dataset_name.lower().strip()

    if normalised in _builtin:
        loader_fn = _builtin[normalised]
        bunch = loader_fn()
        X = bunch.data
        y = bunch.target
        feature_names = (
            list(bunch.feature_names)
            if hasattr(bunch, "feature_names") and bunch.feature_names is not None
            else [f"feature_{i}" for i in range(X.shape[1])]
        )
        resolved_task = task_type or "classification"
    elif os.path.isfile(dataset_name):
        # Try to load custom dataset.
        ext = os.path.splitext(dataset_name)[1].lower()
        if ext == ".npz":
            data = np.load(dataset_name, allow_pickle=True)
            X, y = data["X"], data["y"]
        elif ext in (".joblib", ".pkl"):
            import joblib
            payload = joblib.load(dataset_name)
            if isinstance(payload, dict):
                X, y = payload["X"], payload["y"]
            elif isinstance(payload, (tuple, list)) and len(payload) == 2:
                X, y = payload
            else:
                raise ValueError(f"Unexpected payload type in '{dataset_name}'")
        else:
            raise ValueError(f"Unsupported dataset format: '{ext}'")

        X = np.asarray(X)
        y = np.asarray(y)
        feature_names = [f"feature_{i}" for i in range(X.shape[1] if X.ndim > 1 else 1)]
        resolved_task = task_type or "classification"
    else:
        raise ValueError(
            f"Dataset '{dataset_name}' is not a built-in dataset and no file "
            f"was found.  Built-in: {sorted(_builtin.keys())}"
        )

    # Stratification for classification.
    stratify = y if resolved_task == "classification" else None
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=stratify,
    )

    return {
        "X_train": X_train,
        "X_test": X_test,
        "y_train": y_train,
        "y_test": y_test,
        "task_type": resolved_task,
        "feature_names": feature_names,
    }


# ─── Standalone evaluator (minimal fallback) ───────────────────────────────────

def _evaluate_standalone(
    model: Any,
    dataset: Dict[str, Any],
    task_type: str,
) -> Dict[str, Any]:
    """Run a minimal evaluation without importing from the app package.

    Computes classification or regression metrics using scikit-learn
    directly, plus basic latency measurement.

    Args:
        model: A loaded model object with a ``predict`` method.
        dataset: Dataset dictionary with ``X_test`` and ``y_test``.
        task_type: ``classification`` or ``regression``.

    Returns:
        Dictionary of computed metrics.
    """
    import numpy as np
    import time
    from sklearn.metrics import (
        accuracy_score, precision_score, recall_score, f1_score,
        mean_absolute_error, mean_squared_error, r2_score,
    )

    X_test = np.asarray(dataset["X_test"])
    y_test = np.asarray(dataset["y_test"])

    # Run predictions.
    t0 = time.perf_counter()
    y_pred = model.predict(X_test)
    pred_time = time.perf_counter() - t0

    y_pred = np.asarray(y_pred).ravel()
    y_test = y_test.ravel()

    results: Dict[str, Any] = {
        "inference_count": int(len(y_test)),
        "latency_ms": round(pred_time * 1000.0, 4),
    }

    if task_type == "classification":
        results.update({
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "precision": float(precision_score(y_test, y_pred, average="weighted", zero_division=0)),
            "recall": float(recall_score(y_test, y_pred, average="weighted", zero_division=0)),
            "f1_score": float(f1_score(y_test, y_pred, average="weighted", zero_division=0)),
            "mae": None,
            "rmse": None,
            "r2_score": None,
        })
    elif task_type == "regression":
        mse = mean_squared_error(y_test, y_pred)
        results.update({
            "mae": float(mean_absolute_error(y_test, y_pred)),
            "rmse": float(np.sqrt(mse)),
            "r2_score": float(r2_score(y_test, y_pred)),
            "accuracy": None,
            "precision": None,
            "recall": None,
            "f1_score": None,
        })
    else:
        results.update({
            "accuracy": None,
            "precision": None,
            "recall": None,
            "f1_score": None,
            "mae": None,
            "rmse": None,
            "r2_score": None,
        })

    # Memory and CPU are not measured in standalone mode.
    results.update({
        "memory_mb": 0.0,
        "cpu_percent": 0.0,
    })

    return results


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _fail(message: str) -> None:
    """Print an error to stderr and exit with code 1.

    The error is formatted as JSON so that it can be parsed by the
    host-side runner if needed.

    Args:
        message: Human-readable error description.
    """
    error_payload = json.dumps({"error": message, "status": "failed"})
    sys.stderr.write(error_payload + "\n")
    sys.stderr.flush()
    sys.exit(1)


def _make_json_safe(obj: Any) -> Any:
    """Recursively convert an object to a JSON-serialisable form.

    NumPy types, Python ``float`` infinity/NaN, and other non-standard
    types are converted to native Python types that ``json.dumps`` can
    handle.

    Args:
        obj: Any Python object.

    Returns:
        A JSON-safe representation of *obj*.
    """
    import numpy as np

    if isinstance(obj, dict):
        return {str(k): _make_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_make_json_safe(item) for item in obj]
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        val = float(obj)
        if np.isnan(val) or np.isinf(val):
            return None
        return val
    elif isinstance(obj, np.ndarray):
        return _make_json_safe(obj.tolist())
    elif isinstance(obj, float):
        import math
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, (bool, int, str, type(None))):
        return obj
    else:
        # Fallback: convert to string.
        return str(obj)


# ─── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    main()
