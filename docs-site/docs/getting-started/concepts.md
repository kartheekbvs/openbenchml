# Concepts

OpenBenchML organises the world into four core entities. Understanding how they relate will make everything else click.

## The four core entities

```text
┌─────────┐  upload   ┌────────┐  benchmark on  ┌──────────┐  ranks  ┌──────────────┐
│  User   │ ────────► │ Model  │ ─────────────► │ Dataset  │ ──────► │ Leaderboard  │
└─────────┘           └────────┘                └──────────┘         └──────────────┘
                          │                                                 ▲
                          │ submit to                                       │
                          ▼                                                 │
                     ┌──────────────┐  best per user  ┌──────────────────┐  │
                     │ Competition  │ ──────────────► │ Comp. leaderboard│ ─┘
                     └──────────────┘                 └──────────────────┘
```

### User

A registered account. Users own models, submit to competitions, post comments, and receive notifications. Authentication is JWT-based; tokens can be passed as a cookie (HTML flow) or `Authorization: Bearer` header (CLI / API flow).

### Model

A serialized ML model file uploaded by a user. OpenBenchML supports six frameworks:

| Framework | File extensions | Loader |
|-----------|-----------------|--------|
| `scikit-learn` | `.pkl`, `.joblib` | `joblib.load` |
| `pytorch` | `.pt`, `.pth` | `torch.load(map_location="cpu")` |
| `onnx` | `.onnx` | `onnxruntime.InferenceSession` |
| `tensorflow` | `.h5`, `.pb` (SavedModel dir) | `tf.keras.models.load_model` |
| `xgboost` | `.json`, `.ubj`, `.bin`, `.joblib` | `xgb.Booster.load_model` or `joblib.load` |
| `lightgbm` | `.txt`, `.model`, `.joblib` | `lgb.Booster` or `joblib.load` |

Models are stored under `uploads/{user_id}/{filename}` on disk. Path traversal is prevented by resolving and validating against `UPLOAD_DIR`.

### Dataset

A benchmark dataset — either built-in (loaded from sklearn) or custom (loaded from a `.npz` / `.joblib` file).

Built-in datasets (lowercase names, no spaces):

| Name | Task | Samples | Features |
|------|------|---------|----------|
| `iris` | classification | 150 | 4 |
| `wine` | classification | 178 | 13 |
| `breastcancer` | classification | 569 | 30 |
| `digits` | classification | 1,797 | 64 |
| `californiahousing` | regression | 20,640 (subsampled to 2,000) | 8 |
| `diabetes` | regression | 442 | 10 |

Each dataset is split 80/20 (stratified for classification) with `random_state=42` for reproducibility.

### Benchmark Job

A single execution of "load model + load dataset + run predictions + measure metrics". Each job produces a `BenchmarkResult` row containing:

- **Classification metrics**: accuracy, precision, recall, F1, AUC-ROC, log-loss, confusion matrix, classification report
- **Regression metrics**: MAE, RMSE, R², MSE, explained variance, max error
- **Performance metrics**: latency mean / P50 / P95 / P99 / std / min / max, throughput, peak memory, CPU %, model size, inference count

### Competition

A time-boxed event tied to a specific dataset. Users submit models they've already uploaded; the platform auto-benchmarks each submission and records the score. The competition leaderboard shows each user's **best** submission.

Competitions have:

- A `slug` (URL-safe identifier)
- An evaluation metric (e.g. `accuracy`, `rmse`, `auc_roc`)
- A start and end timestamp (status auto-derives as `upcoming` / `live` / `ended`)
- A max-submissions-per-user limit
- Optional rules, prize, and discussion thread

## How a benchmark works (under the hood)

```text
POST /benchmark
     │
     ▼
create_benchmark_job(model_id, dataset_id)        ◄── validates model + dataset exist
     │                                                and no duplicate pending job
     ▼
run_benchmark(job_id):
     │
     ├── 5%   progress: starting
     ├── 20%  load_model(file_path, framework)        ◄── joblib / torch / onnx / tf
     ├── 40%  load_dataset(name or path, task_type)   ◄── sklearn loader or .npz/.joblib
     ├── 50%  evaluate_model(model, dataset, ...):
     │         ├── run batch predictions on X_test    ◄── captures y_pred + y_proba
     │         ├── compute_classification_metrics      ◄── acc/prec/recall/F1/AUC/logloss/cm
     │         └── compute_performance_metrics:        ◄── 5 warmup + 50 timed runs
     │             ├── for each timed run: time a forward pass
     │             ├── per-sample latencies = elapsed / batch_size
     │             ├── P50/P95/P99 = np.percentile(latencies, [50, 95, 99])
     │             ├── throughput = total_samples / total_time
     │             ├── memory = tracemalloc peak
     │             └── cpu = psutil process.cpu_percent samples
     ├── 85%  persist BenchmarkResult row
     ├── 100% update_leaderboard(dataset_id)         ◄── dense ranking
     │         broadcast WebSocket {"type": "leaderboard_update", ...}
     └─ done
```

## What makes percentiles "real"?

Many benchmarking tools compute P95 as `mean × 1.5` or similar approximations. OpenBenchML does it properly:

```python
# For each of N timed runs (default N=50):
t0 = time.perf_counter()
model.predict(batch)
elapsed_s = time.perf_counter() - t0
per_sample_ms = (elapsed_s * 1000) / batch_size
latencies.append(per_sample_ms)

# Then:
latencies = np.array(latencies)
p50 = np.percentile(latencies, 50)
p95 = np.percentile(latencies, 95)
p99 = np.percentile(latencies, 99)
```

This gives you statistically meaningful tail latencies that reflect what real users will experience.

## Real-time updates

OpenBenchML exposes three WebSocket endpoints:

| Endpoint | Purpose |
|----------|---------|
| `/ws/benchmark` | Live progress for a benchmark job (5% → 100%) |
| `/ws/leaderboard` | Push notifications when the leaderboard changes |
| `/ws/notifications` | In-app notifications (submission received, comment reply, etc.) |

Clients send `{"type": "ping"}` to keep the connection alive; the server responds with `{"type": "pong"}`.

## Authentication

JWT tokens are issued at login or registration. They can be passed in two ways:

1. **Cookie** — `access_token=<jwt>; HttpOnly` (set automatically by the HTML login flow)
2. **Header** — `Authorization: Bearer <jwt>` (used by the CLI and other API clients)

Both are accepted by every authenticated endpoint.

## Next steps

- [User Guide — Models](../user-guide/models.md)
- [User Guide — Benchmarks](../user-guide/benchmarks.md)
- [User Guide — Competitions](../user-guide/competitions.md)
