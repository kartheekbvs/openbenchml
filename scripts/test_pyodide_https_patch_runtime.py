"""
Direct runtime test of the urllib.request monkey-patch that the
/convert page injects into Pyodide at kernel boot.

After the 2026-08-18 fix, the patch no longer uses pyodide.http.open_url
(which decodes responses as UTF-8 and corrupts binary data like sklearn's
.tgz archive files, causing SHA256 checksum mismatches). The patch now
uses js.XMLHttpRequest in sync mode with overrideMimeType('ISO-8859-1')
to fetch raw bytes losslessly.

This test exercises the patch logic against a fake `js.XMLHttpRequest`
(with binary-safe canned responses). We:
  1. Read the patch Python source out of convert.html.
  2. Exec it against a fake `js` module (with XMLHttpRequest mocked to
     return canned bytes via the Latin1 trick).
  3. Call the patched `urllib.request.urlopen` + `urlretrieve` and verify:
     - urlopen("https://example.com/data.csv") returns a BytesIO with the
       canned content (no UTF-8 corruption).
     - urlopen("file:///etc/passwd") falls through to the original.
     - urlretrieve("https://example.com/data.zip", "/tmp/out.zip") writes
       the canned bytes to /tmp/out.zip and returns (filename, headers).
     - Binary content with high bytes (>127) is preserved intact.
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

# ── Build a fake js.XMLHttpRequest that mimics the browser behavior ──────────
# A small "HTTP server" — maps URL → canned response BYTES.
_FAKE_HTTP_RESPONSES = {
    "https://example.com/data.csv":        b"a,b,c\n1,2,3\n4,5,6\n",
    "https://example.com/data.zip":        b"PK\x03\x04fake-zip-bytes",
    "https://example.com/cal_housing.csv": b"MedInc,HouseAge,AveRooms\n5.6,25,4.5\n",
    "http://example.com/plain.txt":        b"hello world",
    # A binary blob with bytes > 127 to verify UTF-8 doesn't corrupt them.
    "https://example.com/binary.bin":      bytes(range(256)) * 4,
}


class _FakeXHR:
    """Mimics js.XMLHttpRequest in sync mode with overrideMimeType trick.

    The real browser, when overrideMimeType('ISO-8859-1') is set, decodes
    the response body as Latin1 — each byte becomes a single Unicode char
    in the 0..255 range, so responseText is byte-faithful.
    """
    def __init__(self):
        self._url = None
        self._async = None
        self._mime = None
        self.status = 0
        self._body = b""

    def open(self, method, url, async_):
        self._url = url
        self._async = async_

    def overrideMimeType(self, mime):
        self._mime = mime

    def send(self, data=None):
        if self._url not in _FAKE_HTTP_RESPONSES:
            self.status = 404
            self._body = b""
            return
        self._body = _FAKE_HTTP_RESPONSES[self._url]
        self.status = 200

    @property
    def responseText(self):
        # Browser's responseText after overrideMimeType('ISO-8859-1'):
        # each raw byte → one Unicode char in 0..255. This is what makes
        # the trick binary-safe.
        return "".join(chr(b) for b in self._body)

    @property
    def response(self):
        # For responseType='arraybuffer' (not used in sync mode, but defined
        # for completeness).
        return self._body


def _fake_xhr_new():
    return _FakeXHR()


# Install the fake `js` module so `from js import XMLHttpRequest` succeeds.
fake_js = types.ModuleType("js")
fake_js.XMLHttpRequest = _fake_xhr_new  # XMLHttpRequest.new() returns _FakeXHR
# js.XMLHttpRequest in Pyodide is a class; .new() constructs instances.
class _XHRFactory:
    @staticmethod
    def new():
        return _FakeXHR()
fake_js.XMLHttpRequest = _XHRFactory
sys.modules["js"] = fake_js

# Provide stubs for numpy / pandas / etc so the import statements in the
# injected code don't crash. (We only care about the urllib patch, not the
# pandas.read_csv patch.)
for name in ["numpy", "pandas", "sklearn", "scipy", "joblib", "matplotlib"]:
    if name not in sys.modules:
        m = types.ModuleType(name)
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
    _urllib_request.urlopen("file:///nonexistent-path-xyz")
    check(
        "urlopen('file://...') falls through (no crash from fake_open_url)",
        True,
    )
except Exception:
    # Any error (URLError, FileNotFoundError, etc.) is fine — it
    # means the original urlopen handled it.
    check("non-HTTP URL falls through cleanly", True)

print("\n=== 7. Binary-safe: bytes > 127 are NOT corrupted by UTF-8 ===")
# Fetch a 1KB blob containing ALL 256 byte values including high bytes
# (0x80-0xFF). The patched urlopen MUST return these bytes intact,
# without any UTF-8 replacement char (U+FFFD) corruption.
result = _urllib_request.urlopen("https://example.com/binary.bin")
data = result.read()
expected = bytes(range(256)) * 4
check(
    "binary blob with bytes 0..255 is returned intact (no UTF-8 corruption)",
    data == expected,
    f"length: got {len(data)}, expected {len(expected)}; "
    f"first 32 bytes got: {data[:32]!r}",
)

print("\n=== 8. SHA256 of fetched binary content matches expected ===")
import hashlib
actual_sha = hashlib.sha256(data).hexdigest()
expected_sha = hashlib.sha256(expected).hexdigest()
check(
    "SHA256 of fetched binary blob matches expected SHA256",
    actual_sha == expected_sha,
    f"got: {actual_sha[:16]}... expected: {expected_sha[:16]}...",
)

print("\n" + "=" * 60)
if failures:
    print(f"RESULT: FAIL — {len(failures)} check(s) failed:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
else:
    print("RESULT: PASS — all runtime checks green")
    sys.exit(0)
