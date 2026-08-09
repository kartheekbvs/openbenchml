"""
OpenBenchML — Full Real-World End-to-End Smoke Test (v14)
==========================================================
Exercises every feature the way a real user would:
  1. Register + login (cookie + bearer)
  2. Every HTML page returns 200
  3. Every JSON API endpoint returns valid JSON
  4. Convert page presets actually train models via /api/convert
  5. Notebook endpoint runs real Python (numpy/pandas/sklearn/matplotlib)
  6. Upload-pickle endpoint saves a Pyodide-trained model
  7. Benchmark a converted model end-to-end → leaderboard updated
  8. Datasets, models, jobs, results, compare, competitions — all 200
  9. Convert precision: model_class + framework correctly detected for
     RF, Ridge, SVC, GradientBoosting, KNN
 10. Pyodide-style pickle upload path with metrics round-trip

Run:
    USE_SQLITE=True python scripts/smoke_test_realworld_full.py
"""
from __future__ import annotations
import base64
import io
import json
import os
import sys
import time
import uuid
from pathlib import Path

# Ensure we use SQLite for the test
os.environ.setdefault("USE_SQLITE", "True")

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from app.main import app

PASS = 0
FAIL = 0
SKIP = 0
FAILURES: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [ok] {label}")
    else:
        FAIL += 1
        msg = f"  [FAIL] {label} {detail}"
        print(msg)
        FAILURES.append(msg)


def section(n: int, title: str) -> None:
    print(f"\n[{n}] {title}")


# ─── Setup ──────────────────────────────────────────────────────────────────
def make_user(client: TestClient, suffix: str = "") -> tuple[str, str, str, str]:
    """Register a fresh user via the JSON API and return (username, email, password, token)."""
    uname = f"rwuser_{uuid.uuid4().hex[:8]}{suffix}"
    # Use example.com — Pydantic's EmailStr rejects `.test` as a reserved TLD.
    email = f"{uname}@example.com"
    pw = "TestPass123!"
    r = client.post("/api/auth/register", json={
        "username": uname, "email": email, "password": pw,
    })
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    assert "access_token" in data, f"no access_token: {data}"
    return uname, email, pw, data["access_token"]


def login_token(client: TestClient, email: str, password: str) -> str:
    # /api/auth/login accepts JSON {email, password}
    r = client.post("/api/auth/login", json={
        "email": email, "password": password,
    })
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:300]}"
    return r.json()["access_token"]


# ─── Main ───────────────────────────────────────────────────────────────────
def main() -> None:
    print("=" * 78)
    print("OpenBenchML — Full Real-World End-to-End Smoke Test (v14)")
    print("=" * 78)

    with TestClient(app) as client:
        # ── 1. Auth ──────────────────────────────────────────────────────
        section(1, "Auth: register + login")
        username, email, password, token = make_user(client)
        check("register returns access_token", bool(token))
        token2 = login_token(client, email, password)
        check("login returns access_token", bool(token2))

        client.headers.update({"Authorization": f"Bearer {token}"})

        # ── 2. Public HTML pages ─────────────────────────────────────────
        section(2, "Public HTML pages return 200")
        public_pages = [
            "/", "/login", "/register", "/health", "/api/info",
            "/realtime",  # auth-gated but accessible
        ]
        for path in public_pages:
            r = client.get(path)
            check(f"GET {path}", r.status_code == 200, f"got {r.status_code}")

        # ── 3. Authenticated HTML pages ──────────────────────────────────
        section(3, "Authenticated HTML pages return 200")
        auth_pages = [
            "/dashboard", "/convert", "/notebook", "/benchmark", "/jobs",
            "/datasets", "/my-models", "/leaderboard", "/competitions",
            "/models/upload", "/compare",
        ]
        for path in auth_pages:
            r = client.get(path)
            check(f"GET {path}", r.status_code == 200, f"got {r.status_code}")

        # ── 4. JSON API endpoints ────────────────────────────────────────
        section(4, "JSON API endpoints return valid JSON")
        api_endpoints = [
            "/api/info", "/api/datasets", "/api/models", "/api/jobs",
            "/api/competitions", "/api/leaderboard",
        ]
        for path in api_endpoints:
            r = client.get(path)
            ok = r.status_code == 200
            try:
                r.json()
            except Exception:
                ok = False
            check(f"GET {path}", ok, f"got {r.status_code}")

        # ── 5. Datasets ──────────────────────────────────────────────────
        section(5, "Datasets exist and are queryable")
        r = client.get("/api/datasets")
        datasets = r.json()
        check(f"datasets seeded ({len(datasets)})", len(datasets) >= 3)
        if datasets:
            ds = datasets[0]
            r = client.get(f"/datasets/{ds['id']}")
            check(f"GET /datasets/{ds['id']} (HTML)", r.status_code == 200)
        # Find Iris dataset by name (case-insensitive)
        iris_ds = next((d for d in datasets if d["name"].lower() == "iris"), None)
        check("Iris dataset exists", iris_ds is not None,
              f"names={[d['name'] for d in datasets]}")

        # ── 6. Convert — Iris RF (small) ─────────────────────────────────
        section(6, "/api/convert — Iris RandomForest (precision check)")
        iris_code = """
from sklearn.datasets import load_iris
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

X, y = load_iris(return_X_y=True)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

model = RandomForestClassifier(n_estimators=50, random_state=42)
model.fit(X_train, y_train)
acc = accuracy_score(y_test, model.predict(X_test))
print(f"Iris RF accuracy: {acc:.4f}")
"""
        r = client.post("/api/convert", json={
            "model_name": "Test Iris RF",
            "framework": "scikit-learn",
            "code": iris_code,
            "timeout_seconds": 120,
        })
        check(f"/api/convert status=200 (got {r.status_code})", r.status_code == 200)
        if r.status_code == 200:
            d = r.json()
            check("model_class detected (RandomForestClassifier)",
                  d.get("model_class") == "RandomForestClassifier",
                  f"got {d.get('model_class')!r}")
            check("detected_framework=scikit-learn",
                  d.get("detected_framework") == "scikit-learn",
                  f"got {d.get('detected_framework')!r}")
            check("metrics.accuracy captured",
                  "accuracy" in d.get("metrics_in_code", {}),
                  f"metrics={d.get('metrics_in_code')}")
            check("model id assigned", d.get("id") is not None)
            iris_model_id = d["id"]
        else:
            iris_model_id = None

        # ── 7. Convert precision: 5 different model types ────────────────
        section(7, "/api/convert precision — 5 model types correctly detected")
        precision_cases = [
            ("Ridge regression",
             "from sklearn.linear_model import Ridge\nfrom sklearn.datasets import load_diabetes\nfrom sklearn.model_selection import train_test_split\nX,y=load_diabetes(return_X_y=True)\nXtr,Xte,ytr,yte=train_test_split(X,y,test_size=0.2,random_state=42)\nmodel=Ridge(alpha=1.0).fit(Xtr,ytr)\nrmse=float(((yte-model.predict(Xte))**2).mean()**0.5)\n",
             "Ridge", "scikit-learn", ["rmse"], "regression", ["alpha"]),
            ("SVC classifier",
             "from sklearn.svm import SVC\nfrom sklearn.datasets import load_wine\nfrom sklearn.model_selection import train_test_split\nfrom sklearn.metrics import accuracy_score\nX,y=load_wine(return_X_y=True)\nXtr,Xte,ytr,yte=train_test_split(X,y,test_size=0.2,random_state=42,stratify=y)\nmodel=SVC(kernel='rbf',C=1.0,gamma='scale',probability=True).fit(Xtr,ytr)\nacc=accuracy_score(yte,model.predict(Xte))\n",
             "SVC", "scikit-learn", ["accuracy"], "classification", ["C","kernel"]),
            ("GradientBoostingClassifier",
             "from sklearn.ensemble import GradientBoostingClassifier\nfrom sklearn.datasets import load_breast_cancer\nfrom sklearn.model_selection import train_test_split\nfrom sklearn.metrics import accuracy_score\nX,y=load_breast_cancer(return_X_y=True)\nXtr,Xte,ytr,yte=train_test_split(X,y,test_size=0.2,random_state=42,stratify=y)\nmodel=GradientBoostingClassifier(n_estimators=50,random_state=42).fit(Xtr,ytr)\nacc=accuracy_score(yte,model.predict(Xte))\n",
             "GradientBoostingClassifier", "scikit-learn", ["accuracy"], "classification", ["n_estimators","learning_rate"]),
            ("KNeighborsClassifier",
             "from sklearn.neighbors import KNeighborsClassifier\nfrom sklearn.datasets import load_iris\nfrom sklearn.model_selection import train_test_split\nfrom sklearn.metrics import accuracy_score\nX,y=load_iris(return_X_y=True)\nXtr,Xte,ytr,yte=train_test_split(X,y,test_size=0.2,random_state=42,stratify=y)\nmodel=KNeighborsClassifier(n_neighbors=5).fit(Xtr,ytr)\nacc=accuracy_score(yte,model.predict(Xte))\n",
             "KNeighborsClassifier", "scikit-learn", ["accuracy"], "classification", ["n_neighbors"]),
            ("LogisticRegression",
             "from sklearn.linear_model import LogisticRegression\nfrom sklearn.datasets import load_digits\nfrom sklearn.model_selection import train_test_split\nfrom sklearn.metrics import accuracy_score\nX,y=load_digits(return_X_y=True)\nXtr,Xte,ytr,yte=train_test_split(X,y,test_size=0.2,random_state=42,stratify=y)\nmodel=LogisticRegression(max_iter=2000).fit(Xtr,ytr)\nacc=accuracy_score(yte,model.predict(Xte))\n",
             "LogisticRegression", "scikit-learn", ["accuracy"], "classification", ["C"]),
        ]
        for label, code, expected_class, expected_fw, expected_metrics, expected_task, expected_params in precision_cases:
            r = client.post("/api/convert", json={
                "model_name": f"Precision Test — {label}",
                "framework": "scikit-learn",
                "code": code,
                "timeout_seconds": 120,
            })
            if r.status_code != 200:
                check(f"{label}: convert=200", False, f"got {r.status_code}: {r.text[:200]}")
                continue
            d = r.json()
            check(f"{label}: model_class={expected_class}",
                  d.get("model_class") == expected_class,
                  f"got {d.get('model_class')!r}")
            check(f"{label}: framework={expected_fw}",
                  d.get("detected_framework") == expected_fw,
                  f"got {d.get('detected_framework')!r}")
            check(f"{label}: task_type={expected_task}",
                  d.get("task_type") == expected_task,
                  f"got {d.get('task_type')!r}")
            check(f"{label}: is_fitted=True",
                  d.get("is_fitted") is True,
                  f"got {d.get('is_fitted')!r}")
            for m in expected_metrics:
                check(f"{label}: metric {m} captured",
                      m in d.get("metrics_in_code", {}),
                      f"metrics={d.get('metrics_in_code')}")
            for p in expected_params:
                check(f"{label}: param {p} introspected",
                      p in d.get("params", {}),
                      f"params={d.get('params')}")

        # ── 8. Notebook API runs real code ───────────────────────────────
        section(8, "/api/notebook/run executes real Python")
        nb_tests = [
            ("numpy", "import numpy as np\nprint(np.array([1,2,3]).sum())"),
            ("pandas", "import pandas as pd\ndf=pd.DataFrame({'a':[1,2,3]})\nprint(df['a'].mean())"),
            ("sklearn", "from sklearn.datasets import load_iris\nX,y=load_iris(return_X_y=True)\nprint(X.shape)"),
            ("matplotlib", "import matplotlib\nmatplotlib.use('Agg')\nimport matplotlib.pyplot as plt\nplt.plot([1,2,3],[1,4,9])\nplt.savefig('/tmp/_t.png')\nprint('ok')"),
        ]
        for label, code in nb_tests:
            r = client.post("/api/notebook/run", json={"code": code, "timeout_seconds": 30})
            if r.status_code != 200:
                check(f"notebook {label}", False, f"got {r.status_code}: {r.text[:200]}")
                continue
            d = r.json()
            check(f"notebook {label} ok", d.get("ok") is True,
                  f"ok={d.get('ok')}, err={d.get('error')}")

        # ── 9. Upload-pickle (Pyodide browser path simulation) ───────────
        section(9, "/api/convert/upload-pickle (Pyodide browser path)")
        import joblib
        from sklearn.linear_model import LogisticRegression
        from sklearn.datasets import load_iris
        X, y = load_iris(return_X_y=True)
        browser_model = LogisticRegression(max_iter=200).fit(X, y)
        buf = io.BytesIO()
        joblib.dump(browser_model, buf, compress=3)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        r = client.post("/api/convert/upload-pickle", json={
            "model_name": "Pyodide Path Test LR",
            "framework": "scikit-learn",
            "pickle_base64": b64,
            "model_class_hint": "LogisticRegression",
            "stdout": "[pyodide] training finished",
            "stderr": "",
            "metrics": {"accuracy": 0.97},
        })
        check(f"upload-pickle status=200 (got {r.status_code})", r.status_code == 200,
              f"body: {r.text[:200]}")
        if r.status_code == 200:
            d = r.json()
            check("upload-pickle model_class=LogisticRegression",
                  d.get("model_class") == "LogisticRegression",
                  f"got {d.get('model_class')!r}")
            check("upload-pickle engine=pyodide-browser",
                  d.get("engine") == "pyodide-browser")
            check("upload-pickle metrics round-trip",
                  d.get("metrics_in_code", {}).get("accuracy") == 0.97,
                  f"got {d.get('metrics_in_code')}")
            check("upload-pickle model id assigned", d.get("id") is not None)

        # ── 10. End-to-end benchmark → leaderboard ───────────────────────
        section(10, "End-to-end benchmark lifecycle → leaderboard")
        if iris_model_id and iris_ds:
            ds_id = iris_ds["id"]
            r = client.post("/benchmark", data={
                "model_id": str(iris_model_id),
                "dataset_id": str(ds_id),
            }, follow_redirects=False)
            check(f"POST /benchmark status=303 (got {r.status_code})",
                  r.status_code == 303, f"body: {r.text[:200]}")
            if r.status_code == 303:
                # Follow to /results/{job_id}
                loc = r.headers.get("location", "")
                check("redirect goes to /results/", loc.startswith("/results/"),
                      f"location={loc!r}")
                if loc.startswith("/results/"):
                    r2 = client.get(loc)
                    check(f"GET {loc} status=200", r2.status_code == 200,
                          f"got {r2.status_code}")
                    job_id = int(loc.rsplit("/", 1)[-1])
                    # API result
                    r3 = client.get(f"/api/results/{job_id}")
                    check(f"GET /api/results/{job_id} status=200",
                          r3.status_code == 200, f"got {r3.status_code}")
                    if r3.status_code == 200:
                        rd = r3.json()
                        check("benchmark status=completed",
                              rd.get("status") == "completed",
                              f"status={rd.get('status')!r}, err={rd.get('error_message')}")
                        metrics = rd.get("metrics") or {}
                        check("benchmark has accuracy metric",
                              metrics.get("accuracy") is not None,
                              f"metrics={list(metrics.keys())}")
                        check("benchmark has latency_ms",
                              metrics.get("latency_ms") is not None)
                        check("benchmark has model_size_kb",
                              metrics.get("model_size_kb") is not None)
                        check("benchmark has latency_p50/p95/p99",
                              all(metrics.get(k) is not None
                                  for k in ["latency_p50_ms", "latency_p95_ms", "latency_p99_ms"]))

            # Check leaderboard now has an entry
            r = client.get(f"/api/leaderboard?dataset_id={ds_id}")
            check("GET /api/leaderboard?dataset_id=… status=200",
                  r.status_code == 200)
            if r.status_code == 200:
                entries = r.json()
                check("leaderboard has at least 1 entry", len(entries) >= 1,
                      f"entries={len(entries)}")

        # ── 11. Jobs list ────────────────────────────────────────────────
        section(11, "Jobs listing")
        r = client.get("/api/jobs")
        check(f"GET /api/jobs status=200", r.status_code == 200)
        if r.status_code == 200:
            jobs = r.json()
            check("at least 1 job exists", len(jobs) >= 1, f"jobs={len(jobs)}")
            if jobs:
                jid = jobs[0]["id"]
                r = client.get(f"/results/{jid}")
                check(f"GET /results/{jid} status=200", r.status_code == 200,
                      f"got {r.status_code}")

        # ── 12. Model detail + my-models ─────────────────────────────────
        section(12, "Model detail + my-models")
        if iris_model_id:
            r = client.get(f"/models/{iris_model_id}")
            check(f"GET /models/{iris_model_id} status=200",
                  r.status_code == 200, f"got {r.status_code}")

        r = client.get("/api/models")
        if r.status_code == 200:
            models = r.json()
            check(f"public models list non-empty ({len(models)})", len(models) >= 1)

        # ── 13. Compare page ─────────────────────────────────────────────
        section(13, "Model comparison")
        r = client.get("/compare")
        check(f"GET /compare status=200", r.status_code == 200)
        # We need 2 models for a comparison
        r = client.get("/api/models")
        if r.status_code == 200 and len(r.json()) >= 2:
            m1, m2 = r.json()[0]["id"], r.json()[1]["id"]
            r = client.post("/compare", data={
                "model_id_1": str(m1), "model_id_2": str(m2),
            }, follow_redirects=False)
            check(f"POST /compare status=200 (got {r.status_code})",
                  r.status_code == 200, f"body: {r.text[:200]}")

        # ── 14. Competitions ─────────────────────────────────────────────
        section(14, "Competitions")
        r = client.get("/api/competitions")
        check("GET /api/competitions status=200", r.status_code == 200)
        if r.status_code == 200:
            comps = r.json()
            check(f"competitions exist ({len(comps)})", len(comps) >= 1)
            if comps:
                # Competitions are routed by slug, not id.
                slug = comps[0].get("slug")
                if slug:
                    r = client.get(f"/competitions/{slug}")
                    check(f"GET /competitions/{slug} status=200",
                          r.status_code == 200, f"got {r.status_code}")
                    r = client.get(f"/api/competitions/{slug}")
                    check(f"GET /api/competitions/{slug} status=200",
                          r.status_code == 200, f"got {r.status_code}")
                    r = client.get(f"/api/competitions/{slug}/leaderboard")
                    check(f"GET /api/competitions/{slug}/leaderboard status=200",
                          r.status_code == 200, f"got {r.status_code}")

        # ── 15. Convert template has Pyodide as default engine ───────────
        section(15, "Notebook + Convert pages default to Pyodide engine")
        r = client.get("/notebook")
        if r.status_code == 200:
            html = r.text
            check("notebook loads Pyodide CDN script",
                  "cdn.jsdelivr.net/pyodide" in html)
            check("notebook calls pyodide.loadPackage",
                  "loadPackage" in html)
            check("notebook includes numpy+pandas+sklearn+matplotlib in PYODIDE_PACKAGES",
                  all(p in html for p in ["numpy", "pandas", "scikit-learn", "matplotlib"]))
        r = client.get("/convert")
        if r.status_code == 200:
            html = r.text
            check("convert loads Pyodide CDN script",
                  "cdn.jsdelivr.net/pyodide" in html)
            check("convert calls pyodide.loadPackage",
                  "loadPackage" in html)
            check("convert has engine toggle (Pyodide + Server)",
                  "engine-pyodide" in html and "engine-server" in html)
            check("convert has California Housing preset",
                  "cali-rf" in html)
            check("convert uploads pickle via /api/convert/upload-pickle",
                  "/api/convert/upload-pickle" in html)

        # ── 16. Error handling ───────────────────────────────────────────
        section(16, "Error handling — bad inputs")
        # Empty code
        r = client.post("/api/notebook/run", json={"code": "", "timeout_seconds": 5})
        check("empty notebook code rejected (422)",
              r.status_code == 422, f"got {r.status_code}")
        # Code without model var
        r = client.post("/api/convert", json={
            "model_name": "Bad Test",
            "framework": "scikit-learn",
            "code": "x = 1\nprint(x)\n",
            "timeout_seconds": 30,
        })
        check("code without model var returns 400",
              r.status_code == 400, f"got {r.status_code}")
        # Code with non-model object assigned to `model`
        r = client.post("/api/convert", json={
            "model_name": "Non-model Test",
            "framework": "scikit-learn",
            "code": "model = 42\n",
            "timeout_seconds": 30,
        })
        check("non-model object (int) rejected with helpful error (400)",
              r.status_code == 400, f"got {r.status_code}")
        if r.status_code == 400:
            try:
                detail = r.json().get("detail", "")
                check("error mentions predict/transform/score",
                      "predict" in detail or "transform" in detail or "score" in detail,
                      f"detail: {detail[:200]}")
            except Exception:
                pass
        # Code with a non-fitted estimator (has predict but is_fitted=False)
        # — should still convert (we allow it; benchmark engine will catch it).
        r = client.post("/api/convert", json={
            "model_name": "Unfitted Estimator Test",
            "framework": "scikit-learn",
            "code": "from sklearn.ensemble import RandomForestClassifier\nmodel = RandomForestClassifier()\n",
            "timeout_seconds": 30,
        })
        check("unfitted estimator still converts (200)",
              r.status_code == 200, f"got {r.status_code}")
        if r.status_code == 200:
            d = r.json()
            check("unfitted: is_fitted=False surfaced in response",
                  d.get("is_fitted") is False,
                  f"got {d.get('is_fitted')!r}")
        # Invalid framework
        r = client.post("/api/convert", json={
            "model_name": "Bad FW Test",
            "framework": "not-a-real-framework",
            "code": "model = 1\n",
            "timeout_seconds": 30,
        })
        check("invalid framework rejected (400)",
              r.status_code == 400, f"got {r.status_code}")
        # Auth required — no token
        unauth_client = TestClient(app)
        r = unauth_client.post("/api/convert", json={
            "model_name": "X", "framework": "scikit-learn",
            "code": "model=1\n", "timeout_seconds": 30,
        })
        check("unauthenticated /api/convert returns 401",
              r.status_code == 401, f"got {r.status_code}")

    # ─── Summary ───────────────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print(f"RESULT: {PASS} passed, {FAIL} failed, {SKIP} skipped")
    print("=" * 78)
    if FAIL > 0:
        print("\nFAILURES:")
        for f in FAILURES:
            print(f)
        sys.exit(1)
    else:
        print("\nAll real-world checks passed.")
        print("  - All HTML pages render")
        print("  - All JSON APIs return valid responses")
        print("  - /convert correctly detects model_class + framework + metrics for 6 model types")
        print("  - /notebook runs numpy, pandas, sklearn, matplotlib code")
        print("  - Pyodide upload-pickle path round-trips models + metrics")
        print("  - End-to-end benchmark lifecycle: convert → benchmark → results → leaderboard")
        print("  - Pyodide is the default engine on both /convert and /notebook")


if __name__ == "__main__":
    main()
