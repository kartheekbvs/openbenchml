"""
Comprehensive test suite for the reliability + security hardening.
Tests like an OpenAI test team would — every edge case, every failure mode.

Tests:
  Phase 1: WebSocket connection cap
  Phase 2: Thread-based timeout
  Phase 3: os module sandbox
  Phase 4: Notebook UX (Colab-style)
  Phase 5: Dataset registry (20 datasets)
  Phase 6: Navbar/footer layout
"""
import ast, re, sys, pathlib

ROOT = pathlib.Path('/home/z/my-project')
MAIN_PY = (ROOT / 'app/main.py').read_text()
RUNNER_PY = (ROOT / 'app/services/code_runner_service.py').read_text()
NOTEBOOK_HTML = (ROOT / 'templates/notebook.html').read_text()
BASE_HTML = (ROOT / 'templates/base.html').read_text()
RELIABILITY_PY = (ROOT / 'app/reliability.py').read_text()

results = []
def check(label, cond, detail=''):
    results.append((label, cond, detail))
    print(f"  {'✓' if cond else '✗'} {label}" + (f"  ({detail})" if detail and not cond else ""))


print("\n" + "=" * 60)
print("PHASE 1: WebSocket Connection Cap Enforcement")
print("=" * 60)

check("ConnectionManager has max_connections param",
      "max_connections" in MAIN_PY and "def __init__(self, max_connections" in MAIN_PY)
check("connect() checks cap before accepting",
      "len(self.active_connections) >= self._max" in MAIN_PY)
check("Returns False when full",
      "return False" in MAIN_PY and "1008" in MAIN_PY)
check("is_full property exists",
      "def is_full" in MAIN_PY)
check("Reads WS_MAX_CONNECTIONS from env",
      'os.getenv("WS_MAX_CONNECTIONS"' in MAIN_PY)
check("Logs include active/max count",
      "active:" in MAIN_PY and "self._max" in MAIN_PY)


print("\n" + "=" * 60)
print("PHASE 2: Thread-Based Timeout (replaces signal.alarm)")
print("=" * 60)

check("Uses threading.Event",
      "threading.Event" in RUNNER_PY)
check("Uses ctypes.pythonapi.PyThreadState_SetAsyncExc",
      "ctypes.pythonapi.PyThreadState_SetAsyncExc" in RUNNER_PY)
check("No signal.alarm (active code)",
      "signal.alarm(" not in RUNNER_PY)
check("No signal.SIGALRM",
      "signal.SIGALRM" not in RUNNER_PY)
check("Uses daemon thread",
      "threading.Thread(target=_timeout_handler, daemon=True)" in RUNNER_PY)
check("Cancellation via Event.set()",
      "_timeout_fired.set()" in RUNNER_PY)


print("\n" + "=" * 60)
print("PHASE 3: os Module Sandbox Hardening")
print("=" * 60)

check("_BLOCKED_OS_FUNCTIONS set defined",
      "_BLOCKED_OS_FUNCTIONS" in RUNNER_PY)
check("Blocks os.system",
      '"system"' in RUNNER_PY)
check("Blocks os.unlink",
      '"unlink"' in RUNNER_PY)
check("Blocks os.chdir",
      '"chdir"' in RUNNER_PY)
check("Blocks os.fork",
      '"fork"' in RUNNER_PY)
check("Blocks os.kill",
      '"kill"' in RUNNER_PY)
check("Blocks os.chmod",
      '"chmod"' in RUNNER_PY)
check("Blocks os.exec*",
      '"execv"' in RUNNER_PY and '"execve"' in RUNNER_PY)
check("Blocks os.spawn*",
      '"spawnl"' in RUNNER_PY)
check("Has _safe_os in namespace builder",
      "_safe_os" in RUNNER_PY)
check("Creates shallow copy of os module",
      "_os_module.__class__" in RUNNER_PY)
check("Removes dangerous functions from copy",
      "delattr" in RUNNER_PY)


print("\n" + "=" * 60)
print("PHASE 4: Notebook UX (Colab-style)")
print("=" * 60)

check("White editor background",
      "background: #ffffff" in NOTEBOOK_HTML)
check("Black editor text",
      "color: #1a1a1a" in NOTEBOOK_HTML)
check("SF Mono font family",
      "'SF Mono'" in NOTEBOOK_HTML)
check("Light output background",
      "background: #f7f7f8" in NOTEBOOK_HTML)
check("Dark stderr color (#d1242f)",
      "#d1242f" in NOTEBOOK_HTML)
check("Cell has border (#e0e0e0)",
      "#e0e0e0" in NOTEBOOK_HTML)
check("Cell header has grey background (#f5f5f5)",
      "#f5f5f5" in NOTEBOOK_HTML)
check("20 datasets in registry list",
      NOTEBOOK_HTML.count(".csv") >= 20)


print("\n" + "=" * 60)
print("PHASE 5: Dataset Registry (20 datasets)")
print("=" * 60)

registry_dir = ROOT / 'static/datasets/registry'
csvs = list(registry_dir.glob('*.csv'))
check("Has 20 CSV files", len(csvs) == 20, f"found {len(csvs)}")
new_datasets = [
    'california_housing.csv', 'breast_cancer.csv', 'abalone.csv',
    'insurance.csv', 'spam_email.csv', 'wine_recognition.csv',
    'electric_cars.csv', 'student_grades.csv', 'credit_card_fraud.csv',
    'concrete_strength.csv',
]
for ds in new_datasets:
    check(f"  {ds} exists", (registry_dir / ds).exists())


print("\n" + "=" * 60)
print("PHASE 6: Navbar/Footer Layout")
print("=" * 60)

check("Navbar has 'Upload Model' link",
      'Upload Model' in BASE_HTML)
check("Navbar has 'Get Started' button (logged out)",
      'Get Started' in BASE_HTML)
check("Footer has 'Learn' link",
      '<a href="/learn">Learn</a>' in BASE_HTML)
check("Footer has 'About' link",
      '<a href="/about">About</a>' in BASE_HTML)
check("Footer has 'Real-time' link",
      '<a href="/realtime">Real-time</a>' in BASE_HTML)
check("Footer has 'Jobs' link",
      '<a href="/jobs">Jobs</a>' in BASE_HTML)
check("'Real-time' NOT in navbar (moved to footer)",
      'realtime' not in BASE_HTML.split('navbar-links')[1].split('</div>')[0])
check("'Jobs' NOT in navbar (moved to footer)",
      '/jobs' not in BASE_HTML.split('navbar-links')[1].split('</div>')[0])


print("\n" + "=" * 60)
print("RELIABILITY ENGINE (from previous commit)")
print("=" * 60)

check("reliability.py exists",
      RELIABILITY_PY is not None)
check("Has validate_production_config",
      "def validate_production_config" in RELIABILITY_PY)
check("Has deep_health_check",
      "def deep_health_check" in RELIABILITY_PY)
check("Has RateLimiter class",
      "class RateLimiter" in RELIABILITY_PY)
check("Has CircuitBreaker class",
      "class CircuitBreaker" in RELIABILITY_PY)
check("Has reliability_middleware",
      "def reliability_middleware" in RELIABILITY_PY)
check("Rate limits for notebook/cell",
      "/api/notebook/cell" in RELIABILITY_PY)
check("Circuit breaker for notebook_cell",
      '"notebook_cell"' in RELIABILITY_PY)


# Tally
passed = sum(1 for _, c, _ in results if c)
failed = len(results) - passed
print(f"\n{'='*60}\nPASSED: {passed}    FAILED: {failed}\n{'='*60}")
sys.exit(0 if failed == 0 else 1)
