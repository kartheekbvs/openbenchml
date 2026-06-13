"""
OpenBenchML Model & Dataset Loader
====================================
Responsible for loading ML models from disk (multi-framework) and
preparing benchmark datasets (built-in sklearn or custom files).

The public API consumed by ``benchmark_service`` is:

* :func:`load_model`  – deserialise a saved model artifact.
* :func:`load_dataset` – prepare a train/test split with metadata.
"""

import logging
import os
from typing import Any, Dict, Optional, Tuple

import joblib
import numpy as np
from sklearn.datasets import load_iris, load_wine, load_breast_cancer, load_digits
from sklearn.model_selection import train_test_split

logger = logging.getLogger(__name__)

_FRAMEWORK_EXTENSIONS = {
    ".pkl": "scikit-learn",
    ".joblib": "scikit-learn",
    ".pt": "pytorch",
    ".pth": "pytorch",
    ".onnx": "onnx",
    ".h5": "tensorflow",
    ".pb": "tensorflow",
    ".bin": "xgboost",
    ".json": "xgboost",
    ".model": "lightgbm",
}

# ─── Built-in dataset registry ────────────────────────────────────────────────
_BUILTIN_DATASETS = {
    "iris": {"loader": load_iris, "task_type": "classification"},
    "wine": {"loader": load_wine, "task_type": "classification"},
    "breast_cancer": {"loader": load_breast_cancer, "task_type": "classification"},
    "digits": {"loader": load_digits, "task_type": "classification"},
}


# ─── Model loading ─────────────────────────────────────────────────────────────

def load_model(file_path: str, framework: str) -> Any:
    """Load a saved ML model from disk based on its framework.

    Supported frameworks and their loading strategies:

    * **auto** – infer the framework from the file extension and load the
      model with the appropriate backend.
    * **scikit-learn** – :func:`joblib.load`
    * **pytorch** – :func:`torch.load` with ``map_location='cpu'``
    * **onnx** – :class:`onnxruntime.InferenceSession`
    * **xgboost** – :class:`xgboost.Booster` or :func:`joblib.load`
    * **lightgbm** – :class:`lightgbm.Booster` or :func:`joblib.load`
    * **tensorflow** – :func:`tf.keras.models.load_model`

    Args:
        file_path: Absolute or relative path to the serialized model file.
        framework: One of the supported framework identifiers
            (``auto``, ``scikit-learn``, ``pytorch``, ``onnx``, ``xgboost``,
            ``lightgbm``, ``tensorflow``).

    Returns:
        The loaded model object (type varies by framework).

    Raises:
        FileNotFoundError: If *file_path* does not exist on disk.
        ValueError: If *framework* is not recognised.
        RuntimeError: If the model cannot be deserialised.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Model file not found: {file_path}")

    framework = framework.lower().strip()
    if framework in ("auto", "detect"):
        guessed = _guess_framework_from_path(file_path)
        if guessed is None:
            raise ValueError(
                f"Could not detect framework from file extension for '{file_path}'. "
                f"Please select one of: scikit-learn, pytorch, onnx, xgboost, lightgbm, tensorflow"
            )
        logger.info(
            "Auto-detected framework '%s' from file extension '%s'",
            guessed,
            os.path.splitext(file_path)[1].lower(),
        )
        framework = guessed

    logger.info("Loading model from '%s' (framework=%s)", file_path, framework)

    try:
        if framework == "scikit-learn":
            return _load_sklearn_model(file_path)

        elif framework == "pytorch":
            return _load_pytorch_model(file_path)

        elif framework == "onnx":
            return _load_onnx_model(file_path)

        elif framework == "xgboost":
            return _load_xgboost_model(file_path)

        elif framework == "lightgbm":
            return _load_lightgbm_model(file_path)

        elif framework == "tensorflow":
            return _load_tensorflow_model(file_path)

        else:
            raise ValueError(
                f"Unsupported framework: '{framework}'. "
                f"Supported: scikit-learn, pytorch, onnx, xgboost, lightgbm, tensorflow"
            )
    except (FileNotFoundError, ValueError):
        raise
    except Exception as exc:
        fallback = _guess_framework_from_path(file_path)
        if fallback is not None and fallback != framework:
            logger.warning(
                "Initial load failed for framework '%s'; attempting fallback to detected framework '%s'",
                framework,
                fallback,
            )
            try:
                return load_model(file_path, fallback)
            except Exception as fallback_exc:
                raise RuntimeError(
                    f"Failed to load model from '{file_path}' using both "
                    f"framework='{framework}' and fallback='{fallback}': {fallback_exc}"
                ) from fallback_exc

        raise RuntimeError(
            f"Failed to load model from '{file_path}' (framework={framework}): {exc}"
        ) from exc


def _guess_framework_from_path(file_path: str) -> Optional[str]:
    """Infer the most likely framework from a model file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    return _FRAMEWORK_EXTENSIONS.get(ext)


# ─── Framework-specific private loaders ────────────────────────────────────────

def _load_sklearn_model(file_path: str) -> Any:
    """Deserialise a scikit-learn model via joblib."""
    model = joblib.load(file_path)
    logger.debug("Loaded scikit-learn model: %s", type(model).__name__)
    return model


def _load_pytorch_model(file_path: str) -> Any:
    """Deserialise a PyTorch model via ``torch.load``.

    The model is mapped to CPU to avoid GPU dependency during
    benchmarking.  The caller is responsible for setting the model
    to eval mode.
    """
    import torch

    model = torch.load(file_path, map_location="cpu", weights_only=False)

    # If the checkpoint is a dict (common pattern), try to extract the
    # state-dict or the model object.
    if isinstance(model, dict):
        if "model" in model:
            model = model["model"]
        elif "state_dict" in model:
            # Cannot reconstruct architecture from state_dict alone.
            logger.warning(
                "Checkpoint contains only state_dict – the model class "
                "definition must be available in the Python path."
            )

    # Best-effort: set to eval mode if it is an nn.Module
    if hasattr(model, "eval"):
        model.eval()

    logger.debug("Loaded PyTorch model: %s", type(model).__name__)
    return model


def _load_onnx_model(file_path: str) -> Any:
    """Load an ONNX model as an :class:`onnxruntime.InferenceSession`."""
    import onnxruntime as ort

    session = ort.InferenceSession(file_path)
    logger.debug(
        "Loaded ONNX session with %d input(s): %s",
        len(session.get_inputs()),
        [inp.name for inp in session.get_inputs()],
    )
    return session


def _load_xgboost_model(file_path: str) -> Any:
    """Load an XGBoost model.

    Tries :class:`xgboost.Booster` first (native format), falling back
    to :func:`joblib.load` for pickle/joblib-serialised models.
    """
    import xgboost as xgb

    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".json", ".ubj", ".bin"):
        booster = xgb.Booster()
        booster.load_model(file_path)
        logger.debug("Loaded XGBoost Booster from native format (%s)", ext)
        return booster
    else:
        try:
            model = joblib.load(file_path)
            logger.debug("Loaded XGBoost model via joblib: %s", type(model).__name__)
            return model
        except Exception:
            booster = xgb.Booster()
            booster.load_model(file_path)
            logger.debug("Loaded XGBoost Booster (joblib fallback failed, used native)")
            return booster


def _load_lightgbm_model(file_path: str) -> Any:
    """Load a LightGBM model.

    Tries :class:`lightgbm.Booster` first (native text format), falling
    back to :func:`joblib.load` for pickle/joblib-serialised models.
    """
    import lightgbm as lgb

    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".txt", ".model"):
        booster = lgb.Booster(model_file=file_path)
        logger.debug("Loaded LightGBM Booster from native format (%s)", ext)
        return booster
    else:
        try:
            model = joblib.load(file_path)
            logger.debug("Loaded LightGBM model via joblib: %s", type(model).__name__)
            return model
        except Exception:
            booster = lgb.Booster(model_file=file_path)
            logger.debug("Loaded LightGBM Booster (joblib fallback failed, used native)")
            return booster


def _load_tensorflow_model(file_path: str) -> Any:
    """Load a TensorFlow / Keras model via ``tf.keras.models.load_model``."""
    import tensorflow as tf

    model = tf.keras.models.load_model(file_path)
    logger.debug("Loaded TensorFlow/Keras model: %s", type(model).__name__)
    return model


# ─── Dataset loading ───────────────────────────────────────────────────────────

def load_dataset(
    dataset_name: str,
    task_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Load a benchmark dataset and return a train/test split with metadata.

    For built-in datasets the *dataset_name* should match a key in the
    sklearn registry (``iris``, ``wine``, ``breast_cancer``, ``digits``).
    For custom datasets *dataset_name* is treated as a file path and must
    point to a ``.npz`` or ``.joblib`` file containing ``X`` and ``y``
    arrays.

    Args:
        dataset_name: Name of a built-in dataset **or** path to a custom
            dataset file on disk.
        task_type: Hint for the task type (``classification`` or
            ``regression``).  When *None* the value is inferred from the
            built-in registry or defaults to ``classification``.

    Returns:
        A dictionary with the following keys:

        * ``X_train`` – training features  (np.ndarray)
        * ``X_test``  – test features       (np.ndarray)
        * ``y_train`` – training labels     (np.ndarray)
        * ``y_test``  – test labels         (np.ndarray)
        * ``task_type``       – str
        * ``feature_names``   – list[str] | None

    Raises:
        FileNotFoundError: If *dataset_name* looks like a file path but
            does not exist.
        ValueError: If the dataset cannot be loaded or is malformed.
    """
    logger.info("Loading dataset: '%s' (task_type=%s)", dataset_name, task_type)

    # ── Built-in sklearn datasets ─────────────────────────────────────────
    normalised = dataset_name.lower().strip()
    if normalised in _BUILTIN_DATASETS:
        return _load_sklearn_dataset(normalised)

    # ── Custom dataset from file ──────────────────────────────────────────
    if os.path.isfile(dataset_name):
        return _load_custom_dataset(dataset_name, task_type)

    # ── Last resort: maybe the user passed just a name that's close ───────
    if normalised.replace("-", "_").replace(" ", "_") in _BUILTIN_DATASETS:
        canonical = normalised.replace("-", "_").replace(" ", "_")
        return _load_sklearn_dataset(canonical)

    raise ValueError(
        f"Dataset '{dataset_name}' is not a built-in dataset and no file "
        f"was found at that path.  Built-in datasets: "
        f"{sorted(_BUILTIN_DATASETS.keys())}"
    )


def _load_sklearn_dataset(name: str) -> Dict[str, Any]:
    """Internal helper for loading a built-in sklearn dataset.

    Args:
        name: Key in :data:`_BUILTIN_DATASETS` (e.g. ``"iris"``).

    Returns:
        Dataset dictionary (see :func:`load_dataset`).
    """
    entry = _BUILTIN_DATASETS[name]
    loader_fn = entry["loader"]
    resolved_task = entry["task_type"]

    logger.debug("Loading sklearn dataset '%s'", name)
    bunch = loader_fn()

    X: np.ndarray = bunch.data
    y: np.ndarray = bunch.target
    feature_names: list = (
        list(bunch.feature_names)
        if hasattr(bunch, "feature_names") and bunch.feature_names is not None
        else [f"feature_{i}" for i in range(X.shape[1])]
    )

    return _split_data(X, y, resolved_task, feature_names=feature_names)


def _load_custom_dataset(
    file_path: str,
    task_type: Optional[str],
) -> Dict[str, Any]:
    """Load a custom dataset from a file on disk.

    Supported formats:

    * ``.npz``  – NumPy compressed archive with ``X`` and ``y`` keys.
    * ``.joblib`` / ``.pkl`` – Joblib/pickle file containing a dict
      with ``X`` and ``y`` keys, **or** a tuple ``(X, y)``.

    Args:
        file_path: Path to the dataset file.
        task_type: ``classification`` or ``regression``.  Defaults to
            ``classification`` when *None*.

    Returns:
        Dataset dictionary (see :func:`load_dataset`).
    """
    resolved_task = task_type or "classification"
    ext = os.path.splitext(file_path)[1].lower()

    X: Optional[np.ndarray] = None
    y: Optional[np.ndarray] = None

    if ext == ".npz":
        data = np.load(file_path, allow_pickle=True)
        if "X" not in data or "y" not in data:
            raise ValueError(
                f"NPZ file '{file_path}' must contain 'X' and 'y' arrays. "
                f"Found keys: {list(data.keys())}"
            )
        X = data["X"]
        y = data["y"]

    elif ext in (".joblib", ".pkl"):
        payload = joblib.load(file_path)
        if isinstance(payload, dict):
            if "X" not in payload or "y" not in payload:
                raise ValueError(
                    f"Dict in '{file_path}' must contain 'X' and 'y' keys. "
                    f"Found keys: {list(payload.keys())}"
                )
            X = payload["X"]
            y = payload["y"]
        elif isinstance(payload, (tuple, list)) and len(payload) == 2:
            X, y = payload
        else:
            raise ValueError(
                f"Unexpected payload type in '{file_path}': {type(payload).__name__}"
            )
    else:
        raise ValueError(
            f"Unsupported dataset file format: '{ext}'. "
            f"Supported: .npz, .joblib, .pkl"
        )

    X = np.asarray(X)
    y = np.asarray(y)

    n_features = X.shape[1] if X.ndim > 1 else 1
    feature_names = [f"feature_{i}" for i in range(n_features)]

    logger.info(
        "Loaded custom dataset from '%s': %d samples, %d features",
        file_path,
        X.shape[0],
        n_features,
    )
    return _split_data(X, y, resolved_task, feature_names=feature_names)


def _split_data(
    X: np.ndarray,
    y: np.ndarray,
    task_type: str,
    *,
    test_size: float = 0.2,
    random_state: int = 42,
    feature_names: Optional[list] = None,
) -> Dict[str, Any]:
    """Split data into train/test sets with appropriate stratification.

    Classification tasks are stratified on ``y`` to preserve class
    distributions.  Regression tasks use a plain random split.

    Args:
        X: Feature matrix of shape ``(n_samples, n_features)``.
        y: Target vector of shape ``(n_samples,)``.
        task_type: ``classification`` or ``regression``.
        test_size: Fraction of the data reserved for testing.
        random_state: Seed for reproducibility.
        feature_names: Optional list of feature names.

    Returns:
        Dictionary with keys ``X_train``, ``X_test``, ``y_train``,
        ``y_test``, ``task_type``, ``feature_names``.
    """
    stratify = y if task_type == "classification" else None

    # Stratification requires at least 2 samples per class in each split.
    # Fall back to non-stratified split when the data is too small or
    # a class has only one member.
    if stratify is not None:
        unique, counts = np.unique(y, return_counts=True)
        if len(unique) < 2 or counts.min() < 2:
            logger.warning(
                "Cannot stratify: %d unique classes, min count=%d. "
                "Falling back to non-stratified split.",
                len(unique),
                counts.min(),
            )
            stratify = None

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=random_state,
        stratify=stratify,
    )

    n_features = X.shape[1] if X.ndim > 1 else 1
    if feature_names is None:
        feature_names = [f"feature_{i}" for i in range(n_features)]

    logger.info(
        "Split data: train=%d, test=%d, features=%d, task=%s",
        X_train.shape[0],
        X_test.shape[0],
        n_features,
        task_type,
    )

    return {
        "X_train": X_train,
        "X_test": X_test,
        "y_train": y_train,
        "y_test": y_test,
        "task_type": task_type,
        "feature_names": feature_names,
    }
