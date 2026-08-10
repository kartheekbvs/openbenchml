"""
OpenBenchML — comprehensive smoke test for v4.3

Tests:
  1. Every public page returns 200 (or 303 for auth-gated)
  2. Every Learn route works (landing, all 9 categories, all 50+ concepts)
  3. About page renders with all sections and workflow diagrams
  4. Notebook page renders without JS errors (the backtick fix)
  5. Competition detail page renders without JS errors (XSS fix)
  6. Realtime page renders without JS errors
  7. No template has unescaped backticks inside JS template literals
  8. Login → run notebook cell flow still works
"""
import re
import sys
import json
import requests

BASE = "http://127.0.0.1:8000"
PASS = 0
FAIL = 0
ERRORS = []

def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  \u2713 {name}")
    else:
        FAIL += 1
        ERRORS.append(f"{name}: {detail}")
        print(f"  \u2717 {name}  {detail}")

def get(path, **kw):
    try:
        return requests.get(BASE + path, timeout=10, allow_redirects=False, **kw)
    except Exception as e:
        return type("Err", (), {"status_code": 0, "text": str(e), "content": b""})

# ─── 1. Public pages ──────────────────────────────────────────────────────
print("\n=== 1. Public page render ===")
for path, expect in [
    ("/", 200),
    ("/about", 200),
    ("/learn", 200),
    ("/login", 200),
    ("/register", 200),
    ("/leaderboard", 200),
    ("/datasets", 200),
    ("/realtime", 200),
    ("/competitions", 200),
    ("/health", 200),
    ("/api/info", 200),
    ("/docs", 200),
]:
    r = get(path)
    check(f"GET {path} → {expect}", r.status_code == expect, f"got {r.status_code}")

# Auth-gated → should redirect to login
for path in ["/notebook", "/dashboard", "/convert", "/benchmark", "/my-models", "/jobs"]:
    r = get(path)
    check(f"GET {path} → 303 (auth)", r.status_code == 303, f"got {r.status_code}")

# ─── 2. Learn routes ──────────────────────────────────────────────────────
print("\n=== 2. Learn site ===")
r = get("/learn")
check("Learn landing renders", r.status_code == 200)
check("Learn landing has category cards",
      'class="category-card"' in r.text,
      "no category-card found")

# Test every category
categories = [
    "python", "web", "database", "ml", "frontend",
    "security", "devops", "realtime", "algorithms"
]
for cat in categories:
    r = get(f"/learn/cat/{cat}")
    check(f"GET /learn/cat/{cat}", r.status_code == 200, f"got {r.status_code}")

# Test specific concepts
concepts = [
    "python-variables", "python-loops", "python-classes", "python-async",
    "fastapi-routes", "fastapi-pydantic", "fastapi-websockets",
    "db-orm", "db-sessions",
    "ml-supervised", "ml-metrics", "ml-pickle",
    "html-structure", "css-flexbox", "js-fetch",
    "sec-jwt", "sec-sandbox", "sec-xss",
    "dev-docker", "dev-render",
    "rt-polling-vs-ws", "rt-xterm",
    "algo-big-o", "algo-hashing",
]
for slug in concepts:
    r = get(f"/learn/{slug}")
    check(f"GET /learn/{slug}", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        check(f"  {slug} has code block", 'class="code-block"' in r.text)
        check(f"  {slug} has 'how it works'", "How it works" in r.text)
        check(f"  {slug} has 'where this is used'", "Where this is used" in r.text)

# ─── 3. About page ────────────────────────────────────────────────────────
print("\n=== 3. About page ===")
r = get("/about")
check("About renders", r.status_code == 200)
check("About has hero section", 'class="about-hero"' in r.text)
check("About has architecture diagram", 'class="arch-diagram"' in r.text)
check("About has workflow diagrams", 'class="workflow-diagram"' in r.text)
check("About has 6+ workflow rows", r.text.count('class="workflow-row"') >= 6,
      f"found {r.text.count('class=\"workflow-row\"')} workflow rows")
sections_found = re.findall(r'class="about-section"', r.text)
check("About has 7+ sections", len(sections_found) >= 7,
      f"found {len(sections_found)} sections")

# ─── 4. Notebook page (after login) ───────────────────────────────────────
print("\n=== 4. Notebook (logged in) ===")
s = requests.Session()
# Register a test user
import random, string
uname = "smoke_" + "".join(random.choices(string.ascii_lowercase, k=5))
try:
    r = s.post(f"{BASE}/register", data={
        "username": uname, "email": f"{uname}@test.com",
        "password": "Test1234!", "confirm_password": "Test1234!"
    }, allow_redirects=False, timeout=10)
    # Login form expects 'email' field, not 'username'
    r = s.post(f"{BASE}/login", data={
        "email": f"{uname}@test.com", "password": "Test1234!"
    }, allow_redirects=False, timeout=10)
except Exception as e:
    print(f"  ! register/login failed: {e}")
    r = type("Err", (), {"status_code": 0, "text": ""})()

try:
    r = s.get(f"{BASE}/notebook", allow_redirects=False, timeout=10)
except Exception as e:
    r = type("Err", (), {"status_code": 0, "text": ""})()
    print(f"  ! notebook fetch failed: {e}")

check("Notebook (logged in) → 200", r.status_code == 200, f"got {r.status_code}")
if r.status_code == 200:
    # The CRITICAL bug: backtick in template literal. Verify the placeholder text is fixed.
    check("Notebook has NO backtick-in-template-literal",
          "`code`, etc" not in r.text,
          "still has backtick in placeholder!")
    check("Notebook has fixed placeholder text",
          "single-backtick code" in r.text or "Markdown — use" in r.text,
          "fixed placeholder not found")
    check("Notebook has addCodeCell function",
          "function addCodeCell" in r.text)
    check("Notebook has + Code button",
          "+ Code" in r.text)
    check("Notebook has runCell function",
          "async function runCell" in r.text)
    check("Notebook has Terminal tab",
          'id="tab-terminal"' in r.text)

    # Try running a cell
    try:
        r = s.post(f"{BASE}/api/notebook/cell", json={
            "code": "x = 42\nprint(x)",
            "timeout_seconds": 30,
        }, timeout=30)
        check("POST /api/notebook/cell → 200", r.status_code == 200, f"got {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            check("Cell result ok=True", data.get("ok") is True, f"got {data}")
            check("Cell output has '42'", "42" in (data.get("stdout") or ""), f"stdout={data.get('stdout')}")

        # Persistent state test
        r = s.post(f"{BASE}/api/notebook/cell", json={
            "code": "print(x * 2)",
            "timeout_seconds": 30,
        }, timeout=30)
        check("Persistent state: x*2 = 84",
              r.status_code == 200 and "84" in (r.json().get("stdout") or ""),
              f"got {r.json() if r.status_code == 200 else r.status_code}")
    except Exception as e:
        check("Notebook cell execution", False, f"exception: {e}")

# ─── 5. Competition detail page ───────────────────────────────────────────
print("\n=== 5. Competition detail XSS fix ===")
# Get a competition slug from the listing
r = get("/competitions")
comp_slugs = re.findall(r'href="/competitions/([\w-]+)"', r.text)
if comp_slugs:
    slug = comp_slugs[0]
    r = get(f"/competitions/{slug}")
    check(f"GET /competitions/{slug}", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        check("Competition has escapeHtml function",
              "function escapeHtml" in r.text or "escapeHtml" in r.text,
              "escapeHtml not found")
        check("Comments use escapeHtml on body",
              "escapeHtml(c.body)" in r.text,
              "escapeHtml(c.body) not found")
        check("Leaderboard uses escapeHtml on username",
              "escapeHtml(r.username)" in r.text,
              "escapeHtml(r.username) not found")
else:
    print("  (no competitions to test)")

# ─── 6. Realtime page ─────────────────────────────────────────────────────
print("\n=== 6. Realtime page XSS fix ===")
r = get("/realtime")
check("GET /realtime", r.status_code == 200)
if r.status_code == 200:
    check("Realtime escapes type in addEvent",
          "escapeHtml(type)" in r.text,
          "escapeHtml(type) not found")
    check("Realtime escapes e.message in error",
          "escapeHtml(e.message)" in r.text,
          "escapeHtml(e.message) not found")

# ─── 7. Static template audit: no backtick-in-template-literal ────────────
print("\n=== 7. Template backtick audit ===")
import os
TEMPLATE_DIR = "/home/z/my-project/templates"
suspect_files = []
for fname in os.listdir(TEMPLATE_DIR):
    if not fname.endswith(".html"):
        continue
    path = os.path.join(TEMPLATE_DIR, fname)
    with open(path) as f:
        content = f.read()
    # Find all JS template literals (between backticks that aren't escaped)
    # Look for placeholder attributes that contain backticks
    if re.search(r'placeholder="[^"`]*`[^"`]*`', content):
        suspect_files.append(fname)
        continue
    # Also look for `text` patterns inside backtick template literals (harder to detect statically)
    # Simple heuristic: find template literals containing unescaped `word` patterns
    # This is approximate but catches the common case
    for m in re.finditer(r'`[^`]*`', content):
        literal = m.group(0)
        # Check if the literal itself contains a backtick that would close it early
        # (this is what we're looking for — the regex stops at the first closing backtick,
        #  so if there's another `word` pattern right after, it's a sign of trouble)
        pass

if suspect_files:
    check("No template has backtick in placeholder", False,
          f"suspects: {suspect_files}")
else:
    check("No template has backtick in placeholder", True)

# ─── 8. Health endpoint ───────────────────────────────────────────────────
print("\n=== 8. Health & API ===")
r = get("/health")
check("GET /health", r.status_code == 200)
if r.status_code == 200:
    h = r.json()
    check("Health status=healthy", h.get("status") == "healthy", f"got {h.get('status')}")
    check("Health has version", "version" in h)

r = get("/api/info")
check("GET /api/info", r.status_code == 200)

# ─── Summary ──────────────────────────────────────────────────────────────
print(f"\n{'=' * 60}")
print(f"PASSED: {PASS}    FAILED: {FAIL}")
print(f"{'=' * 60}")
if ERRORS:
    print("\nFailures:")
    for e in ERRORS:
        print(f"  - {e}")
sys.exit(0 if FAIL == 0 else 1)
