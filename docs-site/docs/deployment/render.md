# Deploy OpenBenchML to Render (Supabase backend)

This guide walks you through deploying OpenBenchML v4.1 to **Render**,
using your existing **Supabase** Postgres database (project
`fzwvxesrtdilljgrntpw`) as the storage backend — the same one used by
`fastapiproject.git`.

Total time: ~15 minutes (most of it is Render building the image).

---

## Prerequisites

1. **Render account** — sign up at <https://render.com> (free tier works
   for testing; the `starter` plan ($7/mo) is recommended for the web
   service because the free tier sleeps after 15 min of inactivity).
2. **Supabase account** with the project `fzwvxesrtdilljgrntpw`
   (or any Supabase project — you'll just need to change the project ref).
3. **Supabase database password** — the password you set when you
   created the Supabase project. If you don't remember it:
   1. Go to <https://supabase.com/dashboard/project/fzwvxesrtdilljgrntpw/settings/database>
   2. Click **Reset database password**
   3. Save the new password somewhere safe — you'll paste it into Render.
4. **GitHub repo** with the OpenBenchML code pushed (covered in step 1
   below).

---

## Step 1 — Push the code to GitHub

If you haven't already pushed the v4.1 code:

```bash
cd /path/to/openbenchml

# Add your GitHub remote (replace with your actual repo URL)
git remote add origin https://github.com/<your-username>/openbenchml.git

# Stage everything
git add -A

# Commit
git commit -m "v4.1: Supabase backend + olive/teal UI palette + Render deploy config"

# Push
git push -u origin main
```

> The repo must be public OR you must connect Render to a private repo
> via the Render dashboard.

---

## Step 2 — Open Render's "New Blueprint" wizard

1. Log in to <https://dashboard.render.com>.
2. Click **New +** → **Blueprint**.
3. Pick the GitHub repo you just pushed.
4. Render will detect `render.yaml` at the repo root and show you
   the services it will create:
   - **openbenchml** (web service, Python)
   - **openbenchml-redis** (Redis)
5. Pick a name for the blueprint (e.g. `openbenchml-prod`).
6. Pick a region (choose the same region as your Supabase project for
   lowest latency — Supabase default is `us-east-1`).

> **No databases will be created** — we're using Supabase instead.
> This keeps all your data co-located with `fastapiproject`'s data, as
> requested.

---

## Step 3 — Fill in the secret env vars

On the "Apply Blueprint" screen, Render will prompt you for any env var
marked `sync: false`. There's only one:

| Env var                    | What to paste                                              |
| -------------------------- | ---------------------------------------------------------- |
| `SUPABASE_DB_PASSWORD`     | Your Supabase project database password (from prerequisite 3) |

The other env vars (`SUPABASE_PROJECT_REF`, `SUPABASE_URL`,
`SUPABASE_ANON_KEY`, `USE_SQLITE=False`, `SECRET_KEY`, `REDIS_URL`,
`APP_URL`, etc.) are filled in automatically by `render.yaml`.

Click **Apply**.

---

## Step 4 — Wait for the first build (~5 min)

Render will now:

1. Pull the repo.
2. Run `pip install -r requirements.txt` (this installs FastAPI,
   SQLAlchemy, scikit-learn, xgboost, lightgbm, supabase, etc.).
3. Run `./start.sh` (which assembles `DATABASE_URL` from
   `SUPABASE_PROJECT_REF` + `SUPABASE_DB_PASSWORD`, then launches
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2`).
4. Hit `/health` to confirm the app is up.

You can watch the build logs in real-time from the Render dashboard.
On the **starter** plan the first build typically takes 4–6 minutes.

When you see:

```
[start.sh] Assembled DATABASE_URL from SUPABASE_PROJECT_REF + SUPABASE_DB_PASSWORD
[start.sh] Pooler host: aws-0-us-east-1.pooler.supabase.com:5432
[start.sh] USE_SQLITE=False
[start.sh] DATABASE_URL is set: yes
[start.sh] Starting uvicorn on 0.0.0.0:10000…
INFO:     Uvicorn running on http://0.0.0.0:10000
INFO:     Application startup complete.
```

…you're live.

---

## Step 5 — Verify the deployment

1. Open the Render web service URL (something like
   `https://openbenchml-xxxx.onrender.com`).
2. Visit `/health` — you should see JSON with
   `"database_status": "connected"`.
3. Visit `/docs` — interactive Swagger UI.
4. Visit `/convert` — log in (or register), paste the sample code, hit
   **Convert & Save Model**. The model should now be saved to your
   Supabase `models` table.
5. Visit `/realtime` — the live WebSocket preview should connect
   successfully.

---

## Step 6 — Set up the database tables (one-time)

On the very first deploy, OpenBenchML auto-creates all tables in your
Supabase database via SQLAlchemy's `Base.metadata.create_all()`. You
don't need to run any migrations.

To verify the tables were created:

1. Go to <https://supabase.com/dashboard/project/fzwvxesrtdilljgrntpw/editor>
2. You should see tables:
   - `users`, `models`, `datasets`, `benchmark_jobs`, `benchmark_results`,
     `leaderboard`, `api_keys`, `user_activity`,
     `competitions`, `competition_submissions`, `teams`, `team_members`,
     `comments`, `notifications`

If you ever need to reset:

```sql
-- In Supabase SQL Editor
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
-- then restart the Render service to re-create everything
```

---

## Troubleshooting

### "connection refused" or "password authentication failed"

- Double-check `SUPABASE_DB_PASSWORD` in Render → Environment.
- Make sure you're using the **database password**, not the anon key.
- Verify the pooler host: visit
  <https://supabase.com/dashboard/project/fzwvxesrtdilljgrntpw/settings/database>
  and look at the **Connection string** section. The host should match
  what `start.sh` logged. If your Supabase project is in a different
  region, set `SUPABASE_POOLER_REGION` in Render env vars
  (e.g. `aws-0-eu-central-1`).

### "relation does not exist"

- The first deploy should auto-create tables. If it didn't:
  1. Render dashboard → your `openbenchml` web service → **Shell**.
  2. Run: `python -c "from app.database.db import init_db; init_db()"`.
  3. Restart the service.

### Free-tier sleep

The Render free tier sleeps the web service after 15 min of inactivity.
First request after sleep takes ~30s to wake. To avoid this, upgrade to
the **starter** plan ($7/mo) — it never sleeps.

### WebSocket disconnects

Render's load balancer closes idle WebSocket connections after 100s.
The `/realtime` page already implements auto-reconnect. For long-lived
CLI `watch` sessions, consider running your own keep-alive ping
(`ws.send(JSON.stringify({type:"ping"}))` every 30s).

### CSS / static files 404

If the UI looks unstyled, the `static/` directory isn't being served.
Verify by visiting `https://your-app.onrender.com/static/css/style.css`
— you should see CSS. If not, check that the `static/` folder is
committed to git (it should be — there's no `.gitignore` entry for it).

---

## Environment variables reference

Full list of env vars the app respects (all optional except where noted):

| Var                          | Required | Default                                          | Notes                                                                 |
| ---------------------------- | -------- | ------------------------------------------------ | --------------------------------------------------------------------- |
| `SUPABASE_PROJECT_REF`       | no       | `fzwvxesrtdilljgrntpw`                           | Supabase project reference. Override to use a different project.      |
| `SUPABASE_DB_PASSWORD`       | **yes**  | (none)                                           | Supabase database password. **Set this in Render.**                   |
| `SUPABASE_POOLER_REGION`     | no       | `aws-0-us-east-1`                                | Supabase pooler region (e.g. `aws-0-eu-central-1`).                  |
| `SUPABASE_POOLER_PORT`       | no       | `5432`                                           | Use `6543` for the transaction pooler.                               |
| `DATABASE_URL`               | no       | (auto-assembled)                                 | Full Postgres URL. If set, overrides the auto-assembly above.        |
| `USE_SQLITE`                 | no       | `True`                                           | Set to `False` in production to use Postgres.                        |
| `REDIS_URL`                  | no       | (Render Redis)                                   | Pulled from the `openbenchml-redis` service.                         |
| `SECRET_KEY`                 | no       | (generated)                                      | JWT signing secret. Render auto-generates via `generateValue: true`. |
| `DEBUG`                      | no       | `True`                                           | Set to `False` in production.                                        |
| `SECURE_COOKIES`             | no       | `False`                                          | Set to `True` over HTTPS.                                            |
| `APP_URL`                    | no       | `https://openbenchml.onrender.com`               | Used in email/notification links.                                    |
| `DOCKER_ENABLED`             | no       | `False`                                          | Future: enable Docker sandbox for `/convert` (off for now).          |
| `MAX_MODEL_SIZE_MB`          | no       | `500`                                            | Max model file size.                                                 |
| `BENCHMARK_TIMEOUT_SECONDS`  | no       | `300`                                            | Wall-clock limit per benchmark job.                                  |
| `WEB_CONCURRENCY`            | no       | `2`                                              | Number of uvicorn workers. Bump on larger plans.                     |

---

## Cost estimate (Render starter plan)

| Service                  | Plan      | Monthly cost |
| ------------------------ | --------- | ------------ |
| openbenchml (web)        | starter   | $7           |
| openbenchml-redis        | starter   | $7           |
| Supabase (existing)      | free tier | $0           |
| **Total**                |           | **~$14/mo**  |

The starter plan gives you 512 MB RAM + 0.5 CPU for the web service —
plenty for personal / classroom use. For competitions with >50
concurrent users, upgrade to the **standard** plan ($25/mo for 2 GB
RAM + 1 CPU).

---

## What's next?

- Visit `/realtime` on your deployed app to see the WebSocket live preview.
- Install the CLI: `npm install -g openbenchml-cli` then
  `openbenchml init --host https://your-app.onrender.com`.
- Set up the docs site (separate deploy): see
  [Deployment → Cloud](./cloud.md) for the GitHub Pages flow.
- For Docker sandboxing of `/convert` (recommended for public-facing
  deployments), see [Deployment → Docker](./docker.md).
