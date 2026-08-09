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
import json
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

# ─── Module blocklist ────────────────────────────────────────────────────────
# We use *prefix matching* — a prefix of "subprocess" blocks "subprocess",
# "subprocess.foo", etc. Be careful with broad prefixes: blocking "importlib"
# would also block "importlib.resources", "importlib.metadata",
# "importlib.readers" — which scikit-learn, pandas, and most modern Python
# libraries legitimately need to load bundled data files.
#
# Instead, we use a TWO-TIER system:
#   1. _BLOCKED_MODULE_PREFIXES — fully blocked (subprocess, socket, etc.)
#   2. _BLOCKED_IMPORTLIB_SUBMODULES — submodule-level blocklist for the
#      dangerous parts of importlib, while allowing the safe parts
#      (resources, metadata, readers, util) that legitimate libraries need.
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
    # `runpy` — run_module / run_path can load arbitrary code without
    # going through __import__. No legitimate library uses these.
    "runpy",
    # `code`, `codeop` — interactive interpreter, no legitimate use.
    "code",
    "codeop",
    # `pdb`, `pydoc` — introspection tools, no legitimate use in benchmarks.
    "pdb",
    "pydoc",
    # `marshal` — binary serialization format, can be used for exploits.
    "marshal",
    # `pickle` — allows loading arbitrary pickled objects which can trigger
    # __reduce__ exploits. We need pickle *internally* (joblib uses it to
    # save the trained model), but user code shouldn't use it directly.
    # The internal joblib.dump call happens in the service module's own
    # scope, not in the sandbox namespace, so this block doesn't affect it.
    "pickle",
)

# Dangerous importlib submodules — these allow programmatic imports that
# bypass our __import__ hook. Block them specifically.
# NOTE: We DO NOT block `importlib.resources`, `importlib.metadata`,
# `importlib.readers`, `importlib.util`, `importlib.machinery` — these are
# used by scikit-learn, pandas, matplotlib, and most modern Python libraries
# to load bundled data files. Blocking them breaks ALL dataset loaders.
_BLOCKED_IMPORTLIB_SUBMODULES = (
    "importlib.import_module",  # the actual escape vector — but this is
                                 # a function, not a submodule. See the
                                 # namespace wrapping in _build_sandbox_namespace
                                 # for the runtime block.
)

# Top-level `import importlib` is allowed — but we strip `import_module`
# from the imported module's namespace so users can't call it. See
# _build_sandbox_namespace for the runtime enforcement.


class _ImportBlocker:
    """A sys.meta_path finder that raises ``ImportError`` for blocked modules.

    Used to prevent user code from importing ``subprocess`` and friends
    even when our namespace doesn't pre-populate them.

    Note: ``importlib`` is intentionally NOT in the blocklist. Modern
    Python libraries (sklearn, pandas, matplotlib) need
    ``importlib.resources``, ``importlib.metadata``, etc. to load bundled
    data files. Instead, we wrap ``importlib.import_module`` at runtime
    in _build_sandbox_namespace to block the specific escape vector
    (programmatic imports of subprocess/socket/etc.) while leaving
    legitimate importlib submodules functional.
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

    SECURITY NOTE on importlib:
    --------------------------
    We intentionally allow `import importlib` because modern Python
    libraries (sklearn, pandas, matplotlib) need `importlib.resources`,
    `importlib.metadata`, `importlib.readers` to load bundled data files.
    Blocking `importlib` entirely (as v4.2.1 did) breaks ALL sklearn
    dataset loaders — `load_iris`, `fetch_california_housing`, etc.

    Instead, we wrap `importlib.import_module` at runtime so users can
    still import safe submodules (`importlib.resources.files(...)`)
    but cannot use `importlib.import_module("subprocess")` to escape
    the sandbox. This is the surgical fix that closes the v4.2.1
    escape vector WITHOUT breaking legitimate library imports.
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
    import importlib  # legitimately needed by sklearn/pandas/etc.

    safe_builtins = dict(vars(builtins))
    for name in _BLOCKED_BUILTIN_NAMES:
        safe_builtins.pop(name, None)

    # Install a custom ``__import__`` that refuses to load blocked
    # modules even if they are already cached in ``sys.modules``.
    # This is more robust than relying on ``sys.meta_path`` alone
    # because cached imports skip the finder mechanism entirely.
    real_import = safe_builtins.get("__import__", builtins.__import__)

    def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        # Check the top-level module name AND any dotted prefixes.
        # E.g. for "importlib.import_module" we check "importlib" (allowed)
        # but the runtime wrapper below blocks the actual call.
        parts = name.split(".")
        for i in range(len(parts)):
            prefix = ".".join(parts[:i+1])
            if prefix in _BLOCKED_MODULE_PREFIXES:
                raise ImportError(
                    f"Import of '{name}' is blocked by OpenBenchML sandbox. "
                    f"If you genuinely need this module for a benchmark, "
                    f"contact the platform administrator."
                )
        return real_import(name, globals, locals, fromlist, level)

    safe_builtins["__import__"] = _safe_import

    # ── Wrap importlib.import_module ─────────────────────────────────────
    # This is the surgical fix for the v4.2.1 regression. We allow
    # `import importlib` (so sklearn/pandas/etc. can use importlib.resources)
    # but wrap `import_module` so it refuses to load any blocked module.
    real_import_module = importlib.import_module

    def _safe_import_module(name, package=None):
        parts = (name or "").split(".")
        for i in range(len(parts)):
            prefix = ".".join(parts[:i+1])
            if prefix in _BLOCKED_MODULE_PREFIXES:
                raise ImportError(
                    f"importlib.import_module('{name}') is blocked by "
                    f"OpenBenchML sandbox."
                )
        return real_import_module(name, package)

    importlib.import_module = _safe_import_module

    ns: Dict[str, Any] = {
        "__builtins__": safe_builtins,
        # Pre-imported common libs (student-friendly — they can just write
        # ``np.array(...)``, ``pd.DataFrame(...)``, etc.)
        "np": numpy,
        "pd": pandas,
        "sklearn": sklearn,
        "scipy": scipy,
        "joblib": joblib,
        # importlib is exposed so user code can use importlib.resources
        # (legitimate). The wrapped import_module blocks escapes.
        "importlib": importlib,
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
    timeout_seconds: int = 300,
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
        timeout_seconds: Wall-clock limit. Default 300s (5 min) so
            real-world training (e.g. RandomForestRegressor on
            California Housing, XGBoost on full Wine) doesn't get
            killed mid-fit the way it did with the old 60s limit.

    Returns:
        Tuple ``(pickled_bytes, metadata)`` where ``metadata`` has
        keys ``model_class``, ``framework``, ``namespace_keys``,
        ``stdout``, ``stderr``.

    Raises:
        ValueError: If execution failed or no ``model`` variable
            was found in the resulting namespace. The error message
            for timeouts specifically mentions the Pyodide browser
            engine as an alternative.
    """
    result = run_code(code, timeout_seconds=timeout_seconds)

    if not result["ok"]:
        # Surface a more actionable message for the common timeout case —
        # users training RandomForest on California Housing (20,640 samples)
        # hit the limit on Render's free tier. Point them at the Pyodide
        # in-browser engine, which has no server timeout.
        if result.get("timed_out"):
            raise ValueError(
                f"Training exceeded the {timeout_seconds}s server timeout. "
                f"This usually means your model is large (e.g. RandomForest "
                f"on California Housing, or n_estimators > 200). "
                f"Two options:\n"
                f"  1. Switch to the Pyodide (in-browser) engine on the "
                f"/convert page — it has NO server timeout, training runs "
                f"in your browser tab.\n"
                f"  2. Reduce n_estimators, max_depth, or sample size; "
                f"or set n_jobs=-1 if your plan has multiple CPUs.\n"
                f"--- stdout ---\n{result['stdout']}\n"
                f"--- stderr ---\n{result['stderr']}"
            )
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

    # ── Validate this is actually a model object ──────────────────────────
    # The whole point of /convert is to capture a *trained model*. If the
    # user assigned something like ``model = 42`` or ``model = "hello"``
    # to the `model` variable, we should fail with a helpful message
    # rather than pickling garbage and breaking the benchmark engine later.
    if not _looks_like_a_model(model_obj):
        raise ValueError(
            f"The '{expected_var}' variable is a {model_class}, which doesn't "
            f"look like a trained ML model (it has no predict() / transform() / "
            f"score() method). Please assign your trained estimator to "
            f"'{expected_var}'. For example:\n"
            f"    model = RandomForestClassifier(n_estimators=100)\n"
            f"    model.fit(X_train, y_train)\n"
        )

    # ── Detect framework from the model class ─────────────────────────────
    framework = _detect_framework(model_obj)

    # ── Auto-detect task type from the model class ────────────────────────
    # Used by the benchmark form to pre-select the right dataset. Also
    # surfaces in the API response so CLI users know what to expect.
    task_type = _detect_task_type(model_obj)

    # ── Introspect key model parameters (for the model detail page) ───────
    # We grab a small curated set of "interesting" hyperparameters that
    # vary by model type. This is purely for display — the pickled model
    # already has all its real params.
    params = _introspect_model_params(model_obj)

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
        "task_type": task_type,
        "params": params,
        "is_fitted": _is_fitted(model_obj),
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
    # This is a *hint* for display — the authoritative metrics come from
    # the benchmark engine when the model is later benchmarked on a
    # known dataset.
    _METRIC_ALIASES = {
        "accuracy":     ("accuracy", "acc", "test_accuracy", "test_acc"),
        "precision":    ("precision", "prec"),
        "recall":       ("recall", "sensitivity"),
        "f1_score":     ("f1_score", "f1"),
        "auc_roc":      ("auc_roc", "auc", "roc_auc"),
        "log_loss":     ("log_loss", "logloss"),
        "rmse":         ("rmse",),
        "mse":          ("mse",),
        "r2_score":     ("r2_score", "r2"),
        "mae":          ("mae",),
        "mape":         ("mape",),
    }
    for canonical, aliases in _METRIC_ALIASES.items():
        for alias in aliases:
            if alias in ns:
                v = ns[alias]
                # Accept ints, floats, and 0-d numpy scalars. Reject
                # anything that can't be losslessly cast to float.
                try:
                    fv = float(v)
                except (TypeError, ValueError):
                    continue
                if isinstance(v, (int, float)) or hasattr(v, "item"):
                    metadata[canonical] = fv
                    break

    return pickled_bytes, metadata


def _detect_framework(model_obj: Any) -> str:
    """Best-effort framework detection from the model object's class.

    Falls back to ``"scikit-learn"`` for anything pickleable that
    isn't obviously one of the other frameworks (this is correct
    for the vast majority of student-submitted models).

    Robust against dynamically-created classes (e.g. ``type('Foo', (), {})``)
    that have no ``__module__`` attribute — these would previously crash
    with ``AttributeError: __module__``.
    """
    cls = type(model_obj)
    # Guard against dynamic classes that may not have __module__.
    try:
        mod = (getattr(cls, "__module__", "") or "").lower()
    except Exception:
        mod = ""
    name = (getattr(cls, "__name__", "") or "").lower()

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


# ─── Model introspection helpers ────────────────────────────────────────────
# Used by /convert to enrich the API response and to validate that the
# user actually trained a model (rather than e.g. ``model = 42``).
#
# These helpers are deliberately defensive — they must not raise on
# exotic model objects (Keras, custom classes, etc.).

# A small set of method names that any real ML model should have. We
# require at least one of these to consider the object a "model".
_MODEL_METHOD_HINTS = ("predict", "transform", "fit_transform", "score",
                        "decision_function", "predict_proba", "forward")


def _looks_like_a_model(obj: Any) -> bool:
    """Return True if ``obj`` has at least one method that real ML models have.

    This catches the common mistake of assigning a non-model object
    (int, str, list, dict, numpy array, etc.) to the ``model`` variable
    in /convert code. Without this check the platform would happily
    pickle garbage, save it as an MLModel, and then fail confusingly
    when the benchmark engine tried to call .predict() on it.

    A trained model will have at least ``predict`` (sklearn, xgboost,
    lightgbm), ``forward`` (pytorch), or ``predict`` (keras). Pipelines
    and transformers have ``transform`` or ``fit_transform``.
    """
    return any(callable(getattr(obj, m, None)) for m in _MODEL_METHOD_HINTS)


def _is_fitted(model_obj: Any) -> bool:
    """Best-effort check that a sklearn-style estimator has been fitted.

    Uses sklearn's ``check_is_fitted`` if available; falls back to
    checking for the conventional ``_estimator_type`` + any fitted
    attribute ending in ``_`` (sklearn's naming convention for learned
    attributes).
    """
    try:
        from sklearn.utils.validation import check_is_fitted
        check_is_fitted(model_obj)
        return True
    except Exception:
        pass
    # Fallback: look for any attribute ending in "_" (sklearn's convention
    # for fitted attributes like ``coef_``, ``classes_``, ``feature_importances_``).
    try:
        return any(k.endswith("_") and not k.startswith("__")
                   for k in vars(model_obj))
    except TypeError:
        # vars() doesn't work on objects without __dict__ (e.g. slots).
        return False


# Maps model-class name fragments → task type. Order matters: more
# specific patterns (e.g. "RandomForestClassifier") must come before
# generic ones ("RandomForest").
_TASK_TYPE_PATTERNS = (
    ("classifier", "classification",
     ("classifier", "logisticregression", "svc", "randomforestclassifier",
      "gradientboostingclassifier", "kneighborsclassifier", "decisiontreeclassifier",
      "extratreesclassifier", "adaboostclassifier", "gaussiannb", "multinomialnb",
      "bernoullinb", "mlpclassifier", "perceptron", "ridgeclassifier",
      "sgdclassifier", "linearsvc", "quadraticdiscriminantanalysis",
      "lineardiscriminantanalysis")),
    ("regressor", "regression",
     ("regressor", "ridge", "lasso", "elasticnet", "linearregression",
      "svr", "randomforestregressor", "gradientboostingregressor",
      "kneighborsregressor", "decisiontreeregressor", "extratreesregressor",
      "adaboostregressor", "mlpregressor", "sgdregressor", "svr",
      "ardregression", "bayesianridge", "huberregressor", "theilsenregressor",
      "ransacregressor", "orthogonalmatchingpursuit")),
    ("clusterer", "clustering",
     ("kmeans", "dbscan", "meanshift", "spectralclustering", "agglomerativeclustering",
      "birch", "optics", "affinitypropagation", "minibatchkmeans",
      "featureagglomeration")),
)


def _detect_task_type(model_obj: Any) -> str:
    """Infer task_type (classification/regression/clustering) from class name.

    Uses sklearn's ``_estimator_type`` attribute when present (most
    sklearn estimators set this to ``"classifier"`` / ``"regressor"``
    / ``"clusterer"``). Falls back to substring matching on the class
    name for non-sklearn models (XGBoost, LightGBM, custom classes).
    """
    # Try sklearn's official attribute first.
    try:
        et = getattr(model_obj, "_estimator_type", None)
        if et:
            et = et.lower()
            if "class" in et:
                return "classification"
            if "regress" in et:
                return "regression"
            if "cluster" in et:
                return "clustering"
    except Exception:
        pass

    # Fallback: substring match on the class name.
    name = (getattr(type(model_obj), "__name__", "") or "").lower()
    for _, task, patterns in _TASK_TYPE_PATTERNS:
        if any(p in name for p in patterns):
            return task

    # XGBoost / LightGBM / PyTorch / TensorFlow — look at class + attributes.
    cls_name = name
    if "xgb" in cls_name or "lgbm" in cls_name:
        if "regress" in cls_name:
            return "regression"
        if "classif" in cls_name or "ranker" not in cls_name:
            return "classification"

    # Last resort: try to peek at n_classes_ (sklearn classifiers set
    # this when fitted) vs coef_ shape.
    try:
        if hasattr(model_obj, "n_classes_") or hasattr(model_obj, "classes_"):
            return "classification"
    except Exception:
        pass

    return "unknown"


# Hyperparameters worth surfacing in the model detail page. We pull
# only the most informative ones (the ones students actually tweak).
_PARAM_NAMES_BY_CLASS = {
    # Tree-based
    "n_estimators": ("RandomForest", "GradientBoosting", "ExtraTrees",
                     "AdaBoost", "IsolationForest"),
    "max_depth": ("RandomForest", "GradientBoosting", "ExtraTrees",
                  "DecisionTree", "AdaBoost"),
    "max_features": ("RandomForest", "ExtraTrees", "DecisionTree"),
    "min_samples_split": ("RandomForest", "ExtraTrees", "DecisionTree"),
    "learning_rate": ("GradientBoosting", "AdaBoost", "HistGradientBoosting"),
    # Linear
    "alpha": ("Ridge", "Lasso", "ElasticNet"),
    "C": ("LogisticRegression", "SVC", "SVR", "LinearSVC"),
    "penalty": ("LogisticRegression", "SGDClassifier", "SGDRegressor"),
    # Neighbors
    "n_neighbors": ("KNeighbors",),
    # SVM
    "kernel": ("SVC", "SVR"),
    "gamma": ("SVC", "SVR"),
    # Naive Bayes
    "var_smoothing": ("GaussianNB",),
    "alpha_nb": ("MultinomialNB", "BernoulliNB"),
    # Neural net
    "hidden_layer_sizes": ("MLPClassifier", "MLPRegressor"),
    "activation": ("MLPClassifier", "MLPRegressor"),
    # Clustering
    "n_clusters": ("KMeans", "MiniBatchKMeans", "MeanShift",
                   "SpectralClustering", "AgglomerativeClustering"),
}


def _introspect_model_params(model_obj: Any) -> dict:
    """Pull a small curated set of hyperparameters from the model object.

    Returns a dict of {param_name: value} where value is JSON-serializable
    (str/int/float/bool/None). Anything that can't be JSON-serialized
    (numpy arrays, custom objects) is dropped.

    This is purely for display in the model detail page — the pickled
    model already has all its real params, this is just a quick summary.
    """
    out: dict = {}
    try:
        get_params = getattr(model_obj, "get_params", None)
        params_dict = get_params() if callable(get_params) else {}
    except Exception:
        params_dict = {}

    cls_name = type(model_obj).__name__
    # Find which params are relevant for this class.
    relevant = set()
    for pname, class_patterns in _PARAM_NAMES_BY_CLASS.items():
        if any(p in cls_name for p in class_patterns):
            relevant.add(pname)
    # Also always include these "common" ones if present.
    relevant.update({"random_state", "n_jobs"})

    for pname in relevant:
        if pname in params_dict:
            v = params_dict[pname]
            # Try to make it JSON-safe.
            try:
                json.dumps(v)
                out[pname] = v
            except (TypeError, ValueError):
                # Convert numpy types / tuples to a str representation.
                try:
                    out[pname] = str(v)
                except Exception:
                    pass
    return out





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


def inspect_pickled_bytes(pickled_bytes: bytes) -> Dict[str, Any]:
    """Inspect raw pickle bytes from the browser (Pyodide-trained model).

    The Pyodide path trains the model in the browser, pickles it with
    joblib, base64-encodes the result, and POSTs it to the server. The
    server needs to recover ``model_class`` and ``framework`` so the
    MLModel DB row matches what the server-side /convert flow would
    have produced.

    Args:
        pickled_bytes: Raw pickled model bytes (joblib or pickle format).

    Returns:
        Dict with keys ``model_class``, ``framework``, ``size_kb``.
        On any unpickling failure, returns ``framework="scikit-learn"``
        (the safe default) and an ``error`` key.
    """
    size_kb = round(len(pickled_bytes) / 1024, 2)
    try:
        # joblib.dump wraps pickle — joblib.load can read both formats.
        import joblib as _joblib
        model_obj = _joblib.load(io.BytesIO(pickled_bytes))
        model_class = type(model_obj).__name__
        framework = _detect_framework(model_obj)
        task_type = _detect_task_type(model_obj)
        params = _introspect_model_params(model_obj)
        is_fitted = _is_fitted(model_obj)
        return {
            "model_class": model_class,
            "framework": framework,
            "task_type": task_type,
            "params": params,
            "is_fitted": is_fitted,
            "size_kb": size_kb,
            "ok": True,
        }
    except Exception as exc:
        logger.warning("Could not inspect pickled bytes: %s", exc)
        return {
            "model_class": "Unknown",
            "framework": "scikit-learn",
            "task_type": "unknown",
            "params": {},
            "is_fitted": False,
            "size_kb": size_kb,
            "ok": False,
            "error": str(exc),
        }

