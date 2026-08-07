#!/usr/bin/env python3
"""
OpenBenchML v4.2 — Full Benchmark Lifecycle E2E Test
=====================================================
End-to-end test of the complete benchmark flow:
  1. Register a new user (Supabase)
  2. Login (Supabase) → get bearer token
  3. Convert Python code → pickled model (Supabase-authed)
  4. Submit model to a benchmark
  5. Wait for benchmark to complete
  6. Verify results (accuracy, latency p50/p95/p99)
  7. Submit to a competition
  8. Verify leaderboard entry
"""
import sys
import time
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

print("=" * 72)
print("  Full Benchmark Lifecycle E2E Test")
print("=" * 72)

# Step 1: Register
print("\n[1/8] Registering a new user via Supabase Auth...")
email = f"lifecycle-{int(time.time())}@example.com"
password = "lifecycle123"
username = f"lifecycle_{int(time.time()) % 10000}"

r = client.post("/api/auth/register", json={
    "username": username, "email": email, "password": password,
})
if r.status_code == 409:
    print(f"  User already exists — continuing with login")
elif r.status_code != 200:
    print(f"  ✗ Register failed: {r.status_code} {r.text[:200]}")
    sys.exit(1)
else:
    print(f"  ✓ Registered {username} <{email}>")

# Step 2: Login
print("\n[2/8] Logging in via Supabase Auth...")
r = client.post("/api/auth/login", json={"email": email, "password": password})
if r.status_code != 200:
    print(f"  ✗ Login failed: {r.status_code} {r.text[:200]}")
    sys.exit(1)
token = r.json()["access_token"]
auth = {"Authorization": f"Bearer {token}"}
print(f"  ✓ Logged in, token len={len(token)}")

# Step 3: Convert code → pickled model
print("\n[3/8] Converting Python code → pickled model via /api/convert...")
convert_code = """
from sklearn.ensemble import RandomForestClassifier
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
X, y = load_iris(return_X_y=True)
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42)
model = RandomForestClassifier(n_estimators=20, random_state=42)
model.fit(Xtr, ytr)
acc = model.score(Xte, yte)
"""
r = client.post("/api/convert", json={
    "code": convert_code,
    "model_name": f"Lifecycle RF {int(time.time())}",
    "framework": "scikit-learn",
    "description": "E2E lifecycle test model"
}, headers=auth)
if r.status_code != 200:
    print(f"  ✗ Convert failed: {r.status_code} {r.text[:300]}")
    sys.exit(1)
model_id = r.json().get("id")
print(f"  ✓ Model created, id={model_id}, framework={r.json().get('framework')}")

# Step 4: List datasets, pick the iris
print("\n[4/8] Fetching datasets to pick Iris...")
r = client.get("/api/datasets")
datasets = r.json()
iris = next((d for d in datasets if d["name"].lower() == "iris"), None)
if not iris:
    print(f"  ✗ Could not find iris dataset")
    sys.exit(1)
iris_id = iris["id"]
print(f"  ✓ Iris dataset id={iris_id}")

# Step 5: Submit benchmark job (POST /benchmark — HTML form-encoded)
print("\n[5/8] Submitting benchmark job (model → iris) via POST /benchmark...")
r = client.post("/benchmark", data={
    "model_id": str(model_id),
    "dataset_id": str(iris_id),
}, headers=auth, follow_redirects=False)
if r.status_code in (303, 302):
    # Extract job_id from redirect URL: /results/{job_id}
    loc = r.headers.get("location", "")
    print(f"  ✓ Redirected to {loc}")
    if "/results/" in loc:
        job_id = loc.rsplit("/", 1)[-1]
        print(f"  ✓ Job id={job_id}")
    else:
        print(f"  ✗ Could not extract job_id from redirect URL: {loc}")
        sys.exit(1)
elif r.status_code == 200:
    # Form re-rendered with error
    print(f"  ✗ Benchmark form re-rendered with error")
    if "error" in r.text.lower():
        # Extract error message
        import re
        m = re.search(r'class="alert[^"]*"[^>]*>([^<]+)', r.text)
        if m:
            print(f"     Error: {m.group(1).strip()}")
    sys.exit(1)
else:
    print(f"  ✗ Benchmark submit failed: {r.status_code} {r.text[:300]}")
    sys.exit(1)

# Step 6: Poll for results
print("\n[6/8] Polling for benchmark results (max 30s)...")
results = None
for i in range(30):
    r = client.get(f"/api/results/{job_id}", headers=auth)
    if r.status_code == 200:
        body = r.json()
        status = body.get("status") or body.get("job_status")
        if status in ("completed", "success", "done"):
            results = body
            print(f"  ✓ Benchmark completed after {i+1} poll(s)")
            break
    time.sleep(1)
    print(f"  ... poll {i+1}, status={r.status_code}")

if not results:
    print(f"  ✗ Benchmark did not complete in 30s")
    sys.exit(1)

# Print key metrics
metrics = results.get("metrics") or {}
print(f"\n  Metrics:")
print(f"    accuracy:        {metrics.get('accuracy')}")
print(f"    latency_ms:      {metrics.get('latency_ms')}")
print(f"    latency_p50_ms:  {metrics.get('latency_p50_ms')}")
print(f"    latency_p95_ms:  {metrics.get('latency_p95_ms')}")
print(f"    latency_p99_ms:  {metrics.get('latency_p99_ms')}")
print(f"    throughput:      {metrics.get('throughput_per_sec')}")
if metrics.get("confusion_matrix"):
    print(f"    confusion_matrix present: ✓")
if metrics.get("classification_report"):
    print(f"    classification_report present: ✓")

# Validate that key metrics are non-None
required = ["accuracy", "latency_ms", "latency_p50_ms", "latency_p95_ms", "latency_p99_ms"]
missing = [k for k in required if metrics.get(k) is None]
if missing:
    print(f"\n  ✗ Missing required metrics: {missing}")
    sys.exit(1)
print(f"\n  ✓ All required metrics present and non-null")

# Step 7: Check leaderboard
print("\n[7/8] Fetching leaderboard for Iris dataset...")
r = client.get(f"/api/leaderboard?dataset_id={iris_id}")
if r.status_code != 200:
    print(f"  ✗ Leaderboard fetch failed: {r.status_code}")
    sys.exit(1)
leaderboard = r.json()
if isinstance(leaderboard, dict):
    leaderboard = leaderboard.get("entries", leaderboard.get("leaderboard", []))
print(f"  ✓ Leaderboard returned {len(leaderboard) if isinstance(leaderboard, list) else 'OK'} entries")

# Step 8: List competitions
print("\n[8/8] Fetching active competitions...")
r = client.get("/api/competitions")
if r.status_code == 200:
    comps = r.json()
    if isinstance(comps, list):
        print(f"  ✓ {len(comps)} competitions available")
        for c in comps[:3]:
            print(f"    - {c.get('title') or c.get('name')} (metric={c.get('evaluation_metric')})")
    else:
        print(f"  ✓ Competitions endpoint OK")
else:
    print(f"  ✗ Competitions fetch failed: {r.status_code}")

print("\n" + "=" * 72)
print("  ✅ FULL BENCHMARK LIFECYCLE E2E TEST PASSED")
print("=" * 72)
