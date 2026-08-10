"""Test the Render ↔ HF Spaces auth bridge.

Verifies:
  1. /api/auth/bridge_token issues a valid JWT when logged in
  2. /auth/bridge consumes the token, sets a cookie, redirects to /notebook
  3. The cookie actually authenticates subsequent requests
  4. Bridge tokens are single-use (a second attempt fails)
  5. Stub user is created in the HF-side DB with password_hash="BRIDGED"
"""
import os, sys, time, json
sys.path.insert(0, '/home/z/my-project')

os.environ['SECRET_KEY'] = 'test-secret-key-for-bridge-test-shared'
os.environ['DATABASE_URL'] = 'sqlite:///./test_bridge.db'
os.environ['SESSION_SECRET'] = 'test-session-secret'
os.environ['HF_SPACES_URL'] = 'https://openbenchml-hf.fake.hf.space'

# Clean test DB
import pathlib
for p in [pathlib.Path('./test_bridge.db')]:
    if p.exists(): p.unlink()

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Register + login on Render side
username = f"bridge_{int(time.time())}"
r = client.post('/api/auth/register', json={
    'username': username, 'email': f'{username}@test.com', 'password': 'Test1234!'
})
assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
token = r.json()['access_token']
client.headers.update({'Authorization': f'Bearer {token}'})

# ─── 1. Issue a bridge token ────────────────────────────────────────────────
print("=== 1. Issue bridge token ===")
r = client.get('/api/auth/bridge_token')
assert r.status_code == 200, f"bridge_token failed: {r.status_code} {r.text}"
data = r.json()
print(f"  token issued, url={data['url'][:80]}...")
assert data['url'].startswith('https://openbenchml-hf.fake.hf.space/auth/bridge?token=')
assert data['expires_in_seconds'] == 300
bridge_url = data['url']

# ─── 2. Consume the bridge token (simulate browser redirect to HF) ──────────
print("\n=== 2. Consume bridge token (set cookie + redirect) ===")
# Strip the Authorization header so we test the cookie-based auth
saved_headers = client.headers.copy()
client.headers = {}  # no auth — we want to test that the bridge sets a cookie
r = client.get(bridge_url, follow_redirects=False)
assert r.status_code == 303, f"bridge should redirect 303, got {r.status_code}: {r.text[:200]}"
assert r.headers['location'] == '/notebook', f"unexpected redirect target: {r.headers['location']}"
# Extract the Set-Cookie header
set_cookie = r.headers.get('set-cookie', '')
assert 'access_token=' in set_cookie, f"no access_token cookie in: {set_cookie[:200]}"
assert 'HttpOnly' in set_cookie, "cookie should be HttpOnly"
print(f"  redirected to /notebook with HttpOnly cookie set")
# Capture the cookie value
import re
m = re.search(r'access_token=([^;]+)', set_cookie)
hf_cookie_token = m.group(1)
assert hf_cookie_token, "empty cookie token"

# ─── 3. The cookie authenticates subsequent requests ───────────────────────
print("\n=== 3. Cookie-based auth on HF works ===")
client.cookies.set('access_token', hf_cookie_token)
r = client.get('/api/auth/me')
assert r.status_code == 200, f"cookie auth failed: {r.status_code} {r.text[:200]}"
me = r.json()
print(f"  authenticated as: id={me.get('id')} username={me.get('username')}")
assert me['username'] == username, f"wrong username: {me.get('username')}"

# ─── 4. Stub user creation with password_hash="BRIDGED" ────────────────────
# Simulate the real cross-domain scenario: user exists on RENDER's DB, but
# not yet on HF's DB. To simulate this in our shared test DB:
#   1. Issue bridge token #2 while user still exists on "Render" side
#   2. Delete the user from the DB (simulating HF's empty DB)
#   3. Consume the token — bridge should CREATE a stub with "BRIDGED" hash
print("\n=== 4. Stub user creation with password_hash='BRIDGED' ===")
from app.database.db import SessionLocal
from app.database.models import User

# Step 1: Issue a fresh bridge token while user is still authenticated
client.headers = saved_headers
client.cookies.clear()
r = client.get('/api/auth/bridge_token')
assert r.status_code == 200, f"second bridge_token failed: {r.status_code} {r.text}"
bridge_url_2 = r.json()['url']
print(f"  bridge token #2 issued (5-min TTL)")

# Step 2: Delete user from DB to simulate HF's separate, empty DB
db = SessionLocal()
db.query(User).filter(User.username == username).delete()
db.commit()
db.close()
print(f"  wiped user '{username}' from test DB (simulating HF's empty DB)")

# Step 3: Consume the token — should CREATE stub with "BRIDGED" hash.
# NOTE: The bridge decodes the JWT (which contains user_id, username, email)
# WITHOUT requiring a DB lookup, so this works even though the user is gone.
client.headers = {}
r = client.get(bridge_url_2, follow_redirects=False)
assert r.status_code == 303, f"second bridge should redirect 303, got {r.status_code}: {r.text[:200]}"
print(f"  second bridge consumed, stub user created")

db = SessionLocal()
stub = db.query(User).filter(User.username == username).first()
assert stub is not None, "stub user not in DB"
assert stub.password_hash == "BRIDGED", f"unexpected hash: {stub.password_hash!r}"
print(f"  stub user id={stub.id} password_hash={stub.password_hash!r}")
db.close()

# Verify the BRIDGED hash cannot match any password
from app.services.auth_service import verify_password
db = SessionLocal()
stub = db.query(User).filter(User.username == username).first()
assert not verify_password('Test1234!', stub.password_hash), \
    "BRIDGED hash should not match any password"
assert not verify_password('anything', stub.password_hash), \
    "BRIDGED hash should not match any password"
print(f"  verify_password('Test1234!', 'BRIDGED') = False OK")
print(f"  verify_password('anything',  'BRIDGED') = False OK")
db.close()

# ─── 5. Bridge token is single-use ─────────────────────────────────────────
# Try to consume bridge_url_2 again — should be rejected as already-used.
# We don't need Render auth for this since we're hitting the HF-side /auth/bridge
# endpoint (which only checks the JWT in the URL, not the Bearer header).
print("\n=== 5. Bridge token is single-use ===")
client.headers = {}
client.cookies.clear()
r = client.get(bridge_url_2, follow_redirects=False)
assert r.status_code == 401, f"reuse should fail with 401, got {r.status_code}: {r.text[:200]}"
assert 'already been used' in r.json().get('detail', '').lower(), \
       f"unexpected error message: {r.json().get('detail')}"
print(f"  reuse correctly rejected: {r.json()['detail']}")

# ─── 6. Bridge status endpoint ─────────────────────────────────────────────
print("\n=== 6. Bridge status endpoint ===")
r = client.get('/api/auth/bridge_status')
assert r.status_code == 200
status = r.json()
print(f"  status: {status}")
assert status['can_issue'] is True, "should be able to issue (HF_SPACES_URL set)"
assert status['can_consume'] is True, "should always be able to consume"
assert status['bridge_token_ttl_seconds'] == 300

print("\n" + "=" * 60)
print("ALL AUTH BRIDGE TESTS PASSED")
print("=" * 60)
print("""
Summary of what the bridge does:
  ✓ Logged-in user on Render can request a one-time bridge token
  ✓ Token is valid for 5 minutes only
  ✓ Token is single-use (reuse is rejected with a clear error)
  ✓ HF Space consumes the token, creates a stub user with password_hash="BRIDGED"
  ✓ HF Space sets an HttpOnly access_token cookie on its own domain
  ✓ Subsequent requests to HF are authenticated via the cookie
  ✓ Stub user cannot log in directly on HF (no usable password hash)
  ✓ Bridge works with a shared SECRET_KEY between Render and HF
""")
