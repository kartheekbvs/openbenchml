"""
OpenBenchML — Caching + Keep-Alive Middleware
==============================================

ADDITIVE performance layer — does NOT modify any existing code.
Registers a single middleware that adds:

1. Cache-Control headers on /static/* responses
   - 1-year immutable cache for JS/CSS/images/fonts
   - Browser reuses the file on every page load → no re-download
   - Combined with GZip (already in main.py), pages load in <100ms
     after the first visit.

2. ETag headers on HTML pages
   - Browser sends If-None-Match → server returns 304 Not Modified
     if the page hasn't changed → no body transfer.
   - ETag is a hash of the response body — changes when content changes.

3. A lightweight /keepalive endpoint (no DB, no auth, no templates)
   - Returns 200 + 'ok' in <5ms.
   - Used by the browser-side pinger (every 4 min) to prevent Render's
     free web service from sleeping.

4. A lightweight /api/health/light endpoint (no DB, no auth)
   - Same as /keepalive but with a JSON body for monitoring tools.

All of this is OPT-IN: existing routes/middleware/templates are untouched.
"""

from __future__ import annotations

import hashlib
import time
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse


# ═══════════════════════════════════════════════════════════════════════════
#  Cache-Control + ETag middleware
# ═══════════════════════════════════════════════════════════════════════════

# File extensions that should be cached aggressively (1 year, immutable).
# These are static assets that never change at the same URL — when we
# update them, we update the URL (e.g. style.css?v=2).
_IMMUTABLE_EXTS = {
    ".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot", ".webp", ".avif",
}

# Cache 1 year (in seconds) — the max recommended by HTTP spec
_ONE_YEAR = 31536000


def _is_immutable_static(path: str) -> bool:
    """True if `path` is a static asset that should be cached 1 year."""
    if not path.startswith("/static/"):
        return False
    lower = path.lower()
    return any(lower.endswith(ext) for ext in _IMMUTABLE_EXTS)


def _is_html_page(path: str, content_type: str) -> bool:
    """True if the response is an HTML page (not a static file, not an API)."""
    if path.startswith("/static/"):
        return False
    if path.startswith("/api/"):
        return False
    if path.startswith("/ws/"):
        return False
    if path.startswith("/content/"):
        return False
    return "text/html" in (content_type or "")


async def cache_middleware(request: Request, call_next: Callable):
    """Add Cache-Control + ETag headers to responses.

    - /static/*.{css,js,png,...} → Cache-Control: public, max-age=31536000, immutable
    - HTML pages → ETag + Cache-Control: no-cache (revalidate, but reuse if 304)
    - API responses → no caching (always fresh)
    """
    response = await call_next(request)
    path = request.url.path

    # ── Static assets: 1-year immutable cache ────────────────────────
    if _is_immutable_static(path):
        response.headers["Cache-Control"] = f"public, max-age={_ONE_YEAR}, immutable"
        # Vary: Accept-Encoding so cached gzip + br responses don't mix
        response.headers["Vary"] = "Accept-Encoding"
        return response

    # ── HTML pages: ETag + revalidation ──────────────────────────────
    content_type = response.headers.get("content-type", "")
    if _is_html_page(path, content_type) and response.status_code == 200:
        # Read the body bytes. Starlette responses may use a streaming
        # body iterator (TemplateResponse, StreamingResponse) OR a
        # pre-set .body attribute (Response, JSONResponse). Handle both.
        body_bytes = None
        if hasattr(response, "body") and isinstance(response.body, (bytes, bytearray)):
            # Plain Response / JSONResponse — body is already in memory
            body_bytes = bytes(response.body)
        elif hasattr(response, "body_iterator"):
            # StreamingResponse / TemplateResponse — consume the iterator
            chunks = []
            async for chunk in response.body_iterator:
                chunks.append(chunk)
            body_bytes = b"".join(chunks)
            # Replace the iterator with the consumed bytes so the client
            # still gets the body. We rebuild a plain Response below.

        if body_bytes is not None and len(body_bytes) > 0:
            etag = '"' + hashlib.md5(body_bytes).hexdigest()[:16] + '"'

            # Check If-None-Match — return 304 if the ETag matches
            if_none_match = request.headers.get("if-none-match")
            if if_none_match and etag in if_none_match:
                # 304 Not Modified — no body, just headers
                return Response(
                    status_code=304,
                    headers={
                        "ETag": etag,
                        "Cache-Control": "no-cache",
                        "Vary": "Accept-Encoding",
                    },
                )

            # Return a fresh Response with the body + ETag headers.
            # We can't mutate the original response's headers reliably
            # (StreamingResponse sends headers before body), so we
            # rebuild a plain Response with all the original headers
            # plus our ETag/Cache-Control additions.
            new_headers = dict(response.headers)
            new_headers["ETag"] = etag
            new_headers["Cache-Control"] = "no-cache"
            new_headers["Vary"] = "Accept-Encoding"
            return Response(
                content=body_bytes,
                status_code=200,
                headers=new_headers,
                media_type=response.media_type,
            )

    # ── API responses: no caching by default (avoid stale data) ─────
    # Individual endpoints can opt-in by setting Cache-Control themselves.
    if path.startswith("/api/") and "cache-control" not in {k.lower() for k in response.headers.keys()}:
        response.headers["Cache-Control"] = "no-store"

    return response


# ═══════════════════════════════════════════════════════════════════════════
#  Keep-alive endpoints (no DB, no auth — ultra-fast)
# ═══════════════════════════════════════════════════════════════════════════

# Last time the server was pinged — used by /keepalive to report liveness.
_last_ping_time = time.time()


def register_keepalive_endpoints(app):
    """Register /keepalive + /api/health/light on the FastAPI app.

    These are intentionally MINIMAL — no DB session, no auth check, no
    template rendering. They return in <5ms so the browser can ping
    them every 4 minutes without slowing down.
    """
    @app.get("/keepalive", include_in_schema=False)
    async def keepalive():
        """Ultra-lightweight endpoint to prevent Render from sleeping.

        Render's free web service sleeps after 15 min of inactivity.
        The browser pings this endpoint every 4 minutes (via the
        service worker or a setInterval in main.js) to keep the
        server warm. No DB, no auth — just 'ok'.
        """
        import app.middleware_cache as _mod
        _mod._last_ping_time = time.time()
        return PlainTextResponse("ok", media_type="text/plain")

    @app.get("/api/health/light", include_in_schema=False)
    async def health_light():
        """Lightweight health check — no DB, no auth. For monitoring."""
        uptime = round(time.time() - _last_ping_time, 1)
        return JSONResponse({
            "status": "ok",
            "uptime_since_last_ping_s": uptime,
            "timestamp": time.time(),
        })
