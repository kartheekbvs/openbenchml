# OpenBenchML

> Open-source ML model benchmarking platform with **Kaggle-style competitions**, **real per-sample latency percentiles**, and a **CLI** for terminal-driven workflows.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688.svg)](https://fastapi.tiangolo.com/)

## What is OpenBenchML?

OpenBenchML is a self-hostable platform for benchmarking machine-learning models across multiple frameworks (scikit-learn, PyTorch, ONNX, TensorFlow, XGBoost, LightGBM). Every benchmark produces **real per-sample latency percentiles** (P50 / P95 / P99), throughput, memory usage, and the full slate of classification/regression metrics — including AUC-ROC, log-loss, confusion matrix, and per-class report.

On top of the core engine, OpenBenchML ships Kaggle-style **competitions** with deadlines, leaderboards, threaded discussions, and real-time WebSocket updates.

## Why use it?

- **Real metrics, no fake percentiles.** Every latency number is measured per-sample over 50+ timed runs. P95/P99 are real numpy percentiles, not `mean × 1.5`.
- **Multi-framework.** Load and benchmark models from 6 frameworks with one unified API.
- **Kaggle-style competitions.** Create time-boxed competitions with custom evaluation metrics, submit models, and watch the leaderboard update in real time.
- **Real-time.** WebSocket streams for benchmark progress, leaderboard changes, and notifications.
- **CLI + API.** Drive the whole platform from the terminal via `openbenchml-cli` (npm) or programmatically via the REST API.
- **Self-hostable.** SQLite for dev, PostgreSQL for prod. Runs on Railway / Render / Fly.io / Docker.

## Quick links

- [Quick Start](getting-started/quickstart.md) — have a benchmark running in 60 seconds
- [CLI Reference](cli/index.md) — install the npm package and upload from your terminal
- [API Reference](api/index.md) — full REST API documentation
- [Architecture](architecture/overview.md) — how the benchmark engine works internally
- [Deployment](deployment/local.md) — run it locally or in the cloud

## Screenshot of the workflow

```text
┌──────────────┐    upload     ┌──────────────┐    benchmark   ┌──────────────┐
│  Train model │ ────────────► │  OpenBenchML │ ─────────────► │  Real metrics│
│  (.joblib)   │               │   storage    │                │  + leaderboard│
└──────────────┘               └──────────────┘                └──────────────┘
                                       │
                                       │ submit
                                       ▼
                               ┌──────────────┐
                               │ Competition  │
                               │  leaderboard │
                               └──────────────┘
```

## License

MIT © OpenBenchML contributors.
