# Real-time Snippets

OpenBenchML streams live updates over **three WebSocket channels**:

| Channel                | Endpoint              | What it carries                                  |
| ---------------------- | --------------------- | ------------------------------------------------ |
| Benchmark progress     | `/ws/benchmark`       | Per-job progress (0–100%) + status changes       |
| Leaderboard updates    | `/ws/leaderboard`     | Rank changes when a benchmark completes          |
| In-app notifications   | `/ws/notifications`   | "Benchmark finished", "Comment reply", etc.      |

The `/realtime` page in the web UI shows copy-paste-ready snippets for all
three channels. This page collects the same snippets plus extras.

## Snippet 1 — Benchmark progress (browser)

```javascript
// Track a running benchmark by job_id.
const ws = new WebSocket(`${location.origin.replace('http','ws')}/ws/benchmark`);
ws.onopen = () => {
  ws.send(JSON.stringify({ type: 'subscribe', job_id: 42 }));
};
ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  if (msg.type === 'progress') {
    console.log(`Job ${msg.job_id}: ${msg.progress}% (${msg.status})`);
  }
};
```

## Snippet 2 — Leaderboard live updates (browser)

```javascript
// Get notified every time a benchmark finishes and the leaderboard moves.
// Use this to build Kaggle-style "jumped 3 spots!" alerts.
const ws = new WebSocket(`${location.origin.replace('http','ws')}/ws/leaderboard`);
ws.onopen = () => ws.send(JSON.stringify({ type: 'subscribe', dataset_id: 1 }));
ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  if (msg.type === 'leaderboard_update') {
    console.log(`#${msg.rank} ${msg.model_name} — score ${msg.score}`);
    console.log(`  prev rank: ${msg.previous_rank} → new rank: ${msg.rank}`);
  }
};
```

## Snippet 3 — Notifications (browser)

```javascript
// Receive in-app notifications in real time: benchmark completed,
// leaderboard rank changed, competition started, comment reply.
const ws = new WebSocket(`${location.origin.replace('http','ws')}/ws/notifications`);
ws.onmessage = (e) => {
  const n = JSON.parse(e.data);
  if (n.type === 'notification') {
    showToast(n.title, n.body);
    // e.g. "Leaderboard moved" — "Your model X jumped from #5 to #2!"
  }
};
ws.onclose = () => console.log('Reconnect with exponential backoff…');
```

## Snippet 4 — Python (`websockets` library)

```python
# pip install websockets
import asyncio, json, websockets

async def main():
    async with websockets.connect("ws://localhost:8000/ws/leaderboard") as ws:
        await ws.send(json.dumps({"type": "subscribe", "dataset_id": 1}))
        async for raw in ws:
            msg = json.loads(raw)
            if msg.get("type") == "leaderboard_update":
                print(f"#{msg['rank']}  {msg['model_name']}  "
                      f"score={msg['score']:.4f}")

asyncio.run(main())
```

## Snippet 5 — CLI one-liner

```bash
# Stream leaderboard events from the terminal:
npx openbenchml watch --channel leaderboard --dataset-id 1

# Or benchmark progress:
npx openbenchml watch --channel benchmark --job-id 42

# Or notifications:
npx openbenchml watch --channel notifications
```

## Snippet 6 — Quick health check

```bash
# See how many WS clients are connected right now:
curl -s http://localhost:8000/health | jq .websocket_connections

# Sample response:
# {
#   "status": "healthy",
#   "version": "4.0.0",
#   "websocket_connections": 12,
#   "database_status": "connected",
#   ...
# }
```

## Reconnection strategy

WebSockets drop. Always wrap your client in a reconnection loop with
exponential backoff:

```javascript
function connect() {
  const ws = new WebSocket('ws://localhost:8000/ws/leaderboard');
  ws.onmessage = (e) => console.log(JSON.parse(e.data));
  ws.onclose = () => setTimeout(connect, 1000);
}
connect();
```

## Message formats

Every message is a JSON object with a `type` field. See
[Architecture → Real-time](../architecture/websocket.md) for the full
catalogue of message types per channel.
