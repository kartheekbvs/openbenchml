"""Playwright test: verify the Files tab renders and upload works in a browser."""
import asyncio, os, sys, time, random, subprocess, requests
from playwright.async_api import async_playwright

BASE = "http://localhost:3000"

def start_server():
    proc = subprocess.Popen(
        ["python3", "-m", "uvicorn", "app.main:app",
         "--host", "0.0.0.0", "--port", "3000", "--log-level", "warning"],
        cwd="/home/z/my-project",
        stdout=open("/tmp/obml_files_pw.log", "w"),
        stderr=subprocess.STDOUT,
    )
    for i in range(60):
        try:
            r = requests.get(f"{BASE}/health", timeout=2)
            if r.status_code == 200:
                return proc
        except Exception:
            pass
        time.sleep(0.5)
    proc.terminate()
    sys.exit(1)

async def main():
    proc = start_server()
    try:
        username = f"pwfiles_{random.randint(10000, 99999)}"
        email = f"{username}@test.com"
        password = "Test1234!"
        requests.post(f"{BASE}/api/auth/register",
                      json={"username": username, "email": email, "password": password},
                      timeout=10)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            console_msgs = []
            page.on("console", lambda msg: console_msgs.append(f"[{msg.type}] {msg.text}"))
            page.on("pageerror", lambda err: console_msgs.append(f"[PAGE_ERROR] {err}"))

            print("=== Login ===")
            await page.goto(f"{BASE}/login", wait_until="networkidle")
            await page.fill('input#email', email)
            await page.fill('input#password', password)
            await page.click('button[type="submit"]')
            await page.wait_for_load_state("networkidle")

            print("=== Go to /notebook ===")
            await page.goto(f"{BASE}/notebook", wait_until="networkidle")
            await page.wait_for_timeout(800)

            # Verify version badge
            badge = await page.locator('h1 span').first.text_content()
            print(f"Version badge: {badge!r}")
            assert 'v2.5' in badge, f"wrong version badge: {badge}"

            # Verify all 3 tabs exist
            tabs = await page.locator('.view-tab').all_text_contents()
            print(f"Tabs: {tabs}")
            assert any('Notebook' in t for t in tabs)
            assert any('Files' in t for t in tabs)
            assert any('Terminal' in t for t in tabs)

            print("=== Click Files tab ===")
            await page.click('#tab-files')
            await page.wait_for_timeout(800)

            # Verify the Files panel is visible
            panel = page.locator('#panel-files')
            is_visible = await panel.is_visible()
            print(f"Files panel visible: {is_visible}")
            assert is_visible, "Files panel not visible after click"

            # Verify drop zone exists
            drop_zone = page.locator('#files-drop-zone')
            dz_count = await drop_zone.count()
            print(f"Drop zone count: {dz_count}")
            assert dz_count == 1

            # Verify hint banner mentions git clone
            hint = await page.locator('.file-hint-banner').first.text_content()
            print(f"Hint banner (first 100 chars): {hint[:100]!r}")
            assert 'git clone' in hint.lower(), "hint banner missing git clone mention"
            assert 'GLM-5.2' in hint, "hint banner missing GLM-5.2 example"

            # Verify empty state OR file list shows
            list_html = await page.locator('#files-list').first.inner_html()
            print(f"Files list HTML (first 200): {list_html[:200]!r}")

            # Upload a CSV file via the file input
            print("=== Upload test.csv via input ===")
            csv_path = '/tmp/pw_test_upload.csv'
            with open(csv_path, 'w') as f:
                f.write("name,age\nAlice,30\nBob,25\n")

            await page.set_input_files('#file-input', csv_path)
            await page.wait_for_timeout(2000)

            # Verify the file appears in the list
            await page.wait_for_selector('.file-row .file-name:has-text("pw_test_upload.csv")', timeout=5000)
            file_name = await page.locator('.file-row .file-name').first.text_content()
            print(f"First file in list: {file_name!r}")
            assert 'pw_test_upload.csv' in file_name, f"uploaded file not in list: {file_name}"

            # Click the insert-hint button (clipboard icon)
            print("=== Click insert-code button ===")
            insert_btn = page.locator('.file-row .files-actions-btn[title="Insert code snippet in last cell"]').first
            await insert_btn.click()
            await page.wait_for_timeout(500)

            # Verify we're back on the notebook view with a code snippet
            notebook_panel = page.locator('#panel-notebook')
            is_visible_nb = await notebook_panel.is_visible()
            print(f"Notebook panel visible after insert: {is_visible_nb}")

            # Find the editor with the inserted snippet
            editors = page.locator('.cell-editor')
            editor_count = await editors.count()
            print(f"Cell editors: {editor_count}")
            last_editor = editors.nth(editor_count - 1)
            last_val = await last_editor.input_value()
            print(f"Last editor value: {last_val!r}")
            assert 'pd.read_csv' in last_val, f"snippet not inserted: {last_val}"

            # Run the cell
            print("=== Run the inserted cell ===")
            run_btns = page.locator('.cell-action-btn.run-btn')
            await run_btns.nth(editor_count - 1).click()
            await page.wait_for_timeout(3000)

            # Verify output
            try:
                await page.wait_for_selector('.cell-output .stream-stdout', timeout=10000)
                output = await page.locator('.cell-output .stream-stdout').last.text_content()
                print(f"Cell output: {output!r}")
                assert 'Alice' in output or '(2, 2)' in output, f"output doesn't show CSV data: {output}"
                print("✓ Uploaded CSV was read successfully in a cell!")
            except Exception as e:
                print(f"ERROR waiting for output: {e}")
                output_html = await page.locator('.cell-output').last.inner_html()
                print(f"Output HTML: {output_html[:500]}")

            # Take a screenshot
            await page.screenshot(path="/tmp/notebook_files_v25.png", full_page=True)
            print(f"\nFinal screenshot: /tmp/notebook_files_v25.png")

            print(f"\n=== Console messages ({len(console_msgs)}) ===")
            for m in console_msgs[-15:]:
                print(f"  {m}")

            await browser.close()
    finally:
        proc.terminate()
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired: proc.kill()

asyncio.run(main())
