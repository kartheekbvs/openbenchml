"""
Playwright end-to-end test for the /convert page that reproduces the
user's "Training failed after 11.1s" error on `fetch_california_housing`.

Goal:
  - Load the /convert page
  - Select the 'cali-rf' preset (California Housing RandomForest)
  - Wait for the Pyodide kernel to be ready
  - Click the Train button
  - Capture the FULL live output (the alert message truncates at 400
    chars with "…(see live output for full traceback)" — we want what's
    AFTER that truncation, which is in the #live-output div).
  - Capture the alert banner text too.
  - Print everything so we can see the actual underlying error.

This test is INTENTIONALLY run with a 240s timeout because Pyodide
training of the California Housing dataset takes ~10-30s.
"""
import asyncio
import os
import sys
import time
import random
import subprocess
import requests
from playwright.async_api import async_playwright

BASE = "http://localhost:3042"

def start_server():
    proc = subprocess.Popen(
        ["/home/z/.venv/bin/python", "-m", "uvicorn", "app.main:app",
         "--host", "0.0.0.0", "--port", "3042", "--log-level", "warning"],
        cwd="/home/z/my-project",
        stdout=open("/tmp/obml_convert_cali.log", "w"),
        stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONDONTWRITEBYTECODE": "1"},
    )
    for i in range(60):
        try:
            r = requests.get(f"{BASE}/health", timeout=2)
            if r.status_code == 200:
                print(f"  server ready after {i*0.5}s")
                return proc
        except Exception:
            pass
        time.sleep(0.5)
    print("  server failed to start")
    proc.terminate()
    sys.exit(1)


async def main():
    proc = start_server()
    try:
        # Register + login a user
        username = f"pwcali_{random.randint(10000, 99999)}"
        email = f"{username}@test.com"
        password = "Test1234!"
        r = requests.post(f"{BASE}/api/auth/register",
                          json={"username": username, "email": email, "password": password},
                          timeout=10)
        print(f"  register: {r.status_code}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            console_msgs = []
            page.on("console", lambda msg: console_msgs.append(f"[{msg.type}] {msg.text}"))
            page.on("pageerror", lambda err: console_msgs.append(f"[PAGE_ERROR] {err}"))

            # Login
            await page.goto(f"{BASE}/login", wait_until="networkidle")
            await page.fill('input#email', email)
            await page.fill('input#password', password)
            await page.click('button[type="submit"]')
            await page.wait_for_load_state("networkidle")
            print(f"  logged in, url: {page.url}")

            # Go to /convert
            await page.goto(f"{BASE}/convert", wait_until="networkidle")
            print(f"  on convert page: {page.url}")

            # Wait for Pyodide to be ready (look for kernel: ready status)
            print("  waiting for Pyodide to be ready (up to 180s)…")
            for i in range(360):
                try:
                    pill = await page.locator('#kernel-status').text_content(timeout=2000)
                except Exception:
                    pill = ""
                if pill and "ready" in pill.lower():
                    print(f"  pyodide ready after ~{i*0.5}s — status: {pill}")
                    break
                if pill and "failed" in pill.lower():
                    print(f"  PYODIDE FAILED after ~{i*0.5}s — status: {pill}")
                    break
                await asyncio.sleep(0.5)
            else:
                print("  TIMEOUT waiting for Pyodide ready")

            # Load the cali-rf preset by clicking the chip button
            print("  clicking cali-rf preset chip…")
            await page.click('button.preset-chip[onclick*="cali-rf"]')
            await page.wait_for_timeout(300)
            code_in_editor = await page.locator('textarea#code').input_value()
            print(f"  code in editor (first 200 chars): {code_in_editor[:200]!r}")
            if "fetch_california_housing" not in code_in_editor:
                # Inject the code directly
                print("  preset didn't load — injecting code directly…")
                await page.fill('textarea#code',
                    "from sklearn.datasets import fetch_california_housing\n"
                    "from sklearn.ensemble import RandomForestRegressor\n"
                    "from sklearn.model_selection import train_test_split\n"
                    "from sklearn.metrics import mean_squared_error, r2_score\n"
                    "import numpy as np\n"
                    "print('Loading California Housing dataset...')\n"
                    "X, y = fetch_california_housing(return_X_y=True)\n"
                    "print(f'  X shape: {X.shape}, y shape: {y.shape}')\n"
                    "X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)\n"
                    "print('Training Random Forest Regressor (n_estimators=100)...')\n"
                    "model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=1)\n"
                    "model.fit(X_train, y_train)\n"
                    "y_pred = model.predict(X_test)\n"
                    "rmse = np.sqrt(mean_squared_error(y_test, y_pred))\n"
                    "r2 = r2_score(y_test, y_pred)\n"
                    "print(f'RMSE: {rmse:.4f}')\n"
                    "print(f'R2:   {r2:.4f}')\n"
                    "print('Done — model trained.')\n"
                )

            # Click train
            print("  clicking train button…")
            train_btn = page.locator('#train-btn')
            await train_btn.click()

            # Wait up to 180s for the train button to be re-enabled
            # (i.e., the training either succeeded or failed)
            print("  waiting for training to finish (up to 180s)…")
            for i in range(360):
                disabled = await train_btn.get_attribute('disabled')
                if disabled is None:
                    print(f"  training finished after ~{i*0.5}s")
                    break
                await asyncio.sleep(0.5)
            else:
                print("  training still running after 180s")

            # Capture the full live output (not truncated)
            live_output = await page.locator('#live-output').inner_text()
            print("\n" + "=" * 70)
            print("FULL LIVE OUTPUT (not truncated):")
            print("=" * 70)
            print(live_output)
            print("=" * 70)

            # Also capture any alert banner
            alert_text = await page.locator('.alert').all_text_contents()
            if alert_text:
                print("\nALERT BANNERS:")
                for i, a in enumerate(alert_text):
                    print(f"  [{i}]: {a}")

            # Print last 30 console messages
            print(f"\n=== console messages ({len(console_msgs)} total, last 30) ===")
            for m in console_msgs[-30:]:
                print(f"  {m}")

            await page.screenshot(path="/tmp/convert_cali_final.png", full_page=True)
            print("\n  screenshot: /tmp/convert_cali_final.png")

            await browser.close()
    finally:
        proc.terminate()


if __name__ == "__main__":
    asyncio.run(main())
