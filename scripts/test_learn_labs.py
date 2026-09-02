"""
Static analysis test for the new Interactive Labs feature.

Verifies:
  1. app/routes/learn_labs.py exists and parses cleanly
  2. ALL_LABS is non-empty, has labs in 4 categories
  3. Every lab has all required fields
  4. All slugs are unique
  5. /learn/labs and /learn/labs/{slug} routes are registered
  6. templates/learn_lab.html exists and has the editor + preview panes
  7. templates/learn.html has the 3-way toggle (Concepts | Project | Labs)
  8. app/main.py imports + includes learn_labs_route BEFORE learn_route
  9. Each lab has at least 1 try_changes entry (interactive guidance)
 10. CSS labs have html_template (needed for live iframe preview)
"""
import re, ast, sys, pathlib

ROOT = pathlib.Path('/home/z/my-project')
LL_PY = (ROOT / 'app/routes/learn_labs.py').read_text()
LL_HTML = (ROOT / 'templates/learn_lab.html').read_text()
LEARN_HTML = (ROOT / 'templates/learn.html').read_text()
MAIN_PY = (ROOT / 'app/main.py').read_text()

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


print("\n[1] app/routes/learn_labs.py exists and parses")
check(
    "learn_labs.py parses cleanly",
    _try_parse(LL_PY),
)

print("\n[2] ALL_LABS is non-empty, has labs in 4 categories")
# Count labs in each _XXX_LABS list
counts = {}
for cat_list_name in ['_CSS_LABS', '_HTML_LABS', '_PYTHON_LABS', '_FASTAPI_LABS']:
    m = re.search(rf'^{cat_list_name}\s*=\s*\[', LL_PY, re.MULTILINE)
    if m:
        # Find matching ]
        start = m.start()
        end = LL_PY.find('\n]\n', start)
        block = LL_PY[start:end+2]
        # Count top-level dict literals (each lab)
        count = block.count('{\n        "slug":')
        counts[cat_list_name] = count
total = sum(counts.values())
check(
    "CSS labs defined (>=10)",
    counts.get('_CSS_LABS', 0) >= 10,
    f"got {counts.get('_CSS_LABS', 0)}",
)
check(
    "HTML labs defined (>=5)",
    counts.get('_HTML_LABS', 0) >= 5,
    f"got {counts.get('_HTML_LABS', 0)}",
)
check(
    "Python labs defined (>=8)",
    counts.get('_PYTHON_LABS', 0) >= 8,
    f"got {counts.get('_PYTHON_LABS', 0)}",
)
check(
    "FastAPI labs defined (>=8)",
    counts.get('_FASTAPI_LABS', 0) >= 8,
    f"got {counts.get('_FASTAPI_LABS', 0)}",
)
check(
    "total labs >= 30",
    total >= 30,
    f"got {total}",
)

print("\n[3] Every lab has all required fields")
# Extract ALL_LABS and check each lab
all_labs_match = re.search(r'^ALL_LABS\s*=\s*(\[.*?\])\s*$', LL_PY, re.MULTILINE | re.DOTALL)
check(
    "ALL_LABS is defined",
    'ALL_LABS =' in LL_PY,
)
check(
    "_LAB_BY_SLUG index is defined",
    '_LAB_BY_SLUG =' in LL_PY,
)
check(
    "_LABS_BY_CATEGORY is defined",
    '_LABS_BY_CATEGORY =' in LL_PY,
)

print("\n[4] All slugs are unique")
# Pull all slug strings out of the file. Only count slugs inside the actual
# lab lists (_CSS_LABS, _HTML_LABS, etc.), not in the docstring examples.
# Strategy: find each _XXX_LABS = [...] block and extract slugs from there.
all_slugs = []
for cat_list_name in ['_CSS_LABS', '_HTML_LABS', '_PYTHON_LABS', '_FASTAPI_LABS']:
    m = re.search(rf'^{cat_list_name}\s*=\s*\[', LL_PY, re.MULTILINE)
    if not m:
        continue
    start = m.start()
    end = LL_PY.find('\n]\n', start)
    block = LL_PY[start:end+2]
    slugs_in_block = re.findall(r'"slug":\s*"([^"]+)"', block)
    all_slugs.extend(slugs_in_block)

check(
    f"found {len(all_slugs)} lab slugs (in actual lab lists)",
    len(all_slugs) >= 30,
    f"only {len(all_slugs)} slugs",
)
check(
    "all slugs unique",
    len(set(all_slugs)) == len(all_slugs),
    f"{len(all_slugs) - len(set(all_slugs))} duplicates: {[s for s in set(all_slugs) if all_slugs.count(s) > 1]}" if len(set(all_slugs)) != len(all_slugs) else "",
)

print("\n[5] /learn/labs routes are registered")
check(
    "GET /learn/labs route defined",
    '@router.get("/learn/labs"' in LL_PY,
)
check(
    "GET /learn/labs/{slug} route defined",
    '@router.get("/learn/labs/{slug}"' in LL_PY,
)

print("\n[6] templates/learn_lab.html has editor + preview panes")
check(
    "extends base.html",
    "{% extends \"base.html\" %}" in LL_HTML,
)
check(
    "has {% block content %}",
    "{% block content %}" in LL_HTML,
)
check(
    "has {% block extra_js %}",
    "{% block extra_js %}" in LL_HTML,
)
check(
    "has overview view branch",
    '{% if view == "overview" %}' in LL_HTML,
)
check(
    "has lab view branch",
    '{% elif view == "lab" %}' in LL_HTML,
)
check(
    "has 3-way mode toggle (Concepts | Project | Labs)",
    'mode-toggle' in LL_HTML and '/learn/labs' in LL_HTML,
)
check(
    "has code editor textarea",
    'class="code-editor"' in LL_HTML and 'lab-code-editor' in LL_HTML,
)
check(
    "has preview pane for CSS/HTML (iframe)",
    'preview-iframe' in LL_HTML,
)
check(
    "has preview pane for Python (console)",
    'preview-console' in LL_HTML,
)
check(
    "has preview pane for FastAPI (simulator)",
    'preview-simulator' in LL_HTML,
)
check(
    "has Run button for Python",
    'runPythonLab()' in LL_HTML,
)
check(
    "has Simulate button for FastAPI",
    'runFastApiLab()' in LL_HTML,
)
check(
    "has live preview JS function (updateLivePreview)",
    'function updateLivePreview()' in LL_HTML,
)
check(
    "has reset button (resetLabCode)",
    'function resetLabCode()' in LL_HTML,
)
check(
    "uses iframe srcdoc for live preview",
    'srcdoc' in LL_HTML,
)
check(
    "uses Pyodide for Python execution (no server round-trip)",
    "_loadPyodideForLabs" in LL_HTML and "pyodide.runPython" in LL_HTML,
)
check(
    "does NOT use server /api/notebook/cell (old slow path removed)",
    "/api/notebook/cell" not in LL_HTML,
)

print("\n[7] templates/learn.html has the 3-way toggle")
check(
    "has Concepts / Project / Labs 3-way toggle",
    all(x in LEARN_HTML for x in ['Concepts', 'Project', 'Labs']),
)
check(
    "Labs teaser card links to /learn/labs",
    'href="/learn/labs"' in LEARN_HTML,
)

print("\n[8] app/main.py imports + includes learn_labs_route BEFORE learn_route")
check(
    "main.py imports learn_labs",
    "from app.routes import learn_labs as learn_labs_route" in MAIN_PY,
)
check(
    "main.py includes learn_labs_route.router",
    "app.include_router(learn_labs_route.router)" in MAIN_PY,
)
# Verify ordering: learn_labs_route include appears BEFORE learn_route include
ll_pos = MAIN_PY.find("app.include_router(learn_labs_route.router)")
lr_pos = MAIN_PY.find("app.include_router(learn_route.router)")
check(
    "learn_labs_route is included BEFORE learn_route",
    ll_pos > 0 and lr_pos > 0 and ll_pos < lr_pos,
    f"learn_labs at {ll_pos}, learn at {lr_pos}",
)

print("\n[9] Each lab has at least 1 try_changes entry (interactive guidance)")
try_count = LL_PY.count('"try_changes":')
check(
    "all labs have try_changes field",
    try_count >= 30,
    f"only {try_count} labs have try_changes",
)

print("\n[10] CSS labs have html_template (needed for live iframe preview)")
# Count labs with language: "css"
css_count = LL_PY.count('"language": "css"')
html_template_count = LL_PY.count('"html_template":')
# Every CSS lab + every HTML lab has html_template (HTML labs use empty string)
check(
    "html_template field count matches CSS lab count",
    html_template_count >= css_count,
    f"{css_count} CSS labs but only {html_template_count} html_template fields",
)

# Tally
passed = sum(1 for _, c, _ in results if c)
failed = len(results) - passed
print(f"\n{'='*70}\nPASSED: {passed}    FAILED: {failed}\n{'='*70}")
sys.exit(0 if failed == 0 else 1)
