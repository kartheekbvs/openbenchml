/**
 * LLM Bridge Server — a persistent Node.js HTTP server that calls the
 * z-ai-web-dev-sdk and returns responses to the Python backend.
 *
 * Why this exists:
 *   The Python agent was calling `z-ai` CLI and `node -e` as subprocesses
 *   for every request. On Render, these fail silently (timeout, missing
 *   binary, SDK not found). This persistent server:
 *     1. Starts once (spawned by Python on first agent request)
 *     2. Listens on a local port
 *     3. Python sends HTTP POST with the prompt
 *     4. Node calls z-ai SDK and returns the response
 *     5. Stays alive for subsequent requests (no startup cost)
 *
 * Endpoints:
 *   POST /chat  { system, user }  →  { text }  (raw LLM response)
 *   GET  /health                →  { ok: true }
 */

const http = require('http');
const ZAI = require('z-ai-web-dev-sdk').default;

const PORT = 4599;
let zaiInstance = null;
let isInitializing = false;
let initError = null;

async function initZAI() {
  if (zaiInstance) return zaiInstance;
  if (isInitializing) {
    // Wait for ongoing init
    while (isInitializing) {
      await new Promise(r => setTimeout(r, 100));
    }
    if (zaiInstance) return zaiInstance;
    if (initError) throw initError;
  }
  isInitializing = true;
  try {
    zaiInstance = await ZAI.create();
    console.log('[llm-bridge] ZAI SDK initialized');
    isInitializing = false;
    return zaiInstance;
  } catch (e) {
    initError = e;
    isInitializing = false;
    console.error('[llm-bridge] ZAI init failed:', e.message);
    throw e;
  }
}

const server = http.createServer(async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  res.setHeader('Content-Type', 'application/json');

  if (req.method === 'OPTIONS') {
    res.writeHead(200);
    res.end();
    return;
  }

  if (req.method === 'GET' && req.url === '/health') {
    res.writeHead(200);
    res.end(JSON.stringify({ ok: true, zai_ready: !!zaiInstance }));
    return;
  }

  if (req.method === 'POST' && req.url === '/chat') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', async () => {
      try {
        const { system, user } = JSON.parse(body);

        // Initialize ZAI if needed
        const zai = await initZAI();

        // Call the LLM
        const response = await zai.chat.completions.create({
          messages: [
            { role: 'system', content: system || 'You are a helpful assistant.' },
            { role: 'user', content: user || '' }
          ],
          temperature: 0.3,
          max_tokens: 2000,
        });

        const text = response.choices[0]?.message?.content || '';
        res.writeHead(200);
        res.end(JSON.stringify({ ok: true, text }));
      } catch (e) {
        console.error('[llm-bridge] Error:', e.message);
        res.writeHead(500);
        res.end(JSON.stringify({ ok: false, error: e.message }));
      }
    });
    return;
  }

  res.writeHead(404);
  res.end(JSON.stringify({ error: 'Not found' }));
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`[llm-bridge] Running on http://127.0.0.1:${PORT}`);
  // Pre-initialize ZAI on startup
  initZAI().catch(() => {});
});

// Keep alive
process.on('SIGTERM', () => { server.close(); process.exit(0); });
process.on('SIGINT', () => { server.close(); process.exit(0); });
