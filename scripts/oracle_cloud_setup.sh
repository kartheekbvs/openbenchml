#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════════════
#  OpenBenchML — Oracle Cloud Always Free VM setup script
#  Run this on a fresh Ubuntu 22.04/24.04 ARM instance (Ampere A1).
#
#  What it does:
#    1. Installs Docker + docker-compose
#    2. Installs Caddy (auto-HTTPS reverse proxy)
#    3. Clones the OpenBenchML repo from GitHub
#    4. Builds the Docker image
#    5. Creates a persistent /data volume for SQLite + notebook files
#    6. Sets up a systemd service so the container auto-starts on boot
#    7. Prints the public URL you should set as NOTEBOOK_SERVER_URL on Render
#
#  Usage:
#    sudo bash oracle_cloud_setup.sh <your-domain-or-ip>
#
#  Examples:
#    sudo bash oracle_cloud_setup.sh 123.45.67.89.nip.io
#    sudo bash oracle_cloud_setup.sh notebook.yourdomain.com
# ════════════════════════════════════════════════════════════════════════════
set -euo pipefail

# ─── Args ───────────────────────────────────────────────────────────────────
DOMAIN="${1:-}"
if [ -z "$DOMAIN" ]; then
  echo "Usage: sudo bash $0 <your-domain-or-ip>"
  echo ""
  echo "Examples:"
  echo "  sudo bash $0 123.45.67.89.nip.io        # free hostname based on IP"
  echo "  sudo bash $0 notebook.example.com        # your own domain"
  exit 1
fi

PUBLIC_IP="$(curl -s ifconfig.me || curl -s icanhazip.com || echo unknown)"
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  OpenBenchML — Oracle Cloud setup                                ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo "  Domain / hostname : $DOMAIN"
echo "  Public IP         : $PUBLIC_IP"
echo "  OS                : $(lsb_release -ds 2>/dev/null || cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2)"
echo ""

# ─── 1. Install Docker ──────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  echo "[1/6] Installing Docker…"
  apt-get update -y
  apt-get install -y ca-certificates curl gnupg lsb-release
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
  echo "[1/6] Docker installed: $(docker --version)"
else
  echo "[1/6] Docker already installed: $(docker --version)"
fi

# ─── 2. Install Caddy (auto-HTTPS) ──────────────────────────────────────────
if ! command -v caddy &>/dev/null; then
  echo "[2/6] Installing Caddy…"
  apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -y
  apt-get install -y caddy
  echo "[2/6] Caddy installed: $(caddy version)"
else
  echo "[2/6] Caddy already installed: $(caddy version)"
fi

# ─── 3. Clone the OpenBenchML repo ──────────────────────────────────────────
APP_DIR="/opt/openbenchml"
if [ ! -d "$APP_DIR" ]; then
  echo "[3/6] Cloning OpenBenchML to $APP_DIR…"
  apt-get install -y git
  git clone https://github.com/kartheekbvs/openbenchml.git "$APP_DIR"
else
  echo "[3/6] Repo already at $APP_DIR — pulling latest…"
  cd "$APP_DIR" && git pull --rebase
fi

# ─── 4. Create persistent data volume ───────────────────────────────────────
echo "[4/6] Creating persistent /data volume…"
mkdir -p /data/notebook_files /data/uploads /data/logs
# SQLite DB file (created on first run by the app)
touch /data/openbenchml.db
chmod -R 777 /data
echo "[4/6] /data ready (10 GB+ persistent storage)"

# ─── 5. Build the Docker image ──────────────────────────────────────────────
echo "[5/6] Building Docker image (this takes 5-10 min on first run)…"
cd "$APP_DIR"
docker build -f Dockerfile.hf -t openbenchml:latest .
echo "[5/6] Image built: $(docker images openbenchml:latest --format '{{.Repository}}:{{.Tag}} {{.Size}}')"

# ─── 6. Configure Caddy reverse proxy ───────────────────────────────────────
echo "[6/6] Configuring Caddy reverse proxy for $DOMAIN…"
cat > /etc/caddy/Caddyfile <<EOF
# OpenBenchML notebook server (auto-HTTPS via Let's Encrypt)
$DOMAIN {
    # Route WebSocket upgrade requests (for the terminal) — Caddy handles
    # these automatically when reverse_proxy is used, but we set timeouts
    # so long-running shells don't get killed.
    reverse_proxy localhost:7860 {
        flush_interval -1
        transport http {
            read_timeout 10m
            write_timeout 10m
            dial_timeout 30s
        }
    }

    # Compression + basic security headers
    encode gzip zstd
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "SAMEORIGIN"
        Referrer-Policy "strict-origin-when-cross-origin"
        # Don't cache dynamic notebook pages
        ?Cache-Control "no-store"
    }

    log {
        output file /var/log/caddy/openbenchml.log
        format json
    }
}
EOF
systemctl enable --now caddy
systemctl reload caddy 2>/dev/null || systemctl restart caddy
echo "[6/6] Caddy configured — HTTPS cert will be auto-provisioned on first request"

# ─── Create systemd service for the Docker container ───────────────────────
echo ""
echo "Creating systemd service openbenchml.service…"
cat > /etc/systemd/system/openbenchml.service <<EOF
[Unit]
Description=OpenBenchML Notebook Server (Docker)
After=docker.service network-online.target
Wants=docker.service network-online.target

[Service]
Type=simple
# Read env vars from /etc/openbenchml.env (SECRET_KEY, SESSION_SECRET, etc.)
EnvironmentFile=/etc/openbenchml.env
WorkingDirectory=$APP_DIR
# Run container with --restart unless-stopped so Docker auto-restarts on crash
ExecStart=/usr/bin/docker run --rm \\
    --name openbenchml \\
    -p 127.0.0.1:7860:7860 \\
    -v /data:/data \\
    --env-file /etc/openbenchml.env \\
    --env PYTHONUNBUFFERED=1 \\
    openbenchml:latest
ExecStop=/usr/bin/docker stop openbenchml
Restart=on-failure
RestartSec=5
TimeoutStartSec=120

[Install]
WantedBy=multi-user.target
EOF

# ─── Create the env file (placeholder — user must edit) ────────────────────
if [ ! -f /etc/openbenchml.env ]; then
  cat > /etc/openbenchml.env <<EOF
# OpenBenchML notebook server — environment variables
# These MUST match the values set on Render (Dashboard → Environment):
SECRET_KEY=CHANGE_ME_TO_MATCH_RENDER
SESSION_SECRET=CHANGE_ME_TO_MATCH_RENDER
SECURE_COOKIES=true
COOKIE_SAMESITE=lax
DATABASE_URL=sqlite:////data/openbenchml.db
EOF
  chmod 600 /etc/openbenchml.env
  echo ""
  echo "⚠️  Created /etc/openbenchml.env with placeholder secrets."
  echo "    Edit it now:"
  echo "       sudo nano /etc/openbenchml.env"
  echo "    Replace SECRET_KEY and SESSION_SECRET with the values from"
  echo "    Render → your web service → Environment."
else
  echo "[OK] /etc/openbenchml.env already exists — leaving it as-is"
fi

systemctl daemon-reload
systemctl enable openbenchml

# ─── Done — print next steps ────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  Setup complete! Next steps:                                     ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "1. Edit the env file and set your secrets:"
echo "       sudo nano /etc/openbenchml.env"
echo "   (Use the SAME SECRET_KEY and SESSION_SECRET as Render)"
echo ""
echo "2. Start the notebook server:"
echo "       sudo systemctl start openbenchml"
echo ""
echo "3. Watch the logs (Ctrl+C to exit):"
echo "       sudo journalctl -u openbenchml -f"
echo ""
echo "4. Verify the server is up:"
echo "       curl https://$DOMAIN/health"
echo ""
echo "5. On Render → your web service → Environment → add:"
echo "       NOTEBOOK_SERVER_URL = https://$DOMAIN"
echo ""
echo "6. Visit https://openbenchml.onrender.com/notebook"
echo "   Click '⚡ Open on Compute' — you'll be redirected to https://$DOMAIN"
echo "   already logged in."
echo ""
echo "Public IP: $PUBLIC_IP"
echo "Domain   : $DOMAIN"
