"""Playwright test that starts its own server."""
import asyncio
import os
import sys
import time
import random
import subprocess
import requests
from playwright.async_api import async_playwright

BASE = "http://localhost:3000"

def start_server():
    proc = subprocess.Popen(
        ["python3", "-m", "uvicorn", "app.main:app",
         "--host", "0.0.0.0", "--port", "3000", "--log-level", "warning"],
        cwd="/home/z/my-project",
        stdout=open("/tmp/obml_pw_server.log", "w"),
        stderr=subprocess.STDOUT,
    )
    for i in range(60):
        try:
            r = requests.get(f"{BASE}/health", timeout=2)
            if r.status_code == 200:
                print(f"Server ready after {i*0.5}s")
                return proc
        except Exception:
            pass
        time.sleep(0.5)
    print("Server failed to start")
    proc.terminate()
    sys.exit(1)

async def main():
    proc = start_server()
    try:
        # Register a user via API
        username = f"pwtest_{random.randint(10000, 99999)}"
        email = f"{username}@test.com"
        password = "Test1234!"
        r = requests.post(f"{BASE}/api/auth/register",
                          json={"username": username, "email": email, "password": password},
                          timeout=10)
        print(f"Register: {r.status_code}")
        assert r.status_code == 200, r.text

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            console_msgs = []
            page.on("console", lambda msg: console_msgs.append(f"[{msg.type}] {msg.text}"))
            page.on("pageerror", lambda err: console_msgs.append(f"[PAGE_ERROR] {err}"))

            print("\n=== Login via HTML form ===")
            await page.goto(f"{BASE}/login", wait_until="networkidle")
            await page.fill('input#email', email)
            await page.fill('input#password', password)
            await page.click('button[type="submit"]')
            await page.wait_for_load_state("networkidle")
            print(f"After login, URL: {page.url}")

            print("\n=== Navigate to /notebook ===")
            await page.goto(f"{BASE}/notebook", wait_until="networkidle")
            print(f"URL: {page.url}")

            await page.wait_for_timeout(1500)

            # Check editor
            editor = page.locator('.cell-editor').first
            editor_count = await editor.count()
            print(f"\n.cell-editor count: {editor_count}")

            if editor_count == 0:
                print("ERROR: No cell editor found! Page may not have booted.")
                print("Console messages:")
                for m in console_msgs:
                    print(f"  {m}")
                await page.screenshot(path="/tmp/notebook_no_editor.png")
                await browser.close()
                return

            # Type code
            print("\n=== Typing print('hello from playwright') ===")
            await editor.click()
            await editor.fill("print('hello from playwright')")
            val = await editor.input_value()
            print(f"Editor value: {val!r}")

            # Click Run
            print("\n=== Clicking Run button ===")
            run_btn = page.locator('.cell-action-btn.run-btn').first
            btn_count = await run_btn.count()
            print(f"Run button count: {btn_count}")
            if btn_count == 0:
                print("ERROR: No run button found!")
                await page.screenshot(path="/tmp/notebook_no_run_btn.png")
                print("Console messages:")
                for m in console_msgs:
                    print(f"  {m}")
                await browser.close()
                return

            await run_btn.click()

            # Wait for output
            print("\n=== Waiting for output (up to 15s) ===")
            try:
                await page.wait_for_selector('.cell-output .stream-stdout', timeout=15000)
                output_text = await page.locator('.cell-output .stream-stdout').first.text_content()
                print(f"OUTPUT: {output_text!r}")
            except Exception as e:
                print(f"ERROR waiting for output: {e}")
                await page.screenshot(path="/tmp/notebook_no_output.png")
                output_html = await page.locator('.cell-output').first.inner_html()
                print(f"Output div HTML: {output_html[:500]}")

            pill_text = await page.locator('#kernel-pill-text').text_content()
            print(f"\nKernel status: {pill_text!r}")

            print(f"\n=== Console messages ({len(console_msgs)}) ===")
            for m in console_msgs[-30:]:
                print(f"  {m}")

            # Test 2: variable persistence
            print("\n=== Test 2: Add new cell, set variable, then reference it ===")
            await page.click('button[onclick="addCodeCell()"]')
            await page.wait_for_timeout(300)
            editors = page.locator('.cell-editor')
            editor2 = editors.nth(1)
            await editor2.click()
            await editor2.fill("x = 42\nprint('x =', x)")
            run_btns = page.locator('.cell-action-btn.run-btn')
            await run_btns.nth(1).click()
            try:
                await page.wait_for_selector('.cell-output .stream-stdout', timeout=15000, state='attached')
                outputs = page.locator('.cell-output .stream-stdout')
                out_count = await outputs.count()
                if out_count >= 2:
                    text2 = await outputs.nth(1).text_content()
                    print(f"Cell 2 output: {text2!r}")
                else:
                    print(f"Only {out_count} outputs found")
            except Exception as e:
                print(f"ERROR: {e}")

            await page.screenshot(path="/tmp/notebook_final.png", full_page=True)
            print("\nFinal screenshot: /tmp/notebook_final.png")

            await browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

asyncio.run(main())
