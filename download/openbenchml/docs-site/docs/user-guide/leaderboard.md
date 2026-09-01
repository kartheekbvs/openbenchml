# Leaderboard

The global leaderboard ranks every model on every dataset it has been benchmarked against. The primary score is **accuracy** for classification datasets and **R²** for regression datasets.

## Viewing the leaderboard

```bash
# CLI — global, sorted by score
openbenchml leaderboard

# Filter by dataset
openbenchml leaderboard --dataset-id 1

# Sort by latency (fastest first) or model size (smallest first)
openbenchml leaderboard --sort-by latency
openbenchml leaderboard --sort-by size
```

```bash
# API
curl http://localhost:8000/api/leaderboard
curl 'http://localhost:8000/api/leaderboard?dataset_id=1&sort_by=latency&limit=20'
```

### Via the web UI

- `/leaderboard` — sorted by score (default)
- `/leaderboard/fastest` — sorted by latency
- `/leaderboard/smallest` — sorted by model size

Each row shows rank, model name, owner, dataset, score, latency, and model size. The current user's rows are highlighted.

## Ranking algorithm

Dense ranking is applied. Models with the same score get the same rank, and the next rank skips accordingly:

| Score | Rank |
|-------|------|
| 0.98 | 1 |
| 0.98 | 1 |
| 0.95 | 2 |
| 0.93 | 3 |

## Rank changes

When a leaderboard is recomputed, each entry's previous rank is preserved in `previous_rank`. This lets the UI show "▲ 2" or "▼ 1" indicators when a model moves up or down.

## Real-time updates

When a benchmark completes and the leaderboard is recomputed, the server broadcasts on `/ws/leaderboard`:

```json
{
  "type": "leaderboard_update",
  "dataset_id": 1,
  "dataset_name": "Iris",
  "entries": 5,
  "timestamp": "2025-01-15T12:34:56.789000"
}
```

Subscribing clients can refresh their view automatically.

## What's next?

- [Competitions](competitions.md) — competition-specific leaderboards
- [API Reference — Leaderboard](../api/leaderboard.md)
