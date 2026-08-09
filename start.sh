#!/usr/bin/env bash
# =============================================================================
# OpenBenchML — Render / production start script
# =============================================================================
#
# Renders the runtime DATABASE_URL from SUPABASE_PROJECT_REF +
# SUPABASE_DB_PASSWORD if the operator only set those two (instead of
# pasting the full connection string).  Then launches uvicorn.
#
# Used by `render.yaml` as the startCommand.  Works on any POSIX shell.
#
# Why a wrapper script?
#   - Render env vars can't reference each other directly.
#   - Some operators prefer to paste SUPABASE_DB_PASSWORD only (less
#     typing, no chance of a malformed URL with URL-encoded special
#     chars in the password).
#   - The Python config already handles the empty-DATABASE_URL case,
#     but doing it in shell means the URL shows up in `env` for
#     debugging and works for any future tooling that reads DATABASE_URL
#     directly (alembic, psql, etc.).
# =============================================================================

set -euo pipefail

# ── Step 1: Build DATABASE_URL if missing ────────────────────────────────────
if [ -z "${DATABASE_URL:-}" ] && [ -n "${SUPABASE_PROJECT_REF:-}" ] && [ -n "${SUPABASE_DB_PASSWORD:-}" ]; then
  # Pick the pooler region from env (default: us-east-1).
  POOLER_REGION="${SUPABASE_POOLER_REGION:-aws-0-us-east-1}"
  POOLER_HOST="${POOLER_REGION}.pooler.supabase.com"
  POOLER_PORT="${SUPABASE_POOLER_PORT:-5432}"

  export DATABASE_URL="postgresql://postgres.${SUPABASE_PROJECT_REF}:${SUPABASE_DB_PASSWORD}@${POOLER_HOST}:${POOLER_PORT}/postgres"
  echo "[start.sh] Assembled DATABASE_URL from SUPABASE_PROJECT_REF + SUPABASE_DB_PASSWORD"
  echo "[start.sh] Pooler host: ${POOLER_HOST}:${POOLER_PORT}"
fi

# ── Step 2: Show useful diagnostics (no secrets) ────────────────────────────
echo "[start.sh] USE_SQLITE=${USE_SQLITE:-True}"
echo "[start.sh] DATABASE_URL is set: $([ -n "${DATABASE_URL:-}" ] && echo yes || echo no)"
echo "[start.sh] REDIS_URL is set:    $([ -n "${REDIS_URL:-}" ] && echo yes || echo no)"
echo "[start.sh] SECRET_KEY is set:   $([ -n "${SECRET_KEY:-}" ] && echo yes || echo no)"
echo "[start.sh] Starting uvicorn on 0.0.0.0:${PORT:-8000}…"

# ── Step 3: Launch uvicorn ──────────────────────────────────────────────────
# Render assigns $PORT automatically. 2 workers is plenty for the
# starter plan (512 MB RAM); bump for standard/premium plans.
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --proxy-headers \
  --forwarded-allow-ips='*'
