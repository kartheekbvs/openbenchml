"""FastAPI course website content for the OpenBenchML learning portal."""

COURSE_TITLE = "FastAPI Mastery"
COURSE_SUBTITLE = "From beginner to advanced, learn FastAPI with real examples, projects, and deployment guidance."
COURSE_OVERVIEW = (
    "A step-by-step FastAPI learning website modeled after a modern developer course. "
    "Start with HTTP basics, build production-ready APIs, learn Docker deployment, and master async Python."
)

COURSE_MODULES = [
    {
        "slug": "fastapi-introduction",
        "title": "FastAPI Introduction",
        "description": "Understand what FastAPI is, why it became popular, and how to create your first API.",
        "lessons": [
            {
                "slug": "what-is-fastapi",
                "title": "What is FastAPI?",
                "summary": "Learn the core design goals, benefits, and ecosystem of FastAPI.",
                "sections": [
                    {
                        "heading": "FastAPI in a nutshell",
                        "text": (
                            "FastAPI is a modern Python web framework built on Starlette and Pydantic. "
                            "It is designed for fast development, high performance, automatic validation, and rich APIs."
                        ),
                    },
                    {
                        "heading": "Why choose FastAPI?",
                        "text": (
                            "FastAPI gives you automatic OpenAPI docs, type-driven validation, async support, and excellent developer ergonomics. "
                            "It is ideal for machine learning services, microservices, and production APIs."
                        ),
                    },
                ],
                "code_examples": [
                    "from fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get('/')\ndef root():\n    return {'message': 'Welcome to FastAPI'}\n",
                ],
            },
            {
                "slug": "install-and-run",
                "title": "Install and Run FastAPI",
                "summary": "Install the required packages and launch your first FastAPI app with Uvicorn.",
                "sections": [
                    {
                        "heading": "Install dependencies",
                        "text": "Use pip to install FastAPI and Uvicorn. Uvicorn is the ASGI server that runs your app in development.",
                        "code": "python -m pip install fastapi uvicorn",
                    },
                    {
                        "heading": "Run the app",
                        "text": "Start your app with Uvicorn and open the automatic docs at /docs.",
                        "code": "uvicorn app.main:app --reload",
                    },
                ],
                "code_examples": [
                    "uvicorn app.main:app --reload --host 0.0.0.0 --port 8000\n",
                ],
            },
            {
                "slug": "automatic-docs",
                "title": "Automatic API Documentation",
                "summary": "Use FastAPI's built-in Swagger and ReDoc documentation pages.",
                "sections": [
                    {
                        "heading": "Swagger UI",
                        "text": "Visit /docs to explore your API interactively. FastAPI generates request forms and response schemas automatically.",
                    },
                    {
                        "heading": "ReDoc",
                        "text": "Use /redoc for a different documentation layout that is great for API reference browsing.",
                    },
                ],
            },
        ],
    },
    {
        "slug": "fastapi-basics",
        "title": "FastAPI Basics",
        "description": "Learn routes, request parameters, response models, and how FastAPI validates data automatically.",
        "lessons": [
            {
                "slug": "path-parameters",
                "title": "Path and Query Parameters",
                "summary": "Define dynamic URLs and query string values with typed function parameters.",
                "sections": [
                    {
                        "heading": "Path parameters",
                        "text": "Capture values directly from the URL path and convert them to Python types.",
                        "code": "@app.get('/items/{item_id}')\ndef read_item(item_id: int):\n    return {'item_id': item_id}\n",
                    },
                    {
                        "heading": "Query parameters",
                        "text": "Add optional or required query parameters by declaring function arguments with defaults.",
                        "code": "@app.get('/search')\ndef search(q: str | None = None, limit: int = 10):\n    return {'query': q, 'limit': limit}\n",
                    },
                ],
            },
            {
                "slug": "request-bodies",
                "title": "Request Bodies with Pydantic",
                "summary": "Use Pydantic models to validate JSON bodies and get typed data objects in your endpoint functions.",
                "sections": [
                    {
                        "heading": "Define a Pydantic model",
                        "text": "Create a class that describes the shape of the request body and let FastAPI validate it automatically.",
                        "code": "from pydantic import BaseModel\n\nclass Item(BaseModel):\n    name: str\n    price: float\n    tags: list[str] = []\n",
                    },
                    {
                        "heading": "Use the model in a route",
                        "text": "Declare the model type as a function argument and FastAPI parses the incoming JSON.",
                        "code": "@app.post('/items/')\ndef create_item(item: Item):\n    return {'item_name': item.name, 'item_price': item.price}\n",
                    },
                ],
            },
            {
                "slug": "response-models",
                "title": "Response Models and Serialization",
                "summary": "Control what your API returns by using response models and hiding internal fields.",
                "sections": [
                    {
                        "heading": "Response model example",
                        "text": "Use response_model to ensure your API only returns the fields you want clients to see.",
                        "code": "@app.post('/items/', response_model=Item)\ndef create_item(item: Item):\n    return item\n",
                    },
                ],
            },
        ],
    },
    {
        "slug": "fastapi-dependencies",
        "title": "Dependencies and Security",
        "description": "Learn FastAPI dependency injection patterns, configuration, and authentication helpers.",
        "lessons": [
            {
                "slug": "dependencies",
                "title": "FastAPI Dependencies",
                "summary": "Use Declared dependencies to share logic across routes and manage resources cleanly.",
                "sections": [
                    {
                        "heading": "Dependency function",
                        "text": "Dependencies are normal Python functions that can yield values, run cleanup, and be reused across routes.",
                        "code": "from fastapi import Depends\n\ndef get_token():\n    return 'token'\n\n@app.get('/secure')\ndef secure_route(token: str = Depends(get_token)):\n    return {'token': token}\n",
                    },
                ],
            },
            {
                "slug": "database-dependencies",
                "title": "Database Session Dependency",
                "summary": "Manage database sessions with a dependency that opens and closes connections safely.",
                "sections": [
                    {
                        "heading": "Session dependency",
                        "text": "Use a generator dependency to yield a DB session and ensure it closes after the request.",
                        "code": "def get_db():\n    db = SessionLocal()\n    try:\n        yield db\n    finally:\n        db.close()\n",
                    },
                    {
                        "heading": "Use it in routes",
                        "code": "@app.get('/users/')\ndef list_users(db: Session = Depends(get_db)):\n    return db.query(User).all()\n",
                    },
                ],
            },
            {
                "slug": "auth-security",
                "title": "Authentication and Security",
                "summary": "Protect routes with token auth, headers, and permission checks.",
                "sections": [
                    {
                        "heading": "Security dependency",
                        "text": "Use oauth2_scheme, API keys, or custom token logic to guard endpoints.",
                        "code": "from fastapi.security import OAuth2PasswordBearer\ntoken_scheme = OAuth2PasswordBearer(tokenUrl='token')\n",
                    },
                ],
            },
        ],
    },
    {
        "slug": "fastapi-database",
        "title": "Database and Models",
        "description": "Build CRUD APIs with SQLAlchemy, Pydantic models, and database migrations.",
        "lessons": [
            {
                "slug": "sqlalchemy-basics",
                "title": "SQLAlchemy Models",
                "summary": "Define database tables with SQLAlchemy ORM models and map them to Pydantic schemas.",
                "sections": [
                    {
                        "heading": "Define a model",
                        "text": "Use declarative base classes to declare your database tables as Python classes.",
                        "code": "class User(Base):\n    __tablename__ = 'users'\n    id = Column(Integer, primary_key=True, index=True)\n    username = Column(String, unique=True, index=True)\n",
                    },
                ],
            },
            {
                "slug": "crud-operations",
                "title": "CRUD and Data Persistence",
                "summary": "Create, read, update, and delete records from the database using FastAPI routes.",
                "sections": [
                    {
                        "heading": "Create a record",
                        "text": "Use the DB session dependency to add and commit new objects.",
                        "code": "user = User(username='alice')\ndb.add(user)\ndb.commit()\ndb.refresh(user)\n",
                    },
                ],
            },
            {
                "slug": "pydantic-schemas",
                "title": "Pydantic Schemas for DB Models",
                "summary": "Use separate Pydantic models for requests and responses to avoid leaking internal fields.",
                "sections": [
                    {
                        "heading": "Schema examples",
                        "text": "Create distinct classes for input validation and output serialization.",
                        "code": "class UserCreate(BaseModel):\n    username: str\n\nclass UserRead(BaseModel):\n    id: int\n    username: str\n    class Config:\n        orm_mode = True\n",
                    },
                ],
            },
        ],
    },
    {
        "slug": "fastapi-async",
        "title": "Async and Background Tasks",
        "description": "Learn how to write async routes, handle blocking code, and run tasks in the background.",
        "lessons": [
            {
                "slug": "async-routes",
                "title": "Async Route Handlers",
                "summary": "When to use async def and how FastAPI handles async I/O-bound operations.",
                "sections": [
                    {
                        "heading": "Async endpoint",
                        "text": "Use async def for endpoints that await network calls, database queries, or external API requests.",
                        "code": "@app.get('/fetch')\nasync def fetch():\n    async with httpx.AsyncClient() as client:\n        response = await client.get('https://httpbin.org/get')\n    return response.json()\n",
                    },
                ],
            },
            {
                "slug": "background-tasks",
                "title": "Background Tasks",
                "summary": "Run work after a response is returned without blocking the client.",
                "sections": [
                    {
                        "heading": "Use BackgroundTasks",
                        "text": "Add tasks that execute after the request finishes, such as sending a notification.",
                        "code": "from fastapi import BackgroundTasks\n\ndef write_log(message: str):\n    with open('log.txt', 'a') as f:\n        f.write(message + '\n')\n\n@app.post('/submit')\ndef submit(background_tasks: BackgroundTasks):\n    background_tasks.add_task(write_log, 'submitted')\n    return {'status': 'queued'}\n",
                    },
                ],
            },
            {
                "slug": "websockets",
                "title": "WebSockets and Real-Time APIs",
                "summary": "Use FastAPI WebSocket support for live updates, chat, and progress streaming.",
                "sections": [
                    {
                        "heading": "WebSocket example",
                        "text": "FastAPI supports WebSockets with a simple route decorator and message loop.",
                        "code": "from fastapi import WebSocket\n\n@app.websocket('/ws')\nasync def websocket_endpoint(websocket: WebSocket):\n    await websocket.accept()\n    while True:\n        data = await websocket.receive_text()\n        await websocket.send_text(f'Received: {data}')\n",
                    },
                ],
            },
        ],
    },
    {
        "slug": "fastapi-testing-deployment",
        "title": "Testing and Deployment",
        "description": "Learn how to test FastAPI apps and deploy them using Docker in production.",
        "lessons": [
            {
                "slug": "testing-fastapi",
                "title": "Testing FastAPI Applications",
                "summary": "Use TestClient and pytest to write reliable API tests.",
                "sections": [
                    {
                        "heading": "TestClient example",
                        "text": "Create tests that exercise your routes without running a real server.",
                        "code": "from fastapi.testclient import TestClient\n\nclient = TestClient(app)\n\ndef test_root():\n    response = client.get('/')\n    assert response.status_code == 200\n",
                    },
                ],
            },
            {
                "slug": "docker-deployment",
                "title": "Deploy with Docker",
                "summary": "Package your FastAPI app in Docker, optimize the image, and run it in a container.",
                "sections": [
                    {
                        "heading": "Dockerfile basics",
                        "text": "Use a small base image and install dependencies in a reproducible layer.",
                        "code": "FROM python:3.13-slim\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\nCOPY . .\nCMD [\"uvicorn\", \"app.main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8000\"]\n",
                    },
                ],
            },
            {
                "slug": "production-best-practices",
                "title": "Production Best Practices",
                "summary": "Learn how to configure environment variables, logging, and security for production deployments.",
                "sections": [
                    {
                        "heading": "Environment configuration",
                        "text": "Keep secrets out of source control and use environment variables for production settings.",
                    },
                ],
            },
        ],
    },
    {
        "slug": "fastapi-advanced",
        "title": "Advanced FastAPI",
        "description": "Master higher-level FastAPI concepts like middleware, caching, performance, and custom response classes.",
        "lessons": [
            {
                "slug": "middleware",
                "title": "Middleware and Request Hooks",
                "summary": "Add middleware to modify requests, add headers, or measure performance.",
                "sections": [
                    {
                        "heading": "Create middleware",
                        "text": "Use app.middleware to run code before and after each request.",
                        "code": "@app.middleware('http')\nasync def add_process_time_header(request, call_next):\n    start = time.time()\n    response = await call_next(request)\n    response.headers['X-Process-Time'] = str(time.time() - start)\n    return response\n",
                    },
                ],
            },
            {
                "slug": "custom-responses",
                "title": "Custom Responses and Streaming",
                "summary": "Return templates, files, or streamed responses from your FastAPI app.",
                "sections": [
                    {
                        "heading": "HTML and streaming",
                        "text": "FastAPI can return HTMLResponse, FileResponse, and StreamingResponse for advanced use cases.",
                        "code": "from fastapi.responses import HTMLResponse\n\n@app.get('/page', response_class=HTMLResponse)\ndef page():\n    return '<h1>Hello</h1>'\n",
                    },
                ],
            },
            {
                "slug": "performance",
                "title": "Performance and Caching",
                "summary": "Use caching, async I/O, and fast serializers to improve API performance.",
                "sections": [
                    {
                        "heading": "Caching strategies",
                        "text": "Cache expensive responses in memory or Redis to reduce repeated work.",
                    },
                ],
            },
        ],
    },
]

COURSE_BY_SLUG = {module['slug']: module for module in COURSE_MODULES}

for module in COURSE_MODULES:
    module['lessons_by_slug'] = {lesson['slug']: lesson for lesson in module['lessons']}
