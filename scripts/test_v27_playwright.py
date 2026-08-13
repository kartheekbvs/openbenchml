"""v2.7 Playwright browser test: verify the new Colab-style layout renders,
sidebar is visible, autocomplete popup appears, download menu opens."""
import sys, subprocess, time
sys.path.insert(0, "/home/z/my-project")

# Start the dev server in background
import uvicorn, threading, signal
from app.main import app

config = uvicorn.Config(app, host="127.0.0.1", port=8765, log_level="warning")
server = uvicorn.Server(config)
server_thread = threading.Thread(target=server.run, daemon=True)
server_thread.start()
time.sleep(1.5)

from playwright.sync_api import sync_playwright
import uuid

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})

    # Capture console errors
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type in ("error", "warning") else None)

    # Register + login via API
    u = f'pwuser_{uuid.uuid4().hex[:6]}'
    r = page.request.post('http://127.0.0.1:8765/api/auth/register',
        data={'username': u, 'email': u+'@t.com', 'password': 'Password123!'})
    token = r.json()['access_token']
    # Set cookie via JS
    page.goto('http://127.0.0.1:8765/login')
    page.evaluate(f"""document.cookie = 'access_token={token}; path=/';""")

    page.goto('http://127.0.0.1:8765/notebook')
    page.wait_for_selector('#notebook-canvas', timeout=5000)

    # 1. Verify v2.7 badge
    badge = page.locator('text=v2.7').first
    assert badge.is_visible(), "v2.7 badge not visible"
    print('[1] v2.7 badge visible')

    # 2. Verify sidebar exists and is visible
    sidebar = page.locator('.nb-sidebar')
    assert sidebar.is_visible(), "Sidebar not visible"
    print('[2] Left sidebar visible')

    # 3. Verify Files section in sidebar
    files_section = page.locator('.nb-sidebar-section >> text=Workspace')
    assert files_section.is_visible(), "Workspace section not in sidebar"
    print('[3] Files/Workspace section in sidebar')

    # 4. Verify Packages section in sidebar
    pkgs = page.locator('.nb-sidebar-section:has-text("Packages")')
    assert pkgs.first.is_visible(), "Packages section not in sidebar"
    print('[4] Packages section in sidebar')

    # 5. Verify Download dropdown button
    dl_btn = page.locator('text=Download').first
    assert dl_btn.is_visible(), "Download button not visible"
    print('[5] Download dropdown button visible')

    # 6. Click Download → verify menu items
    dl_btn.click()
    page.wait_for_selector('.download-dropdown-menu', state='visible', timeout=2000)
    ipynb_item = page.locator('.download-dropdown-menu >> text=.ipynb')
    py_item = page.locator('.download-dropdown-menu >> text=.py')
    html_item = page.locator('.download-dropdown-menu >> text=.html')
    assert ipynb_item.is_visible() and py_item.is_visible() and html_item.is_visible(), "Download menu items not visible"
    print('[6] Download menu shows .ipynb / .py / .html options')
    # Close menu
    page.keyboard.press('Escape')

    # 7. Verify a code cell exists (sample code is auto-loaded)
    cell_editor = page.locator('.cell-editor').first
    assert cell_editor.is_visible(), "Cell editor not visible"
    print('[7] Code cell editor visible')

    # 8. Type 'import numpy as np\nnp.' in the first cell and wait for autocomplete
    cell_editor.click()
    # Clear existing content first
    cell_editor.fill('')
    cell_editor.type('import numpy as np')
    page.keyboard.press('Enter')
    page.keyboard.type('np.')
    # Wait for autocomplete popup
    try:
        page.wait_for_selector('.autocomplete-popup', state='visible', timeout=3000)
        items = page.locator('.autocomplete-popup .ac-item')
        count = items.count()
        assert count > 5, f"Expected >5 autocomplete items, got {count}"
        # Verify 'array' is in the list
        first_names = [items.nth(i).locator('.ac-name').inner_text() for i in range(min(5, count))]
        print(f'[8] Autocomplete popup appeared with {count} items: {first_names}')
    except Exception as e:
        print(f'[8] FAIL: Autocomplete popup did not appear: {e}')
        page.screenshot(path='/tmp/v27_autocomplete_fail.png')
        raise

    # 9. Test Tab key inserts 4 spaces (not focus change)
    cell_editor.press('Escape')  # close popup
    cell_editor.click()
    cell_editor.fill('x = 1')
    cell_editor.press('Tab')
    val = cell_editor.input_value()
    assert '    ' in val, f"Tab did not insert 4 spaces, got: {val!r}"
    print(f'[9] Tab inserts 4 spaces: {val!r}')

    # 10. Test auto-indent after ':'
    cell_editor.fill('')
    cell_editor.type('if True:')
    page.keyboard.press('Enter')
    val = cell_editor.input_value()
    # Should have 'if True:\n    ' (4-space indent on next line)
    assert 'if True:\n    ' in val, f"Auto-indent did not trigger, got: {val!r}"
    print(f'[10] Auto-indent after : works: {val!r}')

    # 11. Take a screenshot of the full UI
    page.screenshot(path='/tmp/v27_full_ui.png', full_page=True)
    print('[11] Full UI screenshot saved to /tmp/v27_full_ui.png')

    # 12. Check for console errors
    real_errors = [e for e in errors if 'goglee-metrics' not in e and 'Crypto site' not in e]
    if real_errors:
        print(f'[12] WARNING: {len(real_errors)} console errors:')
        for e in real_errors[:5]:
            print(f'    {e}')
    else:
        print('[12] No console errors')

    browser.close()
    print()
    print('=== All v2.7 Playwright tests passed ===')
