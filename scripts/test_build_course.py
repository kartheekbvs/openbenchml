"""
Test the 10-step Build OpenBenchML course.

Boots the FastAPI app and verifies:
  - The course appears on the /learn landing page
  - /learn/cat/build lists all 10 steps with goals
  - Each step page renders: step badge, progress bar, goal box,
    concept code, build files, try-yourself, common mistakes, next-step link
  - Step 1 shows no prev-step link; step 10 shows "Course complete"
"""
import sys
import time
import urllib.request
import urllib.error
import re
import subprocess
import os

BASE = "http://127.0.0.1:8767"


def fetch(path: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(BASE + path, timeout=10) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return 0, str(e)


def main():
    print("=" * 70)
    print("Test: 10-Step Build OpenBenchML Course")
    print("=" * 70)

    failures = []

    # 1. Landing page lists the build course
    print("\n[1] GET /learn (landing) — build course card")
    code, html = fetch("/learn")
    if code != 200:
        failures.append(f"/learn returned {code}")
        print(f"    FAIL: HTTP {code}")
    else:
        if "Build OpenBenchML" in html and "build" in html:
            print("    OK: 'Build OpenBenchML' category card present")
        else:
            failures.append("landing missing build course card")
            print("    FAIL: build course card not found")
        # Check it shows 10 concepts
        m = re.search(r"Build OpenBenchML.*?(\d+) concepts", html, re.DOTALL)
        if m and m.group(1) == "10":
            print(f"    OK: card shows 10 concepts")
        else:
            failures.append("build course card doesn't show 10 concepts")

    # 2. Category page — all 10 steps with goals
    print("\n[2] GET /learn/cat/build — course overview")
    code, html = fetch("/learn/cat/build")
    if code != 200:
        failures.append(f"/learn/cat/build returned {code}")
        print(f"    FAIL: HTTP {code}")
    else:
        step_slugs = [
            "build-step-01-fastapi-route",
            "build-step-02-html-template",
            "build-step-03-database-user",
            "build-step-04-auth-jwt",
            "build-step-05-file-upload",
            "build-step-06-benchmark",
            "build-step-07-leaderboard",
            "build-step-08-websocket",
            "build-step-09-notebook",
            "build-step-10-docker-deploy",
        ]
        found = [s for s in step_slugs if s in html]
        print(f"    OK: {len(found)}/10 step slugs found on category page")
        if len(found) != 10:
            failures.append(f"only {len(found)}/10 steps on category page")
        # Check that goals (not summaries) are shown for build steps
        if "Visit http://localhost:8000" in html:
            print("    OK: step goals are shown (not just summaries)")
        else:
            failures.append("step goals not shown on category page")
            print("    FAIL: goals not shown")

    # 3. Each step page — full layout
    print("\n[3] Step pages — full layout (badge, progress, goal, concept, files, try, mistakes, next)")
    step_slugs = [
        "build-step-01-fastapi-route",
        "build-step-02-html-template",
        "build-step-03-database-user",
        "build-step-04-auth-jwt",
        "build-step-05-file-upload",
        "build-step-06-benchmark",
        "build-step-07-leaderboard",
        "build-step-08-websocket",
        "build-step-09-notebook",
        "build-step-10-docker-deploy",
    ]
    for i, slug in enumerate(step_slugs, 1):
        code, html = fetch(f"/learn/{slug}")
        if code != 200:
            failures.append(f"/learn/{slug} returned {code}")
            print(f"    FAIL: step {i} HTTP {code}")
            continue

        checks = {
            "step-badge": "step-badge" in html,
            "progress-bar": "step-progress-bar" in html,
            "goal-box": "goal-box" in html,
            "concept-box": "concept-box" in html,
            "project-files": "project-files" in html,
            "try-box": "try-box" in html,
            "mistakes-box": "mistakes-box" in html,
            "used-in": "used-in-box" in html,
        }
        # Next step link (steps 1-9) or "Course complete" (step 10)
        if i < 10:
            checks["next-step-link"] = "next-step-link" in html and step_slugs[i] in html
        else:
            checks["course-complete"] = "Course complete" in html
        # Prev step link (steps 2-10) — step 1 has no prev
        if i > 1:
            checks["prev-step-link"] = 'class="prev-step-link"' in html
        else:
            checks["no-prev-step"] = 'class="prev-step-link"' not in html

        ok = all(checks.values())
        marker = "OK " if ok else "FAIL"
        status = ", ".join(f"{k}={'Y' if v else 'N'}" for k, v in checks.items())
        print(f"    {marker} Step {i:2d} ({slug}): {status}")
        if not ok:
            failures.append(f"step {i} ({slug}): {status}")

    # 4. Verify step content quality — spot check step 1 has real code
    print("\n[4] Content quality spot-check (step 1)")
    code, html = fetch("/learn/build-step-01-fastapi-route")
    if code == 200:
        has_fastapi = "@app.get" in html
        has_uvicorn = "uvicorn" in html
        has_health = "/health" in html
        has_try = "Add a second route" in html
        has_mistake = "Forgetting" in html
        ok = all([has_fastapi, has_uvicorn, has_health, has_try, has_mistake])
        marker = "OK " if ok else "FAIL"
        print(f"    {marker} fastapi={has_fastapi} uvicorn={has_uvicorn} "
              f"health={has_health} try={has_try} mistakes={has_mistake}")
        if not ok:
            failures.append("step 1 content quality check failed")
    else:
        failures.append(f"step 1 returned {code}")

    # 5. Verify step 10 has Dockerfile + render.yaml
    print("\n[5] Content quality spot-check (step 10 — Docker + deploy)")
    code, html = fetch("/learn/build-step-10-docker-deploy")
    if code == 200:
        has_dockerfile = "FROM python:3.11-slim" in html
        has_render = "render.yaml" in html or "render.com" in html
        has_cmd = "CMD" in html
        has_deploy = "git push" in html
        ok = all([has_dockerfile, has_render, has_cmd, has_deploy])
        marker = "OK " if ok else "FAIL"
        print(f"    {marker} Dockerfile={has_dockerfile} render={has_render} "
              f"CMD={has_cmd} deploy={has_deploy}")
        if not ok:
            failures.append("step 10 content quality check failed")
    else:
        failures.append(f"step 10 returned {code}")

    # Summary
    print("\n" + "=" * 70)
    if failures:
        print(f"RESULT: {len(failures)} FAILURE(S)")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("RESULT: ALL CHECKS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    print("Booting uvicorn on :8767 ...")
    env = os.environ.copy()
    env["PYTHONPATH"] = "/home/z/my-project"
    proc = subprocess.Popen(
        ["/home/z/.venv/bin/python", "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", "8767"],
        cwd="/home/z/my-project",
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(30):
            try:
                urllib.request.urlopen(BASE + "/health", timeout=2)
                break
            except Exception:
                time.sleep(1)
        else:
            print("SERVER FAILED TO BOOT")
            sys.exit(1)
        print("Server ready.\n")
        main()
    finally:
        proc.terminate()
        proc.wait(timeout=5)
