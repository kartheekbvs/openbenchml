#!/usr/bin/env python3
"""
End-to-end test of the notebook cell execution flow using FastAPI TestClient.
Verifies that:
  1. The /api/notebook/cell endpoint returns proper JSON with stdout
  2. Variable persistence works across cells
  3. The notebook.html template contains the renderOutput / has-content code
  4. The cell-output CSS rule correctly toggles display:block on has-content

This is the same flow the browser hits, minus the browser itself.
"""
import sys, os, json, re
sys.path.insert(0, '/home/z/my-project')

# Set env before importing app
os.environ['NOTEBOOK_DISABLED'] = '0'
os.environ['SECRET_KEY'] = 'test-secret-key-for-notebook-test-only'
os.environ['DATABASE_URL'] = 'sqlite:///./test_nb_verify.db'
os.environ['SESSION_SECRET'] = 'test-session-secret'

# Clean test DB
import pathlib
p = pathlib.Path('./test_nb_verify.db')
if p.exists():
    p.unlink()

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# ─── Register + Login ──────────────────────────────────────────────────────
import time
username = f"nbverify_{int(time.time())}"
email = f"{username}@test.com"
password = "Test1234!"

print("=== Step 1: Register ===")
r = client.post('/api/auth/register', json={
    'username': username, 'email': email, 'password': password
})
print(f"  status={r.status_code} body={r.text[:200]}")
assert r.status_code in (200, 201), "register failed"

# Login via API (returns access_token in JSON; we use it as Bearer header)
print("\n=== Step 2: Login via /api/auth/login ===")
r = client.post('/api/auth/login', json={
    'email': email, 'password': password
})
print(f"  status={r.status_code} body={r.text[:200]}")
assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"

token = r.json().get('access_token')
assert token, "no access_token in login response"
# The notebook UI uses an HttpOnly cookie (set by /auth/login HTML form).
# For TestClient we use the Authorization header instead — get_current_user_from_cookie
# supports both. This is functionally equivalent for testing the cell endpoint.
client.headers.update({'Authorization': f'Bearer {token}'})
print(f"  Authorization header set (token len={len(token)})")

# Verify auth works
r = client.get('/api/auth/me')
print(f"  /api/auth/me status={r.status_code} body={r.text[:120]}")
assert r.status_code == 200, "auth failed — token not being sent"

# ─── Step 3: GET /notebook page ────────────────────────────────────────────
print("\n=== Step 3: GET /notebook ===")
r = client.get('/notebook')
print(f"  status={r.status_code} len={len(r.text)}")

# Verify critical JS functions are present in the page
required_funcs = ['renderOutput', 'runCellServer', 'runCell', '_fetchJson',
                  'has-content', 'cell-output', 'stream-stdout']
missing = [f for f in required_funcs if f not in r.text]
print(f"  missing JS/CSS pieces: {missing}")
assert not missing, f"template missing: {missing}"

# ─── Step 4: Run a simple cell ─────────────────────────────────────────────
print("\n=== Step 4: POST /api/notebook/cell — print('hello world') ===")
r = client.post('/api/notebook/cell', json={
    'code': "print('hello world')",
    'timeout_seconds': 30,
    'cell_id': 'c1'
})
print(f"  status={r.status_code}")
print(f"  content-type: {r.headers.get('content-type')}")
print(f"  body: {r.text[:500]}")
assert r.status_code == 200, f"cell run failed: {r.status_code}"
assert 'application/json' in r.headers.get('content-type', ''), \
       f"expected JSON, got {r.headers.get('content-type')}"

data = r.json()
print(f"  parsed JSON: ok={data.get('ok')} stdout={data.get('stdout')!r} "
      f"stderr={data.get('stderr')!r} elapsed_ms={data.get('elapsed_ms')}")
assert data.get('ok') is True, f"cell ok=False: {data}"
assert 'hello world' in data.get('stdout', ''), \
       f"stdout missing 'hello world': {data.get('stdout')!r}"

# ─── Step 5: Variable persistence ──────────────────────────────────────────
print("\n=== Step 5: Variable assignment (x = 42) ===")
r = client.post('/api/notebook/cell', json={
    'code': 'x = 42',
    'timeout_seconds': 30,
    'cell_id': 'c2'
})
data = r.json()
print(f"  ok={data.get('ok')} stdout={data.get('stdout')!r}")
assert data.get('ok') is True

print("\n=== Step 6: Use variable (print(x)) ===")
r = client.post('/api/notebook/cell', json={
    'code': 'print(x * 2)',
    'timeout_seconds': 30,
    'cell_id': 'c3'
})
data = r.json()
print(f"  ok={data.get('ok')} stdout={data.get('stdout')!r}")
assert data.get('ok') is True
assert '84' in data.get('stdout', ''), f"expected 84 in stdout, got: {data.get('stdout')!r}"

# ─── Step 7: Verify the CSS rule that toggles output visibility ────────────
print("\n=== Step 7: Verify CSS .cell-output rules ===")
template_path = '/home/z/my-project/templates/notebook.html'
with open(template_path) as f:
    html = f.read()

# Default: display:none
m = re.search(r'\.cell-output\s*\{[^}]*display:\s*none[^}]*\}', html, re.DOTALL)
print(f"  .cell-output {{ display: none }} present: {bool(m)}")
assert m, "CSS rule '.cell-output { display: none }' missing"

# has-content: display:block
m = re.search(r'\.cell-output\.has-content\s*\{[^}]*display:\s*block[^}]*\}', html, re.DOTALL)
print(f"  .cell-output.has-content {{ display: block }} present: {bool(m)}")
assert m, "CSS rule '.cell-output.has-content { display: block }' missing"

# renderOutput adds has-content class
m = re.search(r'out\.classList\.add\([\'"]has-content[\'"]\)', html)
print(f"  renderOutput adds 'has-content' class: {bool(m)}")
assert m, "renderOutput does NOT add 'has-content' class — output will never be visible!"

print("\n=== ALL CHECKS PASSED ===")
print("""
Conclusion: the notebook backend + frontend code is correct.

What the user sees depends on what's deployed:
  • If they see 'v2.0' badge in /notebook header → Render hasn't deployed
    the latest commit yet. Wait 2-3 min, then hard-refresh (Ctrl+Shift+R).
  • If they see 'v2.4 resilient-fetch' badge → the new code is live.
    If output is STILL not visible:
      - Check browser console (F12) for JS errors.
      - Check the Network tab: the /api/notebook/cell response should be
        200 with content-type application/json.
      - If they see a 502/504, the kernel worker crashed (likely OOM from
        a heavy import like tensorflow). Click 'Reset Kernel'.
      - If they see 'Authentication required', the session cookie expired.
        Refresh the page and log in again.
""")
