"""
OpenBenchML - Main Application
================================
FastAPI application entry point with Jinja2 templates.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from app.config import APP_NAME, APP_VERSION, APP_DESCRIPTION, STATIC_DIR, TEMPLATE_DIR, templates
from app.database.db import init_db
from app.database.seed import seed_database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info(f"Starting {APP_NAME} v{APP_VERSION}")
    # Initialize database
    init_db()
    logger.info("Database tables created")
    # Seed with default datasets
    seed_database()
    logger.info("Database seeded with default datasets")
    yield
    logger.info(f"Shutting down {APP_NAME}")


# Create FastAPI application
app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Jinja2 templates (imported from config for single-source-of-truth)
# templates is imported from app.config


# ─── Global Template Context ─────────────────────────────────────────────────
@app.middleware("http")
async def add_template_context(request: Request, call_next):
    """Add common context variables to all requests."""
    response = await call_next(request)
    return response


# ─── Include Routers ─────────────────────────────────────────────────────────
from app.routes import auth, dashboard, models, datasets, benchmark, leaderboard  # noqa: E402

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(models.router)
app.include_router(datasets.router)
app.include_router(benchmark.router)
app.include_router(leaderboard.router)


# ─── Landing Page ────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    """Render the landing page."""
    return templates.TemplateResponse("landing.html", {
        "request": request,
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
    })


# ─── Health Check ────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    """API health check endpoint."""
    return {
        "status": "healthy",
        "app": APP_NAME,
        "version": APP_VERSION,
    }
