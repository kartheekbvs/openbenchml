"""
Runtime test for the autocomplete backend (notebook.py).

Tests the curated completion lookup + the keyword-fallback branch logic
WITHOUT spinning up the full FastAPI app (which would need sqlalchemy,
alembic, supabase, etc — heavy deps that aren't available in CI).

Instead, we extract the logic via the module source and test the data
structures + a small re-implementation of the merge logic.
"""
import sys, os, re, importlib.util
ROOT = "/home/z/my-project"
sys.path.insert(0, ROOT)
os.chdir(ROOT)

# Load notebook.py as a module WITHOUT executing the FastAPI router
# decorators (we just want the _CURATED dict and _PY_KEYWORDS list).
# We do this by reading the source and exec'ing the constants section
# in a throwaway namespace.
src = open("app/routes/notebook.py").read()

# Extract just the _CURATED dict + _PY_KEYWORDS list — exec them in a
# blank namespace so we can poke at the resulting objects.
ns = {}
m_curated = re.search(r"_CURATED = \{[\s\S]*?^\}", src, re.MULTILINE)
assert m_curated, "could not find _CURATED in notebook.py"
m_keywords = re.search(r"_PY_KEYWORDS = \[[\s\S]*?^\]", src, re.MULTILINE)
assert m_keywords, "could not find _PY_KEYWORDS in notebook.py"
exec(m_curated.group(0), ns)
exec(m_keywords.group(0), ns)

_CURATED = ns["_CURATED"]
_PY_KEYWORDS = ns["_PY_KEYWORDS"]

print(f"  loaded _CURATED with {len(_CURATED)} keys")
print(f"  loaded _PY_KEYWORDS with {len(_PY_KEYWORDS)} entries")

# Re-implement the curated-lookup logic from notebook.py
def curated_completions(prefix: str):
    key = prefix.rstrip(".").lower()
    items = _CURATED.get(key, [])
    return [{"name": n, "type": "attr", "desc": ""} for n in items]

# Re-implement the token + prefix extraction
def extract_token(code: str, cursor: int):
    m = re.search(r"[A-Za-z_][A-Za-z0-9_\.]*$", code[:cursor])
    token = m.group(0) if m else ""
    if "." in token:
        obj_part, _, attr_part = token.rpartition(".")
        prefix = obj_part + "."
    else:
        obj_part = ""
        prefix = ""
        attr_part = token
    return token, obj_part, prefix, attr_part

# Re-implement the complete endpoint's merge logic (minus the Jedi
# call which requires the user's live namespace).
def complete(code: str, cursor: int = None):
    if cursor is None:
        cursor = len(code)
    token, obj_part, prefix, attr_part = extract_token(code, cursor)
    curated = curated_completions(prefix) if prefix else []
    if curated and attr_part:
        curated = [c for c in curated if c["name"].lower().startswith(attr_part.lower())]

    merged = list(curated)
    seen = {c["name"] for c in merged}

    # Keyword fallback
    if not prefix and attr_part and len(attr_part) >= 2:
        for kw in _PY_KEYWORDS:
            if kw.lower().startswith(attr_part.lower()) and kw not in seen:
                kw_type = "keyword"
                if kw.startswith("__"):
                    kw_type = "dunder"
                elif kw.startswith("import ") or kw.startswith("from "):
                    kw_type = "snippet"
                elif kw[0].isupper():
                    kw_type = "builtin"
                merged.append({"name": kw, "type": kw_type, "desc": ""})
                seen.add(kw)

    return {"completions": merged[:40], "source": "curated+keywords",
            "prefix": prefix, "token": token}

# ── Test cases ──────────────────────────────────────────────────────────────
failures = []
def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond: failures.append(name)

print("\n=== 1. Python keyword suggestions ===")
r = complete("imp")
names = [c["name"] for c in r["completions"]]
check("'imp' returns 'import'", "import" in names, f"got: {names[:10]}")
check("'imp' returns snippet 'import numpy as np'", "import numpy as np" in names)
check("'imp' returns snippet 'import pandas as pd'", "import pandas as pd" in names)

print("\n=== 2. 'fo' returns 'for' ===")
r = complete("fo")
names = [c["name"] for c in r["completions"]]
check("'fo' returns 'for'", "for" in names, f"got: {names[:10]}")

print("\n=== 3. 'pri' returns 'print' ===")
r = complete("pri")
names = [c["name"] for c in r["completions"]]
check("'pri' returns 'print'", "print" in names, f"got: {names[:10]}")

print("\n=== 4. 'np.ar' returns arange / argmax / argmin ===")
r = complete("np.ar")
names = [c["name"] for c in r["completions"]]
check("'np.ar' returns 'arange'", "arange" in names, f"got: {names[:10]}")
check("'np.ar' returns 'argmax'", "argmax" in names)
check("'np.ar' returns 'argmin'", "argmin" in names)
check("'np.ar' does NOT return 'zeros' (wrong prefix)",
      "zeros" not in names,
      "filtering by prefix is broken")

print("\n=== 5. 'sklearn.metrics.' returns accuracy_score ===")
r = complete("sklearn.metrics.")
names = [c["name"] for c in r["completions"]]
check("'sklearn.metrics.' returns 'accuracy_score'",
      "accuracy_score" in names, f"got: {names[:10]}")
check("'sklearn.metrics.' returns 'f1_score'", "f1_score" in names)
check("'sklearn.metrics.' returns 'mean_squared_error'", "mean_squared_error" in names)

print("\n=== 6. 'sns.set' returns seaborn set functions ===")
r = complete("sns.set")
names = [c["name"] for c in r["completions"]]
check("'sns.set' returns 'set'", "set" in names, f"got: {names[:10]}")
check("'sns.set' returns 'set_theme'", "set_theme" in names)
check("'sns.set' returns 'set_style'", "set_style" in names)

print("\n=== 7. 'sklearn.ensemble.' returns RandomForest* ===")
r = complete("sklearn.ensemble.")
names = [c["name"] for c in r["completions"]]
check("'sklearn.ensemble.' returns 'RandomForestClassifier'",
      "RandomForestClassifier" in names, f"got: {names[:10]}")
check("'sklearn.ensemble.' returns 'GradientBoostingClassifier'",
      "GradientBoostingClassifier" in names)

print("\n=== 8. 'scipy.stats.' returns distributions ===")
r = complete("scipy.stats.")
names = [c["name"] for c in r["completions"]]
check("'scipy.stats.' returns 'norm'", "norm" in names, f"got: {names[:10]}")
check("'scipy.stats.' returns 'ttest_ind'", "ttest_ind" in names)

print("\n=== 9. Source attribution ===")
r = complete("imp")
check("response has 'source' field", "source" in r)
check("response has 'prefix' field", "prefix" in r)
check("response has 'token' field", "token" in r)

print("\n=== 10. Bare single-char token does NOT trigger keyword fallback ===")
r = complete("i")  # only 1 char — threshold is >= 2
names = [c["name"] for c in r["completions"]]
check("single-char 'i' returns no completions (below threshold)",
      len(names) == 0,
      f"got: {names[:5]}")

print("\n=== 11. Snippet names with spaces are recognized as 'snippet' type ===")
r = complete("imp")
snippets = [c for c in r["completions"] if c["type"] == "snippet"]
check(
    "All snippet-typed entries contain a space",
    all(" " in s["name"] for s in snippets),
    f"got: {snippets}",
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
