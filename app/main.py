"""
OpenBenchML - Main Application
================================
FastAPI application entry point with production-ready features:
- CORS middleware for cross-origin requests
- GZip compression for response sizes > 1KB
- Request timing middleware
- Security headers middleware
- Custom exception handlers
- Rate limiting setup
- WebSocket support for real-time updates
- Enhanced health check with dependency status
"""

import logging
import time
import traceback
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.config import (
    APP_NAME, APP_VERSION, APP_DESCRIPTION, STATIC_DIR, TEMPLATE_DIR,
    templates, CORS_ORIGINS, DEBUG, GZIP_MIN_SIZE, LOG_LEVEL, LOG_FORMAT,
    RATE_LIMIT_ENABLED, WS_HEARTBEAT_INTERVAL,
)
from app.database.db import init_db
from app.database.seed import seed_database
from app.services.sample_models_service import ensure_sample_models

# Configure logging
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO), format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# ─── WebSocket Connection Manager ─────────────────────────────────────────────
class ConnectionManager:
    """Manages WebSocket connections for real-time benchmark updates."""

    def __init__(self):
        self.active_connections: dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: int):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info("WebSocket client connected: %d", client_id)

    def disconnect(self, client_id: int):
        self.active_connections.pop(client_id, None)
        logger.info("WebSocket client disconnected: %d", client_id)

    async def send_json(self, client_id: int, data: dict):
        ws = self.active_connections.get(client_id)
        if ws:
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(client_id)

    async def broadcast(self, data: dict):
        disconnected = []
        for cid, ws in self.active_connections.items():
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.append(cid)
        for cid in disconnected:
            self.disconnect(cid)

    @property
    def connection_count(self) -> int:
        return len(self.active_connections)


ws_manager = ConnectionManager()


# ─── Application Lifespan ─────────────────────────────────────────────────────

def _spawn_sample_model_seeder():
    """Train/refresh sample models in a background daemon thread.

    Runs in parallel with uvicorn binding the port so that Render's
    port scanner sees the open socket immediately.  We use a worker
    thread (not asyncio.to_thread) because sklearn's fit() is CPU-bound
    and we don't want to hold the event loop.  ``daemon=True`` ensures
    the thread never blocks process shutdown.
    """
    import threading
    import traceback as _tb

    def _worker():
        try:
            from app.database.db import SessionLocal
            _seed_db = SessionLocal()
            try:
                stats = ensure_sample_models(_seed_db)
                logger.info(
                    "Sample models: created=%d reused=%d failed=%d total=%d",
                    stats["created"], stats["reused"], stats["failed"], stats["total"],
                )
            finally:
                _seed_db.close()
        except Exception as exc:
            logger.error("Sample model seeding failed (non-fatal): %s\n%s",
                         exc, _tb.format_exc())

    t = threading.Thread(target=_worker, name="sample-models-seeder", daemon=True)
    t.start()
    logger.info("Sample-model seeder thread started (background, non-blocking)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info(f"Starting {APP_NAME} v{APP_VERSION}")
    logger.info(f"Debug mode: {DEBUG}")

    # Initialize database
    init_db()
    logger.info("Database tables created/verified")

    # Seed with default datasets
    seed_database()
    logger.info("Database seeded with default datasets")

    # Log configuration
    logger.info(f"Rate limiting: {'enabled' if RATE_LIMIT_ENABLED else 'disabled'}")
    logger.info(f"CORS origins: {CORS_ORIGINS}")

    # IMPORTANT: Train sample models in a BACKGROUND daemon thread.
    # If we call ensure_sample_models() synchronously here, Render's
    # port scanner times out before uvicorn binds to $PORT and the
    # deploy fails with "no open ports detected".  The daemon thread
    # starts immediately but does NOT block — uvicorn binds the port
    # right away, and training continues in parallel.
    _spawn_sample_model_seeder()

    yield

    logger.info(f"Shutting down {APP_NAME}")
    # Cleanup: close all WebSocket connections
    for cid in list(ws_manager.active_connections.keys()):
        ws_manager.disconnect(cid)


# ─── Create FastAPI Application ───────────────────────────────────────────────
app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    contact={
        "name": "OpenBenchML",
        "url": "https://github.com/kartheekbvs/openbenchml",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
)


# ─── Middleware Stack (order matters - last added = first executed) ────────────

# 1. GZip Compression
app.add_middleware(GZipMiddleware, minimum_size=GZIP_MIN_SIZE)

# 2. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Process-Time", "X-Request-ID"],
)


# 3. Request Timing + Security Headers
@app.middleware("http")
async def request_middleware(request: Request, call_next):
    """Add timing, security headers, and request logging."""
    start_time = time.perf_counter()
    request_id = f"{int(start_time * 1000)}-{id(request)}"

    # Process the request
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.error("Unhandled exception: %s\n%s", exc, traceback.format_exc())
        response = JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request_id},
        )

    # Calculate processing time
    process_time = time.perf_counter() - start_time
    process_time_ms = round(process_time * 1000, 2)

    # Add custom headers
    response.headers["X-Process-Time"] = f"{process_time_ms}ms"
    response.headers["X-Request-ID"] = request_id

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if not DEBUG:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    # Log the request (skip static files and health checks to reduce noise)
    path = request.url.path
    if not path.startswith("/static") and path != "/health":
        logger.info(
            "%s %s → %d (%.1fms) [%s]",
            request.method,
            path,
            response.status_code,
            process_time_ms,
            request_id,
        )

    return response


# ─── Custom Exception Handlers ────────────────────────────────────────────────
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Custom 404 handler that returns HTML for browser requests."""
    if request.headers.get("accept", "").startswith("text/html"):
        return templates.TemplateResponse("base.html", {
            "request": request,
            "error": "Page not found",
            "error_code": 404,
        }, status_code=404)
    return JSONResponse(status_code=404, content={"detail": "Not found"})


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Custom 500 handler."""
    logger.error("Internal server error on %s: %s", request.url.path, exc)
    if request.headers.get("accept", "").startswith("text/html"):
        return templates.TemplateResponse("base.html", {
            "request": request,
            "error": "Internal server error",
            "error_code": 500,
        }, status_code=500)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.exception_handler(429)
async def rate_limit_handler(request: Request, exc):
    """Custom 429 rate limit handler."""
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Too many requests. Please slow down.",
            "retry_after": 60,
        },
        headers={"Retry-After": "60"},
    )


# ─── Mount Static Files ──────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ─── Include Routers ─────────────────────────────────────────────────────────
from app.routes import auth, dashboard, models, datasets, benchmark, leaderboard  # noqa: E402
from app.routes import competitions, comments  # noqa: E402
from app.routes import convert  # noqa: E402
from app.routes import notebook as notebook_route  # noqa: E402
from app.routes import learn as learn_route  # noqa: E402
from app.routes import learn_project as learn_project_route  # noqa: E402
from app.routes import auth_bridge  # noqa: E402

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(models.router)
app.include_router(datasets.router)
app.include_router(benchmark.router)
app.include_router(leaderboard.router)
app.include_router(competitions.router)
app.include_router(comments.router)
app.include_router(convert.router)
app.include_router(notebook_route.router)
app.include_router(learn_route.router)
app.include_router(learn_project_route.router)
app.include_router(auth_bridge.router)


# ─── Landing Page ────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    """Render the landing page."""
    return templates.TemplateResponse("landing.html", {
        "request": request,
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
    })


# ─── Real-time snippets page (auth-gated; useful from any browser) ───────────
@app.get("/realtime", response_class=HTMLResponse)
async def realtime_page(request: Request):
    """Render the real-time WebSocket snippets page.

    The page is intentionally accessible without login so that students
    can browse the snippets before signing up.  The embedded live preview
    will simply show "disconnected" events until login; once logged in
    on another tab, the WS endpoints accept the connection anyway.
    """
    # Try to extract the user (for the navbar), but don't redirect.
    from app.routes.auth import get_current_user_from_cookie
    from app.database.db import SessionLocal
    db = SessionLocal()
    try:
        user = await get_current_user_from_cookie(request, db)
    finally:
        db.close()

    return templates.TemplateResponse("realtime.html", {
        "request": request,
        "user": user,
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
    })


# ─── Enhanced Health Check ────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    """Comprehensive API health check with dependency status."""
    import psutil
    from app.config import USE_SQLITE, REDIS_URL, DOCKER_ENABLED

    health_data = {
        "status": "healthy",
        "app": APP_NAME,
        "version": APP_VERSION,
        "environment": "development" if USE_SQLITE else "production",
        "database": "sqlite" if USE_SQLITE else "postgresql",
        "docker_sandbox": "enabled" if DOCKER_ENABLED else "disabled",
    }

    # System metrics
    try:
        health_data["system"] = {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage("/").percent,
        }
    except Exception:
        pass

    # Check database connectivity
    try:
        from app.database.db import SessionLocal
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        health_data["database_status"] = "connected"
    except Exception:
        health_data["database_status"] = "error"

    # Check Redis connectivity
    try:
        import redis
        r = redis.from_url(REDIS_URL)
        r.ping()
        health_data["redis_status"] = "connected"
        r.close()
    except Exception:
        health_data["redis_status"] = "unavailable"

    # WebSocket stats
    health_data["websocket_connections"] = ws_manager.connection_count

    return health_data


# ─── API Info Endpoint ────────────────────────────────────────────────────────
@app.get("/api/info")
async def api_info():
    """Return API metadata and available endpoints."""
    return {
        "name": APP_NAME,
        "version": APP_VERSION,
        "description": APP_DESCRIPTION,
        "endpoints": {
            "auth": {
                "register": "POST /api/auth/register",
                "login": "POST /api/auth/login",
            },
            "models": {
                "list": "GET /api/models",
                "detail": "GET /api/models/{id}",
                "upload": "POST /models/upload",
            },
            "datasets": {
                "list": "GET /api/datasets",
                "detail": "GET /datasets/{id}",
            },
            "benchmarks": {
                "list_jobs": "GET /api/jobs",
                "results": "GET /api/results/{id}",
            },
            "leaderboard": {
                "global": "GET /api/leaderboard",
                "by_score": "GET /leaderboard",
                "by_speed": "GET /leaderboard/fastest",
                "by_size": "GET /leaderboard/smallest",
            },
            "docs": "/docs",
            "health": "/health",
        },
        "supported_frameworks": [
            "scikit-learn", "pytorch", "onnx", "tensorflow", "xgboost", "lightgbm"
        ],
        "supported_task_types": [
            "classification", "regression", "clustering"
        ],
    }


# ─── Model Cache Inspection (admin/debug) ─────────────────────────────────────
@app.get("/api/admin/model-cache")
async def model_cache_info():
    """Return the current in-memory model cache contents.

    The benchmark engine caches deserialised models in process memory
    keyed by ``(file_path, framework)`` so repeated benchmarks against
    the same model don't pay the joblib.load() cost (~80-150 ms) every
    time.  This endpoint exposes the cache state for debugging.
    """
    from app.benchmark_engine.loader import get_model_cache_info, clear_model_cache
    return {
        "cached_models": get_model_cache_info(),
        "count": len(get_model_cache_info()),
    }


@app.post("/api/admin/model-cache/clear")
async def model_cache_clear():
    """Drop all cached models.  Use after re-uploading a model file
    to force the next benchmark to re-load from disk.
    """
    from app.benchmark_engine.loader import clear_model_cache
    n = clear_model_cache()
    return {"cleared": n}


# ─── WebSocket Endpoint ──────────────────────────────────────────────────────
import asyncio

_next_ws_id = 0

@app.websocket("/ws/benchmark")
async def websocket_benchmark(websocket: WebSocket):
    """WebSocket endpoint for real-time benchmark progress updates.
    
    Clients can connect to receive live progress notifications when
    benchmarks are running. Messages are JSON with the format:
    {"type": "progress", "job_id": 1, "progress": 50, "status": "running"}
    """
    global _next_ws_id
    client_id = _next_ws_id
    _next_ws_id += 1

    await ws_manager.connect(websocket, client_id)
    try:
        while True:
            # Receive messages from client (keep-alive / subscription requests)
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await ws_manager.send_json(client_id, {"type": "pong"})
            elif data.get("type") == "subscribe":
                job_id = data.get("job_id")
                if job_id:
                    await ws_manager.send_json(client_id, {
                        "type": "subscribed",
                        "job_id": job_id,
                    })
    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)
    except Exception as exc:
        logger.error("WebSocket error for client %d: %s", client_id, exc)
        ws_manager.disconnect(client_id)


@app.websocket("/ws/leaderboard")
async def websocket_leaderboard(websocket: WebSocket):
    """WebSocket endpoint for real-time leaderboard updates.

    Clients connect to receive notifications whenever a benchmark
    completes and the leaderboard changes. Messages have the format:
    {"type": "leaderboard_update", "dataset_id": 1, "model_id": 5, ...}
    """
    global _next_ws_id
    client_id = _next_ws_id
    _next_ws_id += 1

    await ws_manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await ws_manager.send_json(client_id, {"type": "pong"})
            elif data.get("type") == "subscribe":
                dataset_id = data.get("dataset_id")
                await ws_manager.send_json(client_id, {
                    "type": "subscribed",
                    "dataset_id": dataset_id,
                })
    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)
    except Exception as exc:
        logger.error("Leaderboard WebSocket error for client %d: %s", client_id, exc)
        ws_manager.disconnect(client_id)


@app.websocket("/ws/notifications")
async def websocket_notifications(websocket: WebSocket):
    """WebSocket endpoint for in-app real-time notifications.

    Clients receive messages with the format:
    {"type": "notification", "user_id": 1, "title": "...", "body": "..."}
    """
    global _next_ws_id
    client_id = _next_ws_id
    _next_ws_id += 1

    await ws_manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await ws_manager.send_json(client_id, {"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)
    except Exception as exc:
        logger.error("Notifications WebSocket error for client %d: %s", client_id, exc)
        ws_manager.disconnect(client_id)
