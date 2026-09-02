/* ==========================================================================
   OpenBenchML Service Worker
   ==========================================================================
   ADDITIVE performance layer — does NOT touch any existing JS.

   Responsibilities:
   1. Cache static assets (CSS, JS, images, fonts) on first visit.
      On repeat visits, serve from cache → instant load + zero server load.
   2. Stale-while-revalidate for HTML pages:
      Serve cached page immediately, fetch fresh in background, update cache.
   3. Keep-alive pinger: every 4 minutes, fetch /keepalive to prevent
      Render's free web service from sleeping. The service worker keeps
      pinging even if the user switches tabs (as long as the tab is open).
   4. Offline fallback: if the network is down, serve cached pages.
      If nothing is cached, show a friendly offline page.

   Version: 1.0.0  (bump to force cache invalidation on deploy)
   ========================================================================== */

const CACHE_VERSION = 'obml-v2.0.0';
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const PAGE_CACHE = `${CACHE_VERSION}-pages`;

// Assets to cache immediately on service worker install (precache).
// These are the bare minimum for the page to render.
const PRECACHE_URLS = [
  '/static/css/style.css',
  '/static/js/main.js',
  '/offline.html',
];

// Maximum number of pages to cache (LRU eviction when exceeded).
const MAX_PAGE_CACHE = 30;

// Install event — precache critical assets.
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .catch((err) => console.warn('[SW] precache failed (non-fatal):', err))
      .then(() => self.skipWaiting())  // activate new SW immediately
  );
});

// Activate event — clean up old caches.
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys
          .filter((key) => !key.startsWith(CACHE_VERSION))
          .map((key) => caches.delete(key))
      ))
      .then(() => self.clients.claim())  // take control of all open tabs
  );
});

// ─── Static asset strategy: cache-first, then network ──────────────────
// If the asset is in cache, serve it (instant). If not, fetch from network,
// cache it, and serve. Static assets are immutable (versioned by URL), so
// this is safe.
async function handleStaticAsset(request) {
  const cached = await caches.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    // Only cache successful responses
    if (response.ok && response.type === 'basic') {
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    // Network failed and not in cache — return a 504
    return new Response('Offline', { status: 504, statusText: 'Offline' });
  }
}

// ─── HTML page strategy: stale-while-revalidate ────────────────────────
// Serve cached page immediately (instant load), fetch fresh in background,
// update cache + notify clients if the page changed.
async function handlePage(request) {
  const cache = await caches.open(PAGE_CACHE);
  const cached = await cache.match(request);

  // Fetch fresh in the background
  const fetchPromise = fetch(request)
    .then((response) => {
      if (response.ok && response.type === 'basic') {
        // LRU eviction: if cache is too big, delete oldest entries
        cache.keys().then((keys) => {
          if (keys.length > MAX_PAGE_CACHE) {
            // Delete the oldest 5 entries
            Promise.all(keys.slice(0, 5).map((k) => cache.delete(k)));
          }
        });
        cache.put(request, response.clone());
      }
      return response;
    })
    .catch(() => null);  // network failed — that's ok, we have cache

  // Return cached version immediately if available, else wait for network
  return cached || fetchPromise || new Response('Offline', {
    status: 504,
    statusText: 'Offline',
    headers: { 'Content-Type': 'text/html' },
  });
}

// ─── Main fetch handler ────────────────────────────────────────────────
self.addEventListener('fetch', (event) => {
  const request = event.request;

  // Only handle GET requests
  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  // Skip cross-origin requests (e.g. CDN, fonts.googleapis.com)
  if (url.origin !== self.location.origin) return;

  // Skip /keepalive — it should always hit the server
  if (url.pathname === '/keepalive' || url.pathname === '/api/health/light') return;

  // Skip /api/* — always hit the server (no caching of API responses)
  if (url.pathname.startsWith('/api/')) return;

  // Skip /ws/* — WebSocket upgrade requests
  if (url.pathname.startsWith('/ws/')) return;

  // SKIP /learn/labs/* — lab pages must always be fresh (JS changes frequently)
  // This is the fix for "interactive charts not showing" — stale cache was
  // serving the old broken version. Lab pages now bypass the service worker.
  if (url.pathname.startsWith('/learn/labs')) {
    return;  // Let the browser fetch from network directly
  }

  // Static assets → cache-first
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(handleStaticAsset(request));
    return;
  }

  // HTML pages → stale-while-revalidate
  if (request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(handlePage(request));
    return;
  }

  // Everything else → try network, fall back to cache
  event.respondWith(
    fetch(request).catch(() => caches.match(request) || new Response('Offline', { status: 504 }))
  );
});

// ─── Keep-alive pinger ─────────────────────────────────────────────────
// Every 4 minutes, ping /keepalive to prevent Render from sleeping.
// Render's free web service sleeps after 15 min of inactivity, so 4 min
// intervals give a comfortable margin.
const KEEPALIVE_INTERVAL_MS = 4 * 60 * 1000;  // 4 minutes

async function pingKeepalive() {
  try {
    const response = await fetch('/keepalive', { cache: 'no-store' });
    if (response.ok) {
      // console.log('[SW] keepalive ok');
    }
  } catch (err) {
    // Network failed — server might be restarting. Try again next interval.
    console.warn('[SW] keepalive failed:', err.message);
  }
}

// Start the keepalive loop when the service worker activates
self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      // Clean up old caches (from the activate handler above)
      const keys = await caches.keys();
      await Promise.all(
        keys
          .filter((key) => !key.startsWith(CACHE_VERSION))
          .map((key) => caches.delete(key))
      );
      await self.clients.claim();

      // Start the keepalive loop
      pingKeepalive();  // ping once immediately
      setInterval(pingKeepalive, KEEPALIVE_INTERVAL_MS);
    })()
  );
});

// ─── Message handler — allow pages to manually trigger keepalive ───────
self.addEventListener('message', (event) => {
  if (event.data === 'ping') {
    pingKeepalive();
  }
  if (event.data === 'skipWaiting') {
    self.skipWaiting();
  }
});
