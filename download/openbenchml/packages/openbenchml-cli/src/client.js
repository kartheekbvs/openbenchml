/**
 * OpenBenchML API client.
 *
 * A thin wrapper around fetch / node-fetch that handles auth, JSON,
 * and form/multipart uploads.
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

// Node 18+ has global fetch; older versions need node-fetch.
let fetchImpl;
try {
  if (typeof fetch === 'function') {
    fetchImpl = fetch;
  } else {
    fetchImpl = require('node-fetch');
  }
} catch (e) {
  fetchImpl = require('node-fetch');
}

const FormDataImpl = (() => {
  try { return require('form-data'); } catch { return null; }
})();

const CREDENTIALS_DIR = path.join(os.homedir(), '.openbenchml');
const CREDENTIALS_FILE = path.join(CREDENTIALS_DIR, 'credentials.json');

class ApiClient {
  constructor({ host, token } = {}) {
    this.host = (host || process.env.OPENBENCHML_HOST || 'http://localhost:8000')
      .replace(/\/$/, '');
    this.token = token || process.env.OPENBENCHML_TOKEN || this._loadSavedToken();
  }

  // ─── Auth & config ────────────────────────────────────────────────────────

  setToken(token) {
    this.token = token;
    this._saveToken(token);
  }

  _loadSavedToken() {
    try {
      if (fs.existsSync(CREDENTIALS_FILE)) {
        const data = JSON.parse(fs.readFileSync(CREDENTIALS_FILE, 'utf8'));
        return data.token || null;
      }
    } catch (e) { /* ignore */ }
    return null;
  }

  _saveToken(token) {
    try {
      if (!fs.existsSync(CREDENTIALS_DIR)) fs.mkdirSync(CREDENTIALS_DIR, { recursive: true, mode: 0o700 });
      fs.writeFileSync(CREDENTIALS_FILE, JSON.stringify({ token }, null, 2), { mode: 0o600 });
    } catch (e) {
      console.error(`Warning: could not save credentials: ${e.message}`);
    }
  }

  clearSavedToken() {
    try { fs.unlinkSync(CREDENTIALS_FILE); } catch (e) { /* ignore */ }
    this.token = null;
  }

  // ─── HTTP helpers ─────────────────────────────────────────────────────────

  _headers(extra = {}) {
    const h = { Accept: 'application/json', ...extra };
    if (this.token) h['Authorization'] = `Bearer ${this.token}`;
    return h;
  }

  async _request(method, pathStr, { body, headers, isForm = false } = {}) {
    const url = `${this.host}${pathStr}`;
    const opts = { method, headers: this._headers(headers) };
    if (body !== undefined) opts.body = body;

    const r = await fetchImpl(url, opts);
    return r;
  }

  async _json(method, pathStr, payload) {
    const r = await this._request(method, pathStr, {
      headers: { 'Content-Type': 'application/json' },
      body: payload ? JSON.stringify(payload) : undefined,
    });
    return this._parseJson(r);
  }

  async _parseJson(r) {
    const text = await r.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch (e) {
      throw new Error(`HTTP ${r.status}: invalid JSON response (${text.slice(0, 200)})`);
    }
    if (!r.ok) {
      const msg = (data && (data.detail || data.message)) || `HTTP ${r.status}`;
      const err = new Error(msg);
      err.status = r.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  // ─── Auth API ─────────────────────────────────────────────────────────────

  async login(email, password) {
    const data = await this._json('POST', '/api/auth/login', { email, password });
    if (data.access_token) this.setToken(data.access_token);
    return data;
  }

  async register({ username, email, password }) {
    const data = await this._json('POST', '/api/auth/register', {
      username, email, password, confirm_password: password,
    });
    if (data.access_token) this.setToken(data.access_token);
    return data;
  }

  async whoami() {
    return this._json('GET', '/api/auth/me');
  }

  // ─── Models API ───────────────────────────────────────────────────────────

  async listModels({ framework } = {}) {
    const qs = framework ? `?framework=${encodeURIComponent(framework)}` : '';
    return this._json('GET', `/api/models${qs}`);
  }

  async getModel(modelId) {
    return this._json('GET', `/api/models/${modelId}`);
  }

  async uploadModel({ filePath, name, description = '', framework }) {
    if (!fs.existsSync(filePath)) {
      throw new Error(`File not found: ${filePath}`);
    }

    // Use the Web FormData + Blob (works on Node 18+ with global fetch).
    // This is more reliable than the form-data npm package because the
    // native fetch implementation knows how to compute the multipart
    // boundary and Content-Length itself.
    const fileBuffer = fs.readFileSync(filePath);
    const fileName = require('path').basename(filePath);

    const FormDataCtor = global.FormData;
    if (!FormDataCtor) throw new Error('FormData is not available — use Node 18+');

    const form = new FormDataCtor();
    form.append('model_name', name);
    form.append('description', description);
    form.append('framework', framework);
    form.append('file', new Blob([fileBuffer]), fileName);

    const headers = {};
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
      headers['Cookie'] = `access_token=${this.token}`;
    }

    const r = await fetchImpl(`${this.host}/models/upload`, {
      method: 'POST',
      headers,
      body: form,
      redirect: 'manual',
    });

    // 303 = success (redirect to /my-models)
    if (r.status === 303) {
      const models = await this.listModels();
      return models[0] || { message: 'Upload successful' };
    }

    // Try to parse error
    const text = await r.text();
    let data;
    try { data = JSON.parse(text); } catch { data = { detail: text }; }
    const errMsg = typeof data.detail === 'object'
      ? JSON.stringify(data.detail)
      : (data.detail || text.slice(0, 200));
    throw new Error(`Upload failed (HTTP ${r.status}): ${errMsg}`);
  }

  // ─── Datasets API ─────────────────────────────────────────────────────────

  async listDatasets({ taskType, difficulty } = {}) {
    const params = new URLSearchParams();
    if (taskType) params.set('task_type', taskType);
    if (difficulty) params.set('difficulty', difficulty);
    const qs = params.toString() ? `?${params.toString()}` : '';
    return this._json('GET', `/api/datasets${qs}`);
  }

  // ─── Benchmark API ────────────────────────────────────────────────────────

  async runBenchmark({ modelId, datasetId }) {
    // The HTML form endpoint returns a 303 redirect to /results/{job_id}.
    // We can parse the Location header to extract the job ID.
    const body = new URLSearchParams({ model_id: String(modelId), dataset_id: String(datasetId) });
    const headers = { 'Content-Type': 'application/x-www-form-urlencoded' };
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
      headers['Cookie'] = `access_token=${this.token}`;
    }

    const r = await fetchImpl(`${this.host}/benchmark`, {
      method: 'POST',
      headers,
      body: body.toString(),
      redirect: 'manual',
    });

    if (r.status === 303) {
      const loc = r.headers.get('location') || '';
      const match = loc.match(/\/results\/(\d+)/);
      if (match) {
        const jobId = parseInt(match[1], 10);
        return { job_id: jobId, status: 'submitted', results_url: `${this.host}${loc}` };
      }
      return { status: 'submitted', redirect: loc };
    }

    const text = await r.text();
    throw new Error(`Benchmark failed (HTTP ${r.status}): ${text.slice(0, 300)}`);
  }

  async getJob(jobId) {
    const jobs = await this._json('GET', '/api/jobs');
    return jobs.find(j => j.id === jobId) || null;
  }

  async getResults(jobId) {
    return this._json('GET', `/api/results/${jobId}`);
  }

  // ─── Leaderboard API ──────────────────────────────────────────────────────

  async getLeaderboard({ datasetId, sortBy, limit } = {}) {
    const params = new URLSearchParams();
    if (datasetId) params.set('dataset_id', String(datasetId));
    if (sortBy) params.set('sort_by', sortBy);
    if (limit) params.set('limit', String(limit));
    const qs = params.toString() ? `?${params.toString()}` : '';
    return this._json('GET', `/api/leaderboard${qs}`);
  }

  // ─── Competitions API ─────────────────────────────────────────────────────

  async listCompetitions({ status } = {}) {
    const qs = status ? `?status=${encodeURIComponent(status)}` : '';
    return this._json('GET', `/api/competitions${qs}`);
  }

  async getCompetition(slug) {
    return this._json('GET', `/api/competitions/${encodeURIComponent(slug)}`);
  }

  async submitToCompetition(slug, { modelId, note = '' }) {
    const body = new URLSearchParams({
      model_id: String(modelId),
      submission_note: note,
    });
    const headers = { 'Content-Type': 'application/x-www-form-urlencoded' };
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
      headers['Cookie'] = `access_token=${this.token}`;
    }

    const r = await fetchImpl(`${this.host}/competitions/${encodeURIComponent(slug)}/submit`, {
      method: 'POST',
      headers,
      body: body.toString(),
      redirect: 'manual',
    });

    if (r.status === 303) {
      return { status: 'submitted', competition_slug: slug };
    }
    const text = await r.text();
    let data; try { data = JSON.parse(text); } catch { data = { detail: text }; }
    const errMsg = typeof data.detail === 'object'
      ? JSON.stringify(data.detail)
      : (data.detail || text.slice(0, 200));
    throw new Error(`Submission failed (HTTP ${r.status}): ${errMsg}`);
  }

  // ─── Notifications API ────────────────────────────────────────────────────

  async listNotifications({ unreadOnly = false, limit = 50 } = {}) {
    const params = new URLSearchParams();
    if (unreadOnly) params.set('unread_only', 'true');
    params.set('limit', String(limit));
    return this._json('GET', `/api/notifications?${params.toString()}`);
  }

  // ─── Convert API (code → pickled MLModel) ─────────────────────────────────

  async convertCode({ code, modelName, description = '', framework = 'scikit-learn' }) {
    return this._json('POST', '/api/convert', {
      model_name: modelName,
      description,
      framework,
      code,
    });
  }

  // ─── Notebook API (run Python code, return stdout/stderr) ─────────────────

  async runCode({ code, timeoutSeconds = 30 }) {
    return this._json('POST', '/api/notebook/run', {
      code,
      timeout_seconds: timeoutSeconds,
    });
  }

  // ─── Real-time WebSocket streams ──────────────────────────────────────────
  //
  // Returns an open WebSocket. Caller attaches `.onmessage`.
  // We use the native WebSocket global (Node 22+ ships it; Node 18-21
  // need the `ws` package which the CLI tries to load as a fallback).

  _resolveWsUrl(pathStr) {
    return this.host.replace(/^http/, 'ws') + pathStr;
  }

  _openWebSocket(pathStr) {
    let WS;
    try { WS = WebSocket; } catch (_) { /* not defined globally */ }
    if (typeof WS === 'undefined') {
      try { WS = require('ws'); } catch (e) {
        throw new Error(
          'WebSocket support not found. On Node < 22 run: npm install -g ws'
        );
      }
    }
    return new WS(this._resolveWsUrl(pathStr));
  }

  streamLeaderboard({ datasetId } = {}, onMessage) {
    const ws = this._openWebSocket('/ws/leaderboard');
    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'subscribe', dataset_id: datasetId }));
    };
    ws.onmessage = (e) => {
      try { onMessage(JSON.parse(typeof e.data === 'string' ? e.data : e.data.toString())); }
      catch (err) { onMessage({ type: 'raw', data: e.data }); }
    };
    return ws;
  }

  streamBenchmark({ jobId } = {}, onMessage) {
    const ws = this._openWebSocket('/ws/benchmark');
    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'subscribe', job_id: jobId }));
    };
    ws.onmessage = (e) => {
      try { onMessage(JSON.parse(typeof e.data === 'string' ? e.data : e.data.toString())); }
      catch (err) { onMessage({ type: 'raw', data: e.data }); }
    };
    return ws;
  }

  streamNotifications(onMessage) {
    const ws = this._openWebSocket('/ws/notifications');
    ws.onmessage = (e) => {
      try { onMessage(JSON.parse(typeof e.data === 'string' ? e.data : e.data.toString())); }
      catch (err) { onMessage({ type: 'raw', data: e.data }); }
    };
    return ws;
  }
}

module.exports = { ApiClient };
