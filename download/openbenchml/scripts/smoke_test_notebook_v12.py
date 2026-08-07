"""
Smoke test for the new multi-cell Pyodide notebook template (Task ID 12).

Verifies:
1. /notebook renders without server errors
2. Template contains the new Pyodide multi-cell UI (not the old single-cell version)
3. Template properly loads Pyodide + all required packages (numpy, pandas, scipy,
   scikit-learn, matplotlib) via loadPackage — the bug that caused the
   ModuleNotFoundError in the user's screenshot.
4. Template auto-imports np, pd, sklearn, matplotlib.pyplot
5. All 6 presets are present (iris-explore, train-rf, confusion-matrix,
   regression, cross-val, pandas-demo)
6. Cell controls (Run, move up, move down, add, delete) are present
7. Engine toggle (Pyodide / Server sandbox) is present
8. The existing /api/notebook/run endpoint still works (server sandbox mode)
"""
import sys
import os

# Ensure we import from the project root.
ROOT = "/home/z/my-project/download/openbenchml"
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from fastapi.testclient import TestClient
from app.main import app


def register_and_login(client):
    """Register a test user and return (email, bearer_token).

    We use the Bearer token in the Authorization header on subsequent
    requests instead of a cookie — the auth middleware falls back to
    Authorization: Bearer when no access_token cookie is present, and
    this sidesteps httpx TestClient cookie-domain quirks.
    """
    import uuid
    email = f"nb-test-{uuid.uuid4().hex[:8]}@example.com"
    username = f"nbuser_{uuid.uuid4().hex[:6]}"
    r = client.post("/api/auth/register",
                    json={"username": username,
                          "email": email,
                          "password": "Testpass123!"})
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    body = r.json()
    token = body["access_token"]
    # Set Authorization header as default for all subsequent requests.
    client.headers.update({"Authorization": f"Bearer {token}"})
    return email


def main():
    print("=" * 72)
    print("Notebook template smoke test — Task ID 12")
    print("=" * 72)

    # Use the context manager so FastAPI's lifespan startup event fires
    # and init_db() creates the SQLite tables.
    with TestClient(app) as client:
        run_tests(client)


def run_tests(client):
    email = register_and_login(client)
    print(f"[ok] registered test user: {email}")

    failures = []

    # ── Test 1: /notebook renders without server errors ─────────────────
    r = client.get("/notebook", follow_redirects=False)
    if r.status_code == 303:
        # redirect to login — need to log in via cookie session
        print("[skip] /notebook redirected to login — using authenticated client")
        # The register call above should have set a cookie. Try again.
        r = client.get("/notebook")
    if r.status_code != 200:
        failures.append(f"/notebook returned {r.status_code}, expected 200")
        print(f"[FAIL] /notebook returned {r.status_code}")
    else:
        print(f"[ok] /notebook returns 200 ({len(r.text)} bytes)")

    html = r.text

    # ── Test 2: New multi-cell Pyodide UI markers ───────────────────────
    checks = [
        ("Jupyter-style Notebook title",         "Jupyter-style Notebook"),
        ("Multi-cell description",               "Multi-cell Python notebook"),
        ("Pyodide CDN script tag",               "pyodide.js"),
        ("Pyodide package list (numpy)",         '"numpy"'),
        ("Pyodide package list (pandas)",        '"pandas"'),
        ("Pyodide package list (scipy)",         '"scipy"'),
        ("Pyodide package list (scikit-learn)",  '"scikit-learn"'),
        ("Pyodide package list (matplotlib)",    '"matplotlib"'),
        ("Auto-import np as np",                 "import numpy as np"),
        ("Auto-import pandas as pd",             "import pandas as pd"),
        ("Auto-import sklearn",                  "import sklearn"),
        ("Auto-import matplotlib",               "import matplotlib"),
        ("matplotlib AGG backend",               'matplotlib.use("AGG")'),
        ("loadPackage call (the fix)",           "pyodide.loadPackage(PYODIDE_PACKAGES"),
        ("Engine toggle (Pyodide button)",       "engine-pyodide"),
        ("Engine toggle (Server button)",        "engine-server"),
        ("Kernel status pill",                   "kernel-status"),
        ("Run-all button",                       "btn-run-all"),
        ("Cell DOM builder (makeCell)",          "function makeCell"),
        ("Run-cell function",                    "function runCell"),
        ("Move-cell function",                   "function moveCell"),
        ("Delete-cell function",                 "function deleteCell"),
        ("Add-cell-after function",              "function addCellAfter"),
        ("Per-cell Run button glyph",            "&#9654; Run"),
        ("Per-cell delete button glyph",         "&#10005;"),
        ("Per-cell up arrow glyph",              "&#8593;"),
        ("Per-cell down arrow glyph",            "&#8595;"),
        ("Shift+Enter shortcut",                 "Shift+Enter"),
        ("Preset: iris-explore",                 "'iris-explore'"),
        ("Preset: train-rf",                     "'train-rf'"),
        ("Preset: confusion-matrix",             "'confusion-matrix'"),
        ("Preset: regression",                   "'regression'"),
        ("Preset: cross-val",                    "'cross-val'"),
        ("Preset: pandas-demo",                  "'pandas-demo'"),
        ("Matplotlib figure capture helper",     "__obml_get_figures__"),
        ("DataFrame HTML helper",                "__obml_repr_html__"),
        ("Server sandbox fallback (fetch)",      "/api/notebook/run"),
    ]

    for label, needle in checks:
        if needle in html:
            print(f"[ok] {label}")
        else:
            failures.append(f"missing: {label} (searching for: {needle!r})")
            print(f"[FAIL] {label} — not found in template")

    # ── Test 3: Old single-cell UI markers must NOT be present ──────────
    negative_checks = [
        ("Old single-cell status pill",   'id="status-pill"'),
        ("Old single-cell textarea id",   'id="code"'),
        ("Old runNotebook function",      "function runNotebook"),
    ]
    for label, needle in negative_checks:
        if needle in html:
            failures.append(f"old single-cell marker still present: {label}")
            print(f"[FAIL] Old single-cell marker still present: {label}")
        else:
            print(f"[ok] Old single-cell marker removed: {label}")

    # ── Test 4: /api/notebook/run still works (server sandbox) ──────────
    r2 = client.post("/api/notebook/run",
                     json={"code": "print(2 + 2)", "timeout_seconds": 10})
    if r2.status_code != 200:
        failures.append(f"/api/notebook/run returned {r2.status_code}")
        print(f"[FAIL] /api/notebook/run returned {r2.status_code}")
    else:
        data = r2.json()
        if data.get("ok") and "4" in data.get("stdout", ""):
            print(f"[ok] /api/notebook/run still works (stdout={data['stdout'].strip()!r})")
        else:
            failures.append(f"/api/notebook/run returned unexpected payload: {data}")
            print(f"[FAIL] /api/notebook/run unexpected payload: {data}")

    # ── Summary ─────────────────────────────────────────────────────────
    print()
    print("=" * 72)
    if failures:
        print(f"RESULT: {len(failures)} FAILURE(S)")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("RESULT: ALL CHECKS PASS")
        print("Template is correctly the new multi-cell Pyodide notebook,")
        print("with proper package loading (numpy/pandas/scipy/sklearn/matplotlib).")
        sys.exit(0)


if __name__ == "__main__":
    main()
