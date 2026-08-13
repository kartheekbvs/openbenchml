"""
HTTP-level smoke test for the new dataset preview + sample benchmark
endpoints.  Uses FastAPI's TestClient so we don't need a running
server.  Verifies:

1. GET /datasets/{id} renders with preview table
2. GET /datasets/{id}?rows=10 returns more rows than default 5
3. GET /api/datasets/{id}/preview?rows=3 returns JSON
4. POST /benchmark/sample/{id} redirects to /results/{job_id}
5. GET /results/{job_id} renders real metrics for the sample job
"""
import os
import sys
import re

sys.path.insert(0, "/home/z/my-project")
os.chdir("/home/z/my-project")

import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from fastapi.testclient import TestClient

from app.main import app
from app.database.db import SessionLocal, init_db
from app.database.models import Dataset, BenchmarkJob
from app.database.seed import seed_database
from app.services.sample_models_service import ensure_sample_models


def main():
    print("=" * 78)
    print("OpenBenchML — HTTP Smoke Test (TestClient)")
    print("=" * 78)

    # Setup
    init_db()
    seed_database()
    db = SessionLocal()
    try:
        ensure_sample_models(db)
    finally:
        db.close()

    client = TestClient(app, raise_server_exceptions=False)

    pass_count = 0
    fail_count = 0

    def check(label, cond, detail=""):
        nonlocal pass_count, fail_count
        if cond:
            pass_count += 1
            print(f"  PASS  {label}")
        else:
            fail_count += 1
            print(f"  FAIL  {label}  {detail}")

    # ── 1. GET /datasets/{id} (default rows) ─────────────────────────────
    print("\n[1] GET /datasets/9 (Titanic, default 5 rows)")
    r = client.get("/datasets/9", follow_redirects=False)
    check("status 200", r.status_code == 200, f"got {r.status_code}")
    body = r.text
    check("contains df.head(5) heading", "df.head(5)" in body)
    check("contains <table", "<table" in body)
    check("contains 'Titanic'", "Titanic" in body)
    check("contains 'Run Sample Benchmark' button",
          "Run Sample Benchmark" in body)
    # The only allowed <script> is the shared /static/js/main.js
    # (progressive enhancement: mobile nav toggle, alert dismiss).
    # Page-specific vanilla JS application logic is forbidden.
    import re
    script_srcs = re.findall(r'<script[^>]*src=["\']([^"\']+)["\']', body, re.IGNORECASE)
    inline_scripts = re.findall(r'<script(?![^>]*src)[^>]*>.*?</script>', body, re.IGNORECASE | re.DOTALL)
    check("only the shared main.js script tag is loaded",
          script_srcs == ["/static/js/main.js"] and len(inline_scripts) == 0,
          f"srcs={script_srcs} inline={len(inline_scripts)}")

    # ── 2. GET /datasets/{id}?rows=10 ────────────────────────────────────
    print("\n[2] GET /datasets/9?rows=10 (should show 10 rows)")
    r = client.get("/datasets/9?rows=10", follow_redirects=False)
    check("status 200", r.status_code == 200, f"got {r.status_code}")
    body = r.text
    check("contains df.head(10) heading", "df.head(10)" in body)
    # Count <tr> in tbody (header has 1, body should have 10) — rough check
    n_tr = body.count("<tr>")
    check("at least 11 <tr> tags (1 header + 10 body)", n_tr >= 11, f"only {n_tr}")

    # ── 3. GET /api/datasets/{id}/preview?rows=3 ─────────────────────────
    print("\n[3] GET /api/datasets/9/preview?rows=3 (JSON)")
    r = client.get("/api/datasets/9/preview?rows=3", follow_redirects=False)
    check("status 200", r.status_code == 200, f"got {r.status_code}")
    j = r.json()
    check("returned_rows == 3", j.get("returned_rows") == 3, f"got {j.get('returned_rows')}")
    check("len(rows) == 3", len(j.get("rows", [])) == 3)
    check("columns non-empty", len(j.get("columns", [])) > 0)
    check("source == csv", j.get("source") == "csv", f"got {j.get('source')}")

    # ── 4. POST /benchmark/sample/{id} ───────────────────────────────────
    print("\n[4] POST /benchmark/sample/9 (Titanic — runs sample benchmark)")
    r = client.post("/benchmark/sample/9", follow_redirects=False)
    check("status 303 (redirect)", r.status_code == 303, f"got {r.status_code}")
    loc = r.headers.get("location", "")
    check("redirects to /results/{id}", loc.startswith("/results/"), f"location={loc}")
    m = re.match(r"/results/(\d+)", loc)
    job_id = int(m.group(1)) if m else None
    check("job_id is parseable", job_id is not None, f"loc={loc}")
    if job_id:
        db = SessionLocal()
        try:
            job = db.query(BenchmarkJob).filter(BenchmarkJob.id == job_id).first()
            check("job status == completed",
                  job is not None and job.status == "completed",
                  f"status={job.status if job else 'None'}, err={job.error_message if job else ''}")
            check("job has result", job is not None and job.result is not None)
            if job and job.result:
                check("accuracy is a real number (0..1)",
                      job.result.accuracy is not None and 0.0 <= job.result.accuracy <= 1.0,
                      f"acc={job.result.accuracy}")
                check("p95 latency > 0",
                      job.result.latency_p95_ms is not None and job.result.latency_p95_ms > 0,
                      f"p95={job.result.latency_p95_ms}")
        finally:
            db.close()

    # ── 5. GET /results/{job_id} ─────────────────────────────────────────
    print("\n[5] GET /results/{job_id} (should render real metrics)")
    if job_id:
        r = client.get(f"/results/{job_id}", follow_redirects=False)
        check("status 200", r.status_code == 200, f"got {r.status_code}")
        body = r.text
        check("contains 'SAMPLE BENCHMARK' badge", "SAMPLE BENCHMARK" in body)
        check("contains 'Latency P95'", "Latency P95" in body)
        check("contains 'Throughput'", "Throughput" in body)
        check("contains 'Inferences measured'", "Inferences measured" in body)
    # (allow shared main.js on /results too)
    import re as _re
    srcs = _re.findall(r'<script[^>]*src=["\']([^"\']+)["\']', body, _re.IGNORECASE)
    inline = _re.findall(r'<script(?![^>]*src)[^>]*>.*?</script>', body, _re.IGNORECASE | _re.DOTALL)
    check("/results only loads shared main.js",
          srcs == ["/static/js/main.js"] and len(inline) == 0,
          f"srcs={srcs} inline={len(inline)}")

    # ── 6. GET /datasets/{id} for a regression dataset ───────────────────
    print("\n[6] GET /datasets/19 (BostonHousing, regression)")
    r = client.get("/datasets/19", follow_redirects=False)
    check("status 200", r.status_code == 200, f"got {r.status_code}")
    body = r.text
    check("contains df.head(5)", "df.head(5)" in body)
    check("contains 'R² Score' column header (regression)",
          "R\u00b2 Score" in body or "R&sup2; Score" in body,
          "no regression-aware column header found")

    # ── Summary ──────────────────────────────────────────────────────────
    print()
    print("=" * 78)
    print(f"RESULT: {pass_count} passed, {fail_count} failed")
    print("=" * 78)
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
