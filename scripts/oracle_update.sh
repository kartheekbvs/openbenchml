#!/usr/bin/env bash
# Pull latest code from GitHub + rebuild + restart the Docker container.
# Run this on the Oracle VM after you push new code to GitHub.
set -euo pipefail

APP_DIR="/opt/openbenchml"

echo "Pulling latest code from GitHub…"
cd "$APP_DIR"
git fetch --all
git reset --hard origin/main

echo ""
echo "Rebuilding Docker image (5-10 min on first build, faster on subsequent)…"
docker build -f Dockerfile.hf -t openbenchml:latest .

echo ""
echo "Restarting service…"
systemctl restart openbenchml

echo ""
echo "Watching startup logs (Ctrl+C to exit, service keeps running)…"
sleep 2
journalctl -u openbenchml -f
