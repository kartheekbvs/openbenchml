"""End-to-end notebook flow test.

Registers a fresh user, logs in, then exercises:
1. GET /notebook                       (page renders)
2. POST /api/notebook/cell             (simple Python)
3. POST /api/notebook/cell             (variable persistence)
4. POST /api/notebook/cell             (matplotlib figure capture)
5. POST /api/notebook/cell             (shell command !pip list)
6. POST /api/notebook/cell             (magic %whos)
7. GET  /api/notebook/health
8. POST /api/notebook/cell with NO auth (should return 401 JSON not HTML)

Prints the raw response body of every call so we can see if anything
returns HTML (the user-reported bug).
"""
import sys
import random
import requests

BASE = "http://localhost:3000"
s = requests.Session()

username = f"nbtest_{random.randint(10000, 99999)}"
email = f"{username}@test.com"
password = "Test1234!"

print("=== Register ===")
r = s.post(f"{BASE}/api/auth/register",
           json={"username": username, "email": email, "password": password},
           allow_redirects=False)
print(f"Status: {r.status_code}  Content-Type: {r.headers.get('content-type')}")
print(f"Body (first 400): {r.text[:400]}")
print(f"Cookies: {dict(s.cookies)}")
print()

# If register didn't set a cookie, try login
if "session" not in s.cookies and "access_token" not in s.cookies:
    print("=== Login (no cookie after register) ===")
    r = s.post(f"{BASE}/api/auth/login",
               json={"username": username, "password": password},
               allow_redirects=False)
    print(f"Status: {r.status_code}  Content-Type: {r.headers.get('content-type')}")
    print(f"Body (first 400): {r.text[:400]}")
    print(f"Cookies: {dict(s.cookies)}")
    print()

print("=== GET /notebook ===")
r = s.get(f"{BASE}/notebook", allow_redirects=False)
print(f"Status: {r.status_code}  Content-Type: {r.headers.get('content-type')}")
print(f"Body length: {len(r.text)}")
# Show that the page has the cells container
for marker in ["cellsContainer", "addCodeCell", "runCell", "Terminal", "+ Code"]:
    print(f"  contains '{marker}': {marker in r.text}")
print()

print("=== POST /api/notebook/cell — print('hello') ===")
r = s.post(f"{BASE}/api/notebook/cell",
           json={"code": "print('hello')", "timeout_seconds": 30, "cell_id": "c1"},
           headers={"Accept": "*/*"})
print(f"Status: {r.status_code}  Content-Type: {r.headers.get('content-type')}")
print(f"Body (first 600): {r.text[:600]}")
print()

print("=== POST /api/notebook/cell — variable persistence ===")
r = s.post(f"{BASE}/api/notebook/cell",
           json={"code": "x = 42\nprint('x =', x)", "timeout_seconds": 30, "cell_id": "c2"})
print(f"Status: {r.status_code}  Content-Type: {r.headers.get('content-type')}")
print(f"Body (first 600): {r.text[:600]}")
print()

print("=== POST /api/notebook/cell — refer to x ===")
r = s.post(f"{BASE}/api/notebook/cell",
           json={"code": "print('x is still', x)", "timeout_seconds": 30, "cell_id": "c3"})
print(f"Status: {r.status_code}  Content-Type: {r.headers.get('content-type')}")
print(f"Body (first 600): {r.text[:600]}")
print()

print("=== POST /api/notebook/cell — matplotlib figure ===")
r = s.post(f"{BASE}/api/notebook/cell",
           json={"code": "import matplotlib.pyplot as plt\nplt.plot([1,2,3],[1,4,9])\nplt.title('test')\nplt.show()", "timeout_seconds": 30, "cell_id": "c4"})
print(f"Status: {r.status_code}  Content-Type: {r.headers.get('content-type')}")
print(f"Body length: {len(r.text)}")
import json
try:
    j = r.json()
    print(f"  ok={j.get('ok')} stdout_len={len(j.get('stdout',''))} figures={len(j.get('figures',[]))}")
except Exception as e:
    print(f"  JSON parse failed: {e}")
    print(f"  First 400: {r.text[:400]}")
print()

print("=== POST /api/notebook/cell — shell !pip list (truncated) ===")
r = s.post(f"{BASE}/api/notebook/cell",
           json={"code": "!echo hello-from-shell", "timeout_seconds": 30, "cell_id": "c5"})
print(f"Status: {r.status_code}  Content-Type: {r.headers.get('content-type')}")
print(f"Body (first 600): {r.text[:600]}")
print()

print("=== POST /api/notebook/cell — magic %whos ===")
r = s.post(f"{BASE}/api/notebook/cell",
           json={"code": "%whos", "timeout_seconds": 30, "cell_id": "c6"})
print(f"Status: {r.status_code}  Content-Type: {r.headers.get('content-type')}")
print(f"Body (first 600): {r.text[:600]}")
print()

print("=== GET /api/notebook/health ===")
r = s.get(f"{BASE}/api/notebook/health")
print(f"Status: {r.status_code}  Content-Type: {r.headers.get('content-type')}")
print(f"Body (first 400): {r.text[:400]}")
print()

print("=== POST /api/notebook/cell — NO AUTH (should be 401 JSON) ===")
r2 = requests.post(f"{BASE}/api/notebook/cell",
                   json={"code": "print('hello')", "timeout_seconds": 30, "cell_id": "cX"},
                   headers={"Accept": "*/*"})
print(f"Status: {r2.status_code}  Content-Type: {r2.headers.get('content-type')}")
print(f"Body (first 400): {r2.text[:400]}")
print()

print("=== POST /api/notebook/cell — Accept: text/html (should still be JSON) ===")
r3 = requests.post(f"{BASE}/api/notebook/cell",
                   json={"code": "print('hello')", "timeout_seconds": 30, "cell_id": "cY"},
                   headers={"Accept": "text/html"})
print(f"Status: {r3.status_code}  Content-Type: {r3.headers.get('content-type')}")
print(f"Body (first 400): {r3.text[:400]}")
print()

print("=== DONE ===")
