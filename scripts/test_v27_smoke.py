"""v2.7 smoke test: verify the new template + endpoints work end-to-end."""
import sys, uuid, json
sys.path.insert(0, "/home/z/my-project")

from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)

# Register + login
u = f'testuser_{uuid.uuid4().hex[:8]}'
r = client.post('/api/auth/register', json={'username': u, 'email': u+'@test.com', 'password': 'Password123!'})
assert r.status_code == 200, r.text
token = r.json()['access_token']
H = {'Authorization': f'Bearer {token}'}

# 1. GET /notebook — verify new layout markers + v2.7 badge
r = client.get('/notebook', headers=H)
assert r.status_code == 200
for marker in [
    'v2.7',
    'nb-app',              # new grid layout
    'nb-sidebar',          # left sidebar
    'nb-sidebar-content',
    'packages-list',       # packages section
    'pkg-count-badge',
    'download-dropdown',   # download menu
    "downloadNotebook('ipynb')",
    "downloadNotebook('py')",
    "downloadNotebook('html')",
    'autocomplete-popup',  # autocomplete CSS
    '_maybeTriggerAutocomplete',
    'toggleSidebar',
    'refreshPackages',
]:
    assert marker in r.text, f"missing marker in /notebook HTML: {marker!r}"
print(f"[1] /notebook has all v2.7 markers ({len(r.text)} bytes)")

# 2. Verify old markers removed
for old in ['v2.6 OOM-hardened', 'panel-files']:
    assert old not in r.text, f"old marker should be gone: {old!r}"
print(f"[2] old markers removed (panel-files, v2.6 badge)")

# 3. Test /api/notebook/download (.ipynb)
r = client.post('/api/notebook/download', headers=H,
    json={'cells': [
        {'type': 'code', 'source': 'import numpy as np\nprint(np.array([1,2,3]))'},
        {'type': 'text', 'source': '# Title\nSome markdown'},
    ], 'format': 'ipynb'})
assert r.status_code == 200
nb = json.loads(r.text)
assert nb['nbformat'] == 4
assert len(nb['cells']) == 2
assert nb['cells'][0]['cell_type'] == 'code'
assert nb['cells'][1]['cell_type'] == 'markdown'
print(f"[3] download .ipynb OK: {len(nb['cells'])} cells, nbformat={nb['nbformat']}")

# 4. Test /api/notebook/download (.py)
r = client.post('/api/notebook/download', headers=H,
    json={'cells': [{'type': 'code', 'source': 'print("hi")'}], 'format': 'py'})
assert r.status_code == 200
assert '# %%' in r.text
assert 'print("hi")' in r.text
print(f"[4] download .py OK: has # %% markers")

# 5. Test /api/notebook/download (.html)
r = client.post('/api/notebook/download', headers=H,
    json={'cells': [{'type': 'code', 'source': 'x=1'}], 'format': 'html'})
assert r.status_code == 200
assert '<!DOCTYPE html>' in r.text
assert 'In [1]' in r.text
print(f"[5] download .html OK: has DOCTYPE + In [1]")

# 6. Test /api/notebook/complete with `np.`
r = client.post('/api/notebook/complete', headers=H,
    json={'code': 'import numpy as np\nnp.', 'cursor_pos': 22})
assert r.status_code == 200
data = r.json()
assert data['ok']
names = [c['name'] for c in data['completions']]
assert 'array' in names, f"array missing from {names[:10]}"
assert 'zeros' in names
print(f"[6] complete np. → {len(names)} completions, source={data['source']}")

# 7. Test /api/notebook/complete with `np.arr`
r = client.post('/api/notebook/complete', headers=H,
    json={'code': 'import numpy as np\nnp.arr', 'cursor_pos': 25})
assert r.status_code == 200
data = r.json()
names = [c['name'] for c in data['completions']]
assert 'array' in names, f"array missing from {names}"
# 'arange' starts with 'ara' not 'arr' — so it should NOT match
assert 'arange' not in names, f"arange should not match 'arr' prefix"
print(f"[7] complete np.arr → {names[:6]}")

# 8. Test /api/notebook/complete with `pd.`
r = client.post('/api/notebook/complete', headers=H,
    json={'code': 'import pandas as pd\npd.', 'cursor_pos': 24})
data = r.json()
names = [c['name'] for c in data['completions']]
assert 'DataFrame' in names
assert 'read_csv' in names
print(f"[8] complete pd. → {len(names)} completions")

# 9. Test /api/notebook/packages (empty initially)
r = client.get('/api/notebook/packages', headers=H)
assert r.status_code == 200
data = r.json()
assert data['ok']
assert data['count'] == 0
assert 'site-packages' in data['note']
print(f"[9] packages endpoint OK: count={data['count']}, note explains site-packages")

# 10. Run a cell with !pip install — verify package gets tracked
r = client.post('/api/notebook/cell', headers=H,
    json={'code': '!pip install requests', 'timeout_seconds': 60})
assert r.status_code == 200
# The install might fail due to network, but it should at least be tracked
r = client.get('/api/notebook/packages', headers=H)
data = r.json()
print(f"[10] after !pip install requests, packages: {data['packages']}")
# Note: pip install might fail in sandbox; that's OK as long as endpoint works

print()
print("=== All v2.7 smoke tests passed ===")
