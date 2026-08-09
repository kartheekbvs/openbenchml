# Installation

OpenBenchML has two parts:

1. **The server** — a FastAPI app you run locally or in the cloud.
2. **The CLI** (optional) — a Node.js command-line client for terminal-driven workflows.

## Server (Python)

### Prerequisites

- Python 3.10 or newer
- `pip` (or `pipx`)

### Steps

```bash
# 1. Clone the repo
git clone https://github.com/kartheekbvs/openbenchml.git
cd openbenchml

# 2. Create a virtual env
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) Install the heavy ML frameworks you actually use.
#    The base install ships scikit-learn + xgboost + lightgbm so you can
#    start immediately. Add PyTorch / ONNX / TensorFlow as needed:
pip install torch            # for .pt models
pip install onnxruntime      # for .onnx models
pip install tensorflow       # for .h5 / SavedModel

# 5. Run the server
python run.py
# or
uvicorn app.main:app --reload --port 8000
```

The server starts on `http://localhost:8000`. Open it in your browser to see the landing page, or visit `http://localhost:8000/docs` for the interactive API docs.

### Configuration

All settings are environment variables with sensible defaults. Copy `.env.example` to `.env` and tweak as needed.

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_SQLITE` | `True` | Use SQLite (dev) or PostgreSQL (prod). |
| `DATABASE_URL` | `postgresql://...` | PostgreSQL URL (used when `USE_SQLITE=False`). |
| `SECRET_KEY` | (change me!) | JWT signing secret. |
| `DEBUG` | `True` | Enable verbose logging & SQL echo. |
| `MAX_MODEL_SIZE_MB` | `500` | Max upload size in MB. |
| `BENCHMARK_TIMEOUT_SECONDS` | `300` | Per-benchmark hard timeout. |
| `RATE_LIMIT_ENABLED` | `True` | Enable API rate limiting. |

## CLI (Node.js)

The CLI is published to npm as `openbenchml-cli`.

```bash
# Global install
npm install -g openbenchml-cli

# or use it ad-hoc with npx
npx openbenchml-cli --help
```

Requires Node.js 16+ (Node 18+ recommended for native `fetch`).

## Verifying the install

After starting the server:

```bash
# Health check
curl http://localhost:8000/health

# List datasets (no auth required)
curl http://localhost:8000/api/datasets
```

After installing the CLI:

```bash
openbenchml --version
openbenchml --help
```

## Next steps

- [Quick Start](quickstart.md) — upload a model and run a benchmark in 60 seconds.
- [Concepts](concepts.md) — understand the platform's mental model.
