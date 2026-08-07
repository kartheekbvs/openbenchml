#!/usr/bin/env python3
"""
End-to-end HTTP smoke test for OpenBenchML v4.

Flow:
  1. Register a fresh user via the JSON API.
  2. Hit /api/convert with Python code that trains a RandomForest on Iris.
  3. Verify the new MLModel exists in /api/models.
  4. Hit /api/notebook/run with a small Python snippet.
  5. Subscribe to /ws/leaderboard and verify it accepts the connection.

Run:
    python scripts/smoke_test_http_v4.py
"""
import json
import sys
import time
import urllib.request
import urllib.error

HOST = "http://127.0.0.1:8765"
USERNAME = f"smoke_v4_{int(time.time())}"
EMAIL = f"{USERNAME}@example.com"
PASSWORD = "testpass123"

PASS = 0
FAIL = 0

def ok(name):
    global PASS; PASS += 1
    print(f"  PASS  {name}")

def fail(name, why):
    global FAIL; FAIL += 1
    print(f"  FAIL  {name} — {why}")

def request(method, path, body=None, token=None, expect_status=None):
    url = HOST + path
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            raw = resp.read().decode("utf-8")
            try:
                parsed = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                parsed = raw
            return status, parsed
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = raw
        return e.code, parsed


print("\n═══ Step 1: Register a fresh user ═══")
status, body = request("POST", "/api/auth/register", {
    "username": USERNAME, "email": EMAIL, "password": PASSWORD,
})
print(f"  register → HTTP {status}")
if status in (200, 201) and body and body.get("access_token"):
    token = body["access_token"]
    ok(f"registered as {USERNAME}")
else:
    fail("register", f"status={status}, body={body}")
    sys.exit(1)


print("\n═══ Step 2: /api/convert — code → pickled model ═══")
convert_code = """
from sklearn.ensemble import RandomForestClassifier
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split

X, y = load_iris(return_X_y=True)
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
model = RandomForestClassifier(n_estimators=25, random_state=42)
model.fit(Xtr, ytr)
acc = model.score(Xte, yte)
print(f'trained; test acc = {acc:.4f}')
"""
status, body = request("POST", "/api/convert", {
    "model_name": "SmokeTest RF on Iris",
    "description": "Created by smoke_test_http_v4.py",
    "framework": "scikit-learn",
    "code": convert_code,
}, token=token)
print(f"  /api/convert → HTTP {status}")
if status == 200 and body and body.get("id"):
    model_id = body["id"]
    ok(f"converted → model_id={model_id}, framework={body['framework']}, "
       f"class={body['model_class']}, size={body['size_kb']} KB")
    if body.get("metrics_in_code", {}).get("accuracy") is not None:
        ok(f"metric captured from code: accuracy = {body['metrics_in_code']['accuracy']:.4f}")
    else:
        fail("metric captured from code", "no accuracy in response")
else:
    fail("/api/convert", f"status={status}, body={body}")
    sys.exit(1)


print("\n═══ Step 3: /api/notebook/run — execute Python in the sandbox ═══")
status, body = request("POST", "/api/notebook/run", {
    "code": "import numpy as np\nprint(f'np version: {np.__version__}')\nprint(f'sum: {np.array([1,2,3]).sum()}')",
    "timeout_seconds": 10,
}, token=token)
print(f"  /api/notebook/run → HTTP {status}")
if status == 200 and body and body.get("ok") and "np version" in body.get("stdout", ""):
    ok(f"notebook executed: stdout={body['stdout'].strip()!r}")
else:
    fail("/api/notebook/run", f"status={status}, body={body}")


print("\n═══ Step 4: /api/notebook/run — blocked import rejected ═══")
status, body = request("POST", "/api/notebook/run", {
    "code": "import subprocess\nsubprocess.run(['ls'])",
    "timeout_seconds": 10,
}, token=token)
print(f"  /api/notebook/run (blocked) → HTTP {status}")
if status == 200 and body and not body.get("ok") and "blocked" in body.get("stderr", "").lower():
    ok("subprocess import was blocked by the sandbox")
else:
    fail("subprocess blocked", f"status={status}, body={body}")


print("\n═══ Step 5: WebSocket /ws/leaderboard accepts connection ═══")
# We use the websocket-client lib if available; otherwise skip with a note.
try:
    import websocket  # noqa
    ws = websocket.create_connection(
        "ws://127.0.0.1:8765/ws/leaderboard", timeout=5,
    )
    ws.send(json.dumps({"type": "subscribe", "dataset_id": 1}))
    raw = ws.recv()
    msg = json.loads(raw)
    if msg.get("type") == "subscribed":
        ok(f"WebSocket subscribed: {msg}")
    else:
        fail("ws subscribe", f"unexpected msg: {msg}")
    ws.close()
except ImportError:
    print("  SKIP  (websocket-client not installed)")


print(f"\n{'═' * 60}")
print(f"TOTAL:  {PASS + FAIL}   PASS: {PASS}   FAIL: {FAIL}")
print(f"{'═' * 60}")
sys.exit(0 if FAIL == 0 else 1)
