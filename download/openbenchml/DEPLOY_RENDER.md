# Deploy OpenBenchML to Render — Step by Step

This guide walks you from zero to a live OpenBenchML deployment on Render in
under 10 minutes. The app uses **Supabase Postgres + Supabase Auth** for the
database and login, so you only need **one** secret from your Supabase
project.

> 💡 All the Supabase connection details (project ref, URL, anon key) are
> already baked into the code — you only need to supply the **database
> password**.

---

## What you'll need

| Thing | Where to get it | Cost |
| ----- | --------------- | ---- |
| GitHub account | <https://github.com> | free |
| Render account | <https://render.com> | free starter OK |
| Supabase project password | (set when you created the Supabase project) | free tier OK |
| The OpenBenchML repo on GitHub | <https://github.com/kartheekbvs/openbenchml> | — |

**That's it.** No Docker, no nginx, no manual Postgres setup.

---

## Step 1 — Fork the repo (if you haven't already)

1. Open <https://github.com/kartheekbvs/openbenchml> in your browser.
2. Click **Fork** in the top-right.
3. You now have your own copy at `https://github.com/<your-username>/openbenchml`.

> If you already have push access to `kartheekbvs/openbenchml` you can skip
> the fork and deploy directly from there.

---

## Step 2 — Find your Supabase DB password

1. Log in to <https://supabase.com>.
2. Open the project **`fzwvxesrtdilljgrntpw`** (the OpenBenchML project).
3. Click the **gear icon → Project Settings → Database**.
4. Look for the field labelled **Database password** — this is the password
   you set when you created the project.  Copy it.

> 🔒 **Keep this password safe.** It's the only secret you need for the
> entire deployment.

---

## Step 3 — Create a new Render Blueprint

1. Log in to <https://dashboard.render.com>.
2. Click **New +** in the top-right → **Blueprint**.
3. Pick the GitHub repo: `kartheekbvs/openbenchml` (or your fork).
4. Render will detect `render.yaml` at the repo root and auto-fill most
   settings.  You should see two services:
   - `openbenchml` (Python web service)
   - `openbenchml-redis` (managed Redis — needed for Celery + rate limiting)

5. Scroll to **Environment Variables** for the `openbenchml` service.
   You'll see most are pre-filled.  **The only one you must fill in
   yourself is:**

   | Name | Value |
   | ---- | ----- |
   | `SUPABASE_DB_PASSWORD` | (paste the password from Step 2) |

   Other interesting vars you can review (already set):
   - `USE_SQLITE=False` (production uses Postgres)
   - `SECRET_KEY` → click **Generate** to let Render create a random one
   - `DEBUG=False`
   - `SECURE_COOKIES=True`
   - `CORS_ORIGINS` → update if you have a custom domain

6. Pick a **region** close to your Supabase region (Supabase free tier is
   `us-east-1`, so Render's `oregon` or `ohio` works well).

7. Pick a **plan** — Starter ($7/mo) is plenty for a class project or
   small team.  Free tier sleeps after 15 min of inactivity.

8. Click **Apply**.

Render will now:
1. Pull the repo
2. Build the Docker image (Python 3.11 + dependencies)
3. Start `uvicorn` via `start.sh`
4. Probe `/health` until it returns 200

First build takes **~5 minutes**.  Subsequent builds are < 1 min (cached).

---

## Step 4 — Watch the first deploy

1. Click the `openbenchml` service in Render's dashboard.
2. Click the **Logs** tab — you should see:

   ```
   INFO:openbenchml.config: Auto-assembled DATABASE_URL from SUPABASE_PROJECT_REF + SUPABASE_DB_PASSWORD (pooler host: aws-0-us-east-1).
   INFO:app.services.supabase_auth_service: Supabase client initialized → https://fzwvxesrtdilljgrntpw.supabase.co (project ref fzwvxesrtdilljgrntpw)
   INFO:     Uvicorn running on http://0.0.0.0:8000
   INFO:     Application startup complete.
   ```

3. When you see `Application startup complete.`, click the URL at the top
   of the service page (looks like
   `https://openbenchml-xxxx.onrender.com`).

4. You should see the OpenBenchML landing page (olive/teal dark theme).

---

## Step 5 — Verify auth works

1. Click **Sign Up** in the top nav.
2. Fill in username / email / password.
3. You should be redirected to `/login` with no error.
4. Log in with the same email/password.
5. You should land on `/dashboard`.

If login fails, check the **Logs** tab for `Supabase sign_in failed: ...`.
Common causes:
- **Email not confirmed**: by default Supabase requires email confirmation
  for new sign-ups.  Either confirm the email (check inbox) or disable
  email confirmation in Supabase → Authentication → Email Auth →
  "Confirm email" toggle.

---

## Step 6 — Install the CLI and point it at your Render URL

```bash
npm install -g openbenchml-cli
obml login --server https://openbenchml-xxxx.onrender.com
# → enter the email + password you registered with
obml whoami
# → logged in as <your-username>
```

Now you can submit models, run benchmarks, and watch live leaderboards from
your terminal.

---

## What each env var does

| Var | Required | Default in code | Notes |
| --- | -------- | --------------- | ----- |
| `SUPABASE_DB_PASSWORD` | **YES** | — | Your Supabase project's DB password. |
| `SUPABASE_PROJECT_REF` | no | `fzwvxesrtdilljgrntpw` | Already baked in. |
| `SUPABASE_URL` | no | `https://fzwvxesrtdilljgrntpw.supabase.co` | Already baked in. |
| `SUPABASE_ANON_KEY` | no | `eyJhbGci...` | Already baked in (public key, RLS-protected). |
| `USE_SQLITE` | no | `True` | **Set to `False` on Render** (already done in `render.yaml`). |
| `DATABASE_URL` | no | auto-assembled | Leave blank — Render's `start.sh` will build it from `SUPABASE_*`. |
| `SECRET_KEY` | no | hardcoded dev key | **Click "Generate" in Render** for a random one. |
| `SECURE_COOKIES` | no | `False` | **Set to `True` on Render** (already done). |
| `CORS_ORIGINS` | no | localhost list | Add your Render URL + any custom domains. |
| `REDIS_URL` | no | `redis://localhost:6379/0` | Render's Blueprint wires this to the `openbenchml-redis` service automatically. |

---

## Troubleshooting

### "Could not connect to Postgres"

- Double-check `SUPABASE_DB_PASSWORD` — it must be the password set when
  creating the Supabase project (NOT the anon key, NOT the project ref).
- In Supabase → Project Settings → Database, make sure your IP is allowed
  (Supabase free tier allows all IPs by default).
- Confirm the Supabase project is **paused** vs **active**.  Free-tier
  projects auto-pause after a week of inactivity — click **Restore** in
  the Supabase dashboard.

### "Email not confirmed"

Supabase requires email confirmation by default. Two fixes:

- **Quick fix** (for dev): Supabase dashboard → Authentication →
  Providers → Email → turn OFF "Confirm email".
- **Proper fix**: check the user's inbox (including spam) for the
  confirmation link.

### "WebSocket disconnected" on the live leaderboard

Render's free tier kills idle WebSocket connections after 30s.  Two fixes:

- Upgrade to a paid plan (Starter or above).
- Add a heartbeat ping in the client every 20s.

### "CSS looks unstyled"

You're hitting `/static/` through Render's CDN which is sometimes slow on
first deploy.  Hard refresh (Ctrl+Shift+R) — if it persists, check the
Logs for any 404s on static files.

### App boots but `/api/auth/status` says `supabase_auth_enabled: false`

The `supabase` Python package failed to install.  Check the build logs
for pip errors.  Render's Python 3.11 image should have no issues — if
you see errors, file an issue at
<https://github.com/kartheekbvs/openbenchml/issues>.

---

## Cost estimate

| Service | Plan | Monthly cost |
| ------- | ---- | ------------ |
| Render web service | Starter | $7 |
| Render Redis | Starter | $7 |
| Supabase | Free | $0 |
| **Total** | | **~$14/mo** |

Free tiers are fine for a class project but the Render web service will
sleep after 15 min of inactivity (first request after sleep takes ~30s).

---

## tl;dr — minimum steps

```bash
# 1. Fork the repo on GitHub (browser)

# 2. On Render dashboard:
#    New → Blueprint → pick kartheekbvs/openbenchml
#    Fill in SUPABASE_DB_PASSWORD
#    Click Apply

# 3. Wait ~5 min for first build

# 4. Click the Render URL → /register → /login → /dashboard

# 5. CLI:
npm install -g openbenchml-cli
obml login --server https://your-app.onrender.com
```

That's it.  You're live.
