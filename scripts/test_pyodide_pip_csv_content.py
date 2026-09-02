"""
Smoke-test the new Colab-style fixes:
  1. Pyodide pandas.read_csv patch supports local-name fallback to /api/notebook/files/
  2. Pyodide open() patch supports local-name fallback
  3. _pyodidePipInstall + _pyodidePipList JS helpers exist
  4. _syncServerFilesToPyodide JS helper exists
  5. uploadFiles() mirrors uploaded file to Pyodide FS
  6. /content/<path> route registered in app/routes/notebook.py
  7. file row renders an <a href="/content/..."> link
  8. CSS no longer uses white-space: nowrap on .file-name (so full name shows)
"""
import re, ast, sys, pathlib

ROOT = pathlib.Path('/home/z/my-project')
NB_HTML = (ROOT / 'templates/notebook.html').read_text()
NB_PY = (ROOT / 'app/routes/notebook.py').read_text()

def _try_parse(src):
    try:
        ast.parse(src)
        return True
    except SyntaxError as e:
        return f"SyntaxError: {e}"

results = []
def check(label, cond, detail=''):
    results.append((label, cond, detail))
    print(f"  {'OK' if cond else 'FAIL'}  {label}" + (f"  ({detail})" if detail and not cond else ""))

print("\n[1] Pyodide read_csv patch supports local-name fallback")
check(
    "read_csv tries /api/notebook/files/ when file not in FS",
    "/api/notebook/files/" in NB_HTML and "_obml_srv_bytes = _obml_fetch_bytes_sync" in NB_HTML,
)
check(
    "read_csv patch prints 'server-side files' banner",
    "HTTPS URLs + server-side files" in NB_HTML,
)

print("\n[2] Pyodide open() patch")
check(
    "open() patched with _obml_open fallback",
    "_obml_orig_open = open" in NB_HTML and "_obml_builtins.open = _obml_open" in NB_HTML,
)
check(
    "open() patch prints banner",
    "Patched open() to fall back to server workspace files" in NB_HTML,
)

print("\n[3] _pyodidePipInstall / _pyodidePipList helpers")
check(
    "_pyodidePipInstall function defined",
    "async function _pyodidePipInstall(pkgSpec)" in NB_HTML,
)
check(
    "_pyodidePipList function defined",
    "async function _pyodidePipList(args)" in NB_HTML,
)
check(
    "pip regex recognises pip / pip3 / !pip / %pip / python -m pip",
    all(p in NB_HTML for p in ["pip3?", "%pip|", "python\\s+-m\\s+pip"]),
)

print("\n[4] _syncServerFilesToPyodide + upload mirrors")
check(
    "_syncServerFilesToPyodide function defined",
    "async function _syncServerFilesToPyodide()" in NB_HTML,
)
check(
    "loadPyodideEngine calls _syncServerFilesToPyodide on boot",
    "await _syncServerFilesToPyodide()" in NB_HTML,
)
check(
    "uploadFiles writes to /workspace/datasets/user/ via FS.writeFile",
    "/workspace/datasets/user/' + file.name" in NB_HTML and "FS.writeFile" in NB_HTML,
)

print("\n[5] /content/<path> route registered server-side")
check(
    "notebook.py defines /content/{path:path} route",
    '@router.get("/content/{path:path}")' in NB_PY,
)
check(
    "route handler uses Content-Disposition: inline",
    "Content-Disposition" in NB_PY and 'inline' in NB_PY,
)
check(
    "notebook.py parses cleanly",
    _try_parse(NB_PY),
)

print("\n[6] File row UI shows Colab-style link")
check(
    "_renderFileRow renders <a href='/content/...'> link",
    'href="/content/${encodeURIComponent(f.path)}"' in NB_HTML,
)
check(
    "_renderChildRow also has /content/ link",
    'href="/content/${encodeURIComponent(c.path)}"' in NB_HTML,
)
check(
    "upload success row has /content/ link too",
    'href="/content/${encodeURIComponent(data.path' in NB_HTML,
)

print("\n[7] File name CSS shows full name (no nowrap truncation)")
file_name_css = re.search(r'\.files-list \.file-row \.file-name \{[^}]+\}', NB_HTML, re.DOTALL)
check(
    "file-name CSS rule exists",
    file_name_css is not None,
)
if file_name_css:
    css = file_name_css.group(0)
    check(
        "no white-space: nowrap in file-name rule",
        'white-space: nowrap' not in css,
        f"found nowrap in: {css!r}",
    )
    check(
        "uses word-break: break-all",
        'word-break: break-all' in css,
    )

print("\n[8] insertFileHint surfaces /content/ link in code comment")
check(
    "csv hint has /content/ comment",
    "# Loaded from /content/" in NB_HTML,
)

passed = sum(1 for _, c, _ in results if c)
failed = len(results) - passed
print(f"\n{'='*70}\nPASSED: {passed}    FAILED: {failed}\n{'='*70}")
sys.exit(0 if failed == 0 else 1)
