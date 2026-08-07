# Architecture Overview

OpenBenchML is a FastAPI application backed by SQLAlchemy (SQLite for dev, PostgreSQL for prod), with optional Celery + Redis for async job processing and Docker for sandboxed model execution.

## High-level diagram

```text
┌────────────────────────────────────────────────────────────────────┐
│                         Browser / CLI / API                          │
└──────────────────────────────┬─────────────────────────────────────┘
                               │  HTTP + WebSocket
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│                          FastAPI Application                         │
│ ┌────────────────────────────────────────────────────────────────┐ │
│ │ Middleware: CORS · GZip · Request timing · Security headers    │ │
│ └────────────────────────────────────────────────────────────────┘ │
│ ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│ │  Auth Routes    │  │  Model Routes   │  │  Benchmark Routes   │  │
│ │  /api/auth/*    │  │  /api/models/*  │  │  /api/jobs, /api/*  │  │
│ └─────────────────┘  └─────────────────┘  └─────────────────────┘  │
│ ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│ │  Leaderboard    │  │  Competitions   │  │  Comments + Notifs  │  │
│ │  /api/leaderboard│  │  /api/comp/*   │  │  /api/comments, etc │  │
│ └─────────────────┘  └─────────────────┘  └─────────────────────┘  │
│ ┌────────────────────────────────────────────────────────────────┐ │
│ │ WebSocket endpoints: /ws/benchmark · /ws/leaderboard · /ws/notif│ │
│ └────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────┬─────────────────────────────────────┘
                               │  SQLAlchemy ORM
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│                           Database (10 tables)                       │
│ users · models · datasets · benchmark_jobs · benchmark_results ·   │
│ leaderboard · api_keys · user_activity ·                            │
│ competitions · competition_submissions · teams · team_members ·     │
│ comments · notifications                                            │
└────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│                       Benchmark Engine (core)                        │
│ ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│ │   loader.py  │  │ evaluator.py │  │       metrics.py         │   │
│ │              │  │              │  │                          │   │
│ │ load_model() │→ │ evaluate_    │→ │ • Classification metrics │   │
│ │ load_dataset │  │   model()    │  │ • Regression metrics     │   │
│ │              │  │              │  │ • Performance (REAL P50/ │   │
│ │ • sklearn    │  │ • predict()  │  │   P95/P99 via np.percent)│   │
│ │ • pytorch    │  │ • proba      │  │ • Throughput, memory, CPU│   │
│ │ • onnx       │  │              │  │                          │   │
│ │ • tensorflow │  │              │  │                          │   │
│ │ • xgboost    │  │              │  │                          │   │
│ │ • lightgbm   │  │              │  │                          │   │
│ └──────────────┘  └──────────────┘  └──────────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
```

## Layered design

1. **Routes layer** (`app/routes/`) — HTTP handlers, request validation, response shaping. No business logic.
2. **Services layer** (`app/services/`) — Business logic: benchmark orchestration, auth, uploads.
3. **Benchmark engine** (`app/benchmark_engine/`) — Pure, framework-agnostic ML evaluation. No HTTP/DB concerns.
4. **Database layer** (`app/database/`) — SQLAlchemy models, session management, seeding.

This separation lets the benchmark engine be unit-tested in isolation (see `scripts/smoke_test_core.py`).

## Why the benchmark engine is "real"

The previous version of OpenBenchML had three critical bugs:

1. `load_dataset(None, ...)` was called for built-in datasets because `dataset.file_path` is `None`. The loader would crash with `AttributeError`.
2. `CaliforniaHousing` and `Diabetes` were seeded as datasets but missing from the loader's `_BUILTIN_DATASETS` registry.
3. Latency percentiles were `latency_ms * 1.5` and `latency_ms * 2.0` — fake approximations, not real measurements.

The new engine:

- Resolves built-in datasets via lowercase `name` (with `CaliforniaHousing` and `Diabetes` properly registered).
- Times each forward pass per-sample and computes true P50/P95/P99 with `numpy.percentile`.
- Adds warmup runs (5 by default), configurable timed runs (50 by default, clamped to [10, 200]).
- Captures `predict_proba` when available to compute AUC-ROC and log-loss.
- Always computes confusion matrix and classification report.

## Reproducibility

- All dataset splits use `random_state=42`.
- Stratification is automatic for classification (falls back to non-stratified if a class has <2 samples).
- Large datasets are subsampled deterministically (`CaliforniaHousing` → 2,000 rows).

## See also

- [Database Schema](database.md) — every table and column.
- [Benchmark Engine](engine.md) — deep-dive into `loader.py`, `evaluator.py`, `metrics.py`.
- [Real-time (WebSocket)](websocket.md) — the three WebSocket channels.
