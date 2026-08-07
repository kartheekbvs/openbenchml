"""
OpenBenchML Configuration
=========================
Central configuration for the entire application.
All settings are loaded from environment variables with sensible defaults.
Production-ready with CORS, rate limiting, caching, and security settings.
"""

import os
from pathlib import Path
from fastapi.templating import Jinja2Templates

# ─── Base Paths ───────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
DATASET_DIR = BASE_DIR / "datasets"
STATIC_DIR = BASE_DIR / "static"
TEMPLATE_DIR = BASE_DIR / "templates"

# Ensure directories exist
UPLOAD_DIR.mkdir(exist_ok=True)
DATASET_DIR.mkdir(exist_ok=True)

# ─── Application Settings ────────────────────────────────────────────────────
APP_NAME = "OpenBenchML"
APP_VERSION = "4.1.0"
APP_DESCRIPTION = (
    "Open Source ML Model Benchmarking Platform — code → pickle → benchmark, "
    "with Kaggle-style real-time leaderboards, competitions, an in-browser "
    "Python notebook, Supabase-backed storage, and an olive/teal UI. "
    "Student-friendly syntax, production-grade engine."
)
APP_URL = os.getenv("APP_URL", "http://localhost:8000")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
SECRET_KEY = os.getenv("SECRET_KEY", "openbenchml-super-secret-key-change-in-production-2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# ─── Database Settings ───────────────────────────────────────────────────────
# OpenBenchML v4.1 — Supabase Postgres backend.
#
# The Supabase project ref is `fzwvxesrtdilljgrntpw` (from the original
# fastapiproject.git).  We use the **connection pooler** URL so the app
# can scale without exhausting Postgres connections.
#
#   Host      : aws-0-<region>.pooler.supabase.com  (region-aware)
#   Port      : 5432  (direct) / 6543 (pooler)
#   Database  : postgres
#   Username  : postgres.fzwvxesrtdilljgrntpw       (project ref appended)
#   Password  : <your Supabase project password>
#
# Per the user's request: "id is username and username is password" —
# i.e. the Supabase project *URL ref* doubles as the username and the
# *anon key* (or any service key) doubles as the password when calling
# the Supabase REST API directly.  For SQL access via SQLAlchemy we
# use the standard Postgres connection string with the project password.
#
# In production (Render), set DATABASE_URL as a Render environment
# variable pointing at the full Supabase pooler URL — see
# `docs-site/docs/deployment/render.md` for the copy-paste instructions.

SUPABASE_PROJECT_REF = "fzwvxesrtdilljgrntpw"
SUPABASE_URL = os.getenv(
    "SUPABASE_URL",
    f"https://{SUPABASE_PROJECT_REF}.supabase.co",
)
SUPABASE_ANON_KEY = os.getenv(
    "SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZ6d3Z4ZXNydGRpbGxqZ3JudHB3Iiwicm9sZSI6ImFub24i"
    "LCJpYXQiOjE3NTA4NzU2NzMsImV4cCI6MjA2NjQ1MTY3M30."
    "YnxjUtFawuumihyVGuk8e-o6iE9OkDf-MX1aKRTqA5U",
)

# Default Postgres connection string for Supabase. The pooler host is
# region-aware — Render will override DATABASE_URL with the correct region.
#
# If DATABASE_URL is unset (or empty), we auto-assemble it from
# SUPABASE_PROJECT_REF + SUPABASE_DB_PASSWORD. This makes Render deploys
# trivial: just set those two env vars and you're done.
_default_db_url = os.getenv("DATABASE_URL", "").strip()
if not _default_db_url:
    _supabase_pw = os.getenv("SUPABASE_DB_PASSWORD", "").strip()
    if _supabase_pw:
        _default_db_url = (
            f"postgresql://postgres.{SUPABASE_PROJECT_REF}:{_supabase_pw}@"
            f"aws-0-us-east-1.pooler.supabase.com:5432/postgres"
        )
        logger_config = logging.getLogger("openbenchml.config")
        logger_config.info(
            "Auto-assembled DATABASE_URL from SUPABASE_PROJECT_REF + "
            "SUPABASE_DB_PASSWORD (pooler host: aws-0-us-east-1)."
        )

DATABASE_URL = _default_db_url or (
    # Last-resort placeholder so the import doesn't crash if nothing is set.
    # In dev mode USE_SQLITE=True bypasses this entirely.
    f"postgresql://postgres.{SUPABASE_PROJECT_REF}:<SUPABASE_DB_PASSWORD>@"
    f"aws-0-us-east-1.pooler.supabase.com:5432/postgres"
)

# SQLite fallback for development without PostgreSQL
SQLITE_URL = f"sqlite:///{BASE_DIR / 'openbenchml.db'}"

# Use PostgreSQL in production (Render / Supabase), SQLite for local dev.
# Toggle via USE_SQLITE env var. Default is True so first-time dev setup
# doesn't require a live Supabase password.
USE_SQLITE = os.getenv("USE_SQLITE", "True").lower() == "true"
SQLALCHEMY_DATABASE_URL = SQLITE_URL if USE_SQLITE else DATABASE_URL

# Database connection pool settings
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "3600"))
DB_POOL_PRE_PING = True

# ─── Redis Settings ──────────────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ─── Celery Settings ─────────────────────────────────────────────────────────
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL

# ─── Docker Settings ─────────────────────────────────────────────────────────
DOCKER_ENABLED = os.getenv("DOCKER_ENABLED", "False").lower() == "true"
DOCKER_IMAGE = "openbenchml-worker"
DOCKER_TIMEOUT = int(os.getenv("DOCKER_TIMEOUT", "300"))  # 5 minutes max per benchmark

# ─── Benchmark Settings ──────────────────────────────────────────────────────
MAX_MODEL_SIZE_MB = int(os.getenv("MAX_MODEL_SIZE_MB", "500"))
BENCHMARK_TIMEOUT_SECONDS = int(os.getenv("BENCHMARK_TIMEOUT_SECONDS", "300"))
ALLOWED_EXTENSIONS = {".pkl", ".joblib", ".onnx", ".pt", ".h5", ".pb", ".bin", ".model"}

# ─── Pagination ──────────────────────────────────────────────────────────────
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# ─── CORS Settings ───────────────────────────────────────────────────────────
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:8000,http://localhost:3000,http://127.0.0.1:8000"
).split(",")

# ─── Rate Limiting ───────────────────────────────────────────────────────────
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "True").lower() == "true"
RATE_LIMIT_DEFAULT = os.getenv("RATE_LIMIT_DEFAULT", "60/minute")
RATE_LIMIT_LOGIN = os.getenv("RATE_LIMIT_LOGIN", "5/minute")
RATE_LIMIT_REGISTER = os.getenv("RATE_LIMIT_REGISTER", "3/minute")
RATE_LIMIT_UPLOAD = os.getenv("RATE_LIMIT_UPLOAD", "10/minute")
RATE_LIMIT_BENCHMARK = os.getenv("RATE_LIMIT_BENCHMARK", "5/minute")

# ─── Cache Settings ──────────────────────────────────────────────────────────
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "True").lower() == "true"
CACHE_TTL_LEADERBOARD = int(os.getenv("CACHE_TTL_LEADERBOARD", "60"))  # seconds
CACHE_TTL_DATASETS = int(os.getenv("CACHE_TTL_DATASETS", "300"))  # 5 min
CACHE_TTL_STATS = int(os.getenv("CACHE_TTL_STATS", "30"))  # 30 sec

# ─── Security Settings ───────────────────────────────────────────────────────
SECURE_COOKIES = os.getenv("SECURE_COOKIES", "False").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")
BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "12"))

# ─── Logging Settings ────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
REQUEST_LOG_MAX_BODY = int(os.getenv("REQUEST_LOG_MAX_BODY", "1024"))

# ─── GZip Compression ────────────────────────────────────────────────────────
GZIP_MIN_SIZE = int(os.getenv("GZIP_MIN_SIZE", "1000"))

# ─── Jinja2 Templates ────────────────────────────────────────────────────────
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# ─── Allowed Model Frameworks ────────────────────────────────────────────────
FRAMEWORKS = [
    "scikit-learn",
    "pytorch",
    "onnx",
    "tensorflow",
    "xgboost",
    "lightgbm",
]

# ─── Task Types ──────────────────────────────────────────────────────────────
TASK_TYPES = [
    "classification",
    "regression",
    "clustering",
]

# ─── API Versioning ──────────────────────────────────────────────────────────
API_V1_PREFIX = "/api/v1"

# ─── WebSocket Settings ──────────────────────────────────────────────────────
WS_HEARTBEAT_INTERVAL = int(os.getenv("WS_HEARTBEAT_INTERVAL", "30"))
WS_MAX_CONNECTIONS = int(os.getenv("WS_MAX_CONNECTIONS", "100"))
