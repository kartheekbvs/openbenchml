# Changelog

All notable changes to OpenBenchML are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to [Semantic Versioning](https://semver.org/).

## [4.0.0] — 2026-08-07

The "code → pickle → benchmark, all in the browser" release. Adds an in-browser Python notebook, a `/convert` flow that turns Python code into a benchmarkable MLModel without requiring a local Python install, expands the built-in dataset catalogue from 6 to 17, and adds real-time WebSocket snippets with basic syntax but powerful behaviour.

### Added

- **`/convert` flow (HTML + JSON API)** — paste Python code that trains a model, the platform executes it in a sandboxed namespace, pickles the resulting `model` variable, and registers it as an `MLModel`. No local Python or `.pkl` upload needed.
- **`/notebook` page (HTML + JSON API)** — single-cell in-browser Python playground with 6 one-click presets (Iris explore, train RF, confusion matrix, regression comparison, 5-fold CV, dataset survey). `np`, `pd`, `sklearn`, `scipy`, `joblib` + 12 `sklearn_*` shortcuts pre-imported.
- **`app/services/code_runner_service.py`** — unified sandboxed code execution service backing both `/convert` and `/notebook`. Custom `__import__` blocks `subprocess`, `socket`, `http`, `urllib`, `ctypes`, `shutil`, `pathlib`, `multiprocessing`, `ftplib`, `telnetlib`, `smtplib`. Strips `open`, `exec`, `eval`, `compile`, `globals`, `breakpoint`, `input` from builtins. SIGALRM-enforced timeout (30s notebook / 60s convert).
- **11 new built-in datasets** (catalogue grew from 6 to 17):
  - **OlivettiFaces** (face recognition, 400 samples × 4096 features)
  - **Linnerud** (multi-output regression, 20 samples × 3 features)
  - **MakeClassification** (synthetic, 1000×20, 3 classes)
  - **MakeMoons** (non-linear binary, 800×2)
  - **MakeCircles** (concentric circles, 800×2)
  - **MakeBlobs** (Gaussian clusters, 900×8, 4 centers)
  - **MakeHastie** (Hastie et al. binary, 2000×10)
  - **MakeRegression** (synthetic linear, 1000×15)
  - **MakeFriedman1** / **MakeFriedman2** / **MakeFriedman3** (non-linear regression)
- **2 new default competitions** seeded on first run: "Moons Non-Linear Showdown" (accuracy, 21 days) and "Friedman #1 Grand Prix" (RMSE, 30 days).
- **`/realtime` page** with copy-paste-ready WebSocket snippets for all 3 channels (benchmark, leaderboard, notifications) + a live preview that streams events as you browse.
- **CLI `init` command** — one-shot setup: prints `npm install -g openbenchml-cli`, walks through register/login, and shows a minimum-viable Python training example.
- **CLI `convert` command** — `openbenchml convert --file train.py --name "My RF"` turns a local Python file into a server-side MLModel with no Python install on the client needed.
- **CLI `notebook` command** — `openbenchml notebook --code "print(1+1)"` runs Python in the sandbox from the terminal.
- **CLI `watch` command** — `openbenchml watch --channel leaderboard --dataset-id 1` streams real-time WebSocket events to stdout.
- **CLI `datasets --more` flag** — verbose listing with full dataset descriptions.
- **`help` / `--help` / `-h` command** — full command catalogue with examples.
- **Framework auto-detection** in `/convert` from `type(model).__module__` (torch → pytorch, tensorflow/keras → tensorflow, xgboost → xgboost, lightgbm → lightgbm, onnx → onnx, fallback → scikit-learn).
- **Metric alias capture** — if your code leaves `acc` (not `accuracy`), `f1` (not `f1_score`), or `r2` (not `r2_score`) in scope, the platform still captures it as model metadata.
- **Docs pages**: `user-guide/convert.md`, `user-guide/notebook.md`, `user-guide/realtime.md`, `api/convert.md`, `api/notebook.md`, `architecture/sandbox.md`.
- **`scripts/smoke_test_v4.py`** — 29 unit tests covering all new functionality (all pass).

### Changed

- **App version** bumped to 4.0.0 (was 2.0.0 in the constant; the changelog below covers 3.0.0).
- **Navbar** now includes Convert, Notebook, and Real-time links.
- **CLI version** bumped to 4.0.0. `package.json` keywords expanded with `notebook`, `convert-code`, `realtime`, `websocket`, `student`, `education`.
- **`_BUILTIN_DATASETS` registry** in `loader.py` now supports synthetic generators (return `(X, y)` tuples) via a `params` dict, in addition to classic Bunch-returning loaders and fetchers.
- **`list_builtin_datasets()`** new public function in `loader.py` for enumerating the catalogue.
- **`seed.py`** mirrors the new 17-dataset catalogue and seeds 4 default competitions (was 2).

### Fixed

- **`fetch_olivetti_faces()` and `fetch_california_housing()`** were not in the loader registry — now properly registered with `max_samples` caps for fast benchmarks.
- **CLI bin script** could crash on sync commands (e.g. `help`) because `main()` returned an int but the bin expected a Promise. Normalised via `Promise.resolve(result)`.
- **`TimeoutError`** was being caught by the inner `except Exception` block in `run_code`, preventing `timed_out=True` from being set. Now re-raised explicitly.
- **Sandbox `__import__`** now blocks modules that are already cached in `sys.modules` — previously, `subprocess` could be imported if anything else in the process had imported it first.

### Migration notes

If you're upgrading from v3.0.0:

1. **Delete your existing SQLite database** (`rm openbenchml.db`) — the seed now inserts 17 datasets and 4 competitions instead of 6 and 2. The schema itself is unchanged.
2. **Reinstall the CLI** — `npm install -g openbenchml-cli@4.0.0` to get the new `init`, `convert`, `notebook`, `watch` commands.
3. **Try the new flow** — visit `/notebook` for a no-setup Python playground, or `/convert` to turn code into a benchmarkable model without uploading a file.

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
