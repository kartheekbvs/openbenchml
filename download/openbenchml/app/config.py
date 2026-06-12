"""
OpenBenchML Configuration
=========================
Central configuration for the entire application.
All settings are loaded from environment variables with sensible defaults.
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
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "Open Source ML Model Benchmarking Platform"
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
SECRET_KEY = os.getenv("SECRET_KEY", "openbenchml-super-secret-key-change-in-production-2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

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
ALLOWED_EXTENSIONS = {".pkl", ".joblib", ".onnx", ".pt", ".h5", ".pb"}

# ─── Pagination ──────────────────────────────────────────────────────────────
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

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
