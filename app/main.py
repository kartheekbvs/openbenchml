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

# ─── Mount Course App ─────────────────────────────────────────────────────────
from course_app.main import app as course_app
app.mount("/course", course_app, name="course_app")


# ─── Include Routers ─────────────────────────────────────────────────────────
from app.routes import auth, dashboard, models, datasets, benchmark, leaderboard, fastapi_course  # noqa: E402
from app.learning.router import router as learning_router  # noqa: E402

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(models.router)
app.include_router(datasets.router)
app.include_router(benchmark.router)
app.include_router(leaderboard.router)
app.include_router(fastapi_course.router)
app.include_router(learning_router)


# ─── Landing Page ────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    """Render the landing page."""
    return templates.TemplateResponse("landing.html", {
        "request": request,
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
            "auto", "scikit-learn", "pytorch", "onnx", "tensorflow", "xgboost", "lightgbm"
        ],
        "supported_task_types": [
            "classification", "regression", "clustering"
        ],
    }


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
