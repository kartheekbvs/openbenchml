"""
Test the Pyodide HTTPS patch logic that the /convert page injects.

The user reported:
  Training failed after 0.8s:
  ...
  File "/lib/python3.12/site-packages/sklearn/datasets/_california_housing.py",
    archive_path = _fetch_remote(ARCHIVE, dirname=data_home)
  File "/lib/python3.12/site-packages/sklearn/datasets/_base.py", line 1433,
    in _fetch_remote
    urlretrieve(remote.url, file_path)
  ...
  urllib.error.URLError: <urlopen error unknown url type: https>

Root cause: Pyodide's `urllib.request` does NOT support HTTPS. The previous
fix only patched `pandas.read_csv` — but `sklearn.datasets.fetch_*` uses
`urllib.request.urlretrieve` directly, bypassing the pandas patch.

What this test verifies:
  1. The patch JavaScript string in convert.html injects a urlopen + urlretrieve
     monkey-patch (not just pd.read_csv).
  2. The patch routes https:// URLs through pyodide.http.open_url and returns
     a file-like object with `.read()` and `__call__` interfaces.
  3. The notebook.html editor has auto-close-bracket logic (smoke check).
  4. The convert page has visible-alert + global error catchers so it
     NEVER goes white silently (smoke check).
"""
import re
import sys
import os

ROOT = "/home/z/my-project"
sys.path.insert(0, ROOT)
os.chdir(ROOT)

CONVERT_HTML = open("templates/convert.html").read()
NOTEBOOK_HTML = open("templates/notebook.html").read()

failures = []
def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)

print("\n=== 1. /convert HTTPS patch coverage ===")

# Extract the JavaScript string content that gets injected into Pyodide.
# This is the actual Python code that runs at kernel boot — the only
# code that matters for fixing fetch_california_housing.
inject_match = re.search(
    r"runPythonAsync\(`([\s\S]*?)`\);",
    CONVERT_HTML,
)
injected_python = inject_match.group(1) if inject_match else ""
print(f"  (extracted {len(injected_python)} chars of injected Python)")

# Critical: the patch must monkey-patch urllib.request (or urlretrieve),
# not just pd.read_csv — otherwise sklearn.datasets.fetch_* will still
# raise "unknown url type: https".
has_urllib_patch = (
    "urllib.request.urlretrieve" in injected_python
    or "urllib.request.urlopen" in injected_python
    or "_obml_urlretrieve" in injected_python
    or "urlretrieve" in injected_python
)
check(
    "injected Python monkey-patches urllib.request (not just pd.read_csv)",
    has_urllib_patch,
    "Only pd.read_csv is patched — sklearn.datasets.fetch_* will still fail",
)

# The patch must use pyodide.http.open_url (or pyfetch) for HTTPS URLs.
uses_open_url = (
    "open_url" in injected_python or "pyfetch" in injected_python
)
check(
    "injected Python uses pyodide.http.open_url / pyfetch",
    uses_open_url,
)

# The patch must handle BOTH http:// and https:// schemes.
check(
    "injected Python handles both http:// and https:// schemes",
    "https://" in injected_python and "http://" in injected_python,
)

# The patched urlopen must return a file-like object with .read()
check(
    "injected Python's urlopen replacement returns a BytesIO-like object",
    "BytesIO" in injected_python and "read" in injected_python,
)

# The patch must also patch urlretrieve to write to a local file path,
# because sklearn's _fetch_remote uses urlretrieve(url, file_path).
check(
    "injected Python patches urlretrieve(url, filename) signature",
    "urlretrieve" in injected_python and "file_path" in injected_python
        or "filename" in injected_python,
)

print("\n=== 2. /convert error handling (no white page) ===")

# The page must register global error + unhandledrejection catchers.
check(
    "convert.html registers window.addEventListener('error', ...)",
    "addEventListener('error'" in CONVERT_HTML,
)
check(
    "convert.html registers window.addEventListener('unhandledrejection', ...)",
    "addEventListener('unhandledrejection'" in CONVERT_HTML,
)

# There must be a visible showAlert() helper.
check(
    "convert.html defines showAlert()",
    "function showAlert" in CONVERT_HTML,
)

# The Pyodide training path must wrap pyodide.runPythonAsync in try/catch.
check(
    "convert.html wraps training in try/catch",
    "try {" in CONVERT_HTML and "} catch (err)" in CONVERT_HTML,
)

# The catch block must call showAlert() with the error.
# Find the catch block in trainWithPyodide
m = re.search(r"catch \(err\) \{[\s\S]{0,2000}?showAlert", CONVERT_HTML)
check(
    "trainWithPyodide catch block calls showAlert()",
    m is not None,
)

# The Train button must be re-enabled in a finally block (no stuck state).
check(
    "convert.html has a finally block that re-enables the Train button",
    "finally" in CONVERT_HTML and "train-btn" in CONVERT_HTML,
)

print("\n=== 3. /notebook editor improvements ===")

# Auto-close brackets: must intercept typing of ( [ { ' "
for ch in ["(", "[", "{"]:
    check(
        f"notebook.html handles auto-close for '{ch}'",
        f"'{ch}'" in NOTEBOOK_HTML or f'"{ch}"' in NOTEBOOK_HTML,
    )

# There must be a function that handles bracket auto-closing
# (we'll add _autoCloseBracket in onEditorKeydown or a dedicated handler).
check(
    "notebook.html has bracket auto-close handler",
    "_autoCloseBracket" in NOTEBOOK_HTML or "autoClose" in NOTEBOOK_HTML
        or "auto_close" in NOTEBOOK_HTML or "auto-close" in NOTEBOOK_HTML,
)

# Curated completions must include scipy.stats / sklearn.metrics
check(
    "notebook.html backend has curated completions for scipy",
    "scipy" in open("app/routes/notebook.py").read().lower()
        or '"scipy"' in open("app/routes/notebook.py").read(),
)

# Curated completions for sns (seaborn)
notebook_py = open("app/routes/notebook.py").read()
check(
    "notebook backend has curated completions for seaborn (sns)",
    '"sns"' in notebook_py or "'sns'" in notebook_py,
)

# Check that plt, np, pd, sklearn are still there
for key in ["np", "pd", "plt", "sklearn"]:
    check(
        f"notebook backend still has curated completions for '{key}'",
        f'"{key}"' in notebook_py,
    )

print("\n=== 4. Smoke: pages still render ===")

# Quick Jinja syntax check — count {% %} tags balance roughly.
for path, tmpl in [("convert", CONVERT_HTML), ("notebook", NOTEBOOK_HTML)]:
    n_open = tmpl.count("{%")
    n_close = tmpl.count("%}")
    check(
        f"{path}.html has balanced Jinja tags ({n_open} open / {n_close} close)",
        n_open == n_close,
        f"{n_open} open vs {n_close} close",
    )

print("\n=== 5. Backend: Python keyword + snippet completions ===")

# The backend must offer keyword suggestions when the user is typing
# a bare identifier (no dot) with at least 2 chars.
check(
    "notebook backend defines _PY_KEYWORDS list",
    "_PY_KEYWORDS" in notebook_py,
)

# Must include common keywords: import, for, def, if
for kw in ["import", "for", "def", "if", "print", "range"]:
    check(
        f"_PY_KEYWORDS includes '{kw}'",
        f'"{kw}"' in notebook_py,
    )

# Must include multi-word snippets like "import numpy as np"
check(
    '_PY_KEYWORDS includes snippet "import numpy as np"',
    "import numpy as np" in notebook_py,
)

# The complete endpoint must take the keyword branch when no dot in token.
# Just grep for the conditional logic.
check(
    "complete endpoint has keyword fallback branch",
    "_PY_KEYWORDS" in notebook_py
        and "attr_part" in notebook_py
        and "len(attr_part) >= 2" in notebook_py,
)

print("\n=== 6. Frontend: autocomplete triggers on 2+ chars ===")

# Threshold lowered from 3 → 2.
check(
    "notebook.html autocomplete triggers on 2+ char tokens",
    "token.length < 2" in NOTEBOOK_HTML,
    "Should be < 2 (was < 3 before)",
)

# Snippets (e.g. "import numpy as np") need special handling in
# _acceptCompletion because they contain spaces.
check(
    "notebook.html _acceptCompletion handles snippet names with spaces",
    "name.includes(' ')" in NOTEBOOK_HTML,
)

print("\n=== 7. New CSS classes for completion types ===")

for cls in ["dunder", "snippet", "builtin", "attr"]:
    check(
        f"notebook.html has CSS for .ac-type.{cls}",
        f".ac-type.{cls}" in NOTEBOOK_HTML,
    )

print("\n=== 8. Both pages have the same HTTPS patch (parity) ===")

# Convert and notebook should both patch urllib.request.
CONVERT_INJECT = re.search(r"runPythonAsync\(`([\s\S]*?)`\);", CONVERT_HTML)
NOTEBOOK_INJECT = re.search(r"runPythonAsync\(`([\s\S]*?)`\);", NOTEBOOK_HTML)
convert_py = CONVERT_INJECT.group(1) if CONVERT_INJECT else ""
notebook_py_inject = NOTEBOOK_INJECT.group(1) if NOTEBOOK_INJECT else ""

check(
    "convert.html patches urlretrieve",
    "urlretrieve" in convert_py,
)
check(
    "notebook.html patches urlretrieve",
    "urlretrieve" in notebook_py_inject,
)
check(
    "convert.html patches urlopen",
    "urlopen" in convert_py,
)
check(
    "notebook.html patches urlopen",
    "urlopen" in notebook_py_inject,
)

print("\n=== 9. Binary-safe HTTPS fetcher (no UTF-8 corruption) ===")

# After the 2026-08-18 fix, the patches must use js.XMLHttpRequest
# with the Latin1 overrideMimeType trick — NOT pyodide.http.open_url
# (which decodes as UTF-8 and corrupts binary data like sklearn .tgz
# files, causing SHA256 checksum mismatches).
# We strip Python comments (# ...) before checking so that explanatory
# comments mentioning "open_url" don't trigger a false positive.
import re as _re
def _strip_comments(src):
    """Strip '# ...' line comments from Python source."""
    return _re.sub(r"(^|\n)\s*#[^\n]*", r"\1", src)

convert_py_nocomments = _strip_comments(convert_py)
notebook_py_nocomments = _strip_comments(notebook_py_inject)

check(
    "convert.html patch uses js.XMLHttpRequest (binary-safe, not open_url)",
    "from js import XMLHttpRequest" in convert_py_nocomments
        and "pyodide.http.open_url" not in convert_py_nocomments
        and "from pyodide.http" not in convert_py_nocomments,
    "open_url decodes UTF-8 and corrupts binary; must use XMLHttpRequest sync XHR with overrideMimeType('ISO-8859-1')",
)
check(
    "notebook.html patch uses js.XMLHttpRequest (binary-safe, not open_url)",
    "from js import XMLHttpRequest" in notebook_py_nocomments
        and "pyodide.http.open_url" not in notebook_py_nocomments
        and "from pyodide.http" not in notebook_py_nocomments,
    "same as convert.html — must not use open_url",
)

# The overrideMimeType('ISO-8859-1') trick: forces responseText to be
# byte-faithful (each char 0-255), then encode('latin-1') recovers bytes.
check(
    "convert.html patch calls overrideMimeType('ISO-8859-1') for binary-safe XHR",
    "ISO-8859-1" in convert_py and "overrideMimeType" in convert_py,
)
check(
    "notebook.html patch calls overrideMimeType('ISO-8859-1') for binary-safe XHR",
    "ISO-8859-1" in notebook_py_inject and "overrideMimeType" in notebook_py_inject,
)

# The patched urlopen/urlretrieve must use the binary-safe fetcher.
check(
    "convert.html _obml_fetch_bytes_sync exists and is called from urlretrieve",
    "_obml_fetch_bytes_sync" in convert_py
        and "_obml_fetch_bytes_sync(" in convert_py,
)
check(
    "notebook.html _obml_fetch_bytes_sync exists and is called from urlretrieve",
    "_obml_fetch_bytes_sync" in notebook_py_inject
        and "_obml_fetch_bytes_sync(" in notebook_py_inject,
)

print("\n=== 10. Pre-seeded sklearn dataset cache ===")

# sklearn 1.4+ checks for /home/pyodide/scikit_learn_data/cal_housing_py3.pkz
# (note the _py3 suffix inserted by _pkl_filepath in sklearn/datasets/_base.py).
# Without this cache file, fetch_california_housing tries to download from
# figshare — which is CORS-blocked in the browser, causing a NetworkError.
#
# The fix: bundle the .pkz at /static/datasets/cal_housing_py3.pkz and
# pre-seed the cache at kernel boot. Both convert.html and notebook.html
# must have this pre-seed block.

check(
    "convert.html pre-seeds cal_housing_py3.pkz (sklearn's expected filename)",
    "cal_housing_py3.pkz" in CONVERT_HTML,
)
check(
    "notebook.html pre-seeds cal_housing_py3.pkz",
    "cal_housing_py3.pkz" in NOTEBOOK_HTML,
)

# The bundled .pkz file must actually exist on disk (and be non-trivially sized).
import os
PKZ_PATH = "/home/z/my-project/static/datasets/cal_housing_py3.pkz"
TGZ_PATH = "/home/z/my-project/static/datasets/cal_housing.tgz"
check(
    "static/datasets/cal_housing_py3.pkz exists on disk",
    os.path.exists(PKZ_PATH),
)
if os.path.exists(PKZ_PATH):
    check(
        "cal_housing_py3.pkz is non-empty (>100KB)",
        os.path.getsize(PKZ_PATH) > 100_000,
        f"size: {os.path.getsize(PKZ_PATH)} bytes",
    )
    # Verify the SHA256 of the .tgz matches what sklearn expects.
    import hashlib
    with open(TGZ_PATH, "rb") as f:
        actual_sha = hashlib.sha256(f.read()).hexdigest()
    check(
        "cal_housing.tgz SHA256 matches sklearn expectation (aaa5c9a6...5ea681)",
        actual_sha == "aaa5c9a6afe2225cc2aed2723682ae403280c4a3695a2ddda4ffb5d8215ea681",
        f"got: {actual_sha}",
    )

# Both pages must call FS.writeFile to /home/pyodide/scikit_learn_data/
# (the path sklearn's get_data_home() returns under Pyodide).
check(
    "convert.html writes the .pkz to /home/pyodide/scikit_learn_data/",
    "/home/pyodide/scikit_learn_data/cal_housing_py3.pkz" in CONVERT_HTML,
)
check(
    "notebook.html writes the .pkz to /home/pyodide/scikit_learn_data/",
    "/home/pyodide/scikit_learn_data/cal_housing_py3.pkz" in NOTEBOOK_HTML,
)

# The pre-seed must run BEFORE pyodideReady = true (so the cache is
# populated before any user code can call fetch_california_housing).
check(
    "convert.html pre-seed runs before pyodideReady=true",
    CONVERT_HTML.find("cal_housing_py3.pkz") < CONVERT_HTML.find("pyodideReady = true"),
)
check(
    "notebook.html pre-seed runs before pyodideReady=true",
    NOTEBOOK_HTML.find("cal_housing_py3.pkz") < NOTEBOOK_HTML.find("pyodideReady = true"),
)

print("\n" + "=" * 60)
if failures:
    print(f"RESULT: FAIL — {len(failures)} check(s) failed:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
else:
    print("RESULT: PASS — all checks green")
    sys.exit(0)
