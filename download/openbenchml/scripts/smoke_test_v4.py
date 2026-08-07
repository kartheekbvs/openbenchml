"""
Smoke test for v4.0 new features.

Verifies:
  1. All 17 built-in datasets load + split correctly.
  2. The code_runner_service can execute user code and capture stdout.
  3. The /convert flow: code → pickled model → saved to disk.
  4. The notebook run endpoint's underlying logic.
"""
import os
import sys
import tempfile
import traceback
from pathlib import Path

# Make the project importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.benchmark_engine.loader import list_builtin_datasets, load_dataset
from app.services.code_runner_service import run_code, code_to_pickled_model, save_pickled_model

PASS = 0
FAIL = 0

def ok(name):
    global PASS; PASS += 1
    print(f"  PASS  {name}")

def fail(name, why):
    global FAIL; FAIL += 1
    print(f"  FAIL  {name} — {why}")

print("\n═══ Test 1: All 17 built-in datasets load + split ═══")
datasets = list_builtin_datasets()
print(f"  Found {len(datasets)} datasets")
assert len(datasets) == 17, f"Expected 17 datasets, got {len(datasets)}"

for d in datasets:
    try:
        result = load_dataset(d["name"])
        assert "X_train" in result and "X_test" in result
        assert "y_train" in result and "y_test" in result
        assert result["X_train"].shape[0] > 0
        assert result["X_test"].shape[0] > 0
        n_train = result["X_train"].shape[0]
        n_test = result["X_test"].shape[0]
        ok(f"load_dataset('{d['name']}') → train={n_train}, test={n_test}, task={result['task_type']}")
    except Exception as e:
        fail(f"load_dataset('{d['name']}')", str(e))
        traceback.print_exc()

print("\n═══ Test 2: Code runner — basic execution + stdout capture ═══")
result = run_code("print('hello from sandbox'); x = 2 + 3; print(f'x = {x}')")
if result["ok"] and "hello from sandbox" in result["stdout"] and "x = 5" in result["stdout"]:
    ok("basic stdout capture")
else:
    fail("basic stdout capture", f"ok={result['ok']}, stdout={result['stdout']!r}")

print("\n═══ Test 3: Pre-imported libs (np, pd, sklearn) ═══")
result = run_code("import numpy as np_remote\narr = np.array([1,2,3])\nprint(f'local np: {np.array([10,20]).sum()}')\nprint(f'remote np: {np_remote.array([1,2,3]).sum()}')\nprint(f'pd version: {pd.__version__}')\nprint(f'sklearn version: {sklearn.__version__}')")
if result["ok"] and "6" in result["stdout"] and "30" in result["stdout"]:
    ok("pre-imported libs accessible")
else:
    fail("pre-imported libs accessible", f"ok={result['ok']}, stdout={result['stdout']!r}, stderr={result['stderr']!r}")

print("\n═══ Test 4: Sandbox blocks dangerous builtins ═══")
result = run_code("open('/etc/passwd')")
if not result["ok"] and "blocked" in result["stderr"].lower() or "name 'open' is not defined" in result["stderr"]:
    ok("open() blocked")
else:
    fail("open() blocked", f"ok={result['ok']}, stderr={result['stderr']!r}")

print("\n═══ Test 5: Sandbox blocks dangerous imports (subprocess) ═══")
result = run_code("import subprocess\nsubprocess.run(['ls'])")
if not result["ok"]:
    ok("subprocess import blocked")
else:
    fail("subprocess import blocked", "should have raised")

print("\n═══ Test 6: code_to_pickled_model — happy path ═══")
code = """
from sklearn.ensemble import RandomForestClassifier
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split

X, y = load_iris(return_X_y=True)
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
model = RandomForestClassifier(n_estimators=10, random_state=42)
model.fit(Xtr, ytr)
acc = model.score(Xte, yte)
print(f'trained; test acc = {acc:.4f}')
"""
try:
    pickled_bytes, meta = code_to_pickled_model(code, expected_var="model", timeout_seconds=30)
    if pickled_bytes and meta["framework"] == "scikit-learn" and meta["model_class"] == "RandomForestClassifier":
        ok(f"code_to_pickled_model → {meta['model_class']}, framework={meta['framework']}, size={meta['size_kb']} KB")
        if "accuracy" in meta:
            ok(f"metric captured from code: accuracy = {meta['accuracy']:.4f}")
        else:
            fail("metric captured from code", "no 'accuracy' var found in namespace")
    else:
        fail("code_to_pickled_model", f"unexpected meta: {meta}")
except Exception as e:
    fail("code_to_pickled_model", str(e))
    traceback.print_exc()

print("\n═══ Test 7: code_to_pickled_model — error if no 'model' var ═══")
try:
    code_no_var = "x = 5\nprint('no model here')"
    pickled_bytes, meta = code_to_pickled_model(code_no_var, expected_var="model")
    fail("missing model var", "should have raised ValueError")
except ValueError as e:
    if "no 'model' variable" in str(e).lower():
        ok("missing model var raises ValueError with helpful message")
    else:
        fail("missing model var raises", f"unexpected message: {e}")
except Exception as e:
    fail("missing model var raises", f"wrong exception type: {type(e).__name__}: {e}")

print("\n═══ Test 8: save_pickled_model — persists to disk ═══")
try:
    with tempfile.TemporaryDirectory() as tmpdir:
        upload_dir = Path(tmpdir) / "uploads"
        file_path, size_kb = save_pickled_model(pickled_bytes, user_id=9999, model_name="Test Model", upload_dir=upload_dir)
        if os.path.isfile(file_path) and size_kb > 0:
            ok(f"save_pickled_model → {file_path} ({size_kb} KB)")
            # Verify we can load it back
            import joblib
            loaded = joblib.load(file_path)
            if type(loaded).__name__ == "RandomForestClassifier":
                ok("pickled model can be loaded back via joblib")
            else:
                fail("pickled model reload", f"wrong type: {type(loaded).__name__}")
        else:
            fail("save_pickled_model", "file not found or size=0")
except Exception as e:
    fail("save_pickled_model", str(e))
    traceback.print_exc()

print("\n═══ Test 9: Timeout enforcement ═══")
import time
result = run_code("import time\nfor i in range(100):\n    print(i)\n    time.sleep(0.1)", timeout_seconds=2)
if result["timed_out"]:
    ok("timeout enforced (2s limit hit)")
else:
    fail("timeout enforced", f"timed_out={result['timed_out']}, error={result['error']!r}")

print("\n═══ Test 10: Framework detection variants ═══")
# Test xgboost-style class (mock)
class MockXGBBooster:
    pass
MockXGBBooster.__module__ = "xgboost.core"
fw = None
from app.services.code_runner_service import _detect_framework
fw = _detect_framework(MockXGBBooster())
if fw == "xgboost":
    ok("framework detection: xgboost")
else:
    fail("framework detection: xgboost", f"got {fw!r}")

# Test sklearn fallback
class MockSklearnEstimator:
    pass
MockSklearnEstimator.__module__ = "sklearn.ensemble._forest"
fw = _detect_framework(MockSklearnEstimator())
if fw == "scikit-learn":
    ok("framework detection: sklearn fallback")
else:
    fail("framework detection: sklearn fallback", f"got {fw!r}")


print(f"\n{'═' * 60}")
print(f"TOTAL:  {PASS + FAIL}   PASS: {PASS}   FAIL: {FAIL}")
print(f"{'═' * 60}")
sys.exit(0 if FAIL == 0 else 1)
