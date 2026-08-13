---
title: OpenBenchML Notebook
emoji: 📓
colorFrom: indigo
colorTo: yellow
sdk: docker
app_port: 7860
pinned: true
license: mit
fullWidth: true
---

# OpenBenchML Notebook (HF Spaces deployment)

This Space hosts the **notebook + terminal + file workspace** portion of OpenBenchML.
The main app (landing page, auth, dashboard, leaderboard) runs on Render at
`openbenchml.onrender.com` and links here for notebook work.

## Why HF Spaces?

Render's free tier (512 MB RAM) cannot host multiple Python kernels — each user
session loads numpy/pandas/sklearn (~30-50 MB), and 3-4 concurrent users cause
OOM crashes. HF Spaces free CPU tier provides **16 GB RAM + 2 vCPU**, which
comfortably handles 50+ concurrent notebook sessions.

## How auth works across domains

1. User logs in on Render → Render sets an HttpOnly JWT cookie on
   `openbenchml.onrender.com`.
2. User clicks "Open Notebook" → Render signs a short-lived (5-min) one-time
   token and redirects to `openbenchml.hf.space/auth/bridge?token=...`.
3. HF Space validates the token (shared `SECRET_KEY` env var), sets its own
   HttpOnly cookie on `openbenchml.hf.space`, then redirects to `/notebook`.
4. No second login required.

## Environment variables (set in HF Spaces → Settings → Variables)

| Name | Required | Example | Notes |
|------|----------|---------|-------|
| `SECRET_KEY` | ✅ | (same as Render) | JWT signing key — must match Render for auth bridge |
| `SESSION_SECRET` | ✅ | (same as Render) | Session cookie signing |
| `DATABASE_URL` | optional | (blank) | If unset, uses SQLite at `/data/openbenchml.db` |
| `NOTEBOOK_MODE` | ✅ | `1` | Disables marketing routes on HF, only serves `/notebook` + `/api/notebook/*` |
| `RENDER_ORIGIN` | ✅ | `https://openbenchml.onrender.com` | For CORS — allows Render to call HF APIs |

## Persistent storage

HF Spaces mounts `/data` as a 10 GB persistent volume. The Dockerfile symlinks:
- `/app/openbenchml.db` → `/data/openbenchml.db` (user accounts — note: this is
  separate from Render's DB; users are synced via the auth bridge token)
- `/tmp/notebook_files/` → `/data/notebook_files/` (uploaded files, cloned repos)
- `/app/uploads/` → `/data/uploads/`
- `/app/logs/` → `/data/logs/`

## Local build & test

```bash
docker build -f Dockerfile.hf -t openbenchml-hf .
docker run -p 7860:7860 --env SECRET_KEY=test --env SESSION_SECRET=test openbenchml-hf
# Visit http://localhost:7860/health
```
