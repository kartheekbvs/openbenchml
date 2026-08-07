# Competitions

Competitions are Kaggle-style events: a time-boxed window where users submit models, get auto-benchmarked on a fixed dataset, and compete for the top spot on the competition leaderboard.

## Default competitions

OpenBenchML ships with two seeded competitions:

| Slug | Dataset | Metric | Duration |
|------|---------|--------|----------|
| `iris-classification-challenge` | Iris | accuracy | 30 days |
| `diabetes-regression-sprint` | Diabetes | rmse | 14 days |

Both are marked as `live` on first run (start time is 1 hour in the past).

## Competition lifecycle

```
upcoming → live → ended
```

- `upcoming` — `now < starts_at`
- `live` — `starts_at <= now < ends_at`
- `ended` — `now >= ends_at`

Status is recomputed lazily when a competition is viewed or fetched via API.

## Listing competitions

```bash
# CLI
openbenchml competitions                         # all
openbenchml competitions --status live           # only live ones

# API
curl http://localhost:8000/api/competitions
curl 'http://localhost:8000/api/competitions?status=live'
```

## Viewing a competition

```bash
# CLI
openbenchml competition iris-classification-challenge

# API (includes the leaderboard)
curl http://localhost:8000/api/competitions/iris-classification-challenge

# API (leaderboard only — useful for live updates)
curl http://localhost:8000/api/competitions/iris-classification-challenge/leaderboard
```

The web UI lives at `/competitions/{slug}` and shows:

- Title, description, rules, prize
- Live countdown timer (when status = `live`)
- Live leaderboard (auto-refreshes via WebSocket)
- Submission form (pick one of your models + optional note)
- Discussion thread

## Submitting a model

### Via the CLI

```bash
openbenchml submit \
  --competition iris-classification-challenge \
  --model-id 1 \
  --note "First attempt — default RF hyperparams"
```

The CLI auto-benchmarks your model on the competition's dataset, records the score, and shows the updated leaderboard.

### Via the API

```bash
curl -X POST http://localhost:8000/competitions/iris-classification-challenge/submit \
  -H "Authorization: Bearer $TOKEN" \
  -d "model_id=1&submission_note=First attempt"
```

### What happens on submit?

1. The competition's `status` is checked — must be `live`.
2. The model is verified to belong to the submitter.
3. The user's existing submission count is checked against `max_submissions_per_user`.
4. A benchmark job is created and run synchronously.
5. The score is extracted from the result using the competition's `evaluation_metric` (e.g. `accuracy`, `rmse`).
6. A `CompetitionSubmission` row is created.
7. The competition leaderboard is recomputed — each user's **best** submission is marked with `is_best=True`.
8. A `submission_received` notification is sent to the user.

## Best submission logic

For each (competition, user) pair, only the best submission counts toward the leaderboard. "Best" depends on the metric:

- Higher is better: `accuracy`, `f1_score`, `auc_roc`, `r2_score`
- Lower is better: `rmse`, `mae`, `latency_ms`, `log_loss`

## Creating a competition

Only admins can create competitions. Promote a user to admin:

```bash
# SQLite
sqlite3 openbenchml.db "UPDATE users SET is_admin=1 WHERE username='alice';"

# PostgreSQL
psql -c "UPDATE users SET is_admin=1 WHERE username='alice';"
```

Then visit `/competitions/create` in the browser, or use the form via the API.

## Real-time leaderboard

The competition detail page subscribes to `/ws/leaderboard` and refreshes the leaderboard table automatically whenever any benchmark completes on the competition's dataset.

## What's next?

- [Discussions](discussions.md) — comment threads on models and competitions
- [API Reference — Competitions](../api/competitions.md)
