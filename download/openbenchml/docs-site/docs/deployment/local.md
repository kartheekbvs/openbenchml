# Local Deployment

The fastest way to run OpenBenchML — single Python process, SQLite, no external dependencies.

## Prerequisites

- Python 3.10+
- ~500 MB disk for the venv + ML dependencies

## Steps

```bash
git clone https://github.com/kartheekbvs/openbenchml.git
cd openbenchml

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# (Optional) Install heavier ML frameworks you need
pip install torch onnxruntime tensorflow

python run.py
```

The server starts on `http://localhost:8000`.

## Configuration

Copy `.env.example` to `.env` and tweak:

```bash
cp .env.example .env
```

Key settings for local dev:

```ini
USE_SQLITE=True                    # Use SQLite (no PostgreSQL needed)
DEBUG=True                         # Verbose logging + SQL echo
SECRET_KEY=change-me-in-production
MAX_MODEL_SIZE_MB=500
BENCHMARK_TIMEOUT_SECONDS=300
RATE_LIMIT_ENABLED=True
```

The SQLite database file lives at `openbenchml.db` in the project root. Delete it to reset all data.

## Production-style local run

For a more production-like setup (no debug, GZip, rate limiting):

```ini
USE_SQLITE=True
DEBUG=False
RATE_LIMIT_ENABLED=True
SECURE_COOKIES=False              # True only behind HTTPS
```

Then run with multiple uvicorn workers:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Note: SQLite doesn't support multiple writers well. For real multi-worker production, switch to PostgreSQL (`USE_SQLITE=False`).

## Verifying it works

```bash
# Health check
curl http://localhost:8000/health

# Should return JSON with status=healthy, database=sqlite, etc.
```

Open `http://localhost:8000/` in your browser for the landing page, or `http://localhost:8000/docs` for interactive API docs.

## Logs

Logs go to stdout in the format:

```
2025-01-15 12:34:56 [INFO] app.main: POST /benchmark → 303 (208.3ms) [request-id]
```

To capture to a file:

```bash
python run.py 2>&1 | tee openbenchml.log
```

## Backups

For SQLite, just copy `openbenchml.db` and the `uploads/` directory:

```bash
cp openbenchml.db openbenchml.db.backup
tar czf uploads-backup.tar.gz uploads/
```

## Next steps

- [Docker deployment](docker.md) — containerised single-command setup
- [Cloud deployment](cloud.md) — Railway / Render / Fly.io
