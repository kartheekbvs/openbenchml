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
APP_VERSION = "2.0.0"
APP_DESCRIPTION = "Open Source ML Model Benchmarking Platform - Production Ready"
APP_URL = os.getenv("APP_URL", "http://localhost:8000")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
SECRET_KEY = os.getenv("SECRET_KEY", "openbenchml-super-secret-key-change-in-production-2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# ─── Database Settings ───────────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://openbenchml:openbenchml@localhost:5432/openbenchml"
)

# SQLite fallback for development without PostgreSQL
SQLITE_URL = f"sqlite:///{BASE_DIR / 'openbenchml.db'}"

# Use PostgreSQL in production, SQLite for quick dev
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
