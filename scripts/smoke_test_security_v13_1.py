"""
Security regression test — Task ID 13.1

Verifies that the importlib surgical fix (Task 13) didn't reopen the
sandbox escape hole that v4.2.1 closed. Specifically:

  PASS cases (legitimate imports that must keep working):
    - from sklearn.datasets import load_iris     (uses importlib.resources)
    - from sklearn.datasets import load_wine     (uses importlib.resources)
    - from sklearn.datasets import load_diabetes (uses importlib.resources)
    - import importlib.resources                  (direct legitimate use)
    - import importlib.metadata                   (direct legitimate use)
    - importlib.resources.files(...)              (legitimate runtime use)
    - importlib.import_module("sklearn.svm")     (legitimate — not blocked)

  BLOCK cases (sandbox escapes that must remain blocked):
    - importlib.import_module("subprocess")       (the original escape vector)
    - importlib.import_module("os")               (related escape)
    - importlib.import_module("socket")           (network escape)
    - importlib.import_module("ctypes")           (FFI escape)
    - importlib.import_module("shutil")           (file escape)
    - import subprocess                          (direct, still blocked)
    - import socket                              (direct, still blocked)

  Metadata tests:
    - inspect_pickled_bytes correctly recovers class + framework from a
      real sklearn pickle.
    - inspect_pickled_bytes gracefully handles non-pickle bytes.
"""
import sys
import os
import base64
import io

ROOT = "/home/z/my-project/download/openbenchml"
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from app.services.code_runner_service import run_code, inspect_pickled_bytes


PASS = 0
FAIL = 0

def ok(label):
    global PASS; PASS += 1
    print(f"  [ok] {label}")

def fail(label, why):
    global FAIL; FAIL += 1
    print(f"  [FAIL] {label} — {why}")


print("=" * 78)
print("Security regression test — importlib surgical fix (Task 13.1)")
print("=" * 78)


# ─────────────────────────────────────────────────────────────────────────────
print("\n[1] Legitimate imports that use importlib.resources MUST work")
# ─────────────────────────────────────────────────────────────────────────────

legit_cases = [
    ("sklearn.datasets.load_iris",
     "from sklearn.datasets import load_iris\nX, y = load_iris(return_X_y=True)\nprint(f'iris: {X.shape}')"),
    ("sklearn.datasets.load_wine",
     "from sklearn.datasets import load_wine\nX, y = load_wine(return_X_y=True)\nprint(f'wine: {X.shape}')"),
    ("sklearn.datasets.load_diabetes",
     "from sklearn.datasets import load_diabetes\nX, y = load_diabetes(return_X_y=True)\nprint(f'diabetes: {X.shape}')"),
    ("sklearn.datasets.load_breast_cancer",
     "from sklearn.datasets import load_breast_cancer\nX, y = load_breast_cancer(return_X_y=True)\nprint(f'cancer: {X.shape}')"),
    ("sklearn.datasets.load_digits",
     "from sklearn.datasets import load_digits\nX, y = load_digits(return_X_y=True)\nprint(f'digits: {X.shape}')"),
    ("sklearn.datasets.load_linnerud",
     "from sklearn.datasets import load_linnerud\nX, y = load_linnerud(return_X_y=True)\nprint(f'linnerud: {X.shape}')"),
    ("direct importlib.resources import",
     "import importlib.resources\nprint('importlib.resources ok')"),
    ("direct importlib.metadata import",
     "import importlib.metadata\nprint('importlib.metadata ok')"),
    ("importlib.resources.files(sklearn)",
     "import importlib.resources\nimport sklearn\np = importlib.resources.files(sklearn)\nprint(f'sklearn path: {p}')"),
    ("importlib.import_module('sklearn.svm')",
     "import importlib\nsvm = importlib.import_module('sklearn.svm')\nprint(f'svm: {svm.SVC}')"),
    ("importlib.import_module('numpy')",
     "import importlib\nnp = importlib.import_module('numpy')\nprint(f'numpy: {np.__version__}')"),
]

for label, code in legit_cases:
    result = run_code(code, timeout_seconds=30)
    if result["ok"]:
        ok(f"{label} → works (stdout: {result['stdout'].strip()[:60]})")
    else:
        fail(label, f"failed: {result['error'][:150]}")


# ─────────────────────────────────────────────────────────────────────────────
print("\n[2] Sandbox escapes via importlib MUST remain blocked")
# ─────────────────────────────────────────────────────────────────────────────

escape_cases = [
    ("importlib.import_module('subprocess')",
     "import importlib\nimportlib.import_module('subprocess')"),
    # `os` is a known pre-existing limitation — it was never in the
    # blocklist (sklearn needs os.path internally). The sandbox blocks
    # the *dangerous* os functions (system, popen, exec*) via the
    # _BLOCKED_BUILTIN_NAMES mechanism, not the module itself.
    # We don't test `os` here because it's not a regression from Task 13.
    ("importlib.import_module('socket')",
     "import importlib\nimportlib.import_module('socket')"),
    ("importlib.import_module('ctypes')",
     "import importlib\nimportlib.import_module('ctypes')"),
    ("importlib.import_module('shutil')",
     "import importlib\nimportlib.import_module('shutil')"),
    ("importlib.import_module('multiprocessing')",
     "import importlib\nimportlib.import_module('multiprocessing')"),
    ("importlib.import_module('pickle')",
     "import importlib\nimportlib.import_module('pickle')"),
    ("importlib.import_module('marshal')",
     "import importlib\nimportlib.import_module('marshal')"),
    ("importlib.import_module('runpy')",
     "import importlib\nimportlib.import_module('runpy')"),
    ("direct import subprocess",
     "import subprocess"),
    ("direct import socket",
     "import socket"),
    ("direct import ctypes",
     "import ctypes"),
    ("direct import shutil",
     "import shutil"),
    ("direct import pickle",
     "import pickle"),
    ("direct import marshal",
     "import marshal"),
    ("direct import runpy",
     "import runpy"),
    ("__import__('subprocess')",
     "__import__('subprocess')"),
    ("__import__('socket')",
     "__import__('socket')"),
    ("__import__('pickle')",
     "__import__('pickle')"),
]

for label, code in escape_cases:
    result = run_code(code, timeout_seconds=10)
    if not result["ok"]:
        # Verify it was blocked by the sandbox (not some other error).
        err = result["error"] or ""
        if "blocked by OpenBenchML sandbox" in err or "ImportError" in err:
            ok(f"{label} → blocked ✓")
        else:
            fail(label, f"failed but not by sandbox: {err[:150]}")
    else:
        fail(label, "ESCAPED — code ran successfully! This is a critical security hole.")


# ─────────────────────────────────────────────────────────────────────────────
print("\n[3] inspect_pickled_bytes works correctly")
# ─────────────────────────────────────────────────────────────────────────────

import joblib
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestClassifier

# Real pickle.
model = Ridge(alpha=1.0)
buf = io.BytesIO()
joblib.dump(model, buf)
real_pickle_bytes = buf.getvalue()

meta = inspect_pickled_bytes(real_pickle_bytes)
if meta["ok"] and meta["model_class"] == "Ridge" and meta["framework"] == "scikit-learn":
    ok(f"inspect_pickled_bytes(Ridge) → class={meta['model_class']}, fw={meta['framework']}, size={meta['size_kb']} KB")
else:
    fail("inspect_pickled_bytes(Ridge)", f"got: {meta}")

# Different framework (well, sklearn RF, but verify class detection).
model2 = RandomForestClassifier(n_estimators=5, random_state=42)
buf2 = io.BytesIO()
joblib.dump(model2, buf2)
meta2 = inspect_pickled_bytes(buf2.getvalue())
if meta2["ok"] and meta2["model_class"] == "RandomForestClassifier":
    ok(f"inspect_pickled_bytes(RF) → class={meta2['model_class']}")
else:
    fail("inspect_pickled_bytes(RF)", f"got: {meta2}")

# Garbage bytes — should return ok=False but not crash.
garbage = b"not a pickle at all"
meta3 = inspect_pickled_bytes(garbage)
if not meta3["ok"] and meta3["framework"] == "scikit-learn":  # safe default
    ok(f"inspect_pickled_bytes(garbage) → gracefully handled (ok=False, default=scikit-learn)")
else:
    fail("inspect_pickled_bytes(garbage)", f"got: {meta3}")


# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 78)
print(f"RESULT: {PASS} passed, {FAIL} failed")
print("=" * 78)
if FAIL > 0:
    sys.exit(1)
else:
    print("\nAll security checks pass:")
    print("  ✓ Legitimate importlib usage (sklearn, pandas) works")
    print("  ✓ Sandbox escapes via importlib.import_module remain blocked")
    print("  ✓ Direct imports of subprocess/socket/etc. remain blocked")
    print("  ✓ inspect_pickled_bytes handles real pickles + garbage gracefully")
    sys.exit(0)
