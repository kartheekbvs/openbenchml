# Docker Deployment

OpenBenchML ships with a production-ready Dockerfile and docker-compose.yml. **Note: the Docker sandbox for running untrusted model code is not yet production-ready — see the "Sandbox status" note below.**

## Quick start (docker-compose)

```bash
docker-compose up --build
```

This starts:

- `app` — the FastAPI server on port 8000
- `worker` — Celery worker for async benchmark jobs (optional; the server can run benchmarks synchronously without it)
- `redis` — broker for Celery + cache
- `postgres` — PostgreSQL database (optional; SQLite works fine for small deployments)

## Single-container (no compose)

```bash
docker build -t openbenchml .

docker run -p 8000:8000 \
  -e USE_SQLITE=True \
  -e SECRET_KEY=$(openssl rand -hex 32) \
  -v $(pwd)/data:/app/uploads \
  openbenchml
```

## Environment variables

The Dockerfile respects the same env vars as the Python app. The most important ones for production:

```ini
USE_SQLITE=False
DATABASE_URL=postgresql://openbenchml:openbenchml@postgres:5432/openbenchml
REDIS_URL=redis://redis:6379/0
SECRET_KEY=<generate with: openssl rand -hex 32>
DEBUG=False
SECURE_COOKIES=True               # behind HTTPS
RATE_LIMIT_ENABLED=True
CORS_ORIGINS=https://yourdomain.com
```

## Volumes

| Mount | Purpose |
|-------|---------|
| `/app/uploads` | Uploaded model files (persist!) |
| `/app/openbenchml.db` | SQLite database (only if `USE_SQLITE=True`) |

## Health check

The Dockerfile includes a `HEALTHCHECK` that hits `/health` every 30 seconds. Use `docker ps` to see health status:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

## Sandbox status (important)

The `app/docker_runner/` directory contains scaffolding for running untrusted model code inside a Docker sandbox. **This is not yet production-ready** — the main benchmark engine runs models in-process for now, which is fine when you trust your users (e.g. internal team deployment) but not safe for public multi-tenant deployments.

For public deployments, you have two options:

1. **Wait for v3.1** which will land a proper gVisor / Firecracker-based sandbox.
2. **Run the benchmark worker on a separate, ephemeral VM** that's destroyed after each job (the Celery worker config supports this — see `app/workers/celery_worker.py`).

## Building for production

```bash
# Multi-stage build keeps the image small (~500 MB)
docker build -t openbenchml:prod --target production .

# Push to a registry
docker tag openbenchml:prod your-registry.com/openbenchml:v3
docker push your-registry.com/openbenchml:v3
```

## Next steps

- [Cloud deployment](cloud.md) — one-click deploy on Railway / Render / Fly.io
- [Local deployment](local.md) — for development without Docker
