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
from typing import Any, Dict, Optional

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

    This is the primary function invoked by ``benchmark_service.run_benchmark``.
    It orchestrates the following steps:

    1. Load the model (if not already provided).
    2. Load the dataset (if not already provided).
    3. Run predictions on the test split.
    4. Compute all metrics (task + performance).
    5. Return a results dictionary.

    Args:
        model_path: Path to the serialized model file.  Ignored when
            *model_artifact* is supplied.
        framework: Framework identifier (e.g. ``"scikit-learn"``).
            Ignored when *model_artifact* is supplied.
        dataset_name: Name of a built-in dataset or path to a custom
            dataset file.  Ignored when *dataset* is supplied.
        model_artifact: A pre-loaded model object (as returned by
            :func:`~app.benchmark_engine.loader.load_model`).  When
            provided, *model_path* and *framework* are not needed.
        dataset: A pre-loaded dataset dictionary (as returned by
            :func:`~app.benchmark_engine.loader.load_dataset`).  When
            provided, *dataset_name* is not needed.
        task_type: Override for the task type (``classification`` or
            ``regression``).  Required when *dataset* is supplied
            without a ``task_type`` key; otherwise the value from the
            dataset dict is used.
        timeout_seconds: Maximum wall-clock time for the evaluation.
            A :class:`TimeoutError` is raised if exceeded.  Only
            effective on Unix (uses ``SIGALRM``).

    Returns:
        A dictionary containing all computed metric key/value pairs:

        * **Classification** – accuracy, precision, recall, f1_score
        * **Regression** – mae, rmse, r2_score
        * **Performance** – latency_ms, memory_mb, cpu_percent,
          model_size_kb
        * **Meta** – inference_count

    Raises:
        ValueError: If required arguments are missing.
        _TimeoutError: If the evaluation exceeds *timeout_seconds*.
        RuntimeError: If prediction or metric computation fails.
    """
    # ── Resolve model ─────────────────────────────────────────────────────
    if model_artifact is not None:
        model = model_artifact
        # Derive framework from model_artifact metadata if available.
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
    effective_task = task_type or data.get("task_type", "classification")
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
        # Windows or main-thread-only restriction – skip alarm.
        logger.debug("SIGALRM not available – timeout enforcement disabled")

    try:
        # ── Run predictions ───────────────────────────────────────────────
        logger.info(
            "Running predictions on %d samples (framework=%s)",
            X_test.shape[0],
            framework,
        )
        t0 = time.perf_counter()
        y_pred = _run_predictions(model, X_test, framework, effective_task)
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
        )

        # Attach the raw predictions for optional downstream use.
        results["_y_pred_shape"] = y_pred.shape
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

def _run_predictions(
    model: Any,
    X_test: np.ndarray,
    framework: str,
    task_type: str,
) -> np.ndarray:
    """Run predictions on a batch of test data.

    Dispatches to the framework-appropriate prediction method:

    * **scikit-learn / xgboost / lightgbm** – ``model.predict(X)``
    * **pytorch** – forward pass under ``torch.no_grad()``; returns
      ``argmax`` for classification or raw output for regression.
    * **onnx** – ``session.run()`` with the first input feed.
    * **tensorflow** – ``model.predict(X)``

    Args:
        model: Loaded model object.
        X_test: Test features of shape ``(n_samples, n_features)``.
        framework: Framework identifier.
        task_type: ``classification`` or ``regression`` (used to decide
            whether to apply argmax for PyTorch outputs).

    Returns:
        Predictions as a 1-D NumPy array of shape ``(n_samples,)``.

    Raises:
        RuntimeError: If prediction fails for any reason.
    """
    framework = framework.lower().strip()

    try:
        if framework in ("scikit-learn", "xgboost", "lightgbm"):
            y_pred = model.predict(X_test)
            return np.asarray(y_pred).ravel()

        elif framework == "pytorch":
            return _predict_pytorch(model, X_test, task_type)

        elif framework == "onnx":
            return _predict_onnx(model, X_test)

        elif framework == "tensorflow":
            y_pred = model.predict(X_test, verbose=0)
            return _postprocess_tensorflow(y_pred, task_type)

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
    """Run a PyTorch model forward pass and return predictions.

    For classification tasks the output is argmax-ed along the class
    dimension.  For regression the raw output is returned.
    """
    import torch

    model.eval()
    tensor_input = torch.as_tensor(X_test, dtype=torch.float32)

    with torch.no_grad():
        output = model(tensor_input)

    if isinstance(output, torch.Tensor):
        output_np = output.cpu().numpy()
    elif isinstance(output, (tuple, list)):
        # Some models return (logits, aux) – take the first element.
        output_np = np.asarray(output[0].cpu().numpy()
                                if hasattr(output[0], "cpu")
                                else output[0])
    else:
        output_np = np.asarray(output)

    # Classification: take argmax over class dimension if output is 2-D.
    if task_type == "classification" and output_np.ndim == 2 and output_np.shape[1] > 1:
        output_np = np.argmax(output_np, axis=1)

    return output_np.ravel()


def _predict_onnx(model: Any, X_test: np.ndarray) -> np.ndarray:
    """Run an ONNX InferenceSession and return predictions."""
    input_meta = model.get_inputs()
    if not input_meta:
        raise RuntimeError("ONNX model has no inputs")

    input_name = input_meta[0].name
    # Cast to float32 – the most common ONNX input type.
    feed = {input_name: X_test.astype(np.float32)}

    outputs = model.run(None, feed)
    if not outputs:
        raise RuntimeError("ONNX model produced no outputs")

    y_pred = np.asarray(outputs[0])

    # Softmax output → argmax for classification
    if y_pred.ndim == 2 and y_pred.shape[1] > 1:
        # Check if values look like probabilities (row sums ≈ 1).
        row_sums = y_pred.sum(axis=1)
        if np.allclose(row_sums, 1.0, atol=1e-3):
            y_pred = np.argmax(y_pred, axis=1)

    return y_pred.ravel()


def _postprocess_tensorflow(y_pred: np.ndarray, task_type: str) -> np.ndarray:
    """Post-process TensorFlow model output into a 1-D array."""
    y_pred = np.asarray(y_pred)

    # Keras often returns shape (n, 1) for binary/regression.
    if task_type == "classification" and y_pred.ndim == 2 and y_pred.shape[1] > 1:
        y_pred = np.argmax(y_pred, axis=1)
    elif y_pred.ndim == 2 and y_pred.shape[1] == 1:
        y_pred = y_pred.ravel()

    return y_pred.ravel()


# ─── Single-sample prediction ─────────────────────────────────────────────────

def _predict_single(model: Any, X: np.ndarray, framework: str) -> np.ndarray:
    """Run a single-sample prediction (used for latency measurement).

    This is intentionally lightweight – no metrics, no post-processing
    beyond what is needed to get a valid forward pass.

    Args:
        model: Loaded model object.
        X: Input data (typically 1 sample).
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


# ─── Framework inference helper ────────────────────────────────────────────────

def _infer_framework(model: Any) -> str:
    """Best-effort inference of a model's framework from its type.

    Used when ``model_artifact`` is provided but ``framework`` is not.

    Args:
        model: A loaded model object.

    Returns:
        A framework string or ``"unknown"`` if the type is not recognised.
    """
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
