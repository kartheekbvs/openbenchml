# Leaderboard API

## Global leaderboard

```
GET /api/leaderboard?dataset_id={id}&sort_by={sort}&limit={n}
```

| Param | Required | Description |
|-------|----------|-------------|
| `dataset_id` | no | Filter to a single dataset |
| `sort_by` | no | `score` (default), `latency`, or `size` |
| `limit` | no | Max rows (default 50, max 200) |

**Response (200):**

```json
[
  {
    "rank": 1,
    "previous_rank": 2,
    "model_name": "RandomForest Iris",
    "model_id": 1,
    "owner": "alice",
    "owner_id": 1,
    "dataset": "Iris",
    "dataset_id": 1,
    "score": 1.0,
    "latency_ms": 1.898,
    "latency_p50_ms": 1.869,
    "latency_p95_ms": 2.113,
    "latency_p99_ms": 2.575,
    "throughput_per_sec": 496.3,
    "model_size_kb": 37.36,
    "accuracy": 1.0,
    "f1_score": 1.0,
    "auc_roc": 1.0,
    "r2_score": null,
    "framework": "scikit-learn",
    "updated_at": "2025-01-15T12:34:57"
  }
]
```

---

## WebSocket: live updates

```
WS /ws/leaderboard
```

Whenever a benchmark completes and the leaderboard is recomputed, all subscribers receive:

```json
{
  "type": "leaderboard_update",
  "dataset_id": 1,
  "dataset_name": "Iris",
  "entries": 5,
  "timestamp": "2025-01-15T12:34:57.123000"
}
```

Clients should then re-fetch `/api/leaderboard?dataset_id=...` to get the updated rows.

---

## Sorting modes

- **`score`** (default) — Primary metric (accuracy for classification, R² for regression), highest first.
- **`latency`** — `latency_ms` ascending (fastest first). Filters out rows with no latency.
- **`size`** — `model_size_kb` ascending (smallest first). Filters out rows with no size.
