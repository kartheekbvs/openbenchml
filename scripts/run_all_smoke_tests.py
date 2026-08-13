"""Run all smoke tests against a freshly started dev server.

The sandbox seems to kill idle dev servers, so we start the server inline
and run all tests in one shot.
"""
import os
import sys
import time
import subprocess
import requests

BASE = "http://localhost:3000"

print("=== Starting uvicorn on port 3000 ===")
proc = subprocess.Popen(
    ["python3", "-m", "uvicorn", "app.main:app",
     "--host", "0.0.0.0", "--port", "3000", "--log-level", "warning"],
    cwd="/home/z/my-project",
    stdout=open("/tmp/obml_smoke_server.log", "w"),
    stderr=subprocess.STDOUT,
)

print("Waiting for server...")
ready = False
for i in range(60):
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
    print("Server failed to start. Log:")
    with open("/tmp/obml_smoke_server.log") as f:
        print(f.read()[-2000:])
    proc.terminate()
    sys.exit(1)

# Set env var so smoke tests use the right BASE
os.environ["OBML_SMOKE_BASE"] = BASE

results = {}
try:
    smoke_tests = [
        ("v43 full", "/home/z/my-project/scripts/smoke_test_v43_full.py"),
        ("notebook v2", "/home/z/my-project/scripts/smoke_test_notebook_v2.py"),
        ("convert realworld v13", "/home/z/my-project/scripts/smoke_test_convert_realworld_v13.py"),
        ("security v13.1", "/home/z/my-project/scripts/smoke_test_security_v13_1.py"),
        ("terminal v21", "/home/z/my-project/scripts/smoke_test_terminal_v21.py"),
    ]
    for name, script in smoke_tests:
        print(f"\n{'='*70}")
        print(f"=== {name}: {script}")
        print('='*70)
        # Patch the BASE variable in the script if needed
        with open(script) as f:
            src = f.read()
        # Replace any 127.0.0.1:8000 or localhost:8000 with our BASE
        # We do this by writing a temp copy
        patched_src = src.replace("http://127.0.0.1:8000", BASE).replace("http://localhost:8000", BASE)
        if patched_src != src:
            tmp_path = "/tmp/_smoke_patched.py"
            with open(tmp_path, "w") as f:
                f.write(patched_src)
            run_path = tmp_path
        else:
            run_path = script
        r = subprocess.run(["python3", run_path], cwd="/home/z/my-project",
                            capture_output=True, text=True, timeout=180)
        # Print last 60 lines of stdout
        out_lines = r.stdout.strip().split("\n")
        for line in out_lines[-60:]:
            print(line)
        if r.stderr:
            print("--- STDERR (last 20 lines) ---")
            for line in r.stderr.strip().split("\n")[-20:]:
                print(line)
        print(f"\n{name}: exit={r.returncode}")
        results[name] = r.returncode

    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    for name, rc in results.items():
        marker = "PASS" if rc == 0 else "FAIL"
        print(f"  {marker}  {name}")
finally:
    print("\n=== Stopping server ===")
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
