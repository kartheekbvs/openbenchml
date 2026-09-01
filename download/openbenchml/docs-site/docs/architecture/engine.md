# Benchmark Engine

The benchmark engine is the heart of OpenBenchML. It lives in `app/benchmark_engine/` and is intentionally decoupled from HTTP and the database — you can import it standalone and benchmark a model in three lines:

```python
from app.benchmark_engine.loader import load_model, load_dataset
from app.benchmark_engine.evaluator import evaluate_model

model = load_model("rf.joblib", "scikit-learn")
data = load_dataset("iris", task_type="classification")
metrics = evaluate_model(model_artifact=model, dataset=data, task_type="classification")
print(metrics)
```

## Module layout

```text
app/benchmark_engine/
├── __init__.py
├── loader.py       ← load_model + load_dataset
├── evaluator.py    ← evaluate_model orchestrator
└── metrics.py      ← compute_all_metrics + classification/regression/perf
```

## `loader.py`

### `load_model(file_path, framework) -> Any`

Dispatches to a framework-specific loader:

| Framework | Strategy |
|-----------|----------|
| `scikit-learn` | `joblib.load(path)` |
| `pytorch` | `torch.load(path, map_location="cpu", weights_only=False)`; if checkpoint is a dict, extracts `["model"]` or warns about `state_dict` |
| `onnx` | `onnxruntime.InferenceSession(path)` |
| `xgboost` | Tries `Booster.load_model` for `.json/.ubj/.bin`, falls back to `joblib.load` |
| `lightgbm` | Tries `Booster(model_file=path)` for `.txt/.model`, falls back to `joblib.load` |
| `tensorflow` | `tf.keras.models.load_model(path)` |

Raises `FileNotFoundError` if the file doesn't exist, `ValueError` if the framework is unknown, `RuntimeError` if deserialization fails.

### `load_dataset(dataset_name, task_type=None) -> dict`

Resolution order:

1. If `dataset_name` (lowercased, normalised) is in `_BUILTIN_DATASETS`, load via sklearn.
2. Else if `dataset_name` is an existing file path, load as a custom dataset.
3. Else raise `ValueError`.

Returns a dict with `X_train`, `X_test`, `y_train`, `y_test`, `task_type`, `feature_names`.

Built-in registry:

```python
_BUILTIN_DATASETS = {
    "iris": {"loader": load_iris, "task_type": "classification"},
    "wine": {"loader": load_wine, "task_type": "classification"},
    "breastcancer": {"loader": load_breast_cancer, "task_type": "classification"},
    "digits": {"loader": load_digits, "task_type": "classification"},
    "californiahousing": {
        "loader": fetch_california_housing,
        "task_type": "regression",
        "max_samples": 2000,   # deterministic subsample
    },
    "diabetes": {"loader": load_diabetes, "task_type": "regression"},
}
```

Splits are 80/20 with `random_state=42`, stratified for classification when possible.

## `evaluator.py`

### `evaluate_model(...) -> dict`

The orchestrator. Two calling conventions:

```python
# Service style (pre-loaded)
evaluate_model(model_artifact=model, dataset=data, task_type="classification")

# Standalone style (paths only)
evaluate_model(model_path="rf.joblib", framework="scikit-learn", dataset_name="iris")
```

Steps:

1. Resolve model (use artifact OR load from path).
2. Resolve dataset (use dict OR load by name).
3. Determine task type (explicit > dataset's > "classification").
4. Set a `SIGALRM` timeout (Unix only).
5. Run predictions via `_run_predictions_with_proba` — also captures `y_proba` when the framework exposes probabilities.
6. Call `compute_all_metrics(...)`.
7. Cancel alarm, return results dict.

### Probability extraction

For AUC-ROC and log-loss, the evaluator tries to extract predicted probabilities:

| Framework | Strategy |
|-----------|----------|
| scikit-learn / xgboost / lightgbm | `model.predict_proba(X)` if it exists |
| pytorch | `None` (would need softmax of logits — planned) |
| onnx | If output rows sum to 1.0, treat as probabilities |
| tensorflow | If rows sum to 1.0 → probabilities; else apply softmax to logits |

## `metrics.py`

### `compute_classification_metrics(y_true, y_pred, y_proba=None)`

Always computes: accuracy, precision (weighted), recall (weighted), F1 (weighted), confusion matrix, classification report.

Computes when `y_proba` is provided: AUC-ROC (binary or multi-class OVR weighted), log-loss.

### `compute_regression_metrics(y_true, y_pred)`

MAE, RMSE, MSE, R², explained variance, max error.

### `compute_performance_metrics(model, X_test, framework, model_path=None, warmup_runs=5, timed_runs=50, batch_size=1)`

The performance core. For each of `timed_runs` iterations:

```python
t0 = time.perf_counter()
_predict_single(model, batch_of_size_N, framework)
elapsed_s = time.perf_counter() - t0
per_sample_ms = (elapsed_s * 1000) / N
latencies.append(per_sample_ms)
```

Then:

```python
latencies = np.array(latencies)
latency_mean = np.mean(latencies)
latency_p50  = np.percentile(latencies, 50)
latency_p95  = np.percentile(latencies, 95)
latency_p99  = np.percentile(latencies, 99)
latency_std  = np.std(latencies)
```

Throughput = `total_samples_processed / total_loop_time`. Memory = `tracemalloc` peak. CPU = mean of `psutil.Process.cpu_percent()` samples.

`timed_runs` is clamped to `[10, 200]` so percentiles are statistically meaningful but benchmarks stay bounded.

### `compute_all_metrics(...)`

Combines the three: classification or regression metrics (based on `task_type`) + performance metrics. Sets missing keys to `None` so DB inserts don't break.

## Smoke test

Run `scripts/smoke_test_core.py` to verify the engine end-to-end without a server:

```bash
.venv/bin/python scripts/smoke_test_core.py
```

It trains a RandomForest on Iris, loads it via the loader, runs `evaluate_model`, and validates that P50 ≤ P95 ≤ P99.

## Why this design?

- **Pure functions, no side effects.** `compute_*` functions take numpy arrays and return dicts. Easy to unit-test.
- **No HTTP/DB coupling.** The engine can be imported by a notebook, a CLI, or a Celery task.
- **Real measurements.** No fake percentiles, no synthetic approximations. Every number is computed from real data.
- **Reproducible.** `random_state=42` everywhere, deterministic subsampling for large datasets.
