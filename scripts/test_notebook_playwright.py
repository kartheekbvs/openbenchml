"""Playwright-based browser test of the notebook.

Actually loads /notebook in a real browser, logs in, clicks the Run button,
and verifies output appears. Captures console errors and screenshots.
"""
import asyncio
import random
import requests
from playwright.async_api import async_playwright

BASE = "http://localhost:3000"

async def main():
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

        # Collect console messages
        console_msgs = []
        page.on("console", lambda msg: console_msgs.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: console_msgs.append(f"[PAGE_ERROR] {err}"))

        # Login via HTML form (sets cookie)
        print("\n=== Navigating to /login ===")
        await page.goto(f"{BASE}/login", wait_until="networkidle")
        await page.fill('input#email', email)
        await page.fill('input#password', password)
        await page.click('button[type="submit"]')
        await page.wait_for_load_state("networkidle")
        print(f"After login, URL: {page.url}")

        # Go to notebook
        print("\n=== Navigating to /notebook ===")
        await page.goto(f"{BASE}/notebook", wait_until="networkidle")
        print(f"URL: {page.url}")
        print(f"Title: {await page.title()}")

        # Wait a moment for JS to boot
        await page.wait_for_timeout(1500)

        # Check that the first cell's editor exists
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

        # Clear the editor and type print('hello')
        print("\n=== Typing print('hello from playwright') into first cell ===")
        await editor.click()
        await editor.fill("print('hello from playwright')")

        # Verify the textarea has the value
        val = await editor.input_value()
        print(f"Editor value: {val!r}")

        # Click the Run button on the first cell
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

        # Wait for output to appear
        print("\n=== Waiting for output (up to 15s) ===")
        try:
            await page.wait_for_selector('.cell-output .stream-stdout', timeout=15000)
            output_text = await page.locator('.cell-output .stream-stdout').first.text_content()
            print(f"OUTPUT: {output_text!r}")
        except Exception as e:
            print(f"ERROR waiting for output: {e}")
            await page.screenshot(path="/tmp/notebook_no_output.png")
            # Get the output div content anyway
            output_html = await page.locator('.cell-output').first.inner_html()
            print(f"Output div HTML: {output_html[:500]}")

        # Check kernel status pill
        pill_text = await page.locator('#kernel-pill-text').text_content()
        print(f"\nKernel status: {pill_text!r}")

        # Print all console messages
        print(f"\n=== Console messages ({len(console_msgs)}) ===")
        for m in console_msgs[-20:]:
            print(f"  {m}")

        # Take a final screenshot
        await page.screenshot(path="/tmp/notebook_final.png", full_page=True)
        print("\nFinal screenshot: /tmp/notebook_final.png")

        await browser.close()

asyncio.run(main())
