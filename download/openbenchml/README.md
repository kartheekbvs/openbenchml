# OpenBenchML

**Open-source ML model benchmarking platform with Kaggle-style competitions, real per-sample latency percentiles, and a CLI.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green.svg)](https://fastapi.tiangolo.com)
[![npm](https://img.shields.io/badge/npm-openbenchml--cli-red.svg)](https://www.npmjs.com/package/openbenchml-cli)
[![Docs](https://img.shields.io/badge/docs-mkdocs-material-blue.svg)](https://kartheekbvs.github.io/openbenchml/)

OpenBenchML lets you upload ML models, benchmark them against standard datasets with **real per-sample latency percentiles** (no fake `mean × 1.5` approximations), and compete in **Kaggle-style competitions** with live leaderboards, threaded discussions, and in-app notifications.

Built with FastAPI + SQLAlchemy + WebSocket + Jinja2. SQLite for dev, PostgreSQL for prod. Optional Celery + Redis for async jobs. CLI in Node.js.

---

## What's new in v3.0

This release is a **complete rewrite of the benchmark engine** plus Kaggle-style features on top.

### The core engine — fixed

The previous version had three critical bugs that meant **every single benchmark failed**:

1. `load_dataset(None, ...)` was called for built-in datasets because `dataset.file_path` is `None`. The loader crashed with `AttributeError`.
2. `CaliforniaHousing` and `Diabetes` were seeded as datasets but missing from the loader's registry.
3. Latency percentiles were `latency_ms * 1.5` and `latency_ms * 2.0` — fake approximations.

All three are fixed. The engine now:

- Resolves built-in datasets via lowercase `name` (with CaliforniaHousing + Diabetes properly registered)
- Times each forward pass per-sample and computes **true P50 / P95 / P99** with `numpy.percentile` over 50 timed runs
- Captures `predict_proba` when available for AUC-ROC and log-loss
- Always computes confusion matrix and classification report
- Runs 5 warmup + 50 timed forward passes by default (configurable)

### Kaggle-style features (new)

- **Competitions** with deadlines, custom evaluation metrics, per-user submission limits
- **Per-competition leaderboards** that auto-update via WebSocket
- **Threaded comments** on models and competitions
- **In-app notifications** pushed over WebSocket
- **Default competitions seeded** (Iris Classification Challenge, Diabetes Regression Sprint)

### NPM CLI (new)

`openbenchml-cli` is published to npm. Drive the whole platform from the terminal:

```bash
npm install -g openbenchml-cli
openbenchml register --username alice --email alice@example.com --password '***'
openbenchml upload --model ./rf.joblib --name "My RF" --framework scikit-learn
openbenchml benchmark --model-id 1 --dataset-id 1
openbenchml submit --competition iris-classification-challenge --model-id 1
```

### Separate docs site (new)

Documentation moved to a separate mkdocs-material site at `docs-site/`. 20+ pages covering installation, quickstart, concepts, user guide, CLI reference, API reference, architecture, and deployment. Auto-deploys to GitHub Pages via `.github/workflows/docs.yml`.

---

## Features

- **Multi-framework**: scikit-learn, PyTorch, ONNX, TensorFlow, XGBoost, LightGBM
- **Real metrics**: accuracy, precision, recall, F1, AUC-ROC, log-loss, confusion matrix, classification report (classification) · MAE, RMSE, R², MSE, explained variance, max error (regression)
- **Real performance**: latency mean / P50 / P95 / P99 / std / min / max · throughput · memory · CPU · model size — all measured per-sample
- **6 built-in datasets**: Iris, Wine, BreastCancer, Digits, CaliforniaHousing (subsampled to 2k), Diabetes
- **Kaggle-style competitions** with deadlines, custom metrics, per-user submission limits, best-submission tracking
- **Real-time**: WebSocket streams for benchmark progress, leaderboard updates, and notifications
- **CLI**: full-featured npm package for terminal-driven workflows
- **REST API**: JWT auth (cookie OR Bearer), 30+ endpoints
- **Production-ready**: CORS, GZip, rate limiting, security headers, health checks, connection pooling
- **Self-hostable**: SQLite for dev, PostgreSQL for prod · Docker, Railway, Render, Fly.io configs included

---

## Quick start

### 1. Run the server

```bash
git clone https://github.com/kartheekbvs/openbenchml.git
cd openbenchml
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Server starts on `http://localhost:8000`. Open in browser or visit `/docs` for interactive API docs.

### 2. Install the CLI (optional but recommended)

```bash
npm install -g openbenchml-cli
```

### 3. Register, upload, benchmark

```bash
# Register
openbenchml register --username alice --email alice@example.com --password 'supersecret'

# Train a quick model
python -c "
import joblib
from sklearn.datasets import load_iris
from sklearn.ensemble import RandomForestClassifier
X, y = load_iris(return_X_y=True)
clf = RandomForestClassifier(n_estimators=50, random_state=42).fit(X, y)
joblib.dump(clf, 'rf.joblib')
"

# Upload and benchmark
openbenchml upload --model ./rf.joblib --name "RF Iris" --framework scikit-learn
openbenchml datasets
openbenchml benchmark --model-id 1 --dataset-id 1
```

Output:

```
Job 1 — COMPLETED
Model: RF Iris   Dataset: Iris

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
```

### 4. Submit to a competition

```bash
openbenchml competitions
openbenchml submit --competition iris-classification-challenge --model-id 1
```

---

## Project structure

```text
openbenchml/
├── app/
│   ├── main.py                  ← FastAPI app + 3 WebSocket endpoints
│   ├── config.py                ← All settings (env vars + defaults)
│   ├── database/                ← 14 SQLAlchemy models, session, seed
│   ├── routes/                  ← auth, models, datasets, benchmark,
│   │                              leaderboard, competitions, comments
│   ├── services/                ← auth, upload, benchmark orchestration
│   └── benchmark_engine/        ← loader, evaluator, metrics (the core)
├── templates/                   ← Jinja2 HTML templates
├── static/                      ← CSS, JS, images
├── scripts/
│   ├── smoke_test_core.py       ← Headless engine test (no server)
│   └── smoke_test_http.py       ← Full HTTP end-to-end test
├── packages/
│   └── openbenchml-cli/         ← NPM CLI package
├── docs-site/                   ← mkdocs-material documentation
├── requirements.txt
├── Dockerfile / docker-compose.yml
├── railway.toml / render.yaml / fly.toml
└── run.py
```

---

## Documentation

Full documentation at **<https://kartheekbvs.github.io/openbenchml/>** — covers installation, quickstart, concepts, CLI commands, REST API, architecture, deployment, and contributing.

Key pages:

- [Quick Start](https://kartheekbvs.github.io/openbenchml/getting-started/quickstart/)
- [CLI Reference](https://kartheekbvs.github.io/openbenchml/cli/commands/)
- [API Reference](https://kartheekbvs.github.io/openbenchml/api/)
- [Architecture — Benchmark Engine](https://kartheekbvs.github.io/openbenchml/architecture/engine/)
- [Deployment](https://kartheekbvs.github.io/openbenchml/deployment/local/)

---

## Smoke tests

Verify the engine works without a server:

```bash
.venv/bin/python scripts/smoke_test_core.py
```

End-to-end HTTP test (starts the server, registers, uploads, benchmarks):

```bash
.venv/bin/python scripts/smoke_test_http.py
```

---

## Deployment

| Target | Config file | Notes |
|--------|-------------|-------|
| Local | (none) | `python run.py` |
| Docker | `Dockerfile` + `docker-compose.yml` | `docker-compose up --build` |
| Railway | `railway.toml` | Auto-detects, add Postgres add-on |
| Render | `render.yaml` | Blueprint with web + Postgres + Redis |
| Fly.io | `fly.toml` | `fly launch` then `fly deploy` |

See the [deployment docs](https://kartheekbvs.github.io/openbenchml/deployment/local/) for details.

---

## Roadmap

- [ ] **Code submissions** — submit a Python script that trains + predicts, instead of a pre-trained model
- [ ] **Sandboxed execution** — gVisor / Firecracker for running untrusted model code
- [ ] **Custom dataset upload** — UI for uploading `.npz` / `.joblib` files
- [ ] **Team-based competitions** — expose the `Team` / `TeamMember` models in the UI
- [ ] **Alembic migrations** — proper schema migrations for production upgrades
- [ ] **PyTorch probability extraction** — softmax of logits for AUC-ROC
- [ ] **OAuth login** — GitHub / Google

---

## Contributing

PRs welcome! See [CONTRIBUTING](https://kartheekbvs.github.io/openbenchml/contributing/) for the development setup, code style, and PR workflow.

## License

MIT © OpenBenchML contributors
