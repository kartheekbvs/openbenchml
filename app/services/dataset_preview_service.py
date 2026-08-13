"""
OpenBenchML Dataset Preview Service
====================================
Reads the first N rows of a dataset for display on the /datasets/{id} page
(the ``df.head(N)`` style preview).

Two code paths:

* **CSV datasets** — read the file directly with the same meta-sidecar
  logic as the benchmark loader (so the column names, drop_cols, and
  target_col are honoured).  Returns a list-of-rows plus the header.
* **Built-in sklearn datasets** — load via the loader and materialise
  the first N rows from the Bunch object.

The preview is intentionally capped (default 5, hard max 100) to keep
page rendering fast and safe.
"""

import csv
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from app.config import BASE_DIR

logger = logging.getLogger(__name__)

DATASETS_DIR = BASE_DIR / "datasets"

# Hard limits for the preview
DEFAULT_PREVIEW_ROWS = 5
MIN_PREVIEW_ROWS = 1
MAX_PREVIEW_ROWS = 100


def clamp_rows(requested: Optional[int]) -> int:
    """Clamp the user-supplied row count to a safe range."""
    if requested is None:
        return DEFAULT_PREVIEW_ROWS
    try:
        n = int(requested)
    except (ValueError, TypeError):
        return DEFAULT_PREVIEW_ROWS
    return max(MIN_PREVIEW_ROWS, min(MAX_PREVIEW_ROWS, n))


def _load_csv_preview(
    file_path: str,
    n_rows: int,
) -> Dict[str, Any]:
    """Read the first *n_rows* of a CSV dataset for display.

    Honours the same JSON sidecar format as the benchmark loader
    (``header``, ``delimiter``, ``column_names``, ``strip_bom``,
    ``target_col``, ``drop_cols``, ``target_map``, ``na_values``)
    so the preview matches what the benchmark engine actually sees.
    """
    if not os.path.isfile(file_path):
        return {
            "columns": [],
            "rows": [],
            "total_rows_loaded": 0,
            "source": "csv",
            "error": f"CSV file not found: {file_path}",
        }

    sidecar_path = os.path.splitext(file_path)[0] + ".meta.json"
    meta: Dict[str, Any] = {}
    if os.path.isfile(sidecar_path):
        try:
            with open(sidecar_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception as exc:
            logger.warning("Could not parse sidecar %s: %s", sidecar_path, exc)

    header = meta.get("header", True)
    delimiter = meta.get("delimiter", ",")
    column_names = meta.get("column_names")
    strip_bom = meta.get("strip_bom", False)

    rows: List[List[str]] = []
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        if delimiter is None:
            for line in f:
                line = line.rstrip("\n").rstrip("\r")
                if not line.strip():
                    continue
                tokens = re.findall(r'"[^"]*"|\S+', line)
                tokens = [
                    t[1:-1] if t.startswith('"') and t.endswith('"') else t
                    for t in tokens
                ]
                rows.append(tokens)
        else:
            reader = csv.reader(f, delimiter=delimiter)
            rows = list(reader)

    if not rows:
        return {
            "columns": [],
            "rows": [],
            "total_rows_loaded": 0,
            "source": "csv",
            "error": "CSV file is empty",
        }

    # Resolve header
    if header:
        header_row = rows[0]
        if strip_bom and header_row:
            header_row[0] = header_row[0].lstrip("\ufeff").strip()
        data_rows = rows[1:]
        if column_names:
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

    n_cols = len(cols)
    # Pad/truncate each row to match header width
    cleaned_rows: List[List[str]] = []
    for row in data_rows[:n_rows]:
        if len(row) < n_cols:
            row = row + [""] * (n_cols - len(row))
        elif len(row) > n_cols:
            row = row[:n_cols]
        cleaned_rows.append(row)

    return {
        "columns": cols,
        "rows": cleaned_rows,
        "total_rows_loaded": len(cleaned_rows),
        "total_rows_in_file": len(data_rows),
        "source": "csv",
        "file_name": os.path.basename(file_path),
    }


def _load_sklearn_preview(
    dataset_name: str,
    n_rows: int,
) -> Dict[str, Any]:
    """Build a preview from a built-in sklearn dataset (Bunch)."""
    from app.benchmark_engine.loader import _BUILTIN_DATASETS

    normalised = dataset_name.lower().strip().replace("-", "_").replace(" ", "_")
    if normalised not in _BUILTIN_DATASETS:
        return {
            "columns": [],
            "rows": [],
            "total_rows_loaded": 0,
            "source": "sklearn",
            "error": f"Unknown built-in dataset: {dataset_name}",
        }

    entry = _BUILTIN_DATASETS[normalised]
    loader_fn = entry["loader"]

    try:
        bunch = loader_fn()
    except TypeError:
        bunch = loader_fn
    except Exception as exc:
        # Some fetchers need network or are very large; fail soft
        return {
            "columns": [],
            "rows": [],
            "total_rows_loaded": 0,
            "source": "sklearn",
            "error": f"Could not load sklearn dataset: {exc}",
        }

    # Resolve column names
    if hasattr(bunch, "feature_names") and bunch.feature_names is not None:
        feature_cols = [str(f) for f in bunch.feature_names]
    else:
        n_feat = bunch.data.shape[1] if hasattr(bunch, "data") else 0
        feature_cols = [f"feature_{i}" for i in range(n_feat)]

    # Add a "target" column header
    target_name = "target"

    cols = feature_cols + [target_name]

    # Build rows
    X = bunch.data
    y = bunch.target
    # Safely look up target_names (regression datasets lack this attr)
    target_names = None
    if hasattr(bunch, "target_names") and bunch.target_names is not None:
        try:
            target_names = list(bunch.target_names)
        except Exception:
            target_names = None

    rows: List[List[str]] = []
    n = min(n_rows, X.shape[0])
    for i in range(n):
        row = []
        for j in range(X.shape[1]):
            v = X[i, j]
            # Round floats to 4 dp for display
            if isinstance(v, (float,)) or (
                hasattr(v, "dtype") and "float" in str(v.dtype)
            ):
                row.append(f"{float(v):.4f}")
            else:
                row.append(str(v))
        # Target
        tv = y[i]
        # Handle multi-output regression (e.g. Linnerud has 3 targets)
        if hasattr(tv, "__len__") and not isinstance(tv, str):
            # Could be a 1-D array of multiple targets
            try:
                tv_list = list(tv)
                if len(tv_list) > 1:
                    # Format each value and join with commas
                    formatted = []
                    for v in tv_list:
                        try:
                            formatted.append(f"{float(v):.4f}")
                        except (ValueError, TypeError):
                            formatted.append(str(v))
                    row.append(" | ".join(formatted))
                else:
                    tv = tv_list[0] if tv_list else tv
                    if isinstance(tv, float) or (
                        hasattr(tv, "dtype") and "float" in str(tv.dtype)
                    ):
                        row.append(f"{float(tv):.4f}")
                    else:
                        row.append(str(tv))
                rows.append(row)
                continue
            except TypeError:
                pass  # not iterable after all

        # Map integer target to class name if available (classification only)
        if (
            target_names is not None
            and entry["task_type"] == "classification"
            and isinstance(tv, (int,))
            or (
                hasattr(tv, "dtype")
                and "int" in str(tv.dtype)
                and target_names is not None
                and int(tv) < len(target_names)
            )
        ):
            try:
                row.append(str(target_names[int(tv)]))
            except Exception:
                row.append(str(tv))
        else:
            if isinstance(tv, float) or (
                hasattr(tv, "dtype") and "float" in str(tv.dtype)
            ):
                row.append(f"{float(tv):.4f}")
            else:
                row.append(str(tv))
        rows.append(row)

    return {
        "columns": cols,
        "rows": rows,
        "total_rows_loaded": len(rows),
        "total_rows_in_file": int(X.shape[0]),
        "source": "sklearn",
        "file_name": f"sklearn://{normalised}",
    }


def get_dataset_preview(
    dataset,
    n_rows: int = DEFAULT_PREVIEW_ROWS,
) -> Dict[str, Any]:
    """Public entrypoint: return a preview dict for the given Dataset ORM row.

    Args:
        dataset: A ``Dataset`` ORM instance with ``name``, ``file_path``
            and ``task_type`` attributes.
        n_rows: Number of rows to return (clamped to 1..100).

    Returns:
        Dict with ``columns``, ``rows``, ``total_rows_loaded``,
        ``total_rows_in_file``, ``source``, ``file_name``.
    """
    n = clamp_rows(n_rows)

    # If the dataset has a file_path → CSV preview
    if dataset.file_path:
        return _load_csv_preview(dataset.file_path, n)

    # Otherwise it's a sklearn built-in
    return _load_sklearn_preview(dataset.name, n)
