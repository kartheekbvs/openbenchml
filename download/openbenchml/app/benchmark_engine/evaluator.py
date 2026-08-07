"""
OpenBenchML Evaluation Orchestrator
=====================================
Top-level evaluation pipeline that glues together model loading, dataset
preparation, prediction, and metric computation.

The main entry point is :func:`evaluate_model`, which is called by
``app.services.benchmark_service`` after a job has been created and
transitioned to the ``running`` state.

Two calling conventions are supported:

1. **Service style** (pre-loaded objects)::

       evaluate_model(
           model_artifact=model,
           dataset=data_dict,
           task_type="classification",
           timeout_seconds=300,
       )

2. **Standalone style** (paths only)::

       evaluate_model(
           model_path="/models/rf.joblib",
           framework="scikit-learn",
           dataset_name="iris",
       )
"""

import logging
import signal
import time
from typing import Any, Dict, Optional, Tuple

import numpy as np

from app.benchmark_engine.loader import load_model, load_dataset
from app.benchmark_engine.metrics import compute_all_metrics

logger = logging.getLogger(__name__)


# ─── Timeout handling ─────────────────────────────────────────────────────────

class _TimeoutError(Exception):
    """Raised when the evaluation exceeds the allowed time limit."""


def _timeout_handler(signum: int, frame: Any) -> None:
    raise _TimeoutError("Benchmark evaluation timed out")


# ─── Main evaluation function ─────────────────────────────────────────────────

def evaluate_model(
    model_path: Optional[str] = None,
    framework: Optional[str] = None,
    dataset_name: Optional[str] = None,
    model_artifact: Optional[Any] = None,
    dataset: Optional[Dict[str, Any]] = None,
    task_type: Optional[str] = None,
    timeout_seconds: int = 300,
) -> Dict[str, Any]:
    """Run the full evaluation pipeline and return a metrics dictionary.

    Steps:

    1. Load the model (if not already provided).
    2. Load the dataset (if not already provided).
    3. Run predictions on the test split.
    4. Optionally extract predicted probabilities for AUC-ROC / log-loss.
    5. Compute all metrics (task + performance).
    6. Return a results dictionary.

    Args:
        model_path: Path to the serialized model file.
        framework: Framework identifier (e.g. ``"scikit-learn"``).
        dataset_name: Name of a built-in dataset or path to a custom
            dataset file.
        model_artifact: Pre-loaded model object.
        dataset: Pre-loaded dataset dictionary.
        task_type: Override for the task type (``classification`` or
            ``regression``).
        timeout_seconds: Maximum wall-clock time for the evaluation.

    Returns:
        A dictionary containing all computed metric key/value pairs.
    """
    # ── Resolve model ─────────────────────────────────────────────────────
    if model_artifact is not None:
        model = model_artifact
        if framework is None:
            framework = _infer_framework(model)
        logger.info("Using pre-loaded model (framework=%s)", framework)
    elif model_path is not None and framework is not None:
        logger.info("Loading model from '%s' (framework=%s)", model_path, framework)
        model = load_model(model_path, framework)
    else:
        raise ValueError(
            "Either model_artifact or both model_path and framework must be provided"
        )

    # ── Resolve dataset ───────────────────────────────────────────────────
    if dataset is not None:
        data = dataset
        logger.info("Using pre-loaded dataset with %d test samples", len(data.get("y_test", [])))
    elif dataset_name is not None:
        logger.info("Loading dataset: '%s'", dataset_name)
        data = load_dataset(dataset_name, task_type=task_type)
    else:
        raise ValueError(
            "Either dataset or dataset_name must be provided"
        )

    # ── Determine task type ───────────────────────────────────────────────
    effective_task = (task_type or data.get("task_type") or "classification").lower()
    logger.info("Evaluation task type: %s", effective_task)

    # ── Extract test data ─────────────────────────────────────────────────
    X_test: np.ndarray = np.asarray(data["X_test"])
    y_test: np.ndarray = np.asarray(data["y_test"])

    if X_test.shape[0] == 0:
        raise ValueError("Test set is empty – cannot evaluate model")

    # ── Set timeout alarm (Unix only) ─────────────────────────────────────
    old_handler = None
    try:
        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(timeout_seconds)
    except (AttributeError, ValueError):
        logger.debug("SIGALRM not available – timeout enforcement disabled")

    try:
        # ── Run predictions ───────────────────────────────────────────────
        logger.info(
            "Running predictions on %d samples (framework=%s)",
            X_test.shape[0],
            framework,
        )
        t0 = time.perf_counter()
        y_pred, y_proba = _run_predictions_with_proba(
            model, X_test, framework, effective_task
        )
        pred_time = time.perf_counter() - t0
        logger.info("Predictions completed in %.2f s", pred_time)

        # ── Compute all metrics ───────────────────────────────────────────
        results = compute_all_metrics(
            y_true=y_test,
            y_pred=y_pred,
            model=model,
            X_test=X_test,
            framework=framework,
            task_type=effective_task,
            model_path=model_path,
            y_proba=y_proba,
        )

        results["_y_pred_shape"] = y_pred.shape
        results["_has_proba"] = y_proba is not None
        logger.info(
            "Evaluation complete: %d metrics computed, %d inferences",
            len(results),
            results.get("inference_count", 0),
        )
        return results

    finally:
        # ── Cancel alarm ──────────────────────────────────────────────────
        try:
            signal.alarm(0)
            if old_handler is not None:
                signal.signal(signal.SIGALRM, old_handler)
        except (AttributeError, ValueError):
            pass


# ─── Prediction dispatch ──────────────────────────────────────────────────────

def _run_predictions_with_proba(
    model: Any,
    X_test: np.ndarray,
    framework: str,
    task_type: str,
) -> Tuple[np.ndarray, Optional[np.ndarray]]:
    """Run predictions and, where supported, extract predicted probabilities.

    Returns a tuple ``(y_pred, y_proba)`` where *y_proba* is ``None``
    when the framework/model does not expose probabilities.
    """
    framework = (framework or "").lower().strip()

    try:
        if framework in ("scikit-learn", "xgboost", "lightgbm"):
            y_pred = np.asarray(model.predict(X_test)).ravel()
            y_proba = None
            if task_type == "classification" and hasattr(model, "predict_proba"):
                try:
                    proba = model.predict_proba(X_test)
                    if proba is not None and proba.size > 0:
                        y_proba = np.asarray(proba)
                except Exception as exc:
                    logger.debug("predict_proba failed: %s", exc)
            return y_pred, y_proba

        elif framework == "pytorch":
            y_pred = _predict_pytorch(model, X_test, task_type)
            return y_pred, None  # logits → softmax would be needed; leave None for now

        elif framework == "onnx":
            y_pred = _predict_onnx(model, X_test)
            # If the ONNX model returns probabilities (row-sums ≈ 1) and
            # there are ≥2 columns, treat them as probabilities.
            if (
                task_type == "classification"
                and y_pred.ndim == 2
                and y_pred.shape[1] > 1
                and np.allclose(y_pred.sum(axis=1), 1.0, atol=1e-3)
            ):
                return np.argmax(y_pred, axis=1), y_pred
            return y_pred.ravel(), None

        elif framework == "tensorflow":
            y_pred_raw = model.predict(X_test, verbose=0)
            return _postprocess_tensorflow(y_pred_raw, task_type)

        else:
            raise ValueError(f"Unsupported framework: '{framework}'")

    except Exception as exc:
        if isinstance(exc, (ValueError, _TimeoutError)):
            raise
        raise RuntimeError(
            f"Prediction failed (framework={framework}): {exc}"
        ) from exc


# ─── Framework-specific prediction helpers ─────────────────────────────────────

def _predict_pytorch(model: Any, X_test: np.ndarray, task_type: str) -> np.ndarray:
    """Run a PyTorch model forward pass and return predictions."""
    import torch

    model.eval()
    tensor_input = torch.as_tensor(X_test, dtype=torch.float32)

    with torch.no_grad():
        output = model(tensor_input)

    if isinstance(output, torch.Tensor):
        output_np = output.cpu().numpy()
    elif isinstance(output, (tuple, list)):
        output_np = np.asarray(output[0].cpu().numpy()
                                if hasattr(output[0], "cpu")
                                else output[0])
    else:
        output_np = np.asarray(output)

    if task_type == "classification" and output_np.ndim == 2 and output_np.shape[1] > 1:
        output_np = np.argmax(output_np, axis=1)

    return output_np.ravel()


def _predict_onnx(model: Any, X_test: np.ndarray) -> np.ndarray:
    """Run an ONNX InferenceSession and return raw output."""
    input_meta = model.get_inputs()
    if not input_meta:
        raise RuntimeError("ONNX model has no inputs")

    input_name = input_meta[0].name
    feed = {input_name: X_test.astype(np.float32)}

    outputs = model.run(None, feed)
    if not outputs:
        raise RuntimeError("ONNX model produced no outputs")

    return np.asarray(outputs[0])


def _postprocess_tensorflow(y_pred: np.ndarray, task_type: str) -> Tuple[np.ndarray, Optional[np.ndarray]]:
    """Post-process TensorFlow model output into (y_pred, y_proba)."""
    y_pred = np.asarray(y_pred)

    if task_type == "classification":
        if y_pred.ndim == 2 and y_pred.shape[1] > 1:
            # Check if values look like probabilities
            row_sums = y_pred.sum(axis=1)
            if np.allclose(row_sums, 1.0, atol=1e-3):
                return np.argmax(y_pred, axis=1), y_pred
            # Otherwise treat as logits → softmax to get probabilities
            try:
                e = np.exp(y_pred - y_pred.max(axis=1, keepdims=True))
                proba = e / e.sum(axis=1, keepdims=True)
                return np.argmax(proba, axis=1), proba
            except Exception:
                return np.argmax(y_pred, axis=1), None
        elif y_pred.ndim == 2 and y_pred.shape[1] == 1:
            # Binary classification with single sigmoid output
            binary = (y_pred.ravel() > 0.5).astype(int)
            proba = np.column_stack([1 - y_pred.ravel(), y_pred.ravel()])
            return binary, proba
        else:
            return y_pred.ravel(), None
    else:
        # Regression
        if y_pred.ndim == 2 and y_pred.shape[1] == 1:
            y_pred = y_pred.ravel()
        return y_pred.ravel(), None


# ─── Single-sample prediction ─────────────────────────────────────────────────

def _predict_single(model: Any, X: np.ndarray, framework: str) -> np.ndarray:
    """Run a single-sample prediction (used for latency measurement)."""
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


# ─── Framework inference helper ────────────────────────────────────────────────

def _infer_framework(model: Any) -> str:
    """Best-effort inference of a model's framework from its type."""
    type_name = type(model).__module__ + "." + type(model).__qualname__

    if "sklearn" in type_name:
        return "scikit-learn"
    elif "torch" in type_name:
        return "pytorch"
    elif "onnxruntime" in type_name:
        return "onnx"
    elif "xgboost" in type_name:
        return "xgboost"
    elif "lightgbm" in type_name:
        return "lightgbm"
    elif "tensorflow" in type_name or "keras" in type_name:
        return "tensorflow"

    logger.warning("Could not infer framework for model type: %s", type_name)
    return "unknown"
