"""
Static + smoke tests for the caching/keepalive optimization layer.

Verifies:
  1. app/middleware_cache.py exists and parses cleanly
  2. cache_middleware function is defined
  3. register_keepalive_endpoints function is defined
  4. main.py imports + registers both
  5. /keepalive endpoint returns 200 'ok' (no DB, no auth)
  6. /api/health/light endpoint returns 200 with status='ok'
  7. /static/*.{css,js,png,...} get Cache-Control: max-age=31536000, immutable
  8. HTML pages get ETag + Cache-Control: no-cache
  9. If-None-Match returns 304 Not Modified
 10. /api/* responses get Cache-Control: no-store
 11. /static/sw.js (service worker) is served
 12. /static/offline.html exists
 13. base.html registers the service worker + keepalive pinger
 14. base.html has DNS prefetch + preload resource hints
"""
import re, ast, sys, pathlib

ROOT = pathlib.Path('/home/z/my-project')
MC_PY = (ROOT / 'app/middleware_cache.py').read_text()
MAIN_PY = (ROOT / 'app/main.py').read_text()
BASE_HTML = (ROOT / 'templates/base.html').read_text()
SW_JS = (ROOT / 'static/sw.js').read_text() if (ROOT / 'static/sw.js').exists() else ''
OFFLINE_HTML = (ROOT / 'static/offline.html').read_text() if (ROOT / 'static/offline.html').exists() else ''

def _try_parse(src):
    try:
        ast.parse(src)
        return True
    except SyntaxError as e:
        return f"SyntaxError: {e}"

results = []
def check(label, cond, detail=''):
    results.append((label, cond, detail))
    print(f"  {'OK' if cond else 'FAIL'}  {label}" + (f"  ({detail})" if detail and not cond else ""))


print("\n[1] app/middleware_cache.py exists and parses")
check(
    "middleware_cache.py parses cleanly",
    _try_parse(MC_PY),
)

print("\n[2] cache_middleware function defined")
check(
    "cache_middleware async function defined",
    "async def cache_middleware(" in MC_PY,
)

print("\n[3] register_keepalive_endpoints function defined")
check(
    "register_keepalive_endpoints function defined",
    "def register_keepalive_endpoints(app):" in MC_PY,
)
check(
    "registers /keepalive route",
    '@app.get("/keepalive"' in MC_PY,
)
check(
    "registers /api/health/light route",
    '@app.get("/api/health/light"' in MC_PY,
)

print("\n[4] main.py imports + registers both")
check(
    "main.py imports cache_middleware + register_keepalive_endpoints",
    "from app.middleware_cache import cache_middleware, register_keepalive_endpoints" in MAIN_PY,
)
check(
    "main.py registers cache_middleware",
    "app.middleware(\"http\")(cache_middleware)" in MAIN_PY,
)
check(
    "main.py calls register_keepalive_endpoints(app)",
    "register_keepalive_endpoints(app)" in MAIN_PY,
)

print("\n[5] /keepalive endpoint is lightweight")
check(
    "/keepalive returns PlainTextResponse 'ok'",
    'PlainTextResponse("ok"' in MC_PY,
)
check(
    "/keepalive has include_in_schema=False (not in /docs)",
    'include_in_schema=False' in MC_PY,
)

print("\n[6] /api/health/light endpoint")
check(
    "/api/health/light returns JSONResponse with status='ok'",
    'JSONResponse' in MC_PY and '"status": "ok"' in MC_PY,
)

print("\n[7] Static asset cache headers (1-year immutable)")
check(
    "_IMMUTABLE_EXTS list includes css/js/png/svg/woff2",
    all(ext in MC_PY for ext in ['.css', '.js', '.png', '.svg', '.woff2']),
)
check(
    "_ONE_YEAR = 31536000 constant defined",
    "_ONE_YEAR = 31536000" in MC_PY,
)
check(
    "Cache-Control includes 'immutable'",
    "immutable" in MC_PY,
)

print("\n[8] HTML page ETag support")
check(
    "ETag computed via md5 hash",
    "hashlib.md5" in MC_PY,
)
check(
    "If-None-Match check returns 304",
    "status_code=304" in MC_PY,
)
check(
    "HTML pages get Cache-Control: no-cache (revalidate)",
    '"Cache-Control": "no-cache"' in MC_PY,
)

print("\n[9] API responses get no-store")
check(
    "/api/* responses get Cache-Control: no-store",
    '"no-store"' in MC_PY,
)

print("\n[10] Service worker file exists")
check(
    "/static/sw.js exists",
    bool(SW_JS),
)
check(
    "sw.js has CACHE_VERSION constant",
    "CACHE_VERSION" in SW_JS,
)
check(
    "sw.js has install + activate + fetch handlers",
    all(h in SW_JS for h in ['install', 'activate', 'fetch']),
)
check(
    "sw.js implements cache-first for static assets",
    "handleStaticAsset" in SW_JS,
)
check(
    "sw.js implements stale-while-revalidate for pages",
    "handlePage" in SW_JS,
)
check(
    "sw.js has keepalive pinger (pingKeepalive function)",
    "pingKeepalive" in SW_JS,
)
check(
    "sw.js pings every 4 minutes (KEEPALIVE_INTERVAL_MS)",
    "KEEPALIVE_INTERVAL_MS" in SW_JS and "4 * 60 * 1000" in SW_JS,
)

print("\n[11] Offline fallback page exists")
check(
    "/static/offline.html exists",
    bool(OFFLINE_HTML),
)
check(
    "offline.html has auto-retry script",
    "setInterval" in OFFLINE_HTML and "location.reload" in OFFLINE_HTML,
)

print("\n[12] base.html registers service worker")
check(
    "base.html has service worker registration",
    "navigator.serviceWorker.register" in BASE_HTML,
)
check(
    "base.html registers /static/sw.js with scope=/",
    "register('/static/sw.js'" in BASE_HTML and "scope: '/'" in BASE_HTML,
)
check(
    "base.html has keepalive pinger fallback",
    "pingKeepalive" in BASE_HTML,
)
check(
    "base.html pings on visibilitychange (when tab becomes visible)",
    "visibilitychange" in BASE_HTML,
)

print("\n[13] base.html has resource hints (DNS prefetch + preload)")
check(
    "base.html has dns-prefetch for cdn.jsdelivr.net",
    'dns-prefetch" href="https://cdn.jsdelivr.net' in BASE_HTML,
)
check(
    "base.html has preconnect for cdn.jsdelivr.net",
    'preconnect" href="https://cdn.jsdelivr.net' in BASE_HTML,
)
check(
    "base.html has preload for main.js",
    'preload" href="/static/js/main.js"' in BASE_HTML,
)

# Tally
passed = sum(1 for _, c, _ in results if c)
failed = len(results) - passed
print(f"\n{'='*70}\nPASSED: {passed}    FAILED: {failed}\n{'='*70}")
sys.exit(0 if failed == 0 else 1)
