"""Quick screenshot of just the Files tab in its initial state."""
import asyncio, sys, time, random, subprocess, requests
from playwright.async_api import async_playwright

BASE = "http://localhost:3000"

def start_server():
    proc = subprocess.Popen(
        ["python3", "-m", "uvicorn", "app.main:app",
         "--host", "0.0.0.0", "--port", "3000", "--log-level", "warning"],
        cwd="/home/z/my-project",
        stdout=open("/tmp/obml_files_screen.log", "w"),
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
        username = f"pwscreen_{random.randint(10000, 99999)}"
        email = f"{username}@test.com"
        password = "Test1234!"
        requests.post(f"{BASE}/api/auth/register",
                      json={"username": username, "email": email, "password": password},
                      timeout=10)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(viewport={'width': 1400, 'height': 900})
            page = await context.new_page()

            await page.goto(f"{BASE}/login", wait_until="networkidle")
            await page.fill('input#email', email)
            await page.fill('input#password', password)
            await page.click('button[type="submit"]')
            await page.wait_for_load_state("networkidle")

            await page.goto(f"{BASE}/notebook", wait_until="networkidle")
            await page.wait_for_timeout(800)

            # Upload a file first
            csv_path = '/tmp/screen_demo.csv'
            with open(csv_path, 'w') as f:
                f.write("product,sales,region\nWidget,1500,North\nGadget,2300,South\nGizmo,1800,East\n")
            await page.set_input_files('#file-input', csv_path)
            await page.wait_for_timeout(1500)

            # Now switch to Files tab and screenshot
            await page.click('#tab-files')
            await page.wait_for_timeout(1500)
            await page.screenshot(path="/tmp/notebook_files_tab.png", full_page=False)
            print("Screenshot saved: /tmp/notebook_files_tab.png")

            await browser.close()
    finally:
        proc.terminate()
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired: proc.kill()

asyncio.run(main())
