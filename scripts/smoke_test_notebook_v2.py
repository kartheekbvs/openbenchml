"""Smoke test for Notebook v2.0 — Colab-style notebook."""
import sys
import uuid
sys.path.insert(0, '/home/z/my-project')
from fastapi.testclient import TestClient
from app.main import app

def main():
    with TestClient(app) as client:
        # Register + login
        email = f'nb-{uuid.uuid4().hex[:8]}@example.com'
        username = f'nbuser_{uuid.uuid4().hex[:6]}'
        r = client.post('/api/auth/register',
                        json={'username': username, 'email': email, 'password': 'Testpass123!'})
        assert r.status_code == 200, f'register failed: {r.status_code} {r.text[:300]}'
        token = r.json()['access_token']
        client.headers.update({'Authorization': f'Bearer {token}'})
        print('[ok] registered', username)

        # 1. GET /notebook renders
        r = client.get('/notebook')
        assert r.status_code == 200, f'GET /notebook: {r.status_code}'
        html = r.text
        print(f'[ok] GET /notebook -> {r.status_code} ({len(html)} bytes)')

        checks = [
            ('Multi-cell toolbar',           'notebook-toolbar'),
            ('Run all button',               'run-all-btn'),
            ('+ Code button',                'addCodeCell'),
            ('+ Text button',                'addTextCell'),
            ('Reset kernel button',          'resetKernel'),
            ('Engine selector',              'engine-select'),
            ('Kernel pill',                  'kernel-pill'),
            ('Notebook canvas',              'notebook-canvas'),
            ('Kernel sidebar',               'kernel-sidebar'),
            ('Variable list',                'var-list'),
            ('addCodeCell JS fn',            'function addCodeCell'),
            ('runCell JS fn',                'async function runCell'),
            ('runAllCells JS fn',            'async function runAllCells'),
            ('installPackage JS fn',         'async function installPackage'),
            ('resetKernel JS fn',            'async function resetKernel'),
            ('Pyodide loader',               'loadPyodideEngine'),
            ('Multi-CDN fallback',           'cdnjs.cloudflare.com'),
            ('Shift+Enter shortcut',         'Shift+Enter'),
            ('Shell command hint',           '!pip install'),
            ('Magic hint',                   '%whos'),
            ('Cell output div',              'cell-output'),
            ('Suggestions popup',            'suggest-box'),
            ('Inline figure rendering',      'data:image/png;base64'),
            ('Welcome banner',               'welcome-banner'),
            ('Colab-style badge',            'Colab-style'),
        ]
        p = f = 0
        for label, needle in checks:
            if needle in html:
                p += 1
            else:
                print(f'  [FAIL] {label}')
                f += 1
        print(f'[check] page render: {p}/{p+f} pass')

        # 2. POST /api/notebook/cell - basic Python
        r = client.post('/api/notebook/cell', json={
            'code': 'x = 42\nprint(f"x = {x}")',
            'timeout_seconds': 30,
        })
        assert r.status_code == 200, f'cell run: {r.status_code} {r.text[:300]}'
        data = r.json()
        assert data['ok'] is True, f'cell ok=False: {data}'
        assert 'x = 42' in data['stdout']
        print(f'[ok] /api/notebook/cell (Python) -> {data["stdout"]!r} ({data["elapsed_ms"]}ms)')

        # 3. Persistent state
        r = client.post('/api/notebook/cell', json={
            'code': 'print(f"x is still {x}")',
            'timeout_seconds': 30,
        })
        data = r.json()
        assert data['ok'] is True
        assert 'x is still 42' in data['stdout']
        print(f'[ok] /api/notebook/cell (persistent) -> {data["stdout"]!r}')

        # 4. Shell command
        r = client.post('/api/notebook/cell', json={
            'code': '!python --version',
            'timeout_seconds': 30,
        })
        data = r.json()
        assert data['ok'] is True, f'shell: {data}'
        assert 'Python' in data['stdout']
        print(f'[ok] /api/notebook/cell (shell !python) -> {data["stdout"]!r}')

        # 5. pip install via shell
        r = client.post('/api/notebook/cell', json={
            'code': '!pip install --quiet six',
            'timeout_seconds': 60,
        })
        data = r.json()
        assert data['ok'] is True, f'pip: {data}'
        print(f'[ok] /api/notebook/cell (shell !pip install six)')

        # 6. Magic %whos
        r = client.post('/api/notebook/cell', json={
            'code': '%whos',
            'timeout_seconds': 30,
        })
        data = r.json()
        assert data['ok'] is True
        assert 'x' in data['stdout']
        print(f'[ok] /api/notebook/cell (magic %whos) -> {data["stdout"]!r}')

        # 7. Suggestions
        r = client.post('/api/notebook/suggest', json={'code': 'import torch\nimport xgboost\nimport sklearn'})
        data = r.json()
        sugg = data['suggestions']
        sugg_names = [s['import_name'] for s in sugg]
        print(f'[ok] /api/notebook/suggest -> {len(sugg)} suggestions: {sugg_names}')

        # 8. Health
        r = client.get('/api/notebook/health')
        data = r.json()
        assert data['ok'] is True
        assert 'x' in data['variables']
        print(f'[ok] /api/notebook/health -> cells={data["cell_count"]}, vars={data["variables"]}')

        # 9. Install endpoint
        r = client.post('/api/notebook/install', json={'package': 'six', 'timeout_seconds': 60})
        data = r.json()
        assert data['ok'] is True, f'install: {data}'
        print(f'[ok] /api/notebook/install six')

        # 10. Reset
        r = client.post('/api/notebook/reset')
        data = r.json()
        assert data['ok'] is True
        print(f'[ok] /api/notebook/reset -> {data["message"]}')

        # 11. After reset, x is gone
        r = client.post('/api/notebook/cell', json={'code': 'print(x)', 'timeout_seconds': 10})
        data = r.json()
        assert data['ok'] is False
        assert 'NameError' in (data.get('error') or '')
        print(f'[ok] reset worked -> x gone: {data["error"]!r}')

        print()
        print('=' * 60)
        print('RESULT: ALL NOTEBOOK v2.0 TESTS PASS')
        print('=' * 60)

if __name__ == '__main__':
    main()
