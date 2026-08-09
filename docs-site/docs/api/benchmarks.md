# Benchmarks API

## List jobs

```
GET /api/jobs?status={status}
```

| Param | Required | Description |
|-------|----------|-------------|
| `status` | no | Filter by status (`pending`, `running`, `completed`, `failed`) |

**Response (200):**

```json
[
  {
    "id": 1,
    "model_id": 1,
    "model_name": "RandomForest Iris",
    "dataset_id": 1,
    "dataset_name": "Iris",
    "status": "completed",
    "progress": 100,
    "submitted_at": "2025-01-15T12:34:56",
    "started_at": "2025-01-15T12:34:56",
    "finished_at": "2025-01-15T12:34:57",
    "error_message": null
  }
]
```

---

## Get benchmark results

```
GET /api/results/{job_id}
```

**Response (200):**

```json
{
  "job_id": 1,
  "model_id": 1,
  "model_name": "RandomForest Iris",
  "dataset_id": 1,
  "dataset_name": "Iris",
  "status": "completed",
  "progress": 100,
  "submitted_at": "2025-01-15T12:34:56",
  "finished_at": "2025-01-15T12:34:57",
  "error_message": null,
  "metrics": {
    "accuracy": 1.0,
    "precision": 1.0,
    "recall": 1.0,
    "f1_score": 1.0,
    "auc_roc": 1.0,
    "log_loss": 0.0521,
    "confusion_matrix": [[10, 0, 0], [0, 10, 0], [0, 0, 10]],
    "classification_report": { ... },
    "mae": null,
    "rmse": null,
    "r2_score": null,
    "latency_ms": 1.898,
    "latency_p50_ms": 1.869,
    "latency_p95_ms": 2.113,
    "latency_p99_ms": 2.575,
    "memory_mb": 0.268,
    "cpu_percent": 99.04,
    "model_size_kb": 37.36,
    "inference_count": 50,
    "throughput_per_sec": 496.3
  }
}
```

**Errors:**

- `404` — Job not found

---

## Submit a benchmark

```
POST /benchmark
Content-Type: application/x-www-form-urlencoded
Authorization: Bearer <token>

model_id=1&dataset_id=1
```

**Response (303):**

Redirects to `/results/{job_id}` on success. The job runs synchronously — by the time you receive the redirect, the benchmark is complete.

**Errors:**

- `400` — Invalid model or dataset ID
- `401` — Not authenticated
- `403` — Model not owned by you
- `404` — Model or dataset not found
- `409` — An active job already exists for this (model, dataset) pair
- `500` — Benchmark execution failed (error stored in `job.error_message`)

---

## Cancel a job

```
POST /jobs/{job_id}/cancel
Authorization: Bearer <token>
```

Only the model owner can cancel. Sets status to `failed` with `error_message="Job cancelled by user"`.

---

## WebSocket: live progress

```
WS /ws/benchmark
```

Subscribe to receive progress messages while a benchmark runs:

```json
{
  "type": "benchmark_progress",
  "job_id": 1,
  "progress": 40,
  "status": "running",
  "message": "Dataset loaded",
  "timestamp": "2025-01-15T12:34:56.789000"
}
```

Send `{"type": "ping"}` for keep-alive; receive `{"type": "pong"}`.
