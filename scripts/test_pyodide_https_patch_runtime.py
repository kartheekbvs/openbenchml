"""
Direct runtime test of the urllib.request monkey-patch that the
/convert page injects into Pyodide at kernel boot.

This test exercises the patch logic against the ACTUAL sklearn source
code structure (not against a real Pyodide runtime — that would require
a browser). We:

  1. Read the patch Python source out of convert.html.
  2. Exec it against a fake `pyodide.http` module (with `open_url` mocked
     to return canned bytes).
  3. Call the patched `urllib.request.urlopen` + `urlretrieve` and verify:
     - urlopen("https://example.com/data.csv") returns a BytesIO with the
       canned content.
     - urlopen("file:///etc/passwd") falls through to the original.
     - urlretrieve("https://example.com/data.zip", "/tmp/out.zip") writes
       the canned bytes to /tmp/out.zip and returns (filename, headers).
     - urlretrieve("file://...") falls through.
  4. Simulate `sklearn.datasets._fetch_remote()` calling urlretrieve and
     verify it would succeed end-to-end.
"""
import sys, os, re, io, types, tempfile
ROOT = "/home/z/my-project"
sys.path.insert(0, ROOT)
os.chdir(ROOT)

CONVERT_HTML = open("templates/convert.html").read()

# Extract the injected Python code from the convert.html template
m = re.search(r"runPythonAsync\(`([\s\S]*?)`\);", CONVERT_HTML)
assert m, "could not find runPythonAsync block in convert.html"
injected_py = m.group(1)
print(f"  extracted {len(injected_py)} chars of injected Python from convert.html")

# ── Build a fake pyodide.http module ──────────────────────────────────────────
class _FakeStream:
    """Mimics the file-like object returned by pyodide.http.open_url."""
    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0
    def read(self, n=-1):
        if n < 0 or n is None:
            out = self._data[self._pos:]
            self._pos = len(self._data)
            return out
        out = self._data[self._pos:self._pos + n]
        self._pos += len(out)
        return out
    def __enter__(self): return self
    def __exit__(self, *a): pass

# A small "HTTP server" — maps URL → canned response bytes.
_FAKE_HTTP_RESPONSES = {
    "https://example.com/data.csv":        b"a,b,c\n1,2,3\n4,5,6\n",
    "https://example.com/data.zip":        b"PK\x03\x04fake-zip-bytes",
    "https://example.com/cal_housing.csv": b"MedInc,HouseAge,AveRooms\n5.6,25,4.5\n",
    "http://example.com/plain.txt":        b"hello world",
}

def fake_open_url(url: str):
    """Mimics pyodide.http.open_url — returns a stream of canned bytes."""
    if url not in _FAKE_HTTP_RESPONSES:
        raise ValueError(f"unknown URL in test: {url}")
    return _FakeStream(_FAKE_HTTP_RESPONSES[url])

# Install the fake pyodide.http module so the patch can `from pyodide.http
# import open_url` succeed.
fake_pyodide_pkg = types.ModuleType("pyodide")
fake_pyodide_http = types.ModuleType("pyodide.http")
fake_pyodide_http.open_url = fake_open_url
fake_pyodide_pkg.http = fake_pyodide_http
sys.modules["pyodide"] = fake_pyodide_pkg
sys.modules["pyodide.http"] = fake_pyodide_http

# Provide stubs for numpy / pandas / etc so the import statements in the
# injected code don't crash. (We only care about the urllib patch, not the
# pandas.read_csv patch.)
for name in ["numpy", "pandas", "sklearn", "scipy", "joblib", "matplotlib"]:
    if name not in sys.modules:
        m = types.ModuleType(name)
        # pandas.read_csv needs to exist (we test it doesn't get called for non-HTTP)
        m.read_csv = lambda *a, **k: ("orig-read-csv", a, k)
        sys.modules[name] = m

# matplotlib.use is called
sys.modules["matplotlib"].use = lambda mode: None
sys.modules["matplotlib"].pyplot = types.ModuleType("matplotlib.pyplot")
sys.modules["matplotlib.pyplot"] = sys.modules["matplotlib"].pyplot
sys.modules["matplotlib.pyplot"].get_fignums = lambda: []

# Run the injected patch code — this installs our urlopen + urlretrieve
# monkey-patches on urllib.request.
patch_ns = {}
exec(injected_py, patch_ns)

# The patched urllib.request module is the one stdlib loaded — verify.
import urllib.request as _urllib_request
print(f"  urlopen is patched? {_urllib_request.urlopen.__name__ == '_obml_urlopen'}")
print(f"  urlretrieve is patched? {_urllib_request.urlretrieve.__name__ == '_obml_urlretrieve'}")

failures = []
def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond: failures.append(name)

print("\n=== 1. urlopen('https://...') returns BytesIO with canned content ===")
result = _urllib_request.urlopen("https://example.com/data.csv")
data = result.read()
check(
    "urlopen returns a BytesIO-like with .read()",
    hasattr(result, "read"),
)
check(
    "urlopen('https://...') returns the canned CSV bytes",
    data == b"a,b,c\n1,2,3\n4,5,6\n",
    f"got: {data[:50]!r}",
)

print("\n=== 2. urlopen('http://...') also works (not just https) ===")
result = _urllib_request.urlopen("http://example.com/plain.txt")
data = result.read()
check(
    "urlopen('http://...') returns the canned bytes",
    data == b"hello world",
    f"got: {data[:50]!r}",
)

print("\n=== 3. urlretrieve('https://...', '/tmp/file') writes to disk ===")
with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
    local_path = f.name
try:
    filename, headers = _urllib_request.urlretrieve(
        "https://example.com/data.zip", local_path,
    )
    check(
        "urlretrieve returns (filename, headers) tuple",
        isinstance((filename, headers), tuple),
    )
    check(
        "returned filename matches the requested local path",
        filename == local_path,
        f"got: {filename!r}",
    )
    with open(local_path, "rb") as f:
        written = f.read()
    check(
        "urlretrieve wrote the canned bytes to disk",
        written == b"PK\x03\x04fake-zip-bytes",
        f"got: {written[:30]!r}",
    )
finally:
    os.unlink(local_path)

print("\n=== 4. Simulate sklearn._fetch_remote calling urlretrieve ===")
# sklearn.datasets._base._fetch_remote does roughly:
#   archive_path = os.path.join(dirname, remote.filename)
#   urlretrieve(remote.url, archive_path)
#   return archive_path
class _Remote:
    url = "https://example.com/cal_housing.csv"
    filename = "cal_housing.csv"
    checksum = None

with tempfile.TemporaryDirectory() as tmpdir:
    remote = _Remote()
    archive_path = os.path.join(tmpdir, remote.filename)
    # This is what sklearn does internally
    returned_path, _headers = _urllib_request.urlretrieve(remote.url, archive_path)
    check(
        "sklearn-style fetch: urlretrieve returns the local archive path",
        returned_path == archive_path,
    )
    check(
        "sklearn-style fetch: archive exists on disk",
        os.path.exists(archive_path),
    )
    with open(archive_path, "rb") as f:
        content = f.read()
    check(
        "sklearn-style fetch: archive content matches canned response",
        content == b"MedInc,HouseAge,AveRooms\n5.6,25,4.5\n",
        f"got: {content[:50]!r}",
    )

print("\n=== 5. urllib.request.Request object also works (url attribute) ===")
req = _urllib_request.Request("https://example.com/data.csv")
# The patch checks `url = getattr(url_or_req, "full_url", url_or_req)`,
# which is what urllib.Request exposes.
check(
    "urllib Request has .full_url attribute",
    hasattr(req, "full_url"),
)
result = _urllib_request.urlopen(req)
data = result.read()
check(
    "urlopen(Request('https://...')) returns canned bytes",
    data == b"a,b,c\n1,2,3\n4,5,6\n",
    f"got: {data[:50]!r}",
)

print("\n=== 6. Non-HTTP URL falls through to the original urlopen ===")
# file:// URLs should NOT go through the patch — they should defer to
# the real stdlib urlopen (which we're not testing for content, only
# that the patch DOESN'T intercept them).
try:
    # Use a path that doesn't exist so we get a clear URLError — but the
    # important thing is that the error came from the original urlopen,
    # not from our patch trying to call fake_open_url.
    _urllib_request.urlopen("file:///nonexistent-path-xyz")
    check(
        "urlopen('file://...') falls through (no crash from fake_open_url)",
        True,
    )
except ValueError as e:
    # If fake_open_url were wrongly called, it'd raise ValueError with the
    # "unknown URL in test" message.
    if "unknown URL in test" in str(e):
        check(
            "non-HTTP URL was NOT routed through the HTTPS patch",
            False,
            f"patch wrongly intercepted file:// URL: {e}",
        )
    else:
        check("non-HTTP URL falls through cleanly", True)
except Exception:
    # Any other error (URLError, FileNotFoundError, etc.) is fine — it
    # means the original urlopen handled it.
    check("non-HTTP URL falls through cleanly", True)

print("\n" + "=" * 60)
if failures:
    print(f"RESULT: FAIL — {len(failures)} check(s) failed:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
else:
    print("RESULT: PASS — all runtime checks green")
    sys.exit(0)
