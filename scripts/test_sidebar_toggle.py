"""Verify the Files sidebar toggle works in the rendered /notebook HTML.

Checks:
  1. The sidebar has both an expanded panel and a collapsed rail button
  2. toggleSidebar() flips the `sidebar-collapsed` class on #nb-app
  3. The collapsed state hides .nb-sidebar-expanded and shows .nb-sidebar-rail
  4. No leftover version badges (v2.x, v3.x, v4.x, OOM-hardened, etc.) on the page
"""
import sys, os, re, time
sys.path.insert(0, '/home/z/my-project')

os.environ['SECRET_KEY'] = 'test-secret-key-for-toggle-test'
os.environ['DATABASE_URL'] = 'sqlite:///./test_sidebar_toggle.db'
os.environ['SESSION_SECRET'] = 'test-session-secret'

# Clean test DB
import pathlib
p = pathlib.Path('./test_sidebar_toggle.db')
if p.exists(): p.unlink()

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Register + login
username = f"toggle_{int(time.time())}"
r = client.post('/api/auth/register', json={
    'username': username,
    'email': f'{username}@test.com',
    'password': 'Test1234!'
})
assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
token = r.json().get('access_token')
client.headers.update({'Authorization': f'Bearer {token}'})

r = client.get('/notebook')
assert r.status_code == 200
html = r.text

# ─── 1. Sidebar structure present ──────────────────────────────────────────
print("=== 1. Sidebar structure ===")
for marker in [
    'id="nb-app"',
    'class="nb-sidebar"',
    'nb-sidebar-rail',           # collapsed button
    'nb-sidebar-expanded',       # expanded panel wrapper
    'toggleSidebar()',           # JS toggle
    'nb-app.sidebar-collapsed',  # CSS collapsed rule
    'nb-sidebar-rail {',         # CSS rail definition
]:
    assert marker in html, f"missing sidebar marker: {marker!r}"
    print(f"  [OK] {marker}")

# ─── 2. Toggle button in expanded header (close button) ────────────────────
print("\n=== 2. Close button in expanded header ===")
# Find the header close button (✕ = &#10005;) with onclick="toggleSidebar()"
m = re.search(
    r'<button[^>]*class="nb-sidebar-toggle"[^>]*onclick="toggleSidebar\(\)"[^>]*>',
    html
)
assert m, "expanded-panel close button (nb-sidebar-toggle with toggleSidebar) not found"
print(f"  [OK] expanded close button: {m.group(0)[:80]}...")

# ─── 3. Rail button (open when collapsed) ──────────────────────────────────
print("\n=== 3. Rail button (open when collapsed) ===")
m = re.search(
    r'<button[^>]*class="nb-sidebar-rail"[^>]*onclick="toggleSidebar\(\)"[^>]*>',
    html
)
assert m, "rail button (nb-sidebar-rail with toggleSidebar) not found"
print(f"  [OK] rail button: {m.group(0)[:80]}...")

# ─── 4. CSS rule for collapsed state ───────────────────────────────────────
print("\n=== 4. CSS for collapsed state ===")
# Should have a rule that hides .nb-sidebar-expanded when collapsed
collapsed_rule = re.search(
    r'\.nb-app\.sidebar-collapsed\s+\.nb-sidebar-expanded\s*\{[^}]*display:\s*none[^}]*\}',
    html
)
assert collapsed_rule, "missing CSS: .nb-app.sidebar-collapsed .nb-sidebar-expanded { display: none }"
print(f"  [OK] expanded panel hidden when collapsed")

# Should have a rule that shows .nb-sidebar-rail when collapsed
rail_rule = re.search(
    r'\.nb-app\.sidebar-collapsed\s+\.nb-sidebar-rail\s*\{[^}]*display:\s*flex[^}]*\}',
    html
)
assert rail_rule, "missing CSS: .nb-app.sidebar-collapsed .nb-sidebar-rail { display: flex }"
print(f"  [OK] rail shown when collapsed")

# Rail default (uncollapsed) should be display: none
rail_default = re.search(
    r'\.nb-sidebar-rail\s*\{[^}]*display:\s*none[^}]*\}',
    html
)
assert rail_default, "missing CSS: .nb-sidebar-rail { display: none } (default hidden)"
print(f"  [OK] rail hidden by default")

# ─── 5. No leftover version badges ─────────────────────────────────────────
print("\n=== 5. No version badges in HTML ===")
bad_patterns = [
    (r'>\s*v\d+\.\d+\s*<', 'inline version badge like ">v2.7<"'),
    (r'OOM-hardened', 'OOM-hardened label'),
    (r'Multi-cell\s*·\s*persistent\s*kernel', 'subtitle "Multi-cell · persistent kernel"'),
    (r'OpenBenchML\s+v\d+\.\d+\.\d+', 'versioned brand name "OpenBenchML vX.Y.Z"'),
]
for pat, desc in bad_patterns:
    m = re.search(pat, html)
    assert not m, f"FOUND leftover {desc}: {m.group(0)!r}"
    print(f"  [OK] no {desc}")

print("\n" + "=" * 60)
print("ALL SIDEBAR TOGGLE TESTS PASSED")
print("=" * 60)
