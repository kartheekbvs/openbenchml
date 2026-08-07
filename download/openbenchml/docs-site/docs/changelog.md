# Changelog

All notable changes to OpenBenchML are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to [Semantic Versioning](https://semver.org/).

## [3.0.0] — 2025-01-15

The "we actually fixed the core engine" release. This is a complete rewrite of the benchmark engine, the addition of Kaggle-style competitions, real-time WebSocket updates, a Node.js CLI, and a separate documentation site.

### Added

- **Real per-sample latency percentiles** (P50, P95, P99) computed via `numpy.percentile` over 50 timed runs. No more fake `latency * 1.5` approximations.
- **Advanced classification metrics**: AUC-ROC (binary + multi-class OVR), log-loss, confusion matrix, full per-class classification report.
- **Advanced regression metrics**: MSE, explained variance, max error (in addition to MAE, RMSE, R²).
- **Throughput measurement**: predictions per second over the timed loop.
- **CaliforniaHousing and Diabetes datasets** properly registered in the loader.
- **Kaggle-style competitions** with deadlines, custom evaluation metrics, per-user submission limits, best-submission tracking, and per-competition leaderboards.
- **Default competitions seeded**: "Iris Classification Challenge" (accuracy, 30 days) and "Diabetes Regression Sprint" (RMSE, 14 days).
- **Threaded comments** on models and competitions with reply notifications.
- **In-app notifications** with WebSocket push (`submission_received`, `comment_reply`).
- **Real-time WebSocket channels**: `/ws/benchmark` (job progress), `/ws/leaderboard` (leaderboard updates), `/ws/notifications` (notification push).
- **`openbenchml-cli` npm package** with full CLI: `login`, `upload`, `benchmark`, `submit`, `leaderboard`, `competitions`, `notifications`, and more.
- **Bearer token authentication** support (in addition to cookie auth) so the CLI and other API clients can authenticate.
- **Separate mkdocs-material documentation site** at `docs-site/` with 20+ pages covering installation, quickstart, concepts, user guide, CLI reference, API reference, architecture, and deployment.
- **End-to-end smoke tests** (`scripts/smoke_test_core.py`, `scripts/smoke_test_http.py`).

### Fixed

- **Critical bug**: `load_dataset(None, ...)` was called for built-in datasets because `dataset.file_path` is `None`. The benchmark engine would crash with `AttributeError` on every single benchmark attempt.
- **Critical bug**: `CaliforniaHousing` and `Diabetes` were seeded as datasets but missing from the loader's `_BUILTIN_DATASETS` registry — benchmarks against them would always fail.
- **Fake percentiles**: `latency_p95_ms` was `latency_ms * 1.5` and `latency_p99_ms` was `latency_ms * 2.0`. Now they're real percentiles.
- **Single-sample timing**: `compute_performance_metrics` used `min(X_test.shape[0], 1)` which always returned 1 — the timing was correct but the variable naming was misleading.
- **Navbar auth check**: `base.html` checked `current_user` but templates passed `user`, so the logged-in nav links never appeared. Fixed to use `user` consistently.
- **`get_current_user_from_cookie`** now accepts `Authorization: Bearer <token>` headers, not just cookies — the CLI couldn't authenticate before.

### Changed

- **Benchmark service** now passes the dataset **name** (lowercased) to `load_dataset` for built-in datasets, instead of `file_path=None`.
- **Performance metrics** now configurable via `warmup_runs` (default 5), `timed_runs` (default 50, clamped to [10, 200]), and `batch_size` (default 1).
- **`/api/results/{job_id}`** now exposes all metrics including `latency_p50_ms`, `latency_p95_ms`, `latency_p99_ms`, `throughput_per_sec`, `auc_roc`, `log_loss`, `confusion_matrix`, `classification_report`.
- **`/api/leaderboard`** now exposes `previous_rank`, `latency_p50_ms`, `latency_p95_ms`, `latency_p99_ms`, `throughput_per_sec`, `auc_roc`, `framework` for each row.
- **Database schema** expanded with 6 new tables: `competitions`, `competition_submissions`, `teams`, `team_members`, `comments`, `notifications`.

### Removed

- Nothing user-facing. Internal cleanup of dead code paths only.

### Migration notes

If you're upgrading from v2.x:

1. **Delete your existing SQLite database** (`rm openbenchml.db`) — the schema has changed and there are no Alembic migrations yet. The new schema will be auto-created on first startup.
2. **Upload your models again** — model file paths in the DB won't match if you've moved the project.
3. **Re-run benchmarks** — old results don't have the new percentile/throughput columns populated.

## [2.0.0] — 2024-12-01

- Initial public release with FastAPI + SQLAlchemy + Docker scaffolding.
- Basic model upload + benchmark flow (with the bugs fixed in 3.0.0).
- GitHub Pages landing page.

## [1.0.0] — 2024-10-15

- Initial prototype.
