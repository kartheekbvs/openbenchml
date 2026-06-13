COURSE_TITLE = "FastAPI Mastery"
COURSE_SUBTITLE = "From beginner to advanced, learn FastAPI with real examples and real deployment guidance."
COURSE_OVERVIEW = (
    "A self-contained FastAPI course site built to deploy on a dedicated domain. "
    "Follow the full curriculum, from basics to advanced production topics."
)

COURSE_MODULES = [
    {
        "slug": "fastapi-introduction",
        "title": "FastAPI Introduction",
        "description": "Understand FastAPI and build your first API.",
        "lessons": [
            {
                "slug": "what-is-fastapi",
                "title": "What is FastAPI?",
                "summary": "Learn FastAPI design goals, performance benefits, and use cases.",
                "sections": [
                    {
                        "heading": "FastAPI in a nutshell",
                        "text": "FastAPI is a modern Python framework built on Starlette and Pydantic for fast APIs.",
                    },
                    {
                        "heading": "Why FastAPI?",
                        "text": "FastAPI gives you automatic docs, validation, async support, and high performance.",
                    },
                ],
                "code_examples": [
                    "from fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get('/')\ndef root():\n    return {'message': 'Welcome to FastAPI'}\n",
                ],
            },
            {
                "slug": "install-and-run",
                "title": "Install and Run FastAPI",
                "summary": "Install FastAPI and Uvicorn, then launch your first app.",
                "sections": [
                    {
                        "heading": "Install dependencies",
                        "text": "Use pip to install FastAPI and Uvicorn for local development.",
                        "code": "python -m pip install fastapi uvicorn",
                    },
                    {
                        "heading": "Run the app",
                        "text": "Start your FastAPI app with Uvicorn and visit /docs.",
                        "code": "uvicorn main:app --reload --host 0.0.0.0 --port 8000",
                    },
                ],
            },
        ],
    },
    {
        "slug": "fastapi-basics",
        "title": "FastAPI Basics",
        "description": "Build routes, handle request data, and validate responses.",
        "lessons": [
            {
                "slug": "path-and-query-parameters",
                "title": "Path and Query Parameters",
                "summary": "Capture dynamic URL values and query strings with typed parameters.",
                "sections": [
                    {
                        "heading": "Path parameters",
                        "text": "Use path parameters to accept dynamic values in your routes.",
                        "code": "@app.get('/items/{item_id}')\ndef read_item(item_id: int):\n    return {'item_id': item_id}\n",
                    },
                    {
                        "heading": "Query parameters",
                        "text": "Add optional or required query parameters using default args.",
                        "code": "@app.get('/search')\ndef search(q: str | None = None, limit: int = 10):\n    return {'query': q, 'limit': limit}\n",
                    },
                ],
            },
            {
                "slug": "request-bodies",
                "title": "Request Bodies with Pydantic",
                "summary": "Validate JSON body payloads using Pydantic models.",
                "sections": [
                    {
                        "heading": "Define a model",
                        "text": "A Pydantic model describes the request body shape and validation.",
                        "code": "from pydantic import BaseModel\n\nclass Item(BaseModel):\n    name: str\n    price: float\n",
                    },
                    {
                        "heading": "Use the model",
                        "text": "Declare the model in an endpoint to parse request JSON automatically.",
                        "code": "@app.post('/items/')\ndef create_item(item: Item):\n    return {'item_name': item.name, 'item_price': item.price}\n",
                    },
                ],
            },
        ],
    },
    {
        "slug": "fastapi-deployment",
        "title": "Deployment and Production",
        "description": "Deploy FastAPI with Docker and production settings.",
        "lessons": [
            {
                "slug": "docker-deployment",
                "title": "Deploy with Docker",
                "summary": "Package your FastAPI app in a Docker container for hosting.",
                "sections": [
                    {
                        "heading": "Dockerfile basics",
                        "text": "Build a small Python image and run uvicorn in production mode.",
                        "code": "FROM python:3.11-slim\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\nCOPY . .\nCMD [\"uvicorn\", \"main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8000\"]\n",
                    },
                ],
            },
            {
                "slug": "production-best-practices",
                "title": "Production Best Practices",
                "summary": "Use environment variables and secure settings in production.",
                "sections": [
                    {
                        "heading": "Environment setup",
                        "text": "Keep secrets out of source control and use settings for production."
                    },
                ],
            },
        ],
    },
]

COURSE_BY_SLUG = {module['slug']: module for module in COURSE_MODULES}
for module in COURSE_MODULES:
    module['lessons_by_slug'] = {lesson['slug']: lesson for lesson in module['lessons']}
