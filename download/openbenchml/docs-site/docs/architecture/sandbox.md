# Code Sandbox Architecture

The `/convert` and `/notebook` features both rely on a single service:
`app/services/code_runner_service.py`. This page describes its design,
security model, and limitations.

## Design goals

1. **Student-friendly** — pre-import the common ML libs so beginners don't
   have to remember whether `RandomForestClassifier` lives in
   `sklearn.ensemble` or `sklearn.tree`.
2. **Powerful enough for real benchmarks** — sklearn, xgboost, lightgbm,
   pytorch, tensorflow, scipy, pandas, numpy are all available.
3. **Safe by default** — block the obvious "rm -rf /" foot-guns without
   trying to be a cryptographic sandbox.
4. **Timeout-enforced** — 30s default for the notebook, 60s for convert.
   No student's infinite loop should hold the server hostage.

## Architecture

```text
┌────────────────────────────────────────────────────────────────┐
│  POST /api/convert  or  POST /api/notebook/run                 │
└────────────────┬───────────────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────────────┐
│  code_runner_service.run_code(code, timeout)                   │
│                                                                │
│   1. Build sandbox namespace:                                  │
│      - Pre-imported np/pd/sklearn/scipy/joblib + sklearn_*     │
│      - Stripped builtins: open, exec, eval, compile, globals…  │
│      - Custom __import__ that refuses blocked module prefixes  │
│                                                                │
│   2. Install SIGALRM timeout (POSIX)                           │
│                                                                │
│   3. exec(compile(code, '<user_code>', 'exec'), namespace)     │
│      ↳ stdout/stderr captured via redirect_stdout/stderr       │
│                                                                │
│   4. Restore signal handler, return (ok, stdout, stderr, ns)   │
└────────────────┬───────────────────────────────────────────────┘
                 │
                 ▼ (convert only)
┌────────────────────────────────────────────────────────────────┐
│  code_runner_service.code_to_pickled_model(code)               │
│                                                                │
│   1. Run code                                                  │
│   2. Extract `model` from namespace (raises if missing)        │
│   3. Detect framework from type(model).__module__              │
│   4. joblib.dump(model, tmp_file)  → read bytes                │
│   5. Capture metric aliases (acc, accuracy, rmse, r2, mae, f1) │
│   6. Return (pickled_bytes, metadata)                          │
└────────────────┬───────────────────────────────────────────────┘
                 │
                 ▼ (convert only)
┌────────────────────────────────────────────────────────────────┐
│  save_pickled_model(bytes, user_id, name, upload_dir)          │
│                                                                │
│   - Safe filename: alphanumeric + dashes + timestamp           │
│   - Saves to UPLOAD_DIR/{user_id}/{name}_{ts}.pkl              │
│   - Returns (file_path, size_kb)                               │
└────────────────────────────────────────────────────────────────┘
```

## Security model

### What's blocked

**Builtins removed from the namespace:**

```
open, exec, eval, compile, globals, breakpoint, input
```

**Module prefixes blocked at import time** (via custom `__import__`):

```
subprocess, ctypes, multiprocessing, socket,
http, urllib, ftplib, telnetlib, smtplib, shutil, pathlib
```

The custom `__import__` is more robust than `sys.meta_path` blocking
alone because it also refuses modules that are already cached in
`sys.modules` — important when multiple notebook runs reuse the same
Python process.

### What's NOT blocked

- `os` — yes, `os` is available. Students need `os.getcwd()` etc. for
  debugging. If you run this in production, add `os` to the block list.
- `pickle` / `joblib.load` — these are needed by the convert flow itself.
- Network access via `sklearn.datasets.fetch_*` — needed to download
  OlivettiFaces etc.

### Timeout enforcement

On POSIX (Linux, macOS) we use `signal.SIGALRM` to enforce the wall-clock
limit. On Windows or non-main threads, `signal.alarm` is not available
and the timeout becomes advisory.

When the timeout fires, a `TimeoutError` is raised inside `exec` and
propagates out — the runner catches it, sets `timed_out=True`, and
returns whatever stdout was captured before the alarm fired.

### Limitations

!!! warning "This is not a security sandbox"
    The in-process sandbox is designed for **trusted / educational**
    deployments (classroom, internal hackathon, personal project). It is
    **not** sufficient for public-facing deployments with untrusted
    users. A determined attacker can escape via:

    - `os.system` (we didn't block `os`)
    - `pickle.loads` on a crafted payload
    - `numpy.fromfile` / `pandas.read_csv` to read arbitrary files
    - C-extension bugs in numpy / scipy

    For public deployments, layer Docker sandboxing on top. See
    `app/docker_runner/` and [Deployment → Docker](../deployment/docker.md).

## Framework detection

```python
def _detect_framework(model_obj):
    cls = type(model_obj)
    mod = (cls.__module__ or "").lower()
    name = cls.__name__.lower()

    if "torch" in mod:         return "pytorch"
    if "tensorflow" in mod or "keras" in mod: return "tensorflow"
    if "xgboost" in mod or name.startswith("xgb"): return "xgboost"
    if "lightgbm" in mod or name.startswith("lgbm") or name.startswith("booster"):
        return "lightgbm"
    if "onnx" in mod:          return "onnx"
    return "scikit-learn"  # fallback for any pickleable estimator
```

The fallback is correct for the vast majority of student-submitted
models — anything that quacks like an sklearn estimator lands here.

## Metric alias capture

When a student writes `acc = model.score(X_test, y_test)` (instead of
`accuracy = ...`), the platform still captures the metric. The aliases
tried, in priority order:

| Stored as    | Aliases accepted            |
| ------------ | --------------------------- |
| `accuracy`   | `accuracy`, `acc`           |
| `f1_score`   | `f1_score`, `f1`            |
| `rmse`       | `rmse`                      |
| `r2_score`   | `r2_score`, `r2`            |
| `mae`        | `mae`                       |

Only the first matching alias for each metric is captured; if both
`accuracy` and `acc` exist, `accuracy` wins.

## Testing

The sandbox is exercised by `scripts/smoke_test_v4.py`. Run it with:

```bash
cd /path/to/openbenchml
python scripts/smoke_test_v4.py
```

It verifies:

- All 17 built-in datasets load and split.
- Basic stdout capture works.
- Pre-imported libs are accessible.
- `open()` is blocked.
- `import subprocess` is blocked.
- `code_to_pickled_model` happy path trains + pickles a model.
- Missing `model` variable raises a helpful error.
- `save_pickled_model` writes a loadable file to disk.
- Timeout is enforced (2s test).
- Framework detection works for xgboost-style and sklearn-style classes.
