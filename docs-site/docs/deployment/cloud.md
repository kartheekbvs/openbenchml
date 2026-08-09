# Cloud Deployment

OpenBenchML ships with config files for three cloud platforms. Pick the one that fits your workflow.

## Railway

[Railway](https://railway.app) is the easiest option — single click, managed PostgreSQL + Redis, autoscaling.

1. Push the repo to GitHub.
2. Go to [railway.app/new](https://railway.app/new) and select your repo.
3. Railway auto-detects the `railway.toml` config.
4. Add a PostgreSQL database (Railway offers it as a one-click add-on).
5. Set environment variables:
   - `DATABASE_URL` (auto-injected by Railway's PostgreSQL add-on)
   - `SECRET_KEY` (generate with `openssl rand -hex 32`)
   - `USE_SQLITE=False`
   - `DEBUG=False`
6. Deploy. Railway assigns a public URL like `openbenchml-production.up.railway.app`.

The `railway.toml` file specifies Python 3.11, the start command, and health check path.

## Render

[Render](https://render.com) is similar to Railway with a generous free tier.

1. Push the repo to GitHub.
2. Go to [render.com](https://render.com) → New → Blueprint.
3. Select your repo. Render reads the `render.yaml` blueprint.
4. The blueprint defines:
   - A web service (the FastAPI app)
   - A managed PostgreSQL database
   - A managed Redis instance
5. Set `SECRET_KEY` in the Render dashboard.
6. Deploy. Render assigns a URL like `openbenchml.onrender.com`.

The `render.yaml` includes health checks, auto-deploy from `main`, and resource sizing.

## Fly.io

[Fly.io](https://fly.io) is great for global edge deployment.

1. Install the Fly CLI: `curl -L https://fly.io/install.sh | sh`
2. Authenticate: `fly auth login`
3. Launch: `fly launch` (Fly reads `fly.toml`)
4. Create a PostgreSQL cluster: `fly pg create`
5. Set the `DATABASE_URL` secret: `fly secrets set DATABASE_URL=postgres://...`
6. Deploy: `fly deploy`
7. Open: `fly open`

The `fly.toml` configures:
- Internal port 8000
- Auto-scaling (min 1, max 3 VMs)
- Health check at `/health`
- Persistent volume for `uploads/` at `/app/uploads`

## Environment variables (all platforms)

| Variable | Required | Example |
|----------|----------|---------|
| `DATABASE_URL` | yes (prod) | `postgresql://user:pass@host:5432/db` |
| `SECRET_KEY` | yes | `openssl rand -hex 32` |
| `USE_SQLITE` | yes | `False` (use PostgreSQL) |
| `DEBUG` | yes | `False` |
| `REDIS_URL` | optional | `redis://host:6379/0` |
| `CORS_ORIGINS` | optional | `https://yourdomain.com` |
| `SECURE_COOKIES` | optional | `True` (behind HTTPS) |
| `RATE_LIMIT_ENABLED` | optional | `True` |

## Custom domain

All three platforms support custom domains via DNS CNAME. Refer to each platform's docs:

- Railway: [Custom domains](https://docs.railway.app/deployment/custom-domains)
- Render: [Custom domains](https://render.com/docs/custom-domains)
- Fly.io: [Custom domains](https://fly.io/docs/app-guides/custom-domains-with-fly)

Once your domain is wired up, set:

```ini
CORS_ORIGINS=https://yourdomain.com
APP_URL=https://yourdomain.com
SECURE_COOKIES=True
```

## Cost comparison (rough, as of 2025)

| Platform | Free tier | Paid |
|----------|-----------|------|
| Railway | $5 credit/month | Hobby $5/mo, Pro usage-based |
| Render | 750 hours/month (free web service) | Starter $7/mo per service |
| Fly.io | 3 shared-cpu VMs free | Pay-as-you-go from ~$2/mo |

For a low-traffic deployment, Render's free tier is the cheapest path.

## Database migrations

The first time you deploy with a fresh database, `init_db()` (called at app startup) creates all tables automatically. For schema changes after that, you'll need Alembic migrations (planned for v3.1).

## Backups

- **PostgreSQL**: All three platforms offer automated daily backups on paid plans.
- **Uploads**: Use the platform's persistent volume feature. For mission-critical deployments, sync `uploads/` to S3 via a cron job.

## Next steps

- [Local deployment](local.md) — for development
- [Docker deployment](docker.md) — self-hosted Docker
