"""End-to-end notebook test that logs in via HTML form (sets cookie)."""
import os
import sys
import time
import random
import subprocess
import requests

BASE = "http://localhost:3000"

print("=== Starting uvicorn on port 3000 ===")
proc = subprocess.Popen(
    ["python3", "-m", "uvicorn", "app.main:app",
     "--host", "0.0.0.0", "--port", "3000", "--log-level", "warning"],
    cwd="/home/z/my-project",
    stdout=open("/tmp/obml_test_server.log", "w"),
    stderr=subprocess.STDOUT,
)

print("Waiting for server...")
ready = False
for i in range(40):
    try:
        r = requests.get(f"{BASE}/health", timeout=2)
        if r.status_code == 200:
            print(f"  Server ready after {i*0.5}s")
            ready = True
            break
    except Exception:
        pass
    time.sleep(0.5)

if not ready:
    print("Server failed to start.")
    proc.terminate()
    sys.exit(1)

try:
    s = requests.Session()
    username = f"nbtest_{random.randint(10000, 99999)}"
    email = f"{username}@test.com"
    password = "Test1234!"

    # Register via API (returns token but doesn't set cookie)
    print("\n=== Register via /api/auth/register ===")
    r = s.post(f"{BASE}/api/auth/register",
               json={"username": username, "email": email, "password": password},
               timeout=10)
    print(f"Status: {r.status_code}")
    print(f"Body (first 200): {r.text[:200]}")

    # Login via HTML form (sets cookie)
    print("\n=== Login via HTML form /login ===")
    r = s.post(f"{BASE}/login",
               data={"email": email, "password": password},
               allow_redirects=False, timeout=10)
    print(f"Status: {r.status_code} (expect 303)")
    print(f"Set-Cookie: {r.headers.get('set-cookie', 'NONE')[:200]}")
    print(f"Cookies: {list(s.cookies.keys())}")

    print("\n=== GET /notebook (with cookie) ===")
    r = s.get(f"{BASE}/notebook", allow_redirects=False, timeout=10)
    print(f"Status: {r.status_code} (expect 200)")
    print(f"Content-Type: {r.headers.get('content-type')}")
    print(f"Body length: {len(r.text)}")
    for marker in ["cellsContainer", "addCodeCell", "runCell", "Terminal", "+ Code", "runCellServer", "notebook-canvas"]:
        print(f"  contains '{marker}': {marker in r.text}")

    print("\n=== POST /api/notebook/cell — print('hello') ===")
    r = s.post(f"{BASE}/api/notebook/cell",
               json={"code": "print('hello')", "timeout_seconds": 30, "cell_id": "c1"},
               headers={"Accept": "*/*"}, timeout=30)
    print(f"Status: {r.status_code}  Content-Type: {r.headers.get('content-type')}")
    print(f"Body (first 600): {r.text[:600]}")

    print("\n=== POST /api/notebook/cell — variable assignment ===")
    r = s.post(f"{BASE}/api/notebook/cell",
               json={"code": "x = 42\nprint('x =', x)", "timeout_seconds": 30, "cell_id": "c2"},
               timeout=30)
    print(f"Status: {r.status_code}")
    print(f"Body (first 600): {r.text[:600]}")

    print("\n=== POST /api/notebook/cell — refer to x (persistence) ===")
    r = s.post(f"{BASE}/api/notebook/cell",
               json={"code": "print('x is still', x)", "timeout_seconds": 30, "cell_id": "c3"},
               timeout=30)
    print(f"Status: {r.status_code}")
    print(f"Body (first 600): {r.text[:600]}")

    print("\n=== POST /api/notebook/cell — matplotlib figure ===")
    r = s.post(f"{BASE}/api/notebook/cell",
               json={"code": "import matplotlib.pyplot as plt\nplt.plot([1,2,3],[1,4,9])\nplt.title('test')\nplt.show()", "timeout_seconds": 30, "cell_id": "c4"},
               timeout=60)
    print(f"Status: {r.status_code}  Content-Type: {r.headers.get('content-type')}")
    print(f"Body length: {len(r.text)}")
    try:
        j = r.json()
        print(f"  ok={j.get('ok')} stdout={j.get('stdout','')[:100]!r} figures={len(j.get('figures',[]))}")
    except Exception as e:
        print(f"  JSON parse failed: {e}")
        print(f"  First 400: {r.text[:400]}")

    print("\n=== POST /api/notebook/cell — shell !echo ===")
    r = s.post(f"{BASE}/api/notebook/cell",
               json={"code": "!echo hello-from-shell", "timeout_seconds": 30, "cell_id": "c5"},
               timeout=30)
    print(f"Status: {r.status_code}")
    print(f"Body (first 600): {r.text[:600]}")

    print("\n=== POST /api/notebook/cell — magic %whos ===")
    r = s.post(f"{BASE}/api/notebook/cell",
               json={"code": "%whos", "timeout_seconds": 30, "cell_id": "c6"},
               timeout=30)
    print(f"Status: {r.status_code}")
    print(f"Body (first 600): {r.text[:600]}")

    print("\n=== POST /api/notebook/cell — module not found (suggestions) ===")
    r = s.post(f"{BASE}/api/notebook/cell",
               json={"code": "import tensorflow as tf", "timeout_seconds": 30, "cell_id": "c7"},
               timeout=30)
    print(f"Status: {r.status_code}")
    print(f"Body (first 800): {r.text[:800]}")

    print("\n=== GET /api/notebook/health ===")
    r = s.get(f"{BASE}/api/notebook/health", timeout=10)
    print(f"Status: {r.status_code}")
    print(f"Body (first 400): {r.text[:400]}")

    print("\n=== DONE ===")
finally:
    print("\n=== Stopping server ===")
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
