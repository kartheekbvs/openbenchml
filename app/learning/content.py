"""Learning content definitions for the OpenBenchML learning API."""

from typing import Dict, Any

LEARNING_CONTENT: Dict[str, Dict[str, Any]] = {
    "fastapi": {
        "title": "FastAPI Fundamentals",
        "overview": "A complete FastAPI course from project setup to production-ready API design.",
        "lessons": [
            {
                "slug": "app-structure",
                "title": "FastAPI Application Structure",
                "description": "Learn how to organize a FastAPI project, separate routers, and bootstrap the app.",
                "content": [
                    {
                        "heading": "Why project structure matters",
                        "text": "A clear folder layout helps teams scale. Separate your entry point, routers, services, and configuration so each part is easy to understand and test.",
                    },
                    {
                        "heading": "Core layout",
                        "text": "Use a single main app file to create FastAPI and mount routers. Keep business logic in separate modules and only import routes at startup.",
                        "code": "from fastapi import FastAPI\nfrom app.routes import users, models\n\napp = FastAPI(title=\"OpenBenchML\")\napp.include_router(users.router)\napp.include_router(models.router)\n",
                    },
                    {
                        "heading": "Health check endpoint",
                        "text": "Start with a lightweight health route so the API is always easy to monitor.",
                        "code": "@app.get('/health')\ndef health():\n    return {'status': 'healthy'}\n",
                    },
                ],
                "examples": [
                    "# main.py\nfrom fastapi import FastAPI\nfrom app.routes.health import router as health_router\n\napp = FastAPI()\napp.include_router(health_router)\n",
                ],
                "exercises": [
                    "Create a new FastAPI app folder and add a health endpoint that returns status and uptime.",
                    "Refactor the app so routes live in a separate module under app/routes/.",
                ],
            },
            {
                "slug": "routing",
                "title": "Routing and Request Handling",
                "description": "Define GET, POST, PUT, DELETE routes with path and query parameters, body validation, and response models.",
                "content": [
                    {
                        "heading": "Path parameters",
                        "text": "Use path parameters to capture parts of the URL. FastAPI parses values and converts them to Python types automatically.",
                        "code": "@app.get('/models/{model_id}')\ndef get_model(model_id: int):\n    return {'model_id': model_id}\n",
                    },
                    {
                        "heading": "Query parameters",
                        "text": "Query parameters are optional or required values passed after ? in the URL. They are easy to define with function arguments.",
                        "code": "@app.get('/models/')\ndef list_models(task: str | None = None, limit: int = 10):\n    return {'task': task, 'limit': limit}\n",
                    },
                    {
                        "heading": "Request bodies",
                        "text": "Use Pydantic models to validate request bodies. FastAPI generates docs from these models automatically.",
                        "code": "from pydantic import BaseModel\n\nclass ModelCreate(BaseModel):\n    name: str\n    framework: str\n\n@app.post('/models/')\ndef create_model(payload: ModelCreate):\n    return {'name': payload.name, 'framework': payload.framework}\n",
                    },
                ],
                "examples": [
                    "from fastapi import APIRouter\nfrom pydantic import BaseModel\n\nrouter = APIRouter(prefix=\"/models\")\n\nclass ModelIn(BaseModel):\n    name: str\n    framework: str\n\n@router.post('/')\ndef add(model: ModelIn):\n    return {'saved': model.dict()}\n",
                ],
                "exercises": [
                    "Create a `/datasets` router with list and detail endpoints using query and path parameters.",
                    "Add a POST route that validates a JSON payload for a new dataset entry.",
                ],
            },
            {
                "slug": "validation",
                "title": "Data Validation and Response Models",
                "description": "Use Pydantic to validate request and response data, enforce types, and generate schema documentation.",
                "content": [
                    {
                        "heading": "Request validation",
                        "text": "Pydantic models validate incoming JSON against your schema and return informative errors when the client sends invalid data.",
                        "code": "class Dataset(BaseModel):\n    name: str\n    samples: int\n    task: Literal['classification', 'regression']\n",
                    },
                    {
                        "heading": "Response models",
                        "text": "Define response models to control exactly what your API returns. This is useful for hiding internal fields or formatting values consistently.",
                        "code": "@app.get('/datasets/{id}', response_model=Dataset)\ndef get_dataset(id: int):\n    return Dataset(name='iris', samples=150, task='classification')\n",
                    },
                ],
                "examples": [
                    "from pydantic import BaseModel, Field\n\nclass ModelDetail(BaseModel):\n    id: int\n    name: str\n    framework: str = Field(..., example='onnx')\n",
                ],
                "exercises": [
                    "Add a response model to a GET endpoint and confirm the OpenAPI docs reflect your schema.",
                    "Use a Pydantic field alias and see how FastAPI accepts both alias and original field names.",
                ],
            },
            {
                "slug": "dependencies",
                "title": "Dependencies and Security",
                "description": "Use FastAPI dependency injection for configuration, database sessions, authentication, and reusable logic.",
                "content": [
                    {
                        "heading": "Dependency injection basics",
                        "text": "Dependencies are reusable callables that can provide values to multiple routes. They keep endpoint functions small and composable.",
                        "code": "from fastapi import Depends\n\ndef get_db():\n    db = SessionLocal()\n    try:\n        yield db\n    finally:\n        db.close()\n\n@app.get('/models')\ndef list_models(db = Depends(get_db)):\n    return {'db': 'connected'}\n",
                    },
                    {
                        "heading": "Security dependencies",
                        "text": "Use dependencies to implement token auth, API keys, or permission checks before route code runs.",
                        "code": "def get_current_user(token: str = Depends(oauth2_scheme)):\n    if token != 'secret':\n        raise HTTPException(status_code=401)\n    return {'user': 'alice'}\n",
                    },
                ],
                "examples": [
                    "def get_settings():\n    return {'debug': True}\n\n@app.get('/config')\ndef config(settings = Depends(get_settings)):\n    return settings\n",
                ],
                "exercises": [
                    "Create a shared database dependency and use it in two separate routes.",
                    "Implement a fake auth dependency that checks an authorization header.",
                ],
            },
            {
                "slug": "async-vs-sync",
                "title": "Async vs Sync in FastAPI",
                "description": "Understand how to write asynchronous and synchronous routes, and when to offload blocking work.",
                "content": [
                    {
                        "heading": "Async route handlers",
                        "text": "FastAPI supports async def functions. They are ideal for I/O-bound work such as network or database calls.",
                        "code": "@app.get('/async')\nasync def async_route():\n    await asyncio.sleep(0.1)\n    return {'status': 'done'}\n",
                    },
                    {
                        "heading": "Sync route handlers",
                        "text": "Synchronous functions work too, but blocking operations in sync routes can reduce throughput unless run in a thread executor.",
                        "code": "@app.get('/sync')\ndef sync_route():\n    return {'status': 'done'}\n",
                    },
                    {
                        "heading": "Background tasks",
                        "text": "Use BackgroundTasks for fire-and-forget work after a response is sent, like sending an email or kicking off a benchmark job.",
                        "code": "from fastapi import BackgroundTasks\n\ndef save_result(result):\n    with open('results.log', 'a') as f:\n        f.write(result + '\\n')\n\n@app.post('/jobs')\ndef start_job(background_tasks: BackgroundTasks):\n    background_tasks.add_task(save_result, 'job completed')\n    return {'status': 'started'}\n",
                    },
                ],
                "examples": [
                    "@app.get('/fetch')\nasync def fetch_data():\n    data = await httpx.get('https://example.com')\n    return data.json()\n",
                ],
                "exercises": [
                    "Convert a blocking file read into an async route using run_in_threadpool.",
                    "Add a background task that writes benchmark progress to a file.",
                ],
            },
        ],
    },
    "docker": {
        "title": "Docker for ML APIs",
        "overview": "A complete Docker course for packaging, running, and debugging FastAPI services in containers.",
        "lessons": [
            {
                "slug": "dockerfile",
                "title": "Writing Dockerfiles for Python APIs",
                "description": "Learn how to build smaller, reliable Docker images for FastAPI applications.",
                "content": [
                    {
                        "heading": "Base image selection",
                        "text": "Choose an official Python image or slim variant. Use multi-stage builds to keep final images small.",
                        "code": "FROM python:3.13-slim as builder\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\nCOPY . .\n\nFROM python:3.13-slim\nWORKDIR /app\nCOPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages\nCOPY . .\nCMD [\"uvicorn\", \"app.main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8000\"]",
                    },
                    {
                        "heading": "Dependency installation",
                        "text": "Install Python dependencies in one layer and avoid rebuilding on every code change by copying only requirements first.",
                    },
                ],
                "examples": [
                    "FROM python:3.13-slim\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install -r requirements.txt\nCOPY . .\nCMD [\"uvicorn\", \"app.main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8000\"]",
                ],
                "exercises": [
                    "Create a Dockerfile for this repo and build the image locally.",
                    "Add a .dockerignore file to exclude tests and local files from the image.",
                ],
            },
            {
                "slug": "docker-compose",
                "title": "Docker Compose for Local Development",
                "description": "Use Docker Compose to run the API together with a database, cache, or worker.",
                "content": [
                    {
                        "heading": "Compose services",
                        "text": "Define multiple services, networks, and shared volumes in docker-compose.yml so your app runs with supporting dependencies.",
                        "code": "version: '3.9'\nservices:\n  api:\n    build: .\n    ports:\n      - '8000:8000'\n    depends_on:\n      - db\n  db:\n    image: postgres:15\n    environment:\n      POSTGRES_USER: openbench\n      POSTGRES_PASSWORD: secret\n      POSTGRES_DB: openbenchdb\n",
                    },
                    {
                        "heading": "Volumes and data persistence",
                        "text": "Use volumes to keep database data across container restarts and to mount code during development.",
                    },
                ],
                "examples": [
                    "services:\n  api:\n    build: .\n    ports:\n      - '8000:8000'\n    volumes:\n      - .:/app\n  redis:\n    image: redis:7\n",
                ],
                "exercises": [
                    "Write a docker-compose file that starts the API and a Redis service.",
                    "Add an environment file and pass it into the API container.",
                ],
            },
            {
                "slug": "containers",
                "title": "Running and Debugging Containers",
                "description": "Inspect logs, attach to a shell, and troubleshoot container startup issues.",
                "content": [
                    {
                        "heading": "Inspecting logs",
                        "text": "Use docker logs and docker-compose logs to see startup errors and stack traces.",
                        "code": "docker-compose up --build\ndocker-compose logs -f api\n",
                    },
                    {
                        "heading": "Shell into a container",
                        "text": "Use docker exec to open a shell and inspect installed packages, files, or environment variables.",
                        "code": "docker exec -it openbenchml_api_1 /bin/bash\npython -c \"import sys; print(sys.version)\"\n",
                    },
                ],
                "examples": [
                    "docker-compose ps\ndocker exec -it <container> /bin/bash\n",
                ],
                "exercises": [
                    "Run the container and inspect its environment variables from inside the shell.",
                    "Simulate a failed dependency install and debug the error using logs.",
                ],
            },
        ],
    },
    "dependencies": {
        "title": "Python Dependency Management",
        "overview": "Learn dependency isolation, version pinning, and compatibility troubleshooting for production-ready Python projects.",
        "lessons": [
            {
                "slug": "venvs",
                "title": "Virtual Environments",
                "description": "Use virtual environments to isolate project dependencies from the system Python installation.",
                "content": [
                    {
                        "heading": "Creating a venv",
                        "text": "Use the built-in venv module to create a dedicated environment for the project.",
                        "code": "python -m venv .venv\nsource .venv/Scripts/activate\n",
                    },
                    {
                        "heading": "Installing packages",
                        "text": "Install packages inside the active environment so they do not conflict with global packages.",
                        "code": "pip install -r requirements.txt\n",
                    },
                ],
                "examples": [
                    "python -m venv .venv\n.venv\Scripts\activate\npip install fastapi uvicorn\n",
                ],
                "exercises": [
                    "Create and activate a virtual environment, then install the project requirements.",
                    "Verify the environment is isolated by checking `pip list` before and after activation.",
                ],
            },
            {
                "slug": "requirements",
                "title": "Requirements Files and Version Pins",
                "description": "Create reproducible dependency sets using requirements files and pinned package versions.",
                "content": [
                    {
                        "heading": "Pin exact versions",
                        "text": "Freeze package versions so the same dependencies install across machines and CI.",
                        "code": "fastapi==0.111.0\nuvicorn==0.23.2\n",
                    },
                    {
                        "heading": "Splitting files",
                        "text": "Use separate files for production, development, and testing dependencies for cleaner installations.",
                    },
                ],
                "examples": [
                    "pip freeze > requirements.txt\n",
                ],
                "exercises": [
                    "Generate a pinned requirements.txt from your environment.",
                    "Create a dev-requirements file for testing packages like pytest.",
                ],
            },
            {
                "slug": "compatibility",
                "title": "Compatibility Troubleshooting",
                "description": "Diagnose dependency conflicts, incorrect wheel installs, and platform-specific package issues.",
                "content": [
                    {
                        "heading": "Common issues",
                        "text": "Binary packages such as TensorFlow and PyTorch can depend on OS and Python version compatibility. Pin versions that match your platform.",
                    },
                    {
                        "heading": "Tools to inspect problems",
                        "text": "Use pip check, pipdeptree, and import tests to find mismatch causes and fix broken installs.",
                        "code": "pip check\npipdeptree | grep tensorflow\n",
                    },
                ],
                "examples": [
                    "python -m pip install protobuf<7.0.0,>=3.20.2\n",
                ],
                "exercises": [
                    "Run `pip check` and resolve a dependency conflict in your environment.",
                    "Document why a specific package version is required for Windows + Python 3.13.",
                ],
            },
        ],
    },
    "model-loading": {
        "title": "Model Loading and Serialization",
        "overview": "Learn how to load, detect, validate, and inspect machine learning model files from multiple frameworks.",
        "lessons": [
            {
                "slug": "framework-detection",
                "title": "Framework Auto-Detection",
                "description": "Automatically identify a model file format and choose the correct loader based on extension and metadata.",
                "content": [
                    {
                        "heading": "Why auto-detect models",
                        "text": "Users may upload models without telling the API the framework. Detecting the format prevents wrong loader errors and improves usability.",
                    },
                    {
                        "heading": "Extension-based detection",
                        "text": "Use file extensions like .pkl, .pt, .onnx, .h5, and .bst as first clues for model type.",
                        "code": "EXTENSIONS = {'.pkl': 'scikit-learn', '.pt': 'pytorch', '.onnx': 'onnx'}\n",
                    },
                ],
                "examples": [
                    "def guess_framework(path):\n    ext = Path(path).suffix.lower()\n    return EXTENSIONS.get(ext, 'auto')\n",
                ],
                "exercises": [
                    "Add support for `.h5` and `.keras` model extensions to a loader.",
                    "Write a helper that validates a model path and returns a framework hint.",
                ],
            },
            {
                "slug": "model-formats",
                "title": "Common Model Serialization Formats",
                "description": "Understand ONNX, PyTorch, TensorFlow, scikit-learn, XGBoost, and LightGBM serialization formats.",
                "content": [
                    {
                        "heading": "ONNX",
                        "text": "ONNX is a cross-platform model format for inference and interoperability between frameworks.",
                    },
                    {
                        "heading": "PyTorch and TensorFlow",
                        "text": "PyTorch uses .pt/.pth while TensorFlow can use SavedModel directories or .h5 files for serialized weights.",
                    },
                    {
                        "heading": "Tree-based formats",
                        "text": "LightGBM and XGBoost export models to binary files that can be loaded with framework-specific APIs.",
                    },
                ],
                "examples": [
                    "import onnxruntime as ort\nmodel = ort.InferenceSession('model.onnx')\n",
                ],
                "exercises": [
                    "Build a model metadata endpoint that reports format, size, and framework support.",
                    "Create sample loader functions for ONNX and scikit-learn files.",
                ],
            },
            {
                "slug": "validation",
                "title": "Safe Loading and Validation",
                "description": "Validate uploaded files, handle corrupted models, and return helpful errors to the client.",
                "content": [
                    {
                        "heading": "Input validation",
                        "text": "Reject files with unsupported extensions or invalid contents before attempting to load them.",
                        "code": "ALLOWED_EXTENSIONS = {'.pkl', '.onnx', '.pt', '.h5', '.bst'}\nif extension not in ALLOWED_EXTENSIONS:\n    raise HTTPException(status_code=400, detail='Unsupported model type')\n",
                    },
                    {
                        "heading": "Graceful failure",
                        "text": "Log exceptions and return user-friendly messages so clients can correct uploads without exposing internals.",
                    },
                ],
                "examples": [
                    "try:\n    model = load_model(path, framework)\nexcept Exception as exc:\n    raise HTTPException(status_code=422, detail=str(exc))\n",
                ],
                "exercises": [
                    "Implement a validation layer that returns 400 for unsupported extensions.",
                    "Add a fallback path that tries a second loader if the first attempt fails.",
                ],
            },
        ],
    },
    "benchmarking": {
        "title": "Benchmarking ML APIs",
        "overview": "Build benchmark jobs, collect metrics, and compare model performance in a production-like environment.",
        "lessons": [
            {
                "slug": "benchmark-design",
                "title": "Designing Reliable Benchmarks",
                "description": "Plan benchmark jobs that measure throughput, latency, memory, and prediction accuracy.",
                "content": [
                    {
                        "heading": "What to benchmark",
                        "text": "Focus on latency, batch throughput, memory usage, and model correctness. A benchmark is only useful when it measures real user-facing behavior.",
                    },
                    {
                        "heading": "Benchmark job structure",
                        "text": "Create a job record, run tests against representative input, and persist results for later analysis.",
                        "code": "job = BenchmarkJob(status='running')\ndb.add(job)\ndb.commit()\n",
                    },
                ],
                "examples": [
                    "def run_benchmark(model, inputs):\n    start = time.perf_counter()\n    for batch in inputs:\n        model.predict(batch)\n    return time.perf_counter() - start\n",
                ],
                "exercises": [
                    "Write a benchmark function that measures average response time over 100 requests.",
                    "Create a benchmark record in the database with status and metrics fields.",
                ],
            },
            {
                "slug": "metrics",
                "title": "Collecting and Comparing Metrics",
                "description": "Track benchmark metrics and expose leaderboard endpoints to compare models by speed and accuracy.",
                "content": [
                    {
                        "heading": "Important metrics",
                        "text": "Store total time, average latency, throughput, memory usage, and dataset accuracy. These metrics let you compare models objectively.",
                    },
                    {
                        "heading": "Leaderboard APIs",
                        "text": "Create endpoints that return the fastest, smallest, or highest-scoring models for easy comparison.",
                        "code": "@app.get('/leaderboard/fastest')\ndef fastest():\n    return db.query(Job).order_by(Job.avg_latency).limit(10).all()\n",
                    },
                ],
                "examples": [
                    "metrics = {'avg_latency_ms': 35.4, 'accuracy': 0.92, 'memory_mb': 180}\n",
                ],
                "exercises": [
                    "Add a leaderboard endpoint that returns top 5 models by lowest latency.",
                    "Store benchmark metrics in a JSON field in the database.",
                ],
            },
            {
                "slug": "background-jobs",
                "title": "Async Jobs and WebSockets",
                "description": "Run long-running benchmark jobs asynchronously and stream progress to clients with WebSockets.",
                "content": [
                    {
                        "heading": "Background tasks",
                        "text": "Use FastAPI BackgroundTasks or a dedicated worker to keep the API responsive while benchmarks run.",
                        "code": "@app.post('/benchmarks')\ndef start(background_tasks: BackgroundTasks):\n    background_tasks.add_task(run_benchmark, params)\n    return {'status': 'queued'}\n",
                    },
                    {
                        "heading": "Real-time updates",
                        "text": "Send progress events over WebSockets so users can watch benchmark execution without polling.",
                        "code": "await websocket.send_json({'type': 'progress', 'completed': 40, 'total': 100})\n",
                    },
                ],
                "examples": [
                    "@app.websocket('/ws/benchmark')\nasync def websocket_benchmark(websocket: WebSocket):\n    await websocket.accept()\n",
                ],
                "exercises": [
                    "Create a background benchmark worker that writes updates to the database.",
                    "Implement a WebSocket route that streams progress messages to connected clients.",
                ],
            },
        ],
    },
    "architecture": {
        "title": "Project Architecture",
        "overview": "Learn the architecture patterns used in OpenBenchML, including routers, services, config, and testing.",
        "lessons": [
            {
                "slug": "layers",
                "title": "Service and Router Layers",
                "description": "Separate HTTP routing from business logic and database access to keep code maintainable.",
                "content": [
                    {
                        "heading": "Router responsibilities",
                        "text": "Routers should handle request parsing, dependency injection, and response formatting. Delegate business logic to service modules.",
                    },
                    {
                        "heading": "Service modules",
                        "text": "Service functions contain domain logic and can be reused across routes and tests.",
                        "code": "def create_model(name, framework):\n    return Model(name=name, framework=framework)\n\n@router.post('/models')\ndef create(payload: ModelCreate):\n    return create_model(payload.name, payload.framework)\n",
                    },
                ],
                "examples": [
                    "# service.py\ndef calculate_score(predictions, labels):\n    return accuracy_score(labels, predictions)\n",
                ],
                "exercises": [
                    "Refactor a route to move business logic into a service function.",
                    "Write a service helper for model metadata extraction.",
                ],
            },
            {
                "slug": "configuration",
                "title": "Configuration and Environment",
                "description": "Use a central config module to manage settings for development, testing, and production.",
                "content": [
                    {
                        "heading": "Central config module",
                        "text": "Keep settings such as database URLs, CORS origins, and debug flags in one place.",
                        "code": "class Settings(BaseSettings):\n    debug: bool = False\n    database_url: str = 'sqlite:///./dev.db'\n\nsettings = Settings()\n",
                    },
                    {
                        "heading": "Environment overrides",
                        "text": "Allow values to be overridden by environment variables so deployments remain flexible.",
                    },
                ],
                "examples": [
                    "from pydantic import BaseSettings\n\nclass Settings(BaseSettings):\n    redis_url: str\n    class Config:\n        env_file = '.env'\n",
                ],
                "exercises": [
                    "Add a Settings class and read values from `.env`.",
                    "Use settings in the health check response to show environment mode.",
                ],
            },
            {
                "slug": "testing",
                "title": "Testing and Validation",
                "description": "Write unit and integration tests for FastAPI routers, services, and the learning API.",
                "content": [
                    {
                        "heading": "FastAPI TestClient",
                        "text": "Use TestClient to send HTTP requests to your app and assert API responses.",
                        "code": "from fastapi.testclient import TestClient\nfrom app.main import app\nclient = TestClient(app)\n\ndef test_health():\n    response = client.get('/health')\n    assert response.status_code == 200\n",
                    },
                    {
                        "heading": "Service tests",
                        "text": "Test business logic separately from HTTP routes so you can validate calculations and edge cases independently.",
                    },
                ],
                "examples": [
                    "def test_search_lessons():\n    response = client.get('/learning/search', params={'query': 'Docker'})\n    assert response.status_code == 200\n",
                ],
                "exercises": [
                    "Add a unit test for a service layer helper.",
                    "Write a regression test covering the learning content search endpoint.",
                ],
            },
        ],
    },
}
