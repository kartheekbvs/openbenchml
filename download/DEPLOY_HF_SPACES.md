# Deploy OpenBenchML on Render + Hugging Face Spaces

This guide walks you through running OpenBenchML on **two free services in parallel**:

| Service | URL | Runs | RAM |
|---|---|---|---|
| Render | `openbenchml.onrender.com` | Landing, auth, dashboard, leaderboard, benchmark pages | 512 MB |
| HF Spaces | `openbenchml.hf.space` | Notebook + terminal + file workspace | 16 GB |

Users log in on Render and click **"Open on Compute"** to be securely redirected to HF Spaces — no second login required.

---

## Step 1: Push the new code to GitHub

The auth bridge + Dockerfile.hf + README_HF.md are already committed. Push them:

```bash
cd /home/z/my-project
git add app/routes/auth_bridge.py app/main.py app/routes/notebook.py \
        templates/notebook.html Dockerfile.hf README_HF.md \
        scripts/test_auth_bridge.py
git commit -m "Add Render↔HF Spaces auth bridge + Dockerfile.hf"
git push origin main
```

Render will auto-rebuild with the new code (the auth bridge routes are now active, but invisible until you set `HF_SPACES_URL`).

---

## Step 2: Create the HF Space

1. Go to **https://huggingface.co/login** (sign up if you don't have an account — free)
2. Click your avatar (top-right) → **New Space**
3. Fill in:
   - **Space name:** `openbenchml`
   - **License:** MIT
   - **SDK:** Docker
   - **Visibility:** Public (required for free CPU tier)
4. Click **Create Space**

You should now have an empty Space at `https://huggingface.co/spaces/<your-username>/openbenchml`.

---

## Step 3: Push the code to HF Spaces

The easiest way is to clone the HF Space repo and copy your code into it:

```bash
# Clone your HF Space (it will be empty except for a README.md)
git clone https://huggingface.co/spaces/<your-username>/openbenchml hf-space
cd hf-space

# Copy your project files in (excluding .git, .env, and the local DB)
cp -r /home/z/my-project/app .
cp -r /home/z/my-project/templates .
cp -r /home/z/my-project/static .
cp -r /home/z/my-project/datasets .
cp -r /home/z/my-project/packages .
cp /home/z/my-project/requirements.txt .
cp /home/z/my-project/run.py .

# Copy the HF-specific Dockerfile and README
cp /home/z/my-project/Dockerfile.hf ./Dockerfile
cp /home/z/my-project/README_HF.md ./README.md

# Add a .gitignore so we don't push DB/junk
cat > .gitignore <<'EOF'
*.db
*.db-shm
*.db-wal
__pycache__/
*.pyc
.env
download/
scripts/
EOF

# Commit + push to HF
git add .
git commit -m "Initial OpenBenchML deploy to HF Spaces"
git push
```

HF will start building your Docker image immediately. Watch the build log at:
`https://huggingface.co/spaces/<your-username>/openbenchml`

Build takes ~5-10 minutes the first time (pip install scikit-learn, etc.). Once done, you'll see **"Running"** at the top.

---

## Step 4: Get your HF Spaces URL

Your Space's public URL will be:
```
https://<your-username>-openbenchml.hf.space
```

For example, if your HF username is `kartheekbvs`, the URL is:
```
https://kartheekbvs-openbenchml.hf.space
```

Verify it works:
```bash
curl https://<your-username>-openbenchml.hf.space/health
# Should return: {"status":"healthy",...}
```

---

## Step 5: Configure environment variables on HF Spaces

Go to your HF Space → **Settings** → scroll down to **Variables and secrets** → add these:

| Name | Value |
|---|---|
| `SECRET_KEY` | (paste the same value Render uses — required for auth bridge) |
| `SESSION_SECRET` | (paste the same value Render uses) |
| `HF_SPACES_URL` | (leave blank on HF itself — this var is only set on Render) |

To find your Render `SECRET_KEY`:
1. Go to https://dashboard.render.com → your `openbenchml` web service
2. Click **Environment** in the left sidebar
3. Copy the value of `SECRET_KEY` and `SESSION_SECRET`

**Important:** Both Render and HF must use the **exact same** `SECRET_KEY` value, or the auth bridge won't work.

After adding the variables, HF Spaces will automatically restart.

---

## Step 6: Configure environment variables on Render

Go to https://dashboard.render.com → your `openbenchml` web service → **Environment**:

| Name | Value |
|---|---|
| `HF_SPACES_URL` | `https://<your-username>-openbenchml.hf.space` |

(Save without changing anything else. Render will redeploy.)

After Render redeploys, visit `https://openbenchml.onrender.com/notebook` — you should now see an **"⚡ Open on Compute"** button next to the Notebook title.

---

## Step 7: Test the end-to-end flow

1. Open `https://openbenchml.onrender.com` in your browser (incognito)
2. Log in / register
3. Click **Notebook** in the nav
4. You should see the **⚡ Open on Compute** button at the top of the notebook page
5. Click it → you'll be redirected to `https://<your-username>-openbenchml.hf.space/notebook` — already logged in, no second prompt
6. Run a heavy cell like `import tensorflow as tf` — should work without OOM (you have 16 GB now!)

---

## How the auth bridge works (technical summary)

```
[Browser]-----login----->[Render: openbenchml.onrender.com]
                              │
                              │ sets HttpOnly JWT cookie (Render domain)
                              │
[Browser]--click "Open on Compute"--->[/api/auth/bridge_token]
                              │
                              │ verifies user is logged in
                              │ signs short-lived (5-min) one-time JWT
                              │
[Browser]<---redirect to HF--https://openbenchml.hf.space/auth/bridge?token=...
                              │
                              │ HF decodes JWT (shared SECRET_KEY verifies signature)
                              │ checks JTI is not already consumed (single-use)
                              │ upserts stub user in HF's local SQLite DB
                              │   - password_hash = "BRIDGED" (cannot log in directly)
                              │ mints a fresh 1-hour access_token
                              │ sets HttpOnly cookie on HF domain
                              │
[Browser]<---redirect to /notebook
                              │
                              │ subsequent requests carry HF cookie → authenticated
```

---

## Cost: $0

- Render free tier: 750 hours/month (enough for 24/7)
- HF Spaces free CPU: 16 GB RAM, 2 vCPU, 10 GB storage
- Both services sleep on inactivity (Render after 15 min, HF after 48 hrs)
- Wake-on-request: first request after sleep takes ~30 seconds
- Optional: free [UptimeRobot](https://uptimerobot.com) cron pings both URLs every 5 min to keep them warm

---

## Troubleshooting

### "Cannot connect to HF Space" / 502 error
- HF Spaces sleeps after 48h of inactivity. First request takes ~30s to wake.
- Check the Space status at `https://huggingface.co/spaces/<your-user>/openbenchml`
- If status is "Error", click **Logs** to see the build/runtime error

### "Bridge token is invalid or expired"
- Token has a 5-min TTL. If the user takes >5 min between clicking "Open on Compute" and the redirect completing, it expires.
- Fix: click "Open on Compute" again — it mints a fresh token.

### "This sign-in link has already been used"
- Bridge tokens are single-use. If the user refreshes the `/auth/bridge?token=...` URL, it fails.
- Fix: go back to Render, click "Open on Compute" again.

### Stub user email mismatch
- When a user changes their email on Render, the next bridge call updates the stub user's email on HF.
- Username changes are also synced.

### Notebooks don't persist across HF restarts
- HF Spaces restarts on every push (and after 48h sleep). Notebooks in memory are lost.
- Uploaded files DO persist (they're in `/data/notebook_files/` which is a persistent volume).
- For full notebook persistence, the next feature to add is saving notebook JSON to `/data/notebooks/{user_id}.ipynb`.

---

## What's next (optional improvements)

1. **Auto-redirect to HF for /notebook** — instead of showing a button, just auto-redirect on `/notebook` route. (Simple change: in `notebook_page()`, return a `RedirectResponse` to the bridge URL when `HF_SPACES_URL` is set.)
2. **Notebook persistence** — save/load `.ipynb` files in `/data/notebooks/` so users can resume work after a restart.
3. **GPU support** — if you ever need GPU, upgrade HF Space to a paid GPU tier ($9/mo Pro + usage).
4. **Shared Postgres** — if you want users to see the same leaderboard/benchmarks on both URLs, point both Render and HF at the same Supabase Postgres instance (free 500 MB).
