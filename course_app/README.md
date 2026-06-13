# FastAPI Course App

This inner app is a self-contained FastAPI course site designed to deploy on a dedicated domain such as `http://openbenchml.twss.shop/`.

## Run locally

```bash
cd course_app
python -m pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Then open `http://localhost:8000/`.

## Deploy

Use the included `Dockerfile` to deploy this app as a standalone service.

Example command:

```bash
docker build -t openbenchml-course .
docker run -p 8000:8000 openbenchml-course
```

If you want the course to be served at the root path of a domain, deploy this inner app as the root service for that domain.
