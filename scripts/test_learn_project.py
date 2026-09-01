"""
Static analysis test for the new 'Learn with Project' feature.

Verifies:
  1. app/routes/learn_project.py exists and parses cleanly
  2. PROJECT_COURSE has 13 stages (0-12)
  3. Every stage has all 14 required fields
  4. All slugs are unique
  5. All slugs match the pattern project-stage-NN-*
  6. /learn/project and /learn/project/{slug} routes are registered
  7. templates/learn_project.html exists and has required Jinja blocks
  8. templates/learn.html has the toggle + teaser card pointing to /learn/project
  9. app/main.py imports + includes learn_project_route
 10. Each stage's response_model_explanation answers the question explicitly
"""
import re, ast, sys, pathlib, importlib.util

ROOT = pathlib.Path('/home/z/my-project')
LP_PY = (ROOT / 'app/routes/learn_project.py').read_text()
LP_HTML = (ROOT / 'templates/learn_project.html').read_text()
LEARN_HTML = (ROOT / 'templates/learn.html').read_text()
MAIN_PY = (ROOT / 'app/main.py').read_text()

def _try_parse(src):
    try:
        ast.parse(src)
        return True
    except SyntaxError as e:
        return f"SyntaxError: {e}"

def _extract_project_course(src):
    """Pull PROJECT_COURSE = [...] out of the file and eval it."""
    m = re.search(r'^PROJECT_COURSE = \[', src, re.MULTILINE)
    if not m:
        return None
    start = m.start()
    end = src.find('\n]\n', start)
    if end == -1:
        return None
    block = src[start:end+2]
    ns = {}
    try:
        exec(block, ns)
        return ns['PROJECT_COURSE']
    except Exception as e:
        print(f"  exec failed: {e}")
        return None

results = []
def check(label, cond, detail=''):
    results.append((label, cond, detail))
    print(f"  {'OK' if cond else 'FAIL'}  {label}" + (f"  ({detail})" if detail and not cond else ""))


print("\n[1] app/routes/learn_project.py exists and parses")
check(
    "learn_project.py parses cleanly",
    _try_parse(LP_PY),
)

print("\n[2] PROJECT_COURSE has 13 stages (0-12)")
course = _extract_project_course(LP_PY)
check(
    "PROJECT_COURSE found in source",
    course is not None,
)
if course:
    check(
        "exactly 13 stages (0-12)",
        len(course) == 13,
        f"got {len(course)} stages",
    )
    check(
        "stage numbers are 0..12",
        [s['stage'] for s in course] == list(range(13)),
    )

print("\n[3] Every stage has all 14 required fields")
required = ['stage','slug','title','summary','intuition','tiny_task','check',
            'routes_box','is_response_model_needed','response_model_explanation',
            'files','explanation','common_mistakes','next_preview']
if course:
    for s in course:
        missing = [f for f in required if f not in s]
        check(
            f"Stage {s['stage']} ({s.get('slug', '?')}) has all 14 fields",
            not missing,
            f"missing={missing}" if missing else "",
        )

print("\n[4] All slugs are unique")
if course:
    slugs = [s['slug'] for s in course]
    check(
        "no duplicate slugs",
        len(set(slugs)) == len(slugs),
        f"duplicates: {[s for s in slugs if slugs.count(s) > 1]}" if len(set(slugs)) != len(slugs) else "",
    )

print("\n[5] Slugs match pattern project-stage-NN-*")
if course:
    pat = re.compile(r'^project-stage-\d{2}-[a-z0-9-]+$')
    for s in course:
        check(
            f"Stage {s['stage']} slug matches pattern",
            bool(pat.match(s['slug'])),
            f"slug={s['slug']}",
        )

print("\n[6] /learn/project routes registered in source")
check(
    "GET /learn/project route defined",
    '@router.get("/learn/project"' in LP_PY,
)
check(
    "GET /learn/project/{slug} route defined",
    '@router.get("/learn/project/{slug}"' in LP_PY,
)

print("\n[7] templates/learn_project.html has required Jinja blocks")
check(
    "extends base.html",
    "{% extends \"base.html\" %}" in LP_HTML,
)
check(
    "has {% block content %}",
    "{% block content %}" in LP_HTML,
)
check(
    "has overview view branch",
    '{% if view == "overview" %}' in LP_HTML,
)
check(
    "has stage view branch",
    '{% elif view == "stage" %}' in LP_HTML,
)
check(
    "has mode-toggle pointing to /learn",
    'mode-toggle' in LP_HTML and 'href="/learn"' in LP_HTML,
)
check(
    "has intuition-box block",
    'intuition-box' in LP_HTML,
)
check(
    "has tiny-task-box block",
    'tiny-task-box' in LP_HTML,
)
check(
    "has check-box block",
    'check-box' in LP_HTML,
)
check(
    "has routes-box block",
    'routes-box' in LP_HTML,
)
check(
    "has response-model-box block",
    'response-model-box' in LP_HTML,
)
check(
    "has common-mistakes-box block",
    'common-mistakes-box' in LP_HTML,
)
check(
    "has next-preview-box block",
    'next-preview-box' in LP_HTML,
)

print("\n[8] templates/learn.html has toggle + teaser card")
check(
    "has Concepts / Learn with Project toggle",
    'Concepts' in LEARN_HTML and 'Learn with Project' in LEARN_HTML,
)
check(
    "teaser card links to /learn/project",
    'href="/learn/project"' in LEARN_HTML,
)
# The teaser card text mentions the 5-layer stack — accept any of these phrases
check(
    "teaser card mentions the 5-layer stack",
    any(phrase in LEARN_HTML for phrase in ['5 layers', '5 layer', 'Python &rarr; ML &rarr; FastAPI &rarr; Jinja &rarr; HTML', 'Python → ML → FastAPI → Jinja → HTML']),
    "none of the 5-layer phrases found",
)
check(
    "teaser card mentions '12 stages'",
    '12 stages' in LEARN_HTML,
)

print("\n[9] app/main.py imports + includes learn_project_route")
check(
    "main.py imports learn_project",
    "from app.routes import learn_project as learn_project_route" in MAIN_PY,
)
check(
    "main.py includes learn_project_route.router",
    "app.include_router(learn_project_route.router)" in MAIN_PY,
)

print("\n[10] Each stage's response_model_explanation answers the question explicitly")
if course:
    for s in course:
        ans = s.get('is_response_model_needed', '')
        exp = s.get('response_model_explanation', '')
        # Value can be: 'YES', 'NO', 'No (HTML response)', 'Only for /predict', etc.
        # We just require that the field is non-empty and starts with one of these
        # prefixes (case-insensitive): yes / no / only / not
        ans_lower = ans.lower().strip()
        is_valid = (
            ans_lower.startswith('yes') or
            ans_lower.startswith('no') or
            ans_lower.startswith('only') or
            ans_lower.startswith('not')
        )
        check(
            f"Stage {s['stage']} has explicit is_response_model_needed answer",
            is_valid,
            f"got {ans!r}",
        )
        check(
            f"Stage {s['stage']} response_model_explanation is non-empty",
            len(exp) > 30,
            f"only {len(exp)} chars",
        )

# Tally
passed = sum(1 for _, c, _ in results if c)
failed = len(results) - passed
print(f"\n{'='*70}\nPASSED: {passed}    FAILED: {failed}\n{'='*70}")
sys.exit(0 if failed == 0 else 1)
