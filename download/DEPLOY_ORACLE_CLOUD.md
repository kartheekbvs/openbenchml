# Deploy OpenBenchML on Render + Oracle Cloud Always Free

**Goal:** Run OpenBenchML on two free services in parallel.

| Service | URL | Runs | RAM |
|---|---|---|---|
| Render (free) | `openbenchml.onrender.com` | Landing, auth, dashboard, leaderboard, benchmark pages | 512 MB |
| Oracle Cloud (Always Free) | `notebook.yourdomain.com` or `IP.nip.io` | Notebook + terminal + file workspace | **24 GB** |

Users log in on Render → click **"⚡ Open on Compute"** on the notebook page → securely redirected to Oracle VM (no second login).

---

## Why Oracle Cloud Always Free?

- **24 GB RAM, 4 ARM cores, 200 GB storage** — 48× more RAM than Render free
- Truly free forever (credit card only for verification, never charged)
- Your Docker stack runs unchanged
- No sleep on inactivity (unlike Render/HF free tiers)

**The catch:** Oracle's free ARM instances are sometimes "out of capacity" — you may need to retry the instance creation a few times. See troubleshooting below.

---

## Part A: Get an Oracle Cloud account (10 min)

1. Go to **https://cloud.oracle.com** → click **Start for free**
2. Fill in your details:
   - Country, name, email
   - **Credit card required** for verification (won't be charged — Oracle just checks it's a real card)
3. Choose region (pick the one closest to your users — e.g., `us-ashburn-1` for US, `ap-mumbai-1` for India)
4. Wait for the verification email (1-5 minutes)
5. Log in to https://cloud.oracle.com

---

## Part B: Claim your Always Free ARM instance (15 min)

### Step B1: Navigate to Compute → Instances

1. Click the hamburger menu (top-left) → **Compute** → **Instances**
2. Click **Create instance**

### Step B2: Configure the instance

| Field | Value |
|---|---|
| Name | `openbenchml-notebook` |
| Image | **Canonical Ubuntu 22.04** (click "Change image" if not Ubuntu) |
| Shape | Click "Edit" → **Ampere A1 Compute Flex** (VM.Standard.A1.Flex) |
| OCPUs | **4** |
| Memory | **24 GB** |
| Networking | Default VCN + public subnet (leave defaults) |
| SSH keys | **Save private key** + **Save public key** (download both!) |

⚠️ **If you see "Out of capacity" error:** This is common. Three workarounds:
   - Try a different region (e.g., switch from Mumbai to Singapore)
   - Try at off-peak hours (early morning in your region)
   - Use the [OCI API retry script](https://github.com/hitrov/oci-arm-host-capacity) (advanced — keeps retrying automatically)

### Step B3: Create + wait

1. Click **Create**
2. Wait ~2-3 minutes for the instance to provision
3. Note the **Public IP** shown on the instance page (e.g., `193.123.45.67`)

---

## Part C: Open firewall ports (5 min)

By default, Oracle Cloud only allows SSH (port 22). You need to open ports 80 (HTTP) and 443 (HTTPS) for Caddy to serve traffic.

### Step C1: Open the security list

1. Hamburger menu → **Networking** → **Virtual Cloud Networks**
2. Click your default VCN (named like `vcn-…`)
3. Click **Security Lists** in the left sidebar
4. Click **Default Security List for vcn-…**
5. Click **Add Ingress Rules** and add two rules:

**Rule 1 — HTTP:**
| Field | Value |
|---|---|
| Source CIDR | `0.0.0.0/0` |
| IP Protocol | TCP |
| Destination Port Range | `80` |
| Description | HTTP for Caddy |

**Rule 2 — HTTPS:**
| Field | Value |
|---|---|
| Source CIDR | `0.0.0.0/0` |
| IP Protocol | TCP |
| Destination Port Range | `443` |
| Description | HTTPS for Caddy |

Click **Add Ingress Rules**.

### Step C2: Configure iptables inside the VM (Ubuntu's UFW doesn't manage Oracle's iptables rules)

You'll do this after SSHing in (next step). The setup script handles it automatically.

---

## Part D: SSH into the VM and run the setup script (10 min)

### Step D1: SSH into the instance

From your laptop (replace IP and key path):

```bash
chmod 400 ~/Downloads/ssh-key-*.key
ssh -i ~/Downloads/ssh-key-*.key ubuntu@193.123.45.67
```

Type `yes` when prompted about the host key.

### Step D2: Get a free hostname

You have two options:

**Option 1 (easiest): Use nip.io — free hostname based on your IP**

Just use `193.123.45.67.nip.io` as your domain. nip.io resolves any `IP.nip.io` to that IP. No signup, no DNS, no waiting.

**Option 2 (better for production): Use a real domain**

If you own a domain (e.g., `openbenchml.com`):
- Add an A record in your DNS provider's dashboard pointing `notebook.openbenchml.com` → `193.123.45.67`
- Wait 5-10 min for DNS to propagate

### Step D3: Download and run the setup script

```bash
# Download the setup script from your GitHub repo
wget https://raw.githubusercontent.com/kartheekbvs/openbenchml/main/scripts/oracle_cloud_setup.sh

# Make it executable
chmod +x oracle_cloud_setup.sh

# Run it with your domain (or IP.nip.io)
sudo bash oracle_cloud_setup.sh 193.123.45.67.nip.io
```

The script does everything:
1. ✅ Installs Docker
2. ✅ Installs Caddy (auto-HTTPS reverse proxy)
3. ✅ Clones your repo to `/opt/openbenchml`
4. ✅ Builds the Docker image
5. ✅ Creates a systemd service for auto-restart on boot
6. ✅ Creates `/etc/openbenchml.env` (placeholder secrets — you must edit)
7. ✅ Configures Caddy with auto Let's Encrypt cert

Takes 5-10 minutes. Watch the output — at the end it tells you exactly what to do next.

### Step D4: Open iptables ports (Ubuntu inside Oracle)

Oracle Cloud's Ubuntu images have iptables rules that block all non-SSH traffic, even after you open the security list. Run this:

```bash
sudo iptables -I INPUT 6 -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

### Step D5: Set your secrets

Edit the env file:

```bash
sudo nano /etc/openbenchml.env
```

Replace the placeholder values:

```
SECRET_KEY=<copy from Render → Environment → SECRET_KEY>
SESSION_SECRET=<copy from Render → Environment → SESSION_SECRET>
SECURE_COOKIES=true
COOKIE_SAMESITE=lax
DATABASE_URL=sqlite:////data/openbenchml.db
```

To find your Render secrets:
1. Go to https://dashboard.render.com → your `openbenchml` web service
2. Click **Environment** in the left sidebar
3. Copy the values of `SECRET_KEY` and `SESSION_SECRET`

Save (`Ctrl+O`, `Enter`, `Ctrl+X` to exit nano).

### Step D6: Start the notebook server

```bash
sudo systemctl start openbenchml
```

Watch the startup logs:

```bash
sudo journalctl -u openbenchml -f
```

Wait until you see something like `Uvicorn running on http://0.0.0.0:7860`. Press `Ctrl+C` to exit the log view (the service keeps running in the background).

### Step D7: Verify the server is up

From your laptop:

```bash
curl https://193.123.45.67.nip.io/health
```

Should return:
```json
{"status":"healthy","version":"4.2.0",...}
```

If you see a cert error (self-signed), wait 1-2 min for Let's Encrypt to finish provisioning — check Caddy logs with `sudo journalctl -u caddy -f`.

---

## Part E: Connect Render to your Oracle VM (2 min)

1. Go to https://dashboard.render.com → your `openbenchml` web service
2. Click **Environment** in the left sidebar
3. Add a new environment variable:
   - **Key:** `NOTEBOOK_SERVER_URL`
   - **Value:** `https://193.123.45.67.nip.io` (or your domain)
4. Click **Save Changes** — Render will auto-redeploy (~1-2 min)

---

## Part F: Test the end-to-end flow (2 min)

1. Open `https://openbenchml.onrender.com` (incognito)
2. Log in / register
3. Click **Notebook** in the nav
4. You should see a **⚡ Open on Compute** button next to the title
5. Click it → you'll be redirected to `https://193.123.45.67.nip.io/notebook` — **already logged in, no second prompt**
6. Run a heavy cell like `import tensorflow as tf; print(tf.__version__)` — works without OOM (24 GB RAM!)

---

## How the no-second-login trick works

```
[Browser]-----login----->[Render: openbenchml.onrender.com]
                              │
                              │ sets HttpOnly JWT cookie (Render domain)
                              │
[Browser]--click "⚡ Open on Compute"--->[/api/auth/bridge_token]
                              │
                              │ verifies user is logged in
                              │ signs short-lived (5-min) one-time JWT
                              │
[Browser]<---redirect to Oracle--https://193.123.45.67.nip.io/auth/bridge?token=...
                              │
                              │ Oracle VM decodes JWT (shared SECRET_KEY verifies signature)
                              │ checks jti is not already consumed (single-use)
                              │ upserts stub user in local SQLite DB
                              │   - password_hash = "BRIDGED" (cannot log in directly)
                              │ mints a fresh 1-hour access_token
                              │ sets HttpOnly cookie on Oracle domain
                              │
[Browser]<---redirect to /notebook
                              │
                              │ subsequent requests carry Oracle cookie → authenticated
```

---

## Maintenance

### Update the app on Oracle (after you push new code to GitHub)

```bash
ssh -i ~/Downloads/ssh-key-*.key ubuntu@193.123.45.67
sudo bash /opt/openbenchml/scripts/oracle_update.sh
```

### View logs

```bash
# App logs (FastAPI, uvicorn)
sudo journalctl -u openbenchml -f

# Caddy logs (reverse proxy, HTTPS)
sudo journalctl -u caddy -f

# Container logs (Docker-level)
docker logs -f openbenchml
```

### Restart the service

```bash
sudo systemctl restart openbenchml
```

### Check service status

```bash
sudo systemctl status openbenchml
```

### SSH back in later

```bash
ssh -i ~/Downloads/ssh-key-*.key ubuntu@193.123.45.67
```

---

## Cost breakdown

| Service | Cost | What you get |
|---|---|---|
| Render free | $0 | 750 hrs/mo, 512 MB RAM, sleeps after 15 min idle |
| Oracle Cloud Always Free | $0 | 4 ARM cores, 24 GB RAM, 200 GB storage, never sleeps |
| nip.io hostname | $0 | Free DNS, no signup |
| Let's Encrypt cert | $0 | Auto-renewed by Caddy |
| **Total** | **$0/mo forever** | |

If you already own a domain, point its A record to the Oracle VM's public IP instead of using nip.io — that's also free.

---

## Troubleshooting

### "Out of host capacity" when creating the ARM instance

This is the #1 issue with Oracle Cloud Always Free. Options:

1. **Retry at different times** — capacity fluctuates through the day
2. **Try a different region** — Singapore, Mumbai, Ashburn, Frankfurt all have different capacity
3. **Use the auto-retry script** — https://github.com/hitrov/oci-arm-host-capacity (advanced, requires OCI API key)
4. **Temporarily use a smaller instance** — VM.Standard.E2.1.Micro (1 GB RAM, AMD x86) is also Always Free and easier to claim. Use it until you can claim the ARM instance. Your Docker stack runs on x86 too (just change `Dockerfile.hf`'s base image to `python:3.11-slim` without ARM-specific changes).

### Caddy can't get a Let's Encrypt cert

- **DNS not propagated yet** — wait 5-10 min after adding the A record
- **Using IP directly (no domain)** — Let's Encrypt won't issue a cert for a bare IP. Use `IP.nip.io` instead.
- **Port 443 blocked** — verify with `sudo iptables -L INPUT -n --line-numbers` (you should see rules accepting port 443)
- Check Caddy logs: `sudo journalctl -u caddy -f`

### "Bridge token is invalid or expired"

- Token has 5-min TTL. If user takes too long, it expires. Fix: click "Open on Compute" again.
- Check that `SECRET_KEY` matches exactly between Render and `/etc/openbenchml.env` on Oracle. Even a trailing space will break it.

### "This sign-in link has already been used"

- Bridge tokens are single-use. If user refreshes the `/auth/bridge?token=...` URL, it fails.
- Fix: go back to Render, click "Open on Compute" again.

### Container won't start

```bash
# Check what's failing
sudo journalctl -u openbenchml -n 50 --no-pager

# Common fixes:
# - /etc/openbenchml.env has placeholder values → edit and set real SECRET_KEY
# - Port 7860 already in use → sudo lsof -i :7860
# - /data permissions → sudo chmod -R 777 /data
```

### Notebook files disappear after restart

- Files should be in `/data/notebook_files/` (persistent volume)
- Verify: `ls -la /data/notebook_files/`
- If empty, the Dockerfile symlinks may have failed — check container logs

### Can't SSH in

- Verify the security list has port 22 open (it should by default)
- Verify you're using the right SSH key (the one you downloaded in Step B2)
- Verify the username is `ubuntu` (not `root` or `opc`)
- Try: `ssh -v -i ~/Downloads/ssh-key-*.key ubuntu@193.123.45.67` for verbose output

---

## What's next (optional improvements)

1. **Notebook auto-save** — save `.ipynb` to `/data/notebooks/{user_id}.ipynb` so users resume work after restart
2. **Custom domain** — buy a domain (~$10/yr from Namecheap/Cloudflare), point A record to Oracle VM
3. **CDN in front of Render** — Cloudflare free tier for faster static asset delivery
4. **Backup `/data`** — cron job to rsync `/data` to a free Backblaze B2 bucket (10 GB free)
5. **Monitoring** — install Netdata (free) on the VM for real-time CPU/RAM/disk dashboards

---

## Quick reference — what lives where

| File | Where | Purpose |
|---|---|---|
| `/opt/openbenchml/` | Oracle VM | Your app code (cloned from GitHub) |
| `/etc/openbenchml.env` | Oracle VM | Environment variables (SECRET_KEY etc.) |
| `/data/openbenchml.db` | Oracle VM | SQLite DB (user accounts — separate from Render's DB) |
| `/data/notebook_files/` | Oracle VM | User-uploaded files + git clones (persistent) |
| `/data/uploads/` | Oracle VM | Misc uploads (persistent) |
| `/data/logs/` | Oracle VM | App logs (persistent) |
| `/etc/caddy/Caddyfile` | Oracle VM | Caddy reverse proxy config (auto-HTTPS) |
| `/etc/systemd/system/openbenchml.service` | Oracle VM | Systemd unit (auto-start on boot) |
| `NOTEBOOK_SERVER_URL` env var | Render | Points to your Oracle VM URL |
| `SECRET_KEY` + `SESSION_SECRET` env vars | Both | Must match for auth bridge to work |
