"""
OpenBenchML — 10-Step Build Course
===================================

A progressive, step-by-step course that teaches someone to build OpenBenchML
from scratch. Each step:

  1. Teaches ONE basic concept (Python / HTML / etc.)
  2. Shows the minimal pure-concept code
  3. Applies it to build one piece of OpenBenchML
  4. Gives a "try yourself" exercise
  5. Lists common mistakes
  6. Previews the next step

By step 10, the learner has a deployed app with auth, upload, benchmark,
leaderboard, live WebSocket, and a notebook kernel.
"""

BUILD_COURSE = {
    "category": "Build OpenBenchML \u2014 Step by Step",
    "slug": "build",
    "icon": "rocket",
    "color": "#a0c000",
    "blurb": "A 10-step course that builds OpenBenchML from scratch. Each step teaches one concept and adds one feature. By step 10, you have a deployed app.",
    "concepts": [
        # ─── Step 1 ─────────────────────────────────────────────────────
        {
            "step_number": 1,
            "slug": "build-step-01-fastapi-route",
            "title": "Your First FastAPI Route",
            "summary": "Start with one Python file. Define an async function, decorate it with @app.get, visit it in the browser. This is the atom of every web app.",
            "goal": "Run `python main.py`, open http://localhost:8000/health, and see {\"status\":\"ok\"} in the browser.",
            "concept_code": "# The basic concept: a function that returns data\n\ndef health():\n    return {'status': 'ok'}\n\nprint(health())  # {'status': 'ok'}\n\n# FastAPI adds two things:\n#   1. @app.get('/path') decorator  ->  registers the function as a route\n#   2. async  ->  the function can await I/O without blocking other requests",
            "files": [
                {
                    "name": "main.py",
                    "lang": "python",
                    "code": "# Step 1: A FastAPI app with one route\nfrom fastapi import FastAPI\nimport uvicorn\n\napp = FastAPI(title='OpenBenchML')\n\n@app.get('/health')\nasync def health():\n    return {'status': 'ok'}\n\nif __name__ == '__main__':\n    uvicorn.run(app, host='0.0.0.0', port=8000)",
                },
                {
                    "name": "run.sh",
                    "lang": "bash",
                    "code": "# Install FastAPI + uvicorn\npip install fastapi uvicorn\n\n# Run the server\npython main.py\n\n# In another terminal (or browser):\ncurl http://localhost:8000/health\n# {\"status\":\"ok\"}\n\n# FastAPI also gives you free docs at:\n# http://localhost:8000/docs",
                },
            ],
            "explanation": "Every web app is just functions that return data when a URL is hit. FastAPI's job is to (a) listen for HTTP requests, (b) match the URL to a registered function, (c) call that function, and (d) send the return value back as JSON. The @app.get('/health') decorator is what registers the function — without it, health() is just a regular Python function that nothing calls. The async keyword means the function can yield control to the event loop while waiting for I/O (database, HTTP, file) — so one worker can handle thousands of concurrent requests. In step 1, there's no I/O, so async is just a convention; it becomes essential in step 3 when we add a database.",
            "try_yourself": "Add a second route @app.get('/about') that returns {'name': 'OpenBenchML', 'version': '0.1'}. Visit http://localhost:8000/about. Then add @app.get('/users/{user_id}') that returns {'user_id': user_id} — notice FastAPI extracts the path parameter automatically.",
            "common_mistakes": [
                "Forgetting `async` (or `def`) — the function must be one or the other, FastAPI won't accept a bare expression.",
                "Running `python main.py` without installing fastapi + uvicorn first — `pip install fastapi uvicorn`.",
                "Using `return` with a string — FastAPI wraps dicts as JSON, but a bare string gets quoted twice. Always return a dict (or a Pydantic model).",
                "Binding to `host='127.0.0.1'` in production — use `0.0.0.0` so the app listens on all interfaces, or it's unreachable from outside the container.",
            ],
            "used_in": "app/main.py — the /health endpoint is exactly this. Every other route in the app follows the same pattern.",
        },
        # ─── Step 2 ─────────────────────────────────────────────────────
        {
            "step_number": 2,
            "slug": "build-step-02-html-template",
            "title": "HTML + Jinja2 Templates \u2014 Your First Page",
            "summary": "Return HTML instead of JSON. Jinja2 templates let you compose pages with {% extends %} (shared shell) and {{ var }} (inject data).",
            "goal": "Visit http://localhost:8000/ and see a styled HTML landing page with your app's name.",
            "concept_code": "# The basic concept: a template is an HTML file with holes\n\n# base.html defines the shell:\n#   <title>{% block title %}{% endblock %}</title>\n#   <body>{% block content %}{% endblock %}</body>\n\n# landing.html fills the holes:\n#   {% extends 'base.html' %}\n#   {% block title %}Home{% endblock %}\n#   {% block content %}<h1>{{ app_name }}</h1>{% endblock %}\n\n# {{ app_name }} is replaced by the value you pass from Python.\n# {% %} is for logic (extends, block, for, if). {{ }} is for values.",
            "files": [
                {
                    "name": "main.py",
                    "lang": "python",
                    "code": "# Step 2: Add HTML rendering on top of step 1\nfrom fastapi import FastAPI, Request\nfrom fastapi.responses import HTMLResponse\nfrom fastapi.templating import Jinja2Templates\nimport uvicorn\n\napp = FastAPI(title='OpenBenchML')\ntemplates = Jinja2Templates(directory='templates')\n\n@app.get('/health')\nasync def health():\n    return {'status': 'ok'}\n\n@app.get('/', response_class=HTMLResponse)\nasync def landing(request: Request):\n    # Pass variables to the template\n    return templates.TemplateResponse('landing.html', {\n        'request': request,           # required by Jinja2Templates\n        'app_name': 'OpenBenchML',\n        'tagline': 'Benchmark ML models in the browser',\n    })\n\nif __name__ == '__main__':\n    uvicorn.run(app, host='0.0.0.0', port=8000)",
                },
                {
                    "name": "templates/base.html",
                    "lang": "html",
                    "code": "<!DOCTYPE html>\n<html>\n<head>\n  <title>{% block title %}OpenBenchML{% endblock %}</title>\n  <style>\n    body { font-family: sans-serif; margin: 2rem; background: #fafafa; }\n    .nav { display: flex; gap: 1rem; margin-bottom: 2rem; }\n    .nav a { color: #a0c000; text-decoration: none; }\n  </style>\n</head>\n<body>\n  <nav class='nav'>\n    <a href='/'>Home</a>\n    <a href='/health'>Health</a>\n  </nav>\n  <main>\n    {% block content %}{% endblock %}\n  </main>\n</body>\n</html>",
                },
                {
                    "name": "templates/landing.html",
                    "lang": "html",
                    "code": "{% extends 'base.html' %}\n\n{% block title %}{{ app_name }} \u2014 Home{% endblock %}\n\n{% block content %}\n  <h1>{{ app_name }}</h1>\n  <p>{{ tagline }}</p>\n  <p>This is step 2 of the build course. You now have a styled HTML page.</p>\n{% endblock %}",
                },
            ],
            "explanation": "Templates separate structure (HTML) from data (Python). The base.html file is the shell — every page shares the same <head>, nav, and footer. Each child template (landing.html) extends base.html and fills in named blocks. This is how OpenBenchML has 22 templates that all look like one app: they all extend base.html. The {{ app_name }} syntax is Jinja2's way of saying 'insert the value of app_name here'. When the route calls TemplateResponse, Jinja2 reads landing.html, follows the extends to base.html, fills the blocks, replaces the {{ }} variables, and returns a complete HTML string. FastAPI sends that string to the browser with Content-Type: text/html.",
            "try_yourself": "Add a `features` list to the TemplateResponse call: `'features': ['Upload models', 'Benchmark', 'Leaderboard']`. In landing.html, render it with `{% for f in features %}<li>{{ f }}</li>{% endfor %}`. Wrap it in a <ul>.",
            "common_mistakes": [
                "Forgetting `{% endblock %}` — Jinja2 will throw a TemplateSyntaxError.",
                "Not passing `request` to TemplateResponse — Jinja2Templates requires it since FastAPI 0.85.",
                "Putting templates in the wrong folder — `Jinja2Templates(directory='templates')` expects a `templates/` folder next to main.py.",
                "Using `{{ app_name }}` in base.html when app_name is only passed to landing.html — variables don't flow up to the parent template unless you pass them explicitly.",
            ],
            "used_in": "templates/base.html is the shell every page extends. app/main.py uses Jinja2Templates to render 22 different templates.",
        },
        # ─── Step 3 ─────────────────────────────────────────────────────
        {
            "step_number": 3,
            "slug": "build-step-03-database-user",
            "title": "SQLite + SQLAlchemy \u2014 Store Users",
            "summary": "Data must survive between requests. Define a User class that maps to a DB table, create a /register route that saves a new user.",
            "goal": "Fill a register form, submit, and see the user saved in the SQLite database file (openbenchml.db).",
            "concept_code": "# The basic concept: an ORM maps a Python class to a DB table\n\nfrom sqlalchemy import Column, Integer, String, create_engine\nfrom sqlalchemy.orm import declarative_base, sessionmaker\n\nBase = declarative_base()\n\nclass User(Base):\n    __tablename__ = 'users'\n    id = Column(Integer, primary_key=True)\n    username = Column(String, unique=True)\n\nengine = create_engine('sqlite:///app.db')\nBase.metadata.create_all(engine)   # runs CREATE TABLE\n\nSession = sessionmaker(bind=engine)\ndb = Session()\n\n# Create\nuser = User(username='ada')\ndb.add(user)\ndb.commit()              # writes to disk\nprint(user.id)           # 1 (auto-assigned by DB)\n\n# Read\nall_users = db.query(User).all()\nprint([u.username for u in all_users])  # ['ada']",
            "files": [
                {
                    "name": "database.py",
                    "lang": "python",
                    "code": "# Step 3: Database setup\nfrom sqlalchemy import Column, Integer, String, create_engine\nfrom sqlalchemy.orm import declarative_base, sessionmaker\n\nBase = declarative_base()\n\nclass User(Base):\n    __tablename__ = 'users'\n    id = Column(Integer, primary_key=True)\n    username = Column(String, unique=True, nullable=False)\n    password_hash = Column(String, nullable=False)  # plain text for now; step 4 fixes this\n\nengine = create_engine('sqlite:///openbenchml.db', connect_args={'check_same_thread': False})\nBase.metadata.create_all(engine)\nSessionLocal = sessionmaker(bind=engine)",
                },
                {
                    "name": "main.py",
                    "lang": "python",
                    "code": "# Step 3: Add /register on top of steps 1-2\nfrom fastapi import FastAPI, Request, Form, Depends\nfrom fastapi.responses import HTMLResponse, RedirectResponse\nfrom fastapi.templating import Jinja2Templates\nfrom sqlalchemy.orm import Session\nimport uvicorn\n\nfrom database import User, SessionLocal\n\napp = FastAPI(title='OpenBenchML')\ntemplates = Jinja2Templates(directory='templates')\n\ndef get_db():\n    db = SessionLocal()\n    try:\n        yield db\n    finally:\n        db.close()\n\n@app.get('/health')\nasync def health():\n    return {'status': 'ok'}\n\n@app.get('/', response_class=HTMLResponse)\nasync def landing(request: Request):\n    return templates.TemplateResponse('landing.html', {\n        'request': request, 'app_name': 'OpenBenchML',\n    })\n\n@app.get('/register', response_class=HTMLResponse)\nasync def register_form(request: Request):\n    return templates.TemplateResponse('register.html', {'request': request})\n\n@app.post('/register')\nasync def register(\n    request: Request,\n    username: str = Form(...),\n    password: str = Form(...),\n    db: Session = Depends(get_db),\n):\n    # Check if username exists\n    existing = db.query(User).filter(User.username == username).first()\n    if existing:\n        return {'error': 'username taken'}\n    # Save the new user\n    user = User(username=username, password_hash=password)  # step 4: hash this\n    db.add(user)\n    db.commit()\n    return RedirectResponse(url='/', status_code=303)\n\nif __name__ == '__main__':\n    uvicorn.run(app, host='0.0.0.0', port=8000)",
                },
                {
                    "name": "templates/register.html",
                    "lang": "html",
                    "code": "{% extends 'base.html' %}\n{% block title %}Register{% endblock %}\n{% block content %}\n  <h1>Register</h1>\n  <form method='post' action='/register'>\n    <input type='text' name='username' placeholder='Username' required>\n    <input type='password' name='password' placeholder='Password' required>\n    <button type='submit'>Sign Up</button>\n  </form>\n{% endblock %}",
                },
            ],
            "explanation": "A database is the difference between a toy app and a real app. Without one, every restart wipes your users. SQLAlchemy is an ORM (Object-Relational Mapper) — you write a Python class with Column-typed attributes, and it generates the CREATE TABLE SQL + translates .query()/.add()/.commit() into SQL under the hood. The User class maps to a `users` table with id, username, password_hash columns. create_all(engine) inspects the model and runs CREATE TABLE if it doesn't exist. The get_db() dependency gives each request its own Session and closes it automatically — sessions are not thread-safe, so one-per-request is mandatory. The /register route receives the form fields via Form(...), creates a User object, db.add() stages it, db.commit() writes it to disk. In step 4 we'll hash the password (storing plaintext is a security disaster).",
            "try_yourself": "Add an `email` column to the User model. Add an email field to the register form. After registering a user, add a @app.get('/users') route that returns `[{u.id, u.username, u.email} for u in db.query(User).all()]` as JSON.",
            "common_mistakes": [
                "Forgetting `db.commit()` — the user is staged in memory but never written to disk. The row disappears when the session closes.",
                "Not calling `create_all(engine)` — the table doesn't exist, so INSERT fails with `no such table: users`.",
                "Sharing one Session across requests — sessions are not thread-safe. Use `Depends(get_db)` so each request gets its own.",
                "Using `connect_args={'check_same_thread': False}` without understanding it — it's required for SQLite + FastAPI because FastAPI uses threads. In production with Postgres, you don't need it.",
            ],
            "used_in": "app/database/models.py defines User, Model, Dataset, BenchmarkJob, LeaderboardEntry, Competition, Comment. app/database/db.py creates the engine + SessionLocal. app/routes/auth.py uses get_db for register/login.",
        },
        # ─── Step 4 ─────────────────────────────────────────────────────
        {
            "step_number": 4,
            "slug": "build-step-04-auth-jwt",
            "title": "Forms + Password Hashing + JWT \u2014 Login",
            "summary": "Hash passwords (never store plaintext). Issue a signed JWT. Set it as an httpOnly cookie. Protect routes by verifying the cookie.",
            "goal": "Register a user, log in, visit /dashboard and see your username. Visit /dashboard without logging in \u2014 get redirected to /login.",
            "concept_code": "# The basic concept: a JWT is a signed JSON payload\n\nimport jwt, secrets\nfrom datetime import datetime, timedelta, timezone\n\nSECRET = secrets.token_hex(32)  # random 64-char hex string\n\n# Create a token\npayload = {\n    'sub': 'ada',                              # who is this?\n    'exp': datetime.now(timezone.utc) + timedelta(hours=1),  # expires in 1h\n}\ntoken = jwt.encode(payload, SECRET, algorithm='HS256')\n# token = 'eyJhbGciOiJIUzI1NiIs...'\n\n# Verify the token\ntry:\n    decoded = jwt.decode(token, SECRET, algorithms=['HS256'])\n    print(decoded['sub'])  # 'ada'\nexcept jwt.ExpiredSignatureError:\n    print('token expired')\nexcept jwt.InvalidTokenError:\n    print('bad token')\n\n# The signature proves the token wasn't tampered with.\n# Only someone with SECRET can create valid tokens.",
            "files": [
                {
                    "name": "auth.py",
                    "lang": "python",
                    "code": "# Step 4: Password hashing + JWT helpers\nimport secrets\nfrom datetime import datetime, timedelta, timezone\nfrom jose import jwt, JWTError\nfrom passlib.context import CryptContext\n\nSECRET_KEY = secrets.token_hex(32)  # in production, load from env var\nALGORITHM = 'HS256'\npwd_ctx = CryptContext(schemes=['bcrypt'], deprecated='auto')\n\ndef hash_password(plain: str) -> str:\n    return pwd_ctx.hash(plain)\n\ndef verify_password(plain: str, hashed: str) -> bool:\n    return pwd_ctx.verify(plain, hashed)\n\ndef make_token(username: str) -> str:\n    payload = {\n        'sub': username,\n        'exp': datetime.now(timezone.utc) + timedelta(hours=24),\n    }\n    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)\n\ndef decode_token(token: str) -> str | None:\n    try:\n        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])\n        return payload['sub']\n    except JWTError:\n        return None",
                },
                {
                    "name": "main.py",
                    "lang": "python",
                    "code": "# Step 4: Add /login + /dashboard on top of steps 1-3\nfrom fastapi import FastAPI, Request, Form, Depends, HTTPException\nfrom fastapi.responses import HTMLResponse, RedirectResponse\nfrom sqlalchemy.orm import Session\n\nfrom database import User, SessionLocal\nfrom auth import hash_password, verify_password, make_token, decode_token\n\n# ... (keep /health, /, /register from previous steps) ...\n\n@app.post('/register')\nasync def register(\n    username: str = Form(...),\n    password: str = Form(...),\n    db: Session = Depends(get_db),\n):\n    existing = db.query(User).filter(User.username == username).first()\n    if existing:\n        return {'error': 'username taken'}\n    # NOW we hash the password (step 3 stored plaintext \u2014 never do that!)\n    user = User(username=username, password_hash=hash_password(password))\n    db.add(user); db.commit()\n    return RedirectResponse(url='/', status_code=303)\n\n@app.get('/login', response_class=HTMLResponse)\nasync def login_form(request: Request):\n    return templates.TemplateResponse('login.html', {'request': request})\n\n@app.post('/login')\nasync def login(\n    request: Request,\n    username: str = Form(...),\n    password: str = Form(...),\n    db: Session = Depends(get_db),\n):\n    user = db.query(User).filter(User.username == username).first()\n    if not user or not verify_password(password, user.password_hash):\n        return {'error': 'bad credentials'}\n    # Issue a JWT and set it as an httpOnly cookie\n    token = make_token(user.username)\n    response = RedirectResponse(url='/dashboard', status_code=303)\n    response.set_cookie(\n        'access_token', token,\n        httponly=True,      # JS can't read it \u2014 XSS-safe\n        samesite='lax',     # CSRF defence\n        max_age=86400,      # 24 hours\n    )\n    return response\n\n@app.get('/dashboard', response_class=HTMLResponse)\nasync def dashboard(request: Request, db: Session = Depends(get_db)):\n    # Read the cookie, verify the JWT\n    token = request.cookies.get('access_token')\n    username = decode_token(token) if token else None\n    if not username:\n        return RedirectResponse(url='/login?next=/dashboard', status_code=303)\n    user = db.query(User).filter(User.username == username).first()\n    return templates.TemplateResponse('dashboard.html', {\n        'request': request, 'user': user,\n    })",
                },
                {
                    "name": "templates/login.html",
                    "lang": "html",
                    "code": "{% extends 'base.html' %}\n{% block title %}Login{% endblock %}\n{% block content %}\n  <h1>Login</h1>\n  <form method='post' action='/login'>\n    <input type='text' name='username' placeholder='Username' required>\n    <input type='password' name='password' placeholder='Password' required>\n    <button type='submit'>Log In</button>\n  </form>\n  <p>No account? <a href='/register'>Register</a></p>\n{% endblock %}",
                },
            ],
            "explanation": "Auth has three layers: (1) Password hashing — bcrypt turns 'secret' into '$2b$12$N9q...' (a salted hash). You can't reverse it. On login, hash the submitted password the same way and compare. Even if your DB leaks, attackers can't recover the plaintext passwords. (2) JWT — after login, the server creates a signed JSON payload {sub: username, exp: +24h}. The signature (HS256 + SECRET_KEY) proves the token wasn't tampered with. Only someone with SECRET_KEY can forge tokens. (3) httpOnly cookie — the JWT is stored in a cookie that JavaScript cannot read. This defeats XSS token theft: even if an attacker injects JS into your page, they can't steal the cookie. Every request automatically sends the cookie, so the server just decodes it to identify the user. The /dashboard route reads the cookie, verifies the JWT, and redirects to /login if anything fails.",
            "try_yourself": "Add a /logout route that deletes the cookie: `response.delete_cookie('access_token')`. Add a 'Log Out' link to base.html that only shows when the user is logged in (pass a `user` variable to every template).",
            "common_mistakes": [
                "Storing plaintext passwords — NEVER do this. Always `hash_password(password)` before saving. If your DB leaks, every user is compromised.",
                "Using a short or hardcoded SECRET_KEY — if it's 'secret' or 'changeme', attackers can forge tokens. Use `secrets.token_hex(32)` and load from env var in prod.",
                "Missing `httponly=True` on the cookie — without it, `document.cookie` in JS can read the JWT. Any XSS = account takeover.",
                "Not handling token expiry — `jwt.decode` raises `ExpiredSignatureError`. Catch it and treat as 'not logged in', not a 500.",
            ],
            "used_in": "app/routes/auth.py implements register/login/logout. app/services/auth_service.py has hash/verify/make_token/decode. get_current_user_from_cookie is the dependency used on every protected route.",
        },
        # ─── Step 5 ─────────────────────────────────────────────────────
        {
            "step_number": 5,
            "slug": "build-step-05-file-upload",
            "title": "File Upload + Pickle \u2014 Upload a Model",
            "summary": "Accept a .pkl file via multipart form, save it to disk with a UUID name, store metadata in the DB. This is how users submit trained models.",
            "goal": "Train a sklearn model, pickle it, upload via the form, and see it listed in /my-models.",
            "concept_code": "# The basic concept: pickle saves a Python object to a file\n\nimport pickle\nfrom sklearn.linear_model import LinearRegression\nimport numpy as np\n\n# Train a model\nmodel = LinearRegression()\nX = np.array([[1], [2], [3]])\ny = np.array([2, 4, 6])\nmodel.fit(X, y)\n\n# Save it to a file\nwith open('model.pkl', 'wb') as f:\n    pickle.dump(model, f)\n\n# Later (even in a different process): load it back\nwith open('model.pkl', 'rb') as f:\n    loaded = pickle.load(f)\nprint(loaded.predict([[5]]))  # [10.]\n\n# The .pkl file contains the trained model's weights + structure.\n# You can upload it, download it, and reuse it anywhere.",
            "files": [
                {
                    "name": "main.py",
                    "lang": "python",
                    "code": "# Step 5: Add /upload + /my-models on top of steps 1-4\nimport uuid, shutil, pickle\nfrom pathlib import Path\nfrom fastapi import UploadFile, File, Form, Depends\nfrom sqlalchemy.orm import Session\nfrom sqlalchemy import Column, Integer, String, ForeignKey\n\n# Add to database.py:\n# class Model(Base):\n#     __tablename__ = 'models'\n#     id = Column(Integer, primary_key=True)\n#     name = Column(String)\n#     filename = Column(String)  # UUID.pkl on disk\n#     owner_id = Column(Integer, ForeignKey('users.id'))\n\nUPLOAD_DIR = Path('uploads')\nUPLOAD_DIR.mkdir(exist_ok=True)\n\n@app.get('/upload', response_class=HTMLResponse)\nasync def upload_form(request: Request):\n    return templates.TemplateResponse('upload.html', {'request': request})\n\n@app.post('/upload')\nasync def upload(\n    request: Request,\n    name: str = Form(...),\n    file: UploadFile = File(...),\n    db: Session = Depends(get_db),\n):\n    # 1. Validate the file is a .pkl\n    if not file.filename.endswith('.pkl'):\n        return {'error': 'must be a .pkl file'}\n\n    # 2. Verify it's a valid pickle by loading it\n    try:\n        data = await file.read()\n        model = pickle.loads(data)  # load from bytes\n        assert hasattr(model, 'predict')\n    except Exception:\n        return {'error': 'invalid pickle or not a model'}\n\n    # 3. Save with a UUID name (never trust user's filename)\n    safe_name = f'{uuid.uuid4().hex}.pkl'\n    with open(UPLOAD_DIR / safe_name, 'wb') as f:\n        f.write(data)\n\n    # 4. Store metadata in DB\n    from database import Model, User\n    token = request.cookies.get('access_token')\n    username = decode_token(token)\n    user = db.query(User).filter(User.username == username).first()\n    m = Model(name=name, filename=safe_name, owner_id=user.id)\n    db.add(m); db.commit()\n    return RedirectResponse(url='/my-models', status_code=303)\n\n@app.get('/my-models', response_class=HTMLResponse)\nasync def my_models(request: Request, db: Session = Depends(get_db)):\n    from database import Model, User\n    token = request.cookies.get('access_token')\n    username = decode_token(token)\n    if not username:\n        return RedirectResponse(url='/login', status_code=303)\n    user = db.query(User).filter(User.username == username).first()\n    models = db.query(Model).filter(Model.owner_id == user.id).all()\n    return templates.TemplateResponse('my_models.html', {\n        'request': request, 'models': models,\n    })",
                },
                {
                    "name": "train_model.py",
                    "lang": "python",
                    "code": "# Train a model and save it as a .pkl \u2014 run this to create a file to upload\nimport pickle\nfrom sklearn.linear_model import LinearRegression\nimport numpy as np\n\nmodel = LinearRegression()\nX = np.array([[i] for i in range(100)])\ny = np.array([2 * i + 1 + np.random.normal(0, 0.5) for i in range(100)])\nmodel.fit(X, y)\nprint(f'R^2 = {model.score(X, y):.3f}')\n\nwith open('my_model.pkl', 'wb') as f:\n    pickle.dump(model, f)\nprint('saved my_model.pkl \u2014 upload this via the form')",
                },
                {
                    "name": "templates/upload.html",
                    "lang": "html",
                    "code": "{% extends 'base.html' %}\n{% block title %}Upload Model{% endblock %}\n{% block content %}\n  <h1>Upload a Model</h1>\n  <form method='post' action='/upload' enctype='multipart/form-data'>\n    <input type='text' name='name' placeholder='Model name' required>\n    <input type='file' name='file' accept='.pkl' required>\n    <button type='submit'>Upload</button>\n  </form>\n{% endblock %}",
                },
            ],
            "explanation": "Pickle is Python's serialization format — it turns any Python object (including a trained sklearn model) into a byte stream you can save to disk or send over a network. The upload flow: (1) The form has enctype='multipart/form-data' — WITHOUT it, the file isn't sent. (2) FastAPI's UploadFile streams the file; we read() it into bytes. (3) pickle.loads(data) verifies it's a real model with a .predict() method — never trust user uploads blindly. (4) We save with a UUID name (uuid.uuid4().hex) instead of the user's filename — this prevents path traversal attacks (../../etc/passwd) and filename collisions. (5) Metadata (name, filename, owner_id) goes in the DB; the actual .pkl goes on disk. Storing big binaries in the DB is a performance disaster.",
            "try_yourself": "Add a file-size limit: reject files > 50 MB. Read the Content-Length header from `file.size` before reading the bytes. Add a /download/{model_id} route that streams the .pkl back using FileResponse.",
            "common_mistakes": [
                "Missing `enctype='multipart/form-data'` on the form — the file silently isn't sent. The `file: UploadFile` parameter will be None.",
                "Trusting the user's filename — `file.filename` could be `../../etc/passwd`. ALWAYS generate a UUID name.",
                "Loading the whole file into memory — for large files, use `shutil.copyfileobj(file.file, dest)` to stream to disk. We read() here only because we need to verify the pickle.",
                "Not validating the pickle — `pickle.loads` can execute arbitrary code. In production, only accept pickles from trusted users, or use a safer format like ONNX or joblib with a hash check.",
            ],
            "used_in": "app/routes/models.py — /upload, /my-models, /download/{id}. app/database/models.py — Model table with owner_id, filename, name, benchmark_score.",
        },
        # ─── Step 6 ─────────────────────────────────────────────────────
        {
            "step_number": 6,
            "slug": "build-step-06-benchmark",
            "title": "Benchmark Engine \u2014 Run a Model on a Dataset",
            "summary": "Load the uploaded .pkl, load a holdout dataset, call model.predict(), compute accuracy/F1/RMSE. Save the result. This is the core of the platform.",
            "goal": "Upload a model, click 'Benchmark', and see an accuracy score. The score is saved to the DB and shown on the model's page.",
            "concept_code": "# The basic concept: evaluate a model on held-out data\n\nimport pickle, numpy as np\nfrom sklearn.metrics import accuracy_score\n\n# Load the model\nwith open('model.pkl', 'rb') as f:\n    model = pickle.load(f)\n\n# Load a holdout dataset (X_test, y_test)\nX_test = np.array([[1], [2], [3], [4], [5]])\ny_test = np.array([2, 4, 6, 8, 10])  # true labels\n\n# Predict\npredictions = model.predict(X_test)\nprint('predictions:', predictions)  # [2. 4. 6. 8. 10.]\n\n# Score (classification: accuracy; regression: MSE/R^2)\naccuracy = accuracy_score(y_test, predictions.round())\nprint(f'accuracy = {accuracy:.3f}')\n\n# The model never saw X_test during training \u2014 this is an honest score.\n# Scoring on training data is cheating (overfitting).",
            "files": [
                {
                    "name": "benchmark.py",
                    "lang": "python",
                    "code": "# Step 6: The benchmark engine\nimport pickle\nimport numpy as np\nfrom pathlib import Path\nfrom sklearn.metrics import accuracy_score, mean_squared_error, r2_score\n\ndef run_benchmark(model_path: str, dataset: dict) -> dict:\n    '''\n    model_path: path to a .pkl file containing a trained model\n    dataset: {'X_test': np.array, 'y_test': np.array, 'task': 'classification'|'regression'}\n    Returns: {'score': float, 'metric': str, 'predictions': list}\n    '''\n    # 1. Load the model\n    with open(model_path, 'rb') as f:\n        model = pickle.load(f)\n\n    # 2. Predict on the holdout set\n    predictions = model.predict(dataset['X_test'])\n\n    # 3. Score based on task type\n    if dataset['task'] == 'classification':\n        score = accuracy_score(dataset['y_test'], predictions)\n        metric = 'accuracy'\n    else:  # regression\n        score = r2_score(dataset['y_test'], predictions)\n        metric = 'r2'\n\n    return {\n        'score': float(score),\n        'metric': metric,\n        'n_samples': len(dataset['X_test']),\n    }\n\n# A built-in dataset for testing\nSAMPLE_DATASET = {\n    'X_test': np.array([[i] for i in range(100, 200)]),\n    'y_test': np.array([2 * i + 1 for i in range(100, 200)]),\n    'task': 'regression',\n}",
                },
                {
                    "name": "main.py",
                    "lang": "python",
                    "code": "# Step 6: Add /benchmark/{model_id} on top of steps 1-5\nfrom benchmark import run_benchmark, SAMPLE_DATASET\nfrom database import Model, BenchmarkJob  # add BenchmarkJob to models\n\n# Add to database.py:\n# class BenchmarkJob(Base):\n#     __tablename__ = 'benchmark_jobs'\n#     id = Column(Integer, primary_key=True)\n#     model_id = Column(Integer, ForeignKey('models.id'))\n#     score = Column(Float)\n#     metric = Column(String)\n#     created_at = Column(DateTime, default=datetime.utcnow)\n\n@app.post('/benchmark/{model_id}')\nasync def benchmark_model(model_id: int, db: Session = Depends(get_db)):\n    # 1. Find the model\n    model = db.query(Model).filter(Model.id == model_id).first()\n    if not model:\n        return {'error': 'model not found'}\n\n    # 2. Run the benchmark\n    model_path = UPLOAD_DIR / model.filename\n    result = run_benchmark(str(model_path), SAMPLE_DATASET)\n\n    # 3. Save the result\n    job = BenchmarkJob(\n        model_id=model.id,\n        score=result['score'],\n        metric=result['metric'],\n    )\n    db.add(job); db.commit()\n\n    # 4. Return the score\n    return {'model': model.name, 'score': result['score'], 'metric': result['metric']}",
                },
            ],
            "explanation": "Benchmarking is the scientific part of the platform. The flow: (1) Load the uploaded .pkl — pickle.load brings the trained model back into memory. (2) Load a holdout dataset that the model never saw during training. This is critical: scoring on training data is like grading a student on the exact questions they studied — it tells you nothing about real understanding. (3) model.predict(X_test) generates predictions. (4) Compare predictions to y_test using a metric: accuracy for classification (what fraction was correct), R² for regression (how much variance the model explains). (5) Save the result as a BenchmarkJob row. The key insight: the benchmark is reproducible — same model + same dataset = same score, every time. This is what makes leaderboards fair.",
            "try_yourself": "Add a second dataset (classification) with make_classification from sklearn. Detect the task type automatically by checking if y_test is integer-valued. Add precision and recall metrics for classification.",
            "common_mistakes": [
                "Scoring on training data — the model memorized it, so the score is artificially high. Always hold out a test set the model never saw.",
                "Not handling predict() shape — some models return (n, 1), others (n,). Use `.ravel()` or `.flatten()` to be safe.",
                "Loading the model on every request — pickle.load is slow (~100ms). Cache the loaded model in a dict keyed by filename.",
                "Not catching exceptions in predict() — a malformed model will crash the route. Wrap in try/except and return a 400 with the error message.",
            ],
            "used_in": "app/routes/benchmark.py — /benchmark/{id} route. app/benchmark_engine/ — evaluator.py computes metrics, loader.py loads datasets.",
        },
        # ─── Step 7 ─────────────────────────────────────────────────────
        {
            "step_number": 7,
            "slug": "build-step-07-leaderboard",
            "title": "Leaderboard \u2014 Rank Models by Score",
            "summary": "Query all BenchmarkJobs, join with Model, sort by score descending, render as an HTML table. The competitive heart of the platform.",
            "goal": "After benchmarking 2-3 models, visit /leaderboard and see them ranked from best to worst, with the score and model name.",
            "concept_code": "# The basic concept: sort a list by a key\n\nresults = [\n    {'model': 'random_forest', 'score': 0.92},\n    {'model': 'logistic',      'score': 0.81},\n    {'model': 'xgboost',        'score': 0.95},\n    {'model': 'knn',            'score': 0.74},\n]\n\n# Sort by score, descending\nranked = sorted(results, key=lambda r: r['score'], reverse=True)\nfor i, r in enumerate(ranked, 1):\n    print(f'{i}. {r[\"model\"]:20s} {r[\"score\"]:.3f}')\n\n# Output:\n# 1. xgboost              0.950\n# 2. random_forest        0.920\n# 3. logistic             0.810\n# 4. knn                  0.740\n\n# In SQL:  SELECT * FROM benchmark_jobs ORDER BY score DESC;",
            "files": [
                {
                    "name": "main.py",
                    "lang": "python",
                    "code": "# Step 7: Add /leaderboard on top of steps 1-6\nfrom sqlalchemy import desc\nfrom database import Model, BenchmarkJob, User\n\n@app.get('/leaderboard', response_class=HTMLResponse)\nasync def leaderboard(request: Request, db: Session = Depends(get_db)):\n    # Query: join BenchmarkJob + Model + User, order by score desc\n    rows = (db.query(BenchmarkJob, Model, User)\n              .join(Model, BenchmarkJob.model_id == Model.id)\n              .join(User, Model.owner_id == User.id)\n              .order_by(desc(BenchmarkJob.score))\n              .limit(100)\n              .all())\n\n    # Build a list of dicts for the template\n    entries = [{\n        'rank': i + 1,\n        'model_name': m.name,\n        'owner': u.username,\n        'score': round(b.score, 4),\n        'metric': b.metric,\n    } for i, (b, m, u) in enumerate(rows)]\n\n    return templates.TemplateResponse('leaderboard.html', {\n        'request': request, 'entries': entries,\n    })",
                },
                {
                    "name": "templates/leaderboard.html",
                    "lang": "html",
                    "code": "{% extends 'base.html' %}\n{% block title %}Leaderboard{% endblock %}\n{% block content %}\n  <h1>Leaderboard</h1>\n  {% if entries %}\n  <table style='width:100%; border-collapse:collapse;'>\n    <thead>\n      <tr style='border-bottom:2px solid #a0c000; text-align:left;'>\n        <th>Rank</th>\n        <th>Model</th>\n        <th>Owner</th>\n        <th>Score</th>\n        <th>Metric</th>\n      </tr>\n    </thead>\n    <tbody>\n      {% for e in entries %}\n      <tr style='border-bottom:1px solid #eee;'>\n        <td>{{ e.rank }}</td>\n        <td>{{ e.model_name }}</td>\n        <td>{{ e.owner }}</td>\n        <td>{{ e.score }}</td>\n        <td>{{ e.metric }}</td>\n      </tr>\n      {% endfor %}\n    </tbody>\n  </table>\n  {% else %}\n  <p>No benchmarks yet. Upload a model and run a benchmark!</p>\n  {% endif %}\n{% endblock %}",
                },
            ],
            "explanation": "A leaderboard is just a sorted, joined query rendered as a table. The SQL equivalent of our query is: `SELECT * FROM benchmark_jobs JOIN models ON ... JOIN users ON ... ORDER BY score DESC LIMIT 100`. SQLAlchemy translates the .join() + .order_by() + .limit() chain into that SQL. The key insight: do the sorting in the database, not in Python. The DB is optimized for sorting (indexes, etc.); pulling all rows into Python and calling sorted() is slow for large tables. The template uses {% for e in entries %} to render one <tr> per entry. The rank is just the loop index + 1 (Jinja's loop.index starts at 1, so we could use that instead). The {% if entries %} / {% else %} block shows an empty state when there's no data yet — important for new users.",
            "try_yourself": "Add a `?sort=asc` query parameter that reverses the sort order. Add a 'by date' option that sorts by created_at instead of score. Add a medal emoji for the top 3 (gold/silver/bronze).",
            "common_mistakes": [
                "Sorting in Python instead of SQL — `sorted(rows, key=...)` pulls every row into memory. Use `.order_by(desc(Score))` so the DB does it.",
                "N+1 queries — if you query BenchmarkJob then separately query Model for each one, you do 1 + N queries. Use `.join()` to do it in one query.",
                "Not handling ties — two models with the same score will get different ranks (1, 2) instead of (1, 1). Add a secondary sort key (e.g., earliest benchmark wins ties).",
                "Displaying raw floats — `0.9532146789` looks messy. Use `round(score, 4)` or Jinja's `{{ '%.3f' % e.score }}`.",
            ],
            "used_in": "app/routes/leaderboard.py — /leaderboard and /api/leaderboard. app/database/models.py — LeaderboardEntry table caches the top 100.",
        },
        # ─── Step 8 ─────────────────────────────────────────────────────
        {
            "step_number": 8,
            "slug": "build-step-08-websocket",
            "title": "WebSocket \u2014 Live Leaderboard Updates",
            "summary": "When a benchmark finishes, push the result to every connected browser instantly. No polling, no refresh, no lag.",
            "goal": "Open /leaderboard in two browser tabs. Benchmark a model in one tab. Both tabs update instantly with the new entry.",
            "concept_code": "# The basic concept: a WebSocket is a persistent bidirectional pipe\n\n# Server side\nfrom fastapi import WebSocket\n\n@app.websocket('/ws')\nasync def ws_endpoint(ws: WebSocket):\n    await ws.accept()           # handshake\n    while True:\n        msg = await ws.receive_text()   # wait for client\n        await ws.send_text('echo: ' + msg)  # send back\n\n# Client side (browser JS)\n# const ws = new WebSocket('ws://localhost:8000/ws');\n# ws.onmessage = (e) => console.log('got:', e.data);\n# ws.send('hello');\n\n# Unlike HTTP (request -> response), either side can send at any time.\n# The connection stays open until someone closes it.\n# This is how you push updates without the client asking.",
            "files": [
                {
                    "name": "main.py",
                    "lang": "python",
                    "code": "# Step 8: Add WebSocket broadcast on top of steps 1-7\nfrom fastapi import WebSocket, WebSocketDisconnect\nimport json\n\nclass ConnectionManager:\n    '''Tracks all connected WebSocket clients.'''\n    def __init__(self):\n        self.active: list[WebSocket] = []\n\n    async def connect(self, ws: WebSocket):\n        await ws.accept()\n        self.active.append(ws)\n\n    def disconnect(self, ws: WebSocket):\n        if ws in self.active:\n            self.active.remove(ws)\n\n    async def broadcast(self, msg: dict):\n        '''Send a message to every connected client.'''\n        text = json.dumps(msg)\n        for ws in list(self.active):  # copy \u2014 list may change during iteration\n            try:\n                await ws.send_text(text)\n            except Exception:\n                self.disconnect(ws)\n\nws_manager = ConnectionManager()\n\n@app.websocket('/ws/leaderboard')\nasync def ws_leaderboard(ws: WebSocket):\n    await ws_manager.connect(ws)\n    try:\n        while True:\n            await ws.receive_text()  # keep alive; ignore client msgs\n    except WebSocketDisconnect:\n        ws_manager.disconnect(ws)\n\n# Modify the /benchmark/{model_id} route from step 6:\n# After saving the BenchmarkJob, broadcast the new entry:\n#   await ws_manager.broadcast({\n#       'type': 'new_benchmark',\n#       'model': model.name,\n#       'score': result['score'],\n#   })",
                },
                {
                    "name": "templates/leaderboard.html",
                    "lang": "html",
                    "code": "{% extends 'base.html' %}\n{% block title %}Leaderboard{% endblock %}\n{% block content %}\n  <h1>Leaderboard <span id='live-badge' style='font-size:0.6em; color:#a0c000;'>&#9889; live</span></h1>\n  <table id='lb-table' style='width:100%; border-collapse:collapse;'>\n    <thead>\n      <tr style='border-bottom:2px solid #a0c000; text-align:left;'>\n        <th>Rank</th><th>Model</th><th>Owner</th><th>Score</th>\n      </tr>\n    </thead>\n    <tbody>\n      {% for e in entries %}\n      <tr style='border-bottom:1px solid #eee;'>\n        <td>{{ e.rank }}</td><td>{{ e.model_name }}</td>\n        <td>{{ e.owner }}</td><td>{{ e.score }}</td>\n      </tr>\n      {% endfor %}\n    </tbody>\n  </table>\n  <script>\n    const ws = new WebSocket('ws://' + location.host + '/ws/leaderboard');\n    ws.onmessage = (e) => {\n      const data = JSON.parse(e.data);\n      if (data.type === 'new_benchmark') {\n        // Add a flash row at the top of the table\n        const tbody = document.querySelector('#lb-table tbody');\n        const row = document.createElement('tr');\n        row.style.cssText = 'border-bottom:1px solid #eee; background:#f0fff0; animation:fade 3s;';\n        row.innerHTML = '<td>NEW</td><td>' + data.model + '</td><td>\u2014</td><td>' + data.score + '</td>';\n        tbody.insertBefore(row, tbody.firstChild);\n        // After 3s, reload to get the properly ranked table\n        setTimeout(() => location.reload(), 3000);\n      }\n    };\n    ws.onclose = () => setTimeout(() => location.reload(), 3000);  // reconnect\n  </script>\n{% endblock %}",
                },
            ],
            "explanation": "Polling (setInterval(fetch, 5000)) is laggy and wasteful — 99% of polls return nothing. WebSocket is a persistent pipe: the server pushes the instant something happens, zero lag, zero wasted requests. The ConnectionManager class tracks every connected browser in a list. When a benchmark finishes, broadcast() sends a JSON message to every client. Each browser's ws.onmessage fires, parses the JSON, and updates the DOM. The critical detail: wrap send_text in try/except — a client that closed their tab will raise, and you must remove them from the active list or you'll keep trying to send to a dead socket. The client-side ws.onclose triggers a reload after 3 seconds — basic auto-reconnect for when the server restarts. Open two tabs, benchmark a model, watch both update instantly.",
            "try_yourself": "Add a heartbeat: every 30 seconds, the client sends {type:'ping'} and the server responds {type:'pong'}. This keeps the connection alive through proxies that cut idle connections. Add a 'X users viewing' counter that broadcasts the active connection count.",
            "common_mistakes": [
                "Not removing disconnected clients — the active list grows forever, and every broadcast tries to send to dead sockets, raising exceptions.",
                "Iterating self.active while modifying it — `for ws in self.active:` then `self.active.remove(ws)` inside the loop skips elements. Always iterate over `list(self.active)` (a copy).",
                "Blocking the event loop — `await ws.send_text()` is async for a reason. Never call `time.sleep()` or sync I/O inside a WS handler; it blocks ALL other connections.",
                "Not handling WebSocketDisconnect — without the try/except, a client closing their tab crashes the handler and logs a scary traceback.",
            ],
            "used_in": "app/main.py — ConnectionManager class + /ws/leaderboard, /ws/benchmark, /ws/notifications endpoints. templates/realtime.html — the live demo page.",
        },
        # ─── Step 9 ─────────────────────────────────────────────────────
        {
            "step_number": 9,
            "slug": "build-step-09-notebook",
            "title": "Notebook Kernel \u2014 Run User Python in the Browser",
            "summary": "exec() user code in a per-user namespace, capture stdout, return the output. The sandboxed kernel behind the /notebook page.",
            "goal": "Visit /notebook, type print('hello world'), click Run, and see 'hello world' in the output panel. Then type x = 42 in one cell and print(x) in another \u2014 the second cell sees x.",
            "concept_code": "# The basic concept: exec() runs Python code inside a namespace\n\nnamespace = {}  # shared state between cells\n\n# Cell 1\nexec('x = 42', namespace)\nprint(namespace.keys())  # dict_keys(['x', '__builtins__'])\nprint(namespace['x'])     # 42\n\n# Cell 2 (sees x from cell 1)\nexec('print(x * 2)', namespace)  # prints 84\n\n# Capture stdout\nimport io, contextlib\nbuf = io.StringIO()\nwith contextlib.redirect_stdout(buf):\n    exec('print(\"captured!\")', namespace)\nprint(buf.getvalue())  # 'captured!\\n'\n\n# The namespace dict IS the kernel state \u2014 variables persist across cells.",
            "files": [
                {
                    "name": "main.py",
                    "lang": "python",
                    "code": "# Step 9: Add /notebook + /api/notebook/cell on top of steps 1-8\nimport io, contextlib, traceback\nfrom concurrent.futures import ThreadPoolExecutor\nfrom fastapi import Body\nfrom pydantic import BaseModel\n\n# Per-user kernel state\n_sessions: dict[int, dict] = {}  # user_id -> {'namespace': dict, 'lock': Lock}\nexecutor = ThreadPoolExecutor(max_workers=4)\n\nclass CellRequest(BaseModel):\n    code: str\n\ndef get_session(user_id: int) -> dict:\n    if user_id not in _sessions:\n        _sessions[user_id] = {'namespace': {}, 'lock': __import__('threading').Lock()}\n    return _sessions[user_id]\n\ndef _run_sync(code: str, namespace: dict) -> dict:\n    '''Run code synchronously, capture stdout + errors.'''\n    buf = io.StringIO()\n    try:\n        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):\n            exec(code, namespace)\n        return {'status': 'ok', 'output': buf.getvalue()}\n    except Exception:\n        return {'status': 'error', 'output': buf.getvalue() + traceback.format_exc()}\n\n@app.post('/api/notebook/cell')\nasync def run_cell(\n    request: Request,\n    body: CellRequest,\n    db: Session = Depends(get_db),\n):\n    # Auth: get the user\n    token = request.cookies.get('access_token')\n    username = decode_token(token)\n    if not username:\n        return {'error': 'not logged in'}\n    user = db.query(User).filter(User.username == username).first()\n\n    # Get (or create) this user's kernel session\n    session = get_session(user.id)\n\n    # Run the code in a thread (so we don't block the event loop)\n    # Use a lock so only one cell runs at a time per user\n    with session['lock']:\n        import asyncio\n        loop = asyncio.get_event_loop()\n        result = await loop.run_in_executor(\n            executor, _run_sync, body.code, session['namespace']\n        )\n    return result\n\n@app.get('/notebook', response_class=HTMLResponse)\nasync def notebook_page(request: Request, db: Session = Depends(get_db)):\n    token = request.cookies.get('access_token')\n    username = decode_token(token)\n    if not username:\n        return RedirectResponse(url='/login?next=/notebook', status_code=303)\n    return templates.TemplateResponse('notebook.html', {'request': request})",
                },
                {
                    "name": "templates/notebook.html",
                    "lang": "html",
                    "code": "{% extends 'base.html' %}\n{% block title %}Notebook{% endblock %}\n{% block content %}\n  <h1>Notebook</h1>\n  <textarea id='code' rows='6' style='width:100%; font-family:monospace;'\n    >print(\"hello world\")\nx = 42\nprint(x)</textarea>\n  <br>\n  <button onclick='runCell()' style='margin:0.5rem 0;'>Run</button>\n  <pre id='output' style='background:#0d1117; color:#e6edf3; padding:1rem; border-radius:6px; min-height:100px; white-space:pre-wrap;'></pre>\n\n  <script>\n    async function runCell() {\n      const code = document.getElementById('code').value;\n      const output = document.getElementById('output');\n      output.textContent = 'running...';\n      const res = await fetch('/api/notebook/cell', {\n        method: 'POST',\n        headers: {'Content-Type': 'application/json'},\n        body: JSON.stringify({code}),\n      });\n      const data = await res.json();\n      output.textContent = data.output || data.error || '(no output)';\n    }\n  </script>\n{% endblock %}",
                },
            ],
            "explanation": "A notebook kernel is just exec() with a persistent namespace. exec(code, namespace) runs the code string as Python, and any variables it creates stay in namespace. The next cell call passes the SAME namespace, so variables persist across cells — that's the magic. Three critical details: (1) Capture stdout with contextlib.redirect_stdout — without it, print() goes to the server's terminal, not the browser. (2) Use a per-user lock so two cells from the same user don't run simultaneously and corrupt the namespace. (3) Run in a thread pool via run_in_executor — exec() is synchronous and CPU-bound; if you run it directly in an async route, it blocks the entire event loop (no other request can be served while a cell runs). The ThreadPoolExecutor offloads it so the event loop stays responsive. This is a simplified version — the real OpenBenchML notebook has timeout enforcement, package installation, a WebSocket terminal, and file management.",
            "try_yourself": "Add a timeout: wrap _run_sync in a threading.Timer that kills the exec after 10 seconds. Add a 'Reset Kernel' button that clears the namespace dict. Add matplotlib support: if the code calls plt.savefig(), capture the PNG and display it.",
            "common_mistakes": [
                "Running exec() directly in an async route — it blocks the event loop. ALWAYS use run_in_executor for CPU-bound work.",
                "Not capturing stdout — print() goes to the server terminal, the browser sees nothing. Use contextlib.redirect_stdout.",
                "Sharing one namespace across all users — user A's variables leak to user B. Use a per-user dict keyed by user_id.",
                "No timeout — `while True: pass` hangs the server forever. Use a thread with a timeout, or signal.alarm.",
                "Security: exec() runs ARBITRARY code. In production, sandbox with Docker, seccomp, or a separate VM. Never exec() untrusted code in the main process.",
            ],
            "used_in": "app/routes/notebook.py — /notebook page + /api/notebook/cell endpoint. The real version has timeout enforcement, package installation, WebSocket terminal, file management, and runs in a Docker sandbox.",
        },
        # ─── Step 10 ────────────────────────────────────────────────────
        {
            "step_number": 10,
            "slug": "build-step-10-docker-deploy",
            "title": "Docker + Render \u2014 Ship It to the Internet",
            "summary": "Package the app into a Docker image, push to GitHub, connect Render, and go live. From localhost to a public URL in one step.",
            "goal": "Run `git push`, wait 5 minutes, visit https://yourapp.onrender.com and see your live app with auth, upload, benchmark, leaderboard, and notebook.",
            "concept_code": "# The basic concept: Docker = reproducible environment\n\n# Without Docker:\n#   \"Works on my machine\" \u2014 different Python, different pip, different OS\n#   Deploy = SSH, install deps, pray\n\n# With Docker:\n#   Build an image once: docker build -t myapp .\n#   Run it anywhere: docker run -p 8000:8000 myapp\n#   Same image runs on laptop, Render, AWS, GCP, Oracle Cloud\n\n# A Dockerfile is a recipe:\n#   FROM python:3.11-slim    (start from a base image)\n#   COPY requirements.txt .  (copy deps file)\n#   RUN pip install ...      (install deps)\n#   COPY . .                 (copy code)\n#   CMD [\"uvicorn\", ...]     (what to run)\n\n# Each line is a layer. Change code? Only the COPY layer rebuilds.\n# Change requirements.txt? pip install layer rebuilds. Fast iteration.",
            "files": [
                {
                    "name": "Dockerfile",
                    "lang": "dockerfile",
                    "code": "# Step 10: Package the app\nFROM python:3.11-slim\n\nWORKDIR /app\n\n# Install system deps (if any)\nRUN apt-get update && apt-get install -y --no-install-recommends \\\n    build-essential && rm -rf /var/lib/apt/lists/*\n\n# Install Python deps (cached layer)\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\n\n# Copy the app code\nCOPY . .\n\n# Create the uploads directory\nRUN mkdir -p uploads\n\n# Expose the port\nEXPOSE 8000\n\n# Run with uvicorn\nCMD [\"uvicorn\", \"main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8000\"]",
                },
                {
                    "name": "requirements.txt",
                    "lang": "text",
                    "code": "fastapi==0.104.1\nuvicorn[standard]==0.24.0\nsqlalchemy==2.0.23\npython-jose[cryptography]==3.3.0\npasslib[bcrypt]==1.7.4\npython-multipart==0.0.6\njinja2==3.1.2\nscikit-learn==1.3.2\nnumpy==1.26.2\n",
                },
                {
                    "name": "render.yaml",
                    "lang": "yaml",
                    "code": "# Render deployment config\n# Render reads this file and creates the service automatically\nservices:\n  - type: web\n    name: openbenchml\n    env: docker\n    healthCheckPath: /health\n    envVars:\n      - key: SECRET_KEY\n        generateValue: true    # Render generates a random secret\n      - key: DATABASE_URL\n        value: sqlite:///data.db\n    disk:\n      name: data\n      mountPath: /opt/render\n      sizeGB: 1",
                },
                {
                    "name": "deploy.sh",
                    "lang": "bash",
                    "code": "# Step 10: Deploy to Render\n\n# 1. Push your code to GitHub\ngit init\ngit add .\ngit commit -m 'OpenBenchML step 10: ready to deploy'\ngit remote add origin https://github.com/YOUR_USERNAME/openbenchml.git\ngit push -u origin main\n\n# 2. Go to render.com -> New -> Web Service\n# 3. Connect your GitHub repo\n# 4. Render detects render.yaml and creates the service\n# 5. Wait ~5 minutes for the build\n# 6. Visit https://openbenchml.onrender.com\n\n# To update: just `git push` \u2014 Render auto-deploys on every push to main.\n\n# Test locally with Docker first:\ndocker build -t openbenchml .\ndocker run -p 8000:8000 openbenchml\n# Visit http://localhost:8000",
                },
            ],
            "explanation": "Docker solves 'works on my machine' — the image contains the exact Python, pip packages, and OS libraries, so it runs identically everywhere. The Dockerfile recipe: (1) FROM python:3.11-slim starts from a minimal Python base. (2) COPY requirements.txt + RUN pip install installs deps FIRST so this layer is cached — rebuilding after a code change skips the slow pip install. (3) COPY . . copies your code. (4) EXPOSE 8000 documents the port. (5) CMD [...] is the command that runs when the container starts. Render is a PaaS: you push to GitHub, Render detects the Dockerfile + render.yaml, builds the image, runs it on a managed VM, gives you a URL, terminates HTTPS, and restarts on crash. The healthCheckPath: /health tells Render how to check if the app is alive — if /health returns non-200, Render restarts the container. The SECRET_KEY env var is auto-generated by Render (generateValue: true) — never commit secrets to git. From this point on, `git push` IS the deploy command.",
            "try_yourself": "Add a docker-compose.yml that runs the app + a Postgres database together. Add a .dockerignore file (exclude .git, __pycache__, *.db) to make builds faster. Set up a custom domain in Render's dashboard.",
            "common_mistakes": [
                "Binding to `host='127.0.0.1'` in the Dockerfile CMD — the app is unreachable from outside the container. Always use `--host 0.0.0.0`.",
                "Hardcoding SECRET_KEY in the Dockerfile — anyone with the image can forge JWTs. Use env vars: `SECRET_KEY = os.getenv('SECRET_KEY')`.",
                "Not adding a healthCheckPath — Render can't tell if the app is alive, so it may restart healthy containers or keep dead ones running.",
                "Forgetting to persist the SQLite file — Render's filesystem is ephemeral. Use a disk mount (render.yaml) or switch to Postgres for production data.",
                "Committing .git, __pycache__, or the .db file into the Docker image — bloats the image and leaks secrets. Add a .dockerignore.",
            ],
            "used_in": "Dockerfile + render.yaml at the project root. The same image runs on Render (free tier) and on Oracle Cloud (24 GB RAM Always Free tier for the notebook kernel).",
        },
    ],
}
