# Real-time WebSocket Channels

OpenBenchML exposes three WebSocket endpoints for real-time updates. All three use the same `ConnectionManager` (defined in `app/main.py`) which keeps a dict of `client_id → WebSocket` and supports `broadcast()`.

## Endpoints

| Path | Purpose |
|------|---------|
| `/ws/benchmark` | Live benchmark job progress (5% → 100%) |
| `/ws/leaderboard` | Leaderboard recomputed notifications |
| `/ws/notifications` | In-app notification push |

## Protocol

All channels speak JSON. Clients send `{"type": "ping"}` for keep-alive; the server responds with `{"type": "pong"}`.

### `/ws/benchmark`

Subscribe to a specific job:

```json
{ "type": "subscribe", "job_id": 1 }
```

Server confirms:

```json
{ "type": "subscribed", "job_id": 1 }
```

Progress messages (broadcast to all subscribers):

```json
{
  "type": "benchmark_progress",
  "job_id": 1,
  "progress": 40,
  "status": "running",
  "message": "Dataset loaded",
  "timestamp": "2025-01-15T12:34:56.789000"
}
```

Progress values: 5 (starting) → 20 (model loaded) → 40 (dataset loaded) → 50 (predictions running) → 85 (metrics computed) → 100 (completed).

### `/ws/leaderboard`

Subscribe to a specific dataset:

```json
{ "type": "subscribe", "dataset_id": 1 }
```

Update messages (broadcast when `update_leaderboard` runs):

```json
{
  "type": "leaderboard_update",
  "dataset_id": 1,
  "dataset_name": "Iris",
  "entries": 5,
  "timestamp": "2025-01-15T12:34:57.123000"
}
```

Clients should re-fetch `/api/leaderboard?dataset_id=...` to get the updated rows.

### `/ws/notifications`

No subscription model — every connected client receives every notification (filter by `user_id` on the client side).

```json
{
  "type": "notification",
  "user_id": 1,
  "notification_type": "submission_received",
  "title": "Submission received for Iris Classification Challenge",
  "body": "Score (accuracy): 1.0",
  "link": "/competitions/iris-classification-challenge",
  "created_at": "2025-01-15T12:34:56"
}
```

## JavaScript client example

```js
const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
const ws = new WebSocket(`${proto}//${location.host}/ws/leaderboard`);

ws.onopen = () => {
  ws.send(JSON.stringify({ type: 'subscribe', dataset_id: 1 }));
  // Heartbeat
  setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'ping' }));
  }, 30000);
};

ws.onmessage = async (evt) => {
  const msg = JSON.parse(evt.data);
  if (msg.type === 'leaderboard_update' && msg.dataset_id === 1) {
    const r = await fetch('/api/leaderboard?dataset_id=1');
    const rows = await r.json();
    renderLeaderboard(rows);
  }
};
```

## Connection management

The `ConnectionManager` class tracks active connections by integer `client_id` (auto-incrementing). On disconnect or send-error, the client is removed. `broadcast()` iterates all connections and silently drops any that fail.

## Limits

- `WS_MAX_CONNECTIONS` (default 100) — maximum concurrent connections.
- `WS_HEARTBEAT_INTERVAL` (default 30 seconds) — recommended client ping interval.

There's no per-user authentication on WebSocket connections in this version — any client can subscribe to any channel. For production use behind a login wall, you may want to add a token query param check at connection time (planned for v3.1).
