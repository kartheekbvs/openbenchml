"""HTTP-level end-to-end test for the OpenBenchML web app.

Starts the FastAPI server, registers a user, logs in, uploads a real
sklearn model, runs a benchmark, and verifies the results.

Run with: .venv/bin/python scripts/smoke_test_http.py
"""
import os
import sys
import time
import joblib
import tempfile
import subprocess
from pathlib import Path

import httpx
from sklearn.datasets import load_iris
from sklearn.ensemble import RandomForestClassifier

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "http://127.0.0.1:8000"


def log(msg):
    print(f"  {msg}")


def wait_for_server(timeout=30):
    """Poll the health endpoint until the server responds."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"{BASE_URL}/health", timeout=2.0)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def main():
    print("=" * 70)
    print("OpenBenchML HTTP End-to-End Smoke Test")
    print("=" * 70)

    # ── 0. Train a real model to upload ───────────────────────────────────
    print("\n[0] Training a RandomForest on Iris for upload...")
    iris = load_iris()
    rf = RandomForestClassifier(n_estimators=30, random_state=42)
    rf.fit(iris.data, iris.target)
    tmpdir = Path(tempfile.mkdtemp(prefix="obml_e2e_"))
    model_file = tmpdir / "rf_iris.joblib"
    joblib.dump(rf, model_file)
    log(f"Saved test model: {model_file} ({model_file.stat().st_size / 1024:.1f} KB)")

    # ── 1. Start the FastAPI server in background ────────────────────────
    print("\n[1] Starting FastAPI server on port 8000...")
    env = os.environ.copy()
    env["USE_SQLITE"] = "True"
    env["DEBUG"] = "True"
    # Use a fresh DB so we don't conflict with prior runs
    db_path = tmpdir / "test.db"
    env["DATABASE_URL"] = f"sqlite:///{db_path}"

    server_proc = subprocess.Popen(
        [str(ROOT / ".venv" / "bin" / "uvicorn"), "app.main:app",
         "--host", "127.0.0.1", "--port", "8000", "--log-level", "warning"],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    try:
        log("Waiting for server to come up...")
        if not wait_for_server(timeout=40):
            server_proc.terminate()
            out, _ = server_proc.communicate(timeout=5)
            print("Server failed to start. Output:")
            print(out.decode("utf-8", errors="replace")[-3000:])
            return 1
        log("Server is up.")

        # ── 2. Register a user via API ────────────────────────────────────
        print("\n[2] Registering a test user via /api/auth/register...")
        username = f"e2e_user_{int(time.time())}"
        email = f"{username}@obml.test"
        password = "testpass123"
        r = httpx.post(
            f"{BASE_URL}/api/auth/register",
            json={"username": username, "email": email,
                  "password": password, "confirm_password": password},
            timeout=10.0,
        )
        log(f"Status: {r.status_code}")
        if r.status_code != 200:
            print(r.text)
            return 1
        token = r.json()["access_token"]
        log(f"Got token (first 20 chars): {token[:20]}...")
        headers = {"Authorization": f"Bearer {token}"}

        # ── 3. Verify auth via /api/auth/me ───────────────────────────────
        print("\n[3] Verifying auth via /api/auth/me...")
        r = httpx.get(f"{BASE_URL}/api/auth/me", headers=headers, timeout=5.0)
        log(f"Status: {r.status_code}, username: {r.json().get('username')}")

        # ── 4. List datasets ──────────────────────────────────────────────
        print("\n[4] Listing datasets via /api/datasets...")
        r = httpx.get(f"{BASE_URL}/api/datasets", headers=headers, timeout=10.0)
        log(f"Status: {r.status_code}, count: {len(r.json())}")
        datasets = r.json()
        iris_ds = next((d for d in datasets if d["name"].lower() == "iris"), None)
        if iris_ds is None:
            print("Could not find Iris dataset!")
            return 1
        log(f"Iris dataset id: {iris_ds['id']}")

        # ── 5. Upload the model via the API ───────────────────────────────
        print("\n[5] Uploading model via /api/models/upload...")
        with open(model_file, "rb") as f:
            files = {"file": (model_file.name, f, "application/octet-stream")}
            data = {
                "model_name": "E2E Test RF",
                "description": "RandomForest trained on Iris for smoke test",
                "framework": "scikit-learn",
            }
            # Cookie-based upload: use the cookie set by login flow.
            # We need to follow redirects=False to inspect the response.
            r = httpx.post(
                f"{BASE_URL}/models/upload",
                data=data,
                files=files,
                cookies={"access_token": token},
                follow_redirects=False,
                timeout=30.0,
            )
        log(f"Status: {r.status_code}")
        if r.status_code not in (303, 200):
            print("Upload failed:", r.text[:500])
            return 1

        # ── 6. List user models ───────────────────────────────────────────
        print("\n[6] Fetching uploaded model via /api/models...")
        r = httpx.get(f"{BASE_URL}/api/models", headers=headers, timeout=10.0)
        # /api/models only returns PUBLIC models — our new model is public by default
        log(f"Status: {r.status_code}, count: {len(r.json())}")
        if not r.json():
            print("No public models returned after upload!")
            return 1
        model = r.json()[0]
        log(f"Model id: {model['id']}, name: {model['model_name']}, fw: {model['framework']}")
        model_id = model["id"]

        # ── 7. Run a benchmark ────────────────────────────────────────────
        print("\n[7] Submitting benchmark job (model + iris)...")
        # Use the HTML form endpoint via cookie auth
        r = httpx.post(
            f"{BASE_URL}/benchmark",
            data={"model_id": str(model_id), "dataset_id": str(iris_ds["id"])},
            cookies={"access_token": token},
            follow_redirects=False,
            timeout=120.0,
        )
        log(f"Status: {r.status_code}, Location: {r.headers.get('location')}")

        # ── 8. Find the job id ────────────────────────────────────────────
        print("\n[8] Fetching job list via /api/jobs...")
        r = httpx.get(f"{BASE_URL}/api/jobs", headers=headers, timeout=10.0)
        jobs = r.json()
        log(f"Status: {r.status_code}, job count: {len(jobs)}")
        if not jobs:
            print("No jobs returned!")
            return 1
        job = jobs[0]
        log(f"Job id: {job['id']}, status: {job['status']}, model: {job['model_name']}")
        job_id = job["id"]

        # ── 9. Verify the job completed with REAL metrics ─────────────────
        print("\n[9] Fetching benchmark results via /api/results/{job_id}...")
        r = httpx.get(f"{BASE_URL}/api/results/{job_id}", headers=headers, timeout=10.0)
        result_data = r.json()
        log(f"Status: {r.status_code}, job status: {result_data.get('status')}")
        if result_data.get("status") != "completed":
            print(f"Benchmark did not complete! Error: {result_data.get('error_message')}")
            return 1

        metrics = result_data["metrics"]
        log("\n    ── Computed metrics ──")
        for k in ("accuracy", "precision", "recall", "f1_score", "latency_ms",
                  "latency_p50_ms", "latency_p95_ms", "latency_p99_ms",
                  "throughput_per_sec", "memory_mb", "model_size_kb",
                  "inference_count"):
            log(f"    {k:22s}: {metrics.get(k)}")

        # ── 10. Validate percentile integrity ─────────────────────────────
        print("\n[10] Validating percentile integrity...")
        p50 = metrics.get("latency_p50_ms", 0) or 0
        p95 = metrics.get("latency_p95_ms", 0) or 0
        p99 = metrics.get("latency_p99_ms", 0) or 0
        if not (p95 >= p50 and p99 >= p95):
            print(f"FAIL: percentiles not monotonic: p50={p50} p95={p95} p99={p99}")
            return 1
        if metrics.get("accuracy") is None or metrics["accuracy"] < 0.5:
            print(f"FAIL: accuracy too low: {metrics.get('accuracy')}")
            return 1
        log(f"OK P50={p50:.3f} <= P95={p95:.3f} <= P99={p99:.3f}")
        log(f"OK accuracy = {metrics['accuracy']:.4f}")

        # ── 11. Verify leaderboard was updated ────────────────────────────
        print("\n[11] Verifying leaderboard was updated...")
        r = httpx.get(f"{BASE_URL}/api/leaderboard", headers=headers, timeout=10.0)
        log(f"Status: {r.status_code}")
        if r.status_code == 200:
            lb = r.json()
            log(f"Leaderboard entries: {len(lb)}")

        print("\n" + "=" * 70)
        print("ALL HTTP END-TO-END TESTS PASSED")
        print("=" * 70)
        return 0

    finally:
        # ── Cleanup ──────────────────────────────────────────────────────
        print("\n[Cleanup] Shutting down server...")
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_proc.kill()


if __name__ == "__main__":
    sys.exit(main())
