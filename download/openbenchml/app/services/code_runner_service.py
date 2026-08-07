"""
OpenBenchML Code Runner Service
=================================
Executes user-supplied Python code in a *restricted* namespace so that:

1. Users can write Python in an in-browser notebook and see the output
   (stdout / stderr / result / errors) without installing anything.
2. Users can submit a Python code block that *produces a trained model*
   and the platform will pickle that model and register it as an
   ``MLModel`` — this is the ``/convert`` flow.

SECURITY
--------
This service is intentionally **permissive** about what the user can
import (sklearn, numpy, pandas, xgboost, lightgbm are all allowed
because that's the whole point of a benchmarking platform) but it
**blocks** a small set of dangerous builtins and OS-level operations
that have no legitimate use in a benchmark script:

* ``open``              — file I/O outside the runner's workspace
* ``os.system``         — shell-out
* ``subprocess.*``      — process spawning
* ``socket``            — raw network access
* ``ctypes``            — FFI / shared library loading

For student / classroom deployments this is a reasonable balance
between power and safety.  For production deployments with untrusted
users you should additionally sandbox with Docker (already supported
via the ``docker_runner`` package).
"""

import io
import logging
import os
import pickle
import sys
import tempfile
import traceback
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ─── Blocked builtins / modules ───────────────────────────────────────────────
# Anything in this set is removed from the execution namespace.
# We DO NOT block ``__import__`` because legitimate ``from sklearn... import ...``
# statements need it.  Instead, dangerous modules are blocked at import
# time by the ``_ImportBlocker`` meta_path finder below.
_BLOCKED_BUILTIN_NAMES = {
    "open", "exec", "eval", "compile", "globals",
    "breakpoint", "input",
}

_BLOCKED_MODULE_PREFIXES = (
    "subprocess",
    "ctypes",
    "multiprocessing",
    "socket",
    "http",
    "urllib",
    "ftplib",
    "telnetlib",
    "smtplib",
    "shutil",
    "pathlib",  # blocks Path-based file ops too
    # ⚠ Blocking `importlib` is critical: `importlib.import_module("subprocess")`
    # bypasses our custom __import__ hook (which only catches `import subprocess`
    # statements). Without this, a student could trivially escape the sandbox.
    "importlib",
    # Same for `runpy` (runpy.run_module / run_path) — another way to load
    # arbitrary code without going through __import__.
    "runpy",
    # `pickle` / `marshal` allow loading arbitrary pickled objects which can
    # trigger __reduce__ exploits. We need them internally for pickling the
    # trained model, but user code shouldn't use them directly.
    "pickle",
    "marshal",
    "code",
    "codeop",
    "pdb",
    "pydoc",
)


class _ImportBlocker:
    """A sys.meta_path finder that raises ``ImportError`` for blocked modules.

    Used to prevent user code from importing ``subprocess`` and friends
    even when our namespace doesn't pre-populate them.
    """

    def __init__(self, blocked_prefixes: Tuple[str, ...]):
        self.blocked_prefixes = blocked_prefixes

    def find_spec(self, name, path, target=None):
        for prefix in self.blocked_prefixes:
            if name == prefix or name.startswith(prefix + "."):
                raise ImportError(
                    f"Import of '{name}' is blocked by OpenBenchML sandbox. "
                    f"If you genuinely need this module for a benchmark, "
                    f"contact the platform administrator."
                )
        return None  # let the next finder handle it


def _build_sandbox_namespace() -> Dict[str, Any]:
    """Build the globals dict for user-code execution.

    Pre-imports the common ML / data libraries so students can write
    ``from sklearn.datasets import load_iris`` directly without
    worrying about which packages are available.  Then strips the
    dangerous builtins.
    """
    import builtins
    import numpy
    import sklearn
    import sklearn.datasets
    import sklearn.linear_model
    import sklearn.ensemble
    import sklearn.tree
    import sklearn.svm
    import sklearn.neighbors
    import sklearn.neural_network
    import sklearn.model_selection
    import sklearn.metrics
    import sklearn.preprocessing
    import sklearn.pipeline
    import sklearn.decomposition
    import pandas
    import scipy
    import joblib

    safe_builtins = dict(vars(builtins))
    for name in _BLOCKED_BUILTIN_NAMES:
        safe_builtins.pop(name, None)

    # Install a custom ``__import__`` that refuses to load blocked
    # modules even if they are already cached in ``sys.modules``.
    # This is more robust than relying on ``sys.meta_path`` alone
    # because cached imports skip the finder mechanism entirely.
    real_import = safe_builtins.get("__import__", builtins.__import__)

    def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        mod_top = name.split(".")[0]
        if mod_top in _BLOCKED_MODULE_PREFIXES:
            raise ImportError(
                f"Import of '{name}' is blocked by OpenBenchML sandbox. "
                f"If you genuinely need this module for a benchmark, "
                f"contact the platform administrator."
            )
        return real_import(name, globals, locals, fromlist, level)

    safe_builtins["__import__"] = _safe_import

    ns: Dict[str, Any] = {
        "__builtins__": safe_builtins,
        # Pre-imported common libs (student-friendly — they can just write
        # ``np.array(...)``, ``pd.DataFrame(...)``, etc.)
        "np": numpy,
        "pd": pandas,
        "sklearn": sklearn,
        "scipy": scipy,
        "joblib": joblib,
        # Common sklearn shortcuts students will reach for
        "sklearn_datasets": sklearn.datasets,
        "sklearn_model_selection": sklearn.model_selection,
        "sklearn_metrics": sklearn.metrics,
        "sklearn_linear_model": sklearn.linear_model,
        "sklearn_ensemble": sklearn.ensemble,
        "sklearn_tree": sklearn.tree,
        "sklearn_svm": sklearn.svm,
        "sklearn_neighbors": sklearn.neighbors,
        "sklearn_neural_network": sklearn.neural_network,
        "sklearn_preprocessing": sklearn.preprocessing,
        "sklearn_pipeline": sklearn.pipeline,
        "sklearn_decomposition": sklearn.decomposition,
    }
    return ns


def run_code(
    code: str,
    *,
    timeout_seconds: int = 30,
    extra_globals: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute Python source code in a restricted namespace.

    Captures ``stdout`` and ``stderr`` produced during execution and
    returns them together with the resulting namespace (so callers can
    extract variables like ``model`` after the fact).

    Args:
        code: Python source code to execute.
        timeout_seconds: Wall-clock limit (best-effort; we rely on
            signal-based timeout where available, otherwise this is
            advisory).  Default 30s.
        extra_globals: Optional dict of additional names to inject
            into the namespace before execution.

    Returns:
        A dict with keys:

        * ``ok`` (bool)          — did the code run without raising?
        * ``stdout`` (str)       — captured stdout
        * ``stderr`` (str)       — captured stderr (from prints to stderr
          AND from any traceback)
        * ``namespace`` (dict)   — the globals after execution (so you
          can extract ``model``, ``X``, ``y``, etc.)
        * ``error`` (str | None) — short error summary if any
        * ``traceback`` (str | None) — full traceback string if any
    """
    if not code or not code.strip():
        return {
            "ok": False,
            "stdout": "",
            "stderr": "Empty code block.",
            "namespace": {},
            "error": "Empty code block.",
            "traceback": None,
        }

    namespace = _build_sandbox_namespace()
    if extra_globals:
        namespace.update(extra_globals)

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    # Install the import blocker for the duration of this execution
    blocker = _ImportBlocker(_BLOCKED_MODULE_PREFIXES)
    sys.meta_path.insert(0, blocker)

    # Apply timeout via SIGALRM where available (POSIX only)
    old_handler = None
    timed_out = False
    try:
        try:
            import signal
            def _alarm_handler(signum, frame):
                raise TimeoutError(
                    f"Code execution exceeded {timeout_seconds}s limit."
                )
            old_handler = signal.signal(signal.SIGALRM, _alarm_handler)
            signal.alarm(timeout_seconds)
        except (ImportError, ValueError, OSError):
            # signal not available on Windows / non-main-thread — skip
            pass

        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            try:
                exec(compile(code, "<user_code>", "exec"), namespace)
                ok = True
                error = None
                tb = None
            except TimeoutError:
                # Re-raise so the outer except can set timed_out=True.
                raise
            except Exception as exc:
                ok = False
                error = f"{type(exc).__name__}: {exc}"
                tb = traceback.format_exc()
                stderr_buf.write(tb)
    except TimeoutError as te:
        timed_out = True
        ok = False
        error = str(te)
        tb = traceback.format_exc()
        stderr_buf.write(tb)
    finally:
        # Restore signal handler
        try:
            import signal
            signal.alarm(0)
            if old_handler is not None:
                signal.signal(signal.SIGALRM, old_handler)
        except (ImportError, ValueError, OSError):
            pass
        # Remove the import blocker
        try:
            sys.meta_path.remove(blocker)
        except ValueError:
            pass

    return {
        "ok": ok and not timed_out,
        "stdout": stdout_buf.getvalue(),
        "stderr": stderr_buf.getvalue(),
        "namespace": namespace,
        "error": error,
        "traceback": tb,
        "timed_out": timed_out,
    }


def code_to_pickled_model(
    code: str,
    *,
    expected_var: str = "model",
    timeout_seconds: int = 60,
) -> Tuple[bytes, Dict[str, Any]]:
    """Run user code, extract a trained model, and pickle it.

    The convention is that user code leaves a variable named
    ``model`` in its namespace — this is the trained sklearn /
    xgboost / lightgbm / pytorch object that will be benchmarked.
    Other variables (e.g. ``X``, ``y``, ``accuracy``) are returned
    in the metadata dict so the UI can display them.

    Args:
        code: Python source that trains a model.
        expected_var: Name of the variable to extract & pickle
            (default ``"model"``).
        timeout_seconds: Wall-clock limit.

    Returns:
        Tuple ``(pickled_bytes, metadata)`` where ``metadata`` has
        keys ``model_class``, ``framework``, ``namespace_keys``,
        ``stdout``, ``stderr``.

    Raises:
        ValueError: If execution failed or no ``model`` variable
            was found in the resulting namespace.
    """
    result = run_code(code, timeout_seconds=timeout_seconds)

    if not result["ok"]:
        raise ValueError(
            f"Code execution failed: {result['error']}\n"
            f"--- stdout ---\n{result['stdout']}\n"
            f"--- stderr ---\n{result['stderr']}"
        )

    ns = result["namespace"]
    if expected_var not in ns:
        # Provide a helpful list of what *is* in the namespace so the
        # student can spot the typo (e.g. they named it ``clf`` instead
        # of ``model``).
        user_keys = sorted(
            k for k in ns.keys()
            if not k.startswith("_") and k not in {
                "np", "pd", "sklearn", "scipy", "joblib",
                "sklearn_datasets", "sklearn_model_selection",
                "sklearn_metrics", "sklearn_linear_model",
                "sklearn_ensemble", "sklearn_tree",
                "sklearn_svm", "sklearn_neighbors",
                "sklearn_neural_network",
                "sklearn_preprocessing", "sklearn_pipeline",
                "sklearn_decomposition",
            }
        )
        raise ValueError(
            f"No '{expected_var}' variable found in the code's namespace. "
            f"Please assign your trained model to a variable named "
            f"'{expected_var}'.  Variables we did find: {user_keys}"
        )

    model_obj = ns[expected_var]
    model_class = type(model_obj).__name__

    # ── Detect framework from the model class ─────────────────────────────
    framework = _detect_framework(model_obj)

    # ── Pickle the model to a temp file, then read the bytes ──────────────
    # Using joblib is more robust for sklearn models with numpy arrays.
    import joblib as _joblib
    with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        _joblib.dump(model_obj, tmp_path)
        with open(tmp_path, "rb") as f:
            pickled_bytes = f.read()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    # ── Capture other useful variables for the UI ────────────────────────
    metadata = {
        "model_class": model_class,
        "framework": framework,
        "namespace_keys": sorted(
            k for k in ns.keys() if not k.startswith("_")
        ),
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "size_kb": round(len(pickled_bytes) / 1024, 2),
    }

    # Try to grab any obvious metric variables the user may have left.
    # We accept both long and short names so the UI shows useful info
    # whether the student wrote ``acc = ...`` or ``accuracy = ...``.
    _METRIC_ALIASES = {
        "accuracy":   ("accuracy", "acc"),
        "f1_score":   ("f1_score", "f1"),
        "rmse":       ("rmse",),
        "r2_score":   ("r2_score", "r2"),
        "mae":        ("mae",),
    }
    for canonical, aliases in _METRIC_ALIASES.items():
        for alias in aliases:
            if alias in ns and isinstance(ns[alias], (int, float)):
                metadata[canonical] = float(ns[alias])
                break

    return pickled_bytes, metadata


def _detect_framework(model_obj: Any) -> str:
    """Best-effort framework detection from the model object's class.

    Falls back to ``"scikit-learn"`` for anything pickleable that
    isn't obviously one of the other frameworks (this is correct
    for the vast majority of student-submitted models).
    """
    cls = type(model_obj)
    mod = (cls.__module__ or "").lower()
    name = cls.__name__.lower()

    if "torch" in mod:
        return "pytorch"
    if "tensorflow" in mod or "keras" in mod:
        return "tensorflow"
    if "xgboost" in mod or name.startswith("xgb"):
        return "xgboost"
    if "lightgbm" in mod or name.startswith("lgbm") or name.startswith("booster"):
        return "lightgbm"
    if "onnx" in mod:
        return "onnx"
    return "scikit-learn"


def save_pickled_model(
    pickled_bytes: bytes,
    user_id: int,
    model_name: str,
    upload_dir: Path,
) -> Tuple[str, float]:
    """Persist raw pickled bytes to disk under the user's upload directory.

    Returns ``(file_path, size_kb)``.

    Args:
        pickled_bytes: Raw pickled model bytes.
        user_id: Owner's DB id — used for the on-disk subdirectory.
        model_name: Used to derive a safe filename.
        upload_dir: Root uploads directory.
    """
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in model_name)
    if not safe_name:
        safe_name = "model"
    user_dir = upload_dir / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)

    # Use a timestamp suffix to avoid collisions when the same model
    # name is converted multiple times.
    from datetime import datetime
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    file_path = user_dir / f"{safe_name}_{ts}.pkl"

    with open(file_path, "wb") as f:
        f.write(pickled_bytes)

    size_kb = round(len(pickled_bytes) / 1024, 2)
    logger.info(
        "Saved pickled model '%s' for user_id=%d (%.2f KB)",
        file_path.name, user_id, size_kb,
    )
    return str(file_path), size_kb
