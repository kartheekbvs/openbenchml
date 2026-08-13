"""
OpenBenchML Model & Dataset Loader
====================================
Responsible for loading ML models from disk (multi-framework) and
preparing benchmark datasets (real-world CSV files + sklearn's classic
real datasets — no synthetic random generators).

The public API consumed by ``benchmark_service`` is:

* :func:`load_model`  – deserialise a saved model artifact.
* :func:`load_dataset` – prepare a train/test split with metadata.
* :func:`list_builtin_datasets` – enumerate available built-in datasets.

The dataset catalogue is split into two families:

1. **Classic sklearn built-ins** — ``iris``, ``wine``, ``breastcancer``,
   ``digits``, ``diabetes``, ``californiahousing``, ``olivettifaces``,
   ``linnerud``.  These are *real* curated datasets shipped by scikit-learn
   (not synthetic generators).

2. **Real-world CSV datasets** — downloaded from GitHub raw / UCI ML
   repository by ``scripts/download_real_datasets.py`` and stored in
   ``datasets/<slug>.csv`` with a companion ``<slug>.meta.json`` sidecar
   describing the target column, drop columns, categorical encoding, etc.

This module is **the foundation of the core engine**. It must never
silently swallow a bad argument — every error path raises a clear,
actionable exception so the benchmark service can persist a useful
error message for the user.
"""

import csv
import json
import logging
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
from sklearn.datasets import (
    load_iris,
    load_wine,
    load_breast_cancer,
    load_digits,
    load_diabetes,
    load_linnerud,
    fetch_california_housing,
    fetch_olivetti_faces,
)
from sklearn.model_selection import train_test_split

logger = logging.getLogger(__name__)


# ─── Model cache (load-once, invalidate on file mtime change) ──────────────────
# Without this cache, every benchmark job called ``joblib.load()`` on the
# model file — ~80-150 ms per call for a typical 100 KB sklearn model,
# much more for large PyTorch/ONNX artifacts.  The cache keeps the
# deserialised object in memory keyed by ``(file_path, framework)`` and
# only re-loads if the file's mtime changes (so re-uploading a model
# still picks up the new version).
#
# Thread-safety: a single ``threading.RLock`` guards the dict.  The
# actual ``joblib.load()`` happens OUTSIDE the lock so two threads
# loading different models don't serialise.
_MODEL_CACHE: Dict[Tuple[str, str], Dict[str, Any]] = {}
_MODEL_CACHE_LOCK = threading.RLock()


def clear_model_cache(file_path: Optional[str] = None) -> int:
    """Drop cached model entries.

    Args:
        file_path: If given, drop only entries whose file_path matches.
            If ``None``, drop every cached entry.

    Returns:
        The number of entries evicted.
    """
    with _MODEL_CACHE_LOCK:
        if file_path is None:
            n = len(_MODEL_CACHE)
            _MODEL_CACHE.clear()
            return n
        keys_to_drop = [k for k in _MODEL_CACHE if k[0] == file_path]
        for k in keys_to_drop:
            _MODEL_CACHE.pop(k, None)
        return len(keys_to_drop)


def get_model_cache_info() -> List[Dict[str, Any]]:
    """Return a list of cached model entries (for debugging / health)."""
    with _MODEL_CACHE_LOCK:
        return [
            {
                "file_path": k[0],
                "framework": k[1],
                "mtime": v["mtime"],
                "size_kb": v.get("size_kb"),
                "loaded_at": v.get("loaded_at"),
            }
            for k, v in _MODEL_CACHE.items()
        ]


def _load_model_cached(file_path: str, framework: str) -> Any:
    """Internal: load a model from disk with caching.

    Cache key: ``(file_path, framework)``.  Invalidation: the file's
    mtime is checked on every call; if it changed, the cached entry is
    dropped and the model is re-loaded from disk.

    This is the function that should be called by ``benchmark_service``
    and any other code that needs to load a model for inference.
    """
    if not file_path or not os.path.isfile(file_path):
        raise FileNotFoundError(f"Model file not found: {file_path!r}")

    framework = (framework or "").lower().strip()
    key = (file_path, framework)

    try:
        current_mtime = os.path.getmtime(file_path)
        current_size = os.path.getsize(file_path)
    except OSError as exc:
        raise FileNotFoundError(
            f"Cannot stat model file '{file_path}': {exc}"
        ) from exc

    # ── Fast path: cache hit with unchanged mtime ────────────────────────
    with _MODEL_CACHE_LOCK:
        cached = _MODEL_CACHE.get(key)
        if cached is not None and cached["mtime"] == current_mtime:
            logger.debug(
                "Model cache HIT: %s (framework=%s, mtime=%d, size=%d B)",
                file_path, framework, current_mtime, current_size,
            )
            return cached["model"]

    # ── Slow path: cache miss or mtime changed — load from disk ──────────
    # Load OUTSIDE the lock so concurrent loads of different models
    # don't block each other.
    logger.info(
        "Model cache MISS: %s (framework=%s, mtime=%d, size=%d B) — loading from disk",
        file_path, framework, current_mtime, current_size,
    )
    model = _load_model_uncached(file_path, framework)

    with _MODEL_CACHE_LOCK:
        _MODEL_CACHE[key] = {
            "model": model,
            "mtime": current_mtime,
            "size_kb": round(current_size / 1024.0, 2),
            "loaded_at": time.time(),
        }
    return model


def _load_model_uncached(file_path: str, framework: str) -> Any:
    """Load a model from disk WITHOUT using the cache (internal)."""
    framework = (framework or "").lower().strip()
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
        raise RuntimeError(
            f"Failed to load model from '{file_path}' (framework={framework}): {exc}"
        ) from exc


# ─── Built-in dataset registry (sklearn classics only) ────────────────────────
# The "key" matches the lowercase dataset.name as stored in the DB.
#
# These are all REAL curated datasets from scikit-learn — no synthetic
# ``make_*`` generators.  Synthetic generators were removed in v4.3 because
# they produce "random numbers" that aren't comparable to real-world ML
# benchmarking.  If you need a synthetic stress-test, generate the CSV
# yourself and upload it as a custom dataset.
#
# Adding a new sklearn built-in is a one-line change here.  ``seed.py``
# mirrors this list so the database is consistent.
_BUILTIN_DATASETS: Dict[str, Dict[str, Any]] = {
    # ── Classic sklearn classification ────────────────────────────────────
    "iris":          {"loader": load_iris,           "task_type": "classification"},
    "wine":          {"loader": load_wine,           "task_type": "classification"},
    "breastcancer":  {"loader": load_breast_cancer,  "task_type": "classification"},
    "digits":        {"loader": load_digits,         "task_type": "classification"},

    # ── Classic sklearn regression ────────────────────────────────────────
    "diabetes":          {"loader": load_diabetes,           "task_type": "regression"},
    "californiahousing": {"loader": fetch_california_housing,
                          "task_type": "regression",
                          "max_samples": 2000},   # subsample for speed
    "linnerud":          {"loader": load_linnerud,
                          "task_type": "regression"},

    # ── Image classification ──────────────────────────────────────────────
    "olivettifaces": {"loader": fetch_olivetti_faces,
                       "task_type": "classification",
                       "max_samples": 200},
}


def list_builtin_datasets() -> List[Dict[str, Any]]:
    """Return a list of all built-in dataset descriptors.

    Each descriptor contains ``name``, ``task_type``, ``max_samples``
    (if applicable), and ``synthetic`` flag.  Used by the datasets
    route to render the public catalogue and by ``seed.py`` to
    populate the database on first run.
    """
    out: List[Dict[str, Any]] = []
    for key, entry in _BUILTIN_DATASETS.items():
        out.append({
            "name": key,
            "task_type": entry["task_type"],
            "max_samples": entry.get("max_samples"),
            "synthetic": False,  # all entries here are real datasets
        })
    return out


# ─── Model loading ─────────────────────────────────────────────────────────────

def load_model(file_path: str, framework: str) -> Any:
    """Load a saved ML model from disk based on its framework.

    **Caching**: the loaded model is cached in process memory keyed by
    ``(file_path, framework)``.  Subsequent calls with the same path
    return the cached object immediately (~0 ms) — the file is NOT
    re-read from disk.  The cache is invalidated automatically when
    the file's mtime changes (so re-uploading a model still picks up
    the new version).  Call :func:`clear_model_cache` to force-evict.

    Supported frameworks and their loading strategies:

    * **scikit-learn** – :func:`joblib.load`
    * **pytorch** – :func:`torch.load` with ``map_location='cpu'``
    * **onnx** – :class:`onnxruntime.InferenceSession`
    * **xgboost** – :class:`xgboost.Booster` or :func:`joblib.load`
    * **lightgbm** – :class:`lightgbm.Booster` or :func:`joblib.load`
    * **tensorflow** – :func:`tf.keras.models.load_model`

    Args:
        file_path: Absolute or relative path to the serialized model file.
        framework: One of the supported framework identifiers
            (``scikit-learn``, ``pytorch``, ``onnx``, ``xgboost``,
            ``lightgbm``, ``tensorflow``).

    Returns:
        The loaded model object (type varies by framework).  Repeated
        calls with the same ``file_path`` return the SAME object
        instance (no re-deserialisation).

    Raises:
        FileNotFoundError: If *file_path* does not exist on disk.
        ValueError: If *framework* is not recognised.
        RuntimeError: If the model cannot be deserialised.
    """
    return _load_model_cached(file_path, framework)


# ─── Framework-specific private loaders ────────────────────────────────────────

def _load_sklearn_model(file_path: str) -> Any:
    """Deserialise a scikit-learn model via joblib."""
    model = joblib.load(file_path)
    logger.debug("Loaded scikit-learn model: %s", type(model).__name__)
    return model


def _load_pytorch_model(file_path: str) -> Any:
    """Deserialise a PyTorch model via ``torch.load``."""
    import torch

    model = torch.load(file_path, map_location="cpu", weights_only=False)

    # If the checkpoint is a dict (common pattern), try to extract the
    # state-dict or the model object.
    if isinstance(model, dict):
        if "model" in model:
            model = model["model"]
        elif "state_dict" in model:
            logger.warning(
                "Checkpoint contains only state_dict – the model class "
                "definition must be available in the Python path."
            )

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
    """Load an XGBoost model. Tries native format first, then joblib."""
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
    """Load a LightGBM model. Tries native format first, then joblib."""
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
    """Load a TensorFlow / Keras model."""
    import tensorflow as tf

    model = tf.keras.models.load_model(file_path)
    logger.debug("Loaded TensorFlow/Keras model: %s", type(model).__name__)
    return model


# ─── Dataset loading ───────────────────────────────────────────────────────────

def load_dataset(
    dataset_name: Optional[str],
    task_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Load a benchmark dataset and return a train/test split with metadata.

    Resolution order:

    1. If *dataset_name* is the lowercased name of a built-in sklearn
       dataset (e.g. ``"iris"``, ``"californiahousing"``), the
       corresponding loader is invoked.
    2. Otherwise, if *dataset_name* is a path to an existing file, the
       file is loaded as a custom dataset:
         - ``.csv``  → real-world CSV with optional ``.meta.json`` sidecar
         - ``.npz``  → NumPy compressed archive with ``X`` and ``y`` keys
         - ``.joblib`` / ``.pkl`` → dict ``{X, y}`` or tuple ``(X, y)``
    3. Otherwise a :class:`ValueError` is raised with a clear message.

    Args:
        dataset_name: Name of a built-in dataset **or** path to a custom
            dataset file on disk.  ``None`` or empty string is treated
            as "no dataset specified" and raises ``ValueError``.
        task_type: Hint for the task type (``classification`` or
            ``regression``).  When *None* the value is inferred from
            the built-in registry, the CSV sidecar, or defaults to
            ``classification`` for custom datasets.

    Returns:
        A dictionary with the following keys:

        * ``X_train`` – training features  (np.ndarray)
        * ``X_test``  – test features       (np.ndarray)
        * ``y_train`` – training labels     (np.ndarray)
        * ``y_test``  – test labels         (np.ndarray)
        * ``task_type``       – str
        * ``feature_names``   – list[str] | None

    Raises:
        ValueError: If *dataset_name* is empty/None, or unrecognised.
        FileNotFoundError: If *dataset_name* looks like a file path but
            does not exist.
    """
    if not dataset_name or not str(dataset_name).strip():
        raise ValueError(
            "No dataset name or path provided. Built-in datasets: "
            f"{sorted(_BUILTIN_DATASETS.keys())}"
        )

    logger.info("Loading dataset: '%s' (task_type=%s)", dataset_name, task_type)

    # ── Built-in sklearn datasets ─────────────────────────────────────────
    normalised = str(dataset_name).lower().strip().replace("-", "_").replace(" ", "_")
    if normalised in _BUILTIN_DATASETS:
        return _load_sklearn_dataset(normalised)

    # ── Custom dataset from file (CSV / NPZ / JOBLIB) ─────────────────────
    if os.path.isfile(dataset_name):
        return _load_custom_dataset(dataset_name, task_type)

    raise ValueError(
        f"Dataset '{dataset_name}' is not a built-in dataset and no file "
        f"was found at that path.  Built-in datasets: "
        f"{sorted(_BUILTIN_DATASETS.keys())}"
    )


def _load_sklearn_dataset(name: str) -> Dict[str, Any]:
    """Internal helper for loading a built-in sklearn dataset.

    Handles Bunch-returning loaders (load_iris, etc.) and fetcher
    functions (fetch_california_housing, fetch_olivetti_faces).

    Args:
        name: Key in :data:`_BUILTIN_DATASETS` (e.g. ``"iris"``).

    Returns:
        Dataset dictionary (see :func:`load_dataset`).
    """
    entry = _BUILTIN_DATASETS[name]
    loader_fn = entry["loader"]
    resolved_task = entry["task_type"]
    max_samples = entry.get("max_samples")

    logger.debug("Loading built-in sklearn dataset '%s'", name)

    try:
        bunch = loader_fn()
    except TypeError:
        bunch = loader_fn

    X: np.ndarray = np.asarray(bunch.data)
    y: np.ndarray = np.asarray(bunch.target)
    feature_names: list = (
        list(bunch.feature_names)
        if hasattr(bunch, "feature_names") and bunch.feature_names is not None
        else [f"feature_{i}" for i in range(X.shape[1])]
    )

    # ── Optional subsampling for very large datasets ──────────────────────
    if max_samples is not None and X.shape[0] > max_samples:
        rng = np.random.default_rng(seed=42)
        idx = rng.choice(X.shape[0], size=max_samples, replace=False)
        X = X[idx]
        y = y[idx]
        logger.info(
            "Subsampled '%s' from %d → %d rows for benchmark speed",
            name, len(idx), max_samples,
        )

    return _split_data(X, y, resolved_task, feature_names=feature_names)


def _load_custom_dataset(
    file_path: str,
    task_type: Optional[str],
) -> Dict[str, Any]:
    """Load a custom dataset from a file on disk.

    Supported formats:

    * ``.csv``  – Real-world CSV.  An optional ``<file>.meta.json``
      sidecar can specify ``target_col``, ``drop_cols``,
      ``categorical_encode``, ``header``, ``delimiter``,
      ``column_names``, ``target_map``, ``na_values``.  When no
      sidecar is present the last column is used as the target.
    * ``.npz``  – NumPy compressed archive with ``X`` and ``y`` keys.
    * ``.joblib`` / ``.pkl`` – Joblib/pickle file containing a dict
      with ``X`` and ``y`` keys, **or** a tuple ``(X, y)``.

    Args:
        file_path: Path to the dataset file.
        task_type: ``classification`` or ``regression``.  Defaults to
            the sidecar's ``task_type`` (CSV) or ``classification``.

    Returns:
        Dataset dictionary (see :func:`load_dataset`).
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".csv":
        return _load_csv_dataset(file_path, task_type)

    if ext == ".txt":
        # Many UCI datasets are .txt but really CSV/TSV — try CSV.
        return _load_csv_dataset(file_path, task_type)

    if ext == ".npz":
        data = np.load(file_path, allow_pickle=True)
        if "X" not in data or "y" not in data:
            raise ValueError(
                f"NPZ file '{file_path}' must contain 'X' and 'y' arrays. "
                f"Found keys: {list(data.keys())}"
            )
        X = np.asarray(data["X"])
        y = np.asarray(data["y"])
        resolved_task = task_type or "classification"

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
        resolved_task = task_type or "classification"

    else:
        raise ValueError(
            f"Unsupported dataset file format: '{ext}'. "
            f"Supported: .csv, .txt, .npz, .joblib, .pkl"
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


# ─── CSV dataset loader (real-world datasets) ─────────────────────────────────

def _load_csv_dataset(file_path: str, task_type: Optional[str]) -> Dict[str, Any]:
    """Load a real-world CSV dataset using an optional JSON sidecar.

    The sidecar (``<file>.meta.json``) is written by
    ``scripts/download_real_datasets.py`` and contains:

    * ``target_col``   – column name or index (string or int-as-string)
    * ``drop_cols``    – list of columns to drop before feature matrix
    * ``categorical_encode`` – if True, one-hot encode object columns
    * ``header``       – whether the CSV has a header row (default True)
    * ``delimiter``    – CSV delimiter (default ``,``; ``None`` = whitespace)
    * ``column_names`` – list of column names to apply if no header
    * ``target_map``   – dict mapping string labels to ints (e.g. {"M":1,"R":0})
    * ``na_values``    – list of strings to treat as NaN
    * ``task_type``    – ``classification`` or ``regression``
    * ``strip_bom``    – strip a leading BOM from the first header cell

    When no sidecar is found, the last column is used as the target,
    the task type defaults to ``classification`` (or the *task_type*
    argument), and no categorical encoding is applied.
    """
    sidecar_path = os.path.splitext(file_path)[0] + ".meta.json"
    meta: Dict[str, Any] = {}
    if os.path.isfile(sidecar_path):
        with open(sidecar_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        logger.debug("Loaded CSV sidecar: %s", sidecar_path)

    header = meta.get("header", True)
    delimiter = meta.get("delimiter", ",")
    column_names = meta.get("column_names")
    target_col = meta.get("target_col")
    drop_cols = meta.get("drop_cols", [])
    categorical_encode = meta.get("categorical_encode", False)
    target_map = meta.get("target_map")
    na_values = meta.get("na_values", [])
    strip_bom = meta.get("strip_bom", False)
    resolved_task = task_type or meta.get("task_type") or "classification"

    # ── Read the CSV ──────────────────────────────────────────────────────
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        if delimiter is None:
            # Whitespace-separated (e.g. UCI auto-mpg .data files).
            # Use regex to split on \s+ but keep quoted strings together.
            rows = []
            for line in f:
                # Strip newline but preserve content
                line = line.rstrip("\n").rstrip("\r")
                if not line.strip():
                    continue
                # Match: either a quoted string ("...") or a non-whitespace token
                tokens = re.findall(r'"[^"]*"|\S+', line)
                # Strip surrounding quotes from quoted tokens
                tokens = [t[1:-1] if t.startswith('"') and t.endswith('"') else t
                          for t in tokens]
                rows.append(tokens)
        else:
            reader = csv.reader(f, delimiter=delimiter)
            rows = list(reader)

    if not rows:
        raise ValueError(f"CSV file '{file_path}' is empty")

    # ── Resolve header ────────────────────────────────────────────────────
    if header:
        header_row = rows[0]
        if strip_bom and header_row:
            header_row[0] = header_row[0].lstrip("\ufeff").strip()
        data_rows = rows[1:]
        if column_names:
            # Override header with provided column_names
            cols = list(column_names)
        else:
            cols = [str(h).strip() for h in header_row]
    else:
        data_rows = rows
        if column_names:
            cols = list(column_names)
        else:
            n_cols = len(data_rows[0]) if data_rows else 0
            cols = [f"col_{i}" for i in range(n_cols)]

    if not data_rows:
        raise ValueError(f"CSV file '{file_path}' has header but no data rows")

    n_cols = len(cols)
    n_rows = len(data_rows)

    # ── Resolve target column ─────────────────────────────────────────────
    if target_col is None:
        target_idx = n_cols - 1
    elif isinstance(target_col, int):
        target_idx = target_col
    elif isinstance(target_col, str):
        # Try to match by column name (or by string index)
        if target_col in cols:
            target_idx = cols.index(target_col)
        elif target_col.isdigit():
            target_idx = int(target_col)
        else:
            raise ValueError(
                f"target_col '{target_col}' not found in CSV columns: {cols}"
            )
    else:
        raise ValueError(f"Invalid target_col type: {type(target_col).__name__}")

    # ── Resolve drop column indices ───────────────────────────────────────
    drop_indices = set()
    for dc in drop_cols:
        if isinstance(dc, int):
            drop_indices.add(dc)
        elif isinstance(dc, str):
            if dc in cols:
                drop_indices.add(cols.index(dc))
            elif dc.isdigit():
                drop_indices.add(int(dc))
            # silently ignore unknown drop cols

    if target_idx in drop_indices:
        raise ValueError(
            f"target_col index {target_idx} is in drop_cols — refusing to drop the target"
        )

    feature_indices = [i for i in range(n_cols) if i not in drop_indices and i != target_idx]
    feature_names = [cols[i] for i in feature_indices]

    # ── Build raw feature matrix and target vector ────────────────────────
    X_raw: List[List[Any]] = []
    y_raw: List[Any] = []
    skipped = 0
    for row in data_rows:
        if len(row) < n_cols:
            # Short row — pad with empty strings
            row = row + [""] * (n_cols - len(row))
        elif len(row) > n_cols:
            row = row[:n_cols]

        y_val = row[target_idx]
        # Apply na_values filter to target
        if y_val in na_values or y_val == "" or y_val is None:
            skipped += 1
            continue

        # Check for NaN in any feature
        has_nan = False
        feat_vals = []
        for i in feature_indices:
            v = row[i]
            if v in na_values or v == "":
                has_nan = True
                break
            feat_vals.append(v)
        if has_nan:
            skipped += 1
            continue

        X_raw.append(feat_vals)
        y_raw.append(y_val)

    if skipped:
        logger.info(
            "CSV loader skipped %d/%d rows with missing values in '%s'",
            skipped, n_rows, file_path,
        )

    if not X_raw:
        raise ValueError(
            f"After filtering missing values, no rows remained in '{file_path}'"
        )

    # ── Convert target: apply target_map if present, else try int, else label-encode ─
    y_arr = _convert_target(np.array(y_raw, dtype=object), target_map, resolved_task)

    # ── Convert features ──────────────────────────────────────────────────
    X_arr = _convert_features(
        np.array(X_raw, dtype=object),
        feature_names,
        categorical_encode,
    )

    logger.info(
        "Loaded CSV dataset '%s': %d samples, %d features, task=%s, "
        "categorical_encode=%s",
        os.path.basename(file_path),
        X_arr.shape[0],
        X_arr.shape[1],
        resolved_task,
        categorical_encode,
    )
    return _split_data(X_arr, y_arr, resolved_task, feature_names=feature_names)


def _convert_target(
    y_raw: np.ndarray,
    target_map: Optional[Dict[str, Any]],
    task_type: str,
) -> np.ndarray:
    """Convert raw string target column into a numeric array.

    Order of operations:
    1. If *target_map* is provided, map string labels to ints.
    2. Try to cast to float (works for numeric targets).
    3. If float cast fails and task is classification, label-encode the
       unique string values (alphabetical order → 0..k-1).
    """
    if target_map:
        # Apply explicit mapping
        mapped = []
        for v in y_raw:
            key = str(v).strip()
            if key in target_map:
                mapped.append(target_map[key])
            else:
                # Try int/float keys
                try:
                    if key in target_map:
                        mapped.append(target_map[key])
                    elif int(key) in target_map:
                        mapped.append(target_map[int(key)])
                    elif float(key) in target_map:
                        mapped.append(target_map[float(key)])
                    else:
                        raise ValueError(
                            f"Target value '{v}' not in target_map {list(target_map.keys())}"
                        )
                except (ValueError, TypeError):
                    raise ValueError(
                        f"Target value '{v}' not in target_map {list(target_map.keys())}"
                    )
        return np.asarray(mapped, dtype=np.int64)

    # No target_map — try numeric cast
    try:
        y = y_raw.astype(float)
        if task_type == "classification":
            # If all values are integer-valued, cast to int
            if np.allclose(y, np.round(y)):
                y = y.astype(np.int64)
        return y
    except (ValueError, TypeError):
        # Label-encode strings
        if task_type == "classification":
            unique_vals = sorted(set(str(v).strip() for v in y_raw))
            label_to_int = {v: i for i, v in enumerate(unique_vals)}
            logger.info(
                "Label-encoded target: %d unique classes -> %s",
                len(unique_vals),
                label_to_int,
            )
            return np.asarray([label_to_int[str(v).strip()] for v in y_raw], dtype=np.int64)
        else:
            raise ValueError(
                "Regression task but target column contains non-numeric values "
                f"and no target_map was provided.  Unique values: "
                f"{sorted(set(str(v) for v in y_raw))[:10]}"
            )


def _convert_features(
    X_raw: np.ndarray,
    feature_names: List[str],
    categorical_encode: bool,
) -> np.ndarray:
    """Convert raw string feature matrix into a numeric array.

    * Numeric columns are cast to float.
    * If *categorical_encode* is True, object/string columns are
      one-hot encoded (k-1 dummies via integer encoding for simplicity,
      to avoid dimension explosion on high-cardinality columns).
    * If *categorical_encode* is False, string columns that can't be
      cast to float are integer-encoded (label encoding per column).
    """
    n_rows, n_cols = X_raw.shape
    encoded_cols: List[np.ndarray] = []
    final_feature_names: List[str] = []

    for col_idx in range(n_cols):
        col = X_raw[:, col_idx]
        name = feature_names[col_idx]

        # Try numeric cast first
        try:
            numeric = col.astype(float)
            encoded_cols.append(numeric.reshape(-1, 1))
            final_feature_names.append(name)
            continue
        except (ValueError, TypeError):
            pass

        # String column — needs encoding
        if categorical_encode:
            # One-hot encode (low-cardinality only; high-cardinality gets integer-encoded)
            unique_vals = sorted(set(str(v).strip() for v in col))
            if len(unique_vals) <= 10:
                # One-hot
                for uv in unique_vals:
                    col_vec = np.array(
                        [1.0 if str(v).strip() == uv else 0.0 for v in col],
                        dtype=np.float32,
                    )
                    encoded_cols.append(col_vec.reshape(-1, 1))
                    final_feature_names.append(f"{name}={uv}")
            else:
                # Integer-encode (high-cardinality)
                val_to_int = {v: i for i, v in enumerate(unique_vals)}
                col_vec = np.array(
                    [val_to_int[str(v).strip()] for v in col], dtype=np.float32
                )
                encoded_cols.append(col_vec.reshape(-1, 1))
                final_feature_names.append(name)
        else:
            # Integer-encode (label encoding)
            unique_vals = sorted(set(str(v).strip() for v in col))
            val_to_int = {v: i for i, v in enumerate(unique_vals)}
            col_vec = np.array(
                [val_to_int[str(v).strip()] for v in col], dtype=np.float32
            )
            encoded_cols.append(col_vec.reshape(-1, 1))
            final_feature_names.append(name)

    # Mutate feature_names in place so the caller sees the post-encoding names
    feature_names.clear()
    feature_names.extend(final_feature_names)

    return np.hstack(encoded_cols).astype(np.float32)


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
    """
    stratify = y if task_type == "classification" else None

    # Stratification requires at least 2 samples per class in each split.
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
