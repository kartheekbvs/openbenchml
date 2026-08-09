# Benchmarks

A benchmark is the core unit of evaluation: load a model, load a dataset, run predictions, measure everything.

## Running a benchmark

### Via the CLI

```bash
openbenchml benchmark --model-id 1 --dataset-id 1
```

The CLI submits the benchmark, waits for it to complete, and prints the full result:

```
Job 1 — COMPLETED
Model: RandomForest Iris   Dataset: Iris

── ML Metrics ──────────────────────────────
  Accuracy:        100.00%
  Precision:       1.0000
  Recall:          1.0000
  F1 Score:        1.0000
  AUC-ROC:         1.0000
  Log Loss:        0.0521

── Performance (real per-sample percentiles) ──
  Latency mean:    1.898 ms
  Latency p50:     1.869 ms
  Latency p95:     2.113 ms
  Latency p99:     2.575 ms
  Throughput:      496.3 /s
  Memory:          0.27 MB
  Model size:      37.4 KB
  Inferences:      50
```

### Via the API

```bash
# Submit (returns a 303 redirect to /results/{job_id})
curl -X POST http://localhost:8000/benchmark \
  -H "Authorization: Bearer $TOKEN" \
  -d "model_id=1&dataset_id=1"

# Fetch results
curl http://localhost:8000/api/results/1 -H "Authorization: Bearer $TOKEN"
```

### Via the web UI

Browse to `/benchmark` while logged in. Pick one of your models, pick a dataset, hit "Run Benchmark". You'll be redirected to the results page when it finishes.

## What gets measured

### Classification metrics

| Metric | When | Notes |
|--------|------|-------|
| `accuracy` | Always | `sklearn.metrics.accuracy_score` |
| `precision` | Always | `average="weighted"` |
| `recall` | Always | `average="weighted"` |
| `f1_score` | Always | `average="weighted"` |
| `auc_roc` | When `predict_proba` available | Multi-class uses `ovr` weighted |
| `log_loss` | When `predict_proba` available | |
| `confusion_matrix` | Always | Stored as JSON 2D array |
| `classification_report` | Always | Per-class precision / recall / F1 |

### Regression metrics

| Metric | When |
|--------|------|
| `mae` | Always |
| `rmse` | Always |
| `mse` | Always |
| `r2_score` | Always |
| `explained_variance` | Always |
| `max_error` | Always |

### Performance metrics

| Metric | How |
|--------|-----|
| `latency_ms` | Mean per-sample latency over 50 timed runs |
| `latency_p50_ms` | True 50th percentile of per-sample latencies |
| `latency_p95_ms` | True 95th percentile |
| `latency_p99_ms` | True 99th percentile |
| `latency_std_ms` | Std dev of per-sample latencies |
| `latency_min_ms` / `latency_max_ms` | Min / max |
| `throughput_per_sec` | Total samples processed / total time |
| `memory_mb` | Peak memory delta via `tracemalloc` |
| `cpu_percent` | Mean of `psutil.Process.cpu_percent()` samples |
| `model_size_kb` | File size on disk |
| `inference_count` | Total samples processed during timed loop |

## How latencies are measured

For each of 50 timed runs:

```python
t0 = time.perf_counter()
model.predict(batch_of_size_1)
elapsed_s = time.perf_counter() - t0
per_sample_ms = elapsed_s * 1000  # / 1 since batch_size = 1
latencies.append(per_sample_ms)
```

Then percentiles are computed with `np.percentile(latencies, [50, 95, 99])`. Five warmup runs (untimed) let the runtime JIT/warm caches first.

## Job lifecycle

```
pending → running → completed
                  ↘ failed
```

- `pending` — job created, not yet started
- `running` — model & dataset loading, predictions running
- `completed` — metrics persisted, leaderboard updated, WebSocket broadcast sent
- `failed` — error message stored in `error_message` field

You can cancel a pending or running job via `POST /jobs/{id}/cancel`.

## Real-time progress

While a benchmark runs, the server broadcasts WebSocket messages on `/ws/benchmark`:

```json
{"type": "benchmark_progress", "job_id": 1, "progress": 40, "status": "running", "message": "Dataset loaded"}
```

Clients can subscribe and show a live progress bar. The CLI doesn't use this (it just polls the result), but the web UI does.

## Viewing past results

```bash
# CLI
openbenchml results 1     # show full results for job 1
openbenchml job 1         # show job status only

# API
curl http://localhost:8000/api/results/1
curl http://localhost:8000/api/jobs
```

## Comparing models

The web UI has a `/compare` page that lets you select 2–3 of your models and see their best result side-by-side. Useful for picking which model to submit to a competition.

## What's next?

- [Leaderboard](leaderboard.md) — see how your model ranks
- [Competitions](competitions.md) — submit your model to a Kaggle-style event
