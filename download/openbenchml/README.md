# OpenBenchML

**Open Source ML Model Benchmarking Platform**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://docker.com)

OpenBenchML is an open-source platform where developers upload ML models, run them against standard datasets, and compare accuracy, speed, and size on a public leaderboard. Built with FastAPI, SQLAlchemy, Celery, Redis, and Docker.

---

## Features

- **Multi-Framework Support** - scikit-learn, PyTorch, ONNX, TensorFlow, XGBoost, LightGBM
- **Docker Sandbox** - Secure model execution with network isolation, memory/CPU limits
- **Real-time Leaderboards** - By accuracy, speed, and model size
- **Performance Metrics** - Accuracy, Precision, Recall, F1, MAE, RMSE, R2, Latency (P50/P95/P99), Memory, CPU, Throughput
- **REST API** - Full JSON API with JWT authentication, refresh tokens, and API keys
- **WebSocket** - Real-time benchmark progress updates
- **Async Processing** - Celery + Redis background task queue
- **6 Built-in Datasets** - Iris, Wine, Breast Cancer, Digits, California Housing, Diabetes
- **Dark Theme UI** - Professional dashboard with Chart.js visualizations
- **Production Ready** - CORS, GZip, rate limiting, security headers, health checks

---

## Quick Start

### Local Development (SQLite, no Docker required)

```bash
# Clone the repository
git clone https://github.com/kartheekbvs/openbenchml.git
cd openbenchml

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Run the development server
python run.py
```

Visit http://localhost:8000

### Docker Compose (Full Stack)

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f app

# Stop all services
docker compose down
```

---

## API Documentation

Interactive API docs available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login and get JWT token |
| POST | `/api/auth/refresh` | Refresh access token |
| GET | `/api/models` | List public models |
| POST | `/models/upload` | Upload ML model |
| GET | `/api/datasets` | List datasets |
| GET | `/api/jobs` | List benchmark jobs |
| GET | `/api/results/{id}` | Get benchmark results |
| GET | `/api/leaderboard` | Get leaderboard data |
| GET | `/api/info` | API metadata |
| GET | `/health` | Health check |

---

## Architecture

```
Client (Browser)
    |
    v
Nginx (Reverse Proxy, Static Files)
    |
    v
FastAPI Application
    |-- Jinja2 Templates (HTML Pages)
    |-- REST API (JSON Endpoints)
    |-- WebSocket (Real-time Updates)
    |
    +-- PostgreSQL (Production) / SQLite (Dev)
    +-- Redis (Cache + Message Broker)
    +-- Celery Worker (Async Benchmark Execution)
    +-- Docker Sandbox (Secure Model Execution)
```

---

## Project Structure

```
openbenchml/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, middleware, WebSocket
│   ├── config.py             # Central configuration
│   ├── database/
│   │   ├── db.py             # SQLAlchemy engine, sessions
│   │   ├── models.py         # 8 ORM models
│   │   └── seed.py           # Built-in dataset seeding
│   ├── routes/
│   │   ├── auth.py           # Auth routes (HTML + API)
│   │   ├── dashboard.py      # Dashboard + stats API
│   │   ├── models.py         # Model management
│   │   ├── datasets.py       # Dataset browsing
│   │   ├── benchmark.py      # Benchmark execution
│   │   └── leaderboard.py    # Leaderboard views
│   ├── services/
│   │   ├── auth_service.py   # Auth + API keys + activity logging
│   │   ├── benchmark_service.py  # Benchmark orchestration
│   │   └── upload_service.py # File upload handling
│   ├── benchmark_engine/
│   │   ├── evaluator.py      # Evaluation pipeline
│   │   ├── loader.py         # Multi-framework model loading
│   │   └── metrics.py        # All metric computations
│   ├── docker_runner/
│   │   ├── runner.py         # Docker sandbox execution
│   │   ├── worker.py         # In-container worker
│   │   └── Dockerfile        # Worker image
│   └── workers/
│       └── celery_worker.py  # Celery task queue
├── templates/                # 15 Jinja2 HTML templates
├── static/
│   ├── css/style.css         # Dark theme stylesheet
│   └── js/
│       ├── main.js           # Client utilities
│       └── charts.js         # Chart.js visualizations
├── docs/
│   └── index.html            # GitHub Pages landing page
├── docker-compose.yml        # Full stack deployment
├── Dockerfile                # App image
├── nginx.conf                # Reverse proxy config
├── requirements.txt          # Python dependencies
├── run.py                    # Dev server launcher
├── railway.toml              # Railway deployment
├── render.yaml               # Render deployment
├── fly.toml                  # Fly.io deployment
├── .env.example              # Environment template
└── .gitignore
```

---

## Configuration

All settings are configurable via environment variables. See `.env.example` for the full list.

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | True | Enable debug mode |
| `SECRET_KEY` | (change in prod) | JWT signing key |
| `USE_SQLITE` | True | Use SQLite (True) or PostgreSQL (False) |
| `DATABASE_URL` | postgresql://... | PostgreSQL connection string |
| `REDIS_URL` | redis://localhost:6379/0 | Redis connection |
| `DOCKER_ENABLED` | False | Enable Docker sandbox |
| `MAX_MODEL_SIZE_MB` | 500 | Max upload size |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 60 | JWT token expiry |
| `CORS_ORIGINS` | localhost:8000 | Allowed origins |
| `RATE_LIMIT_ENABLED` | True | Enable rate limiting |

---

## Deployment

### Railway

```bash
railway init
railway up
```

### Render

Push to GitHub and connect the repository in Render dashboard. The `render.yaml` blueprint configures everything automatically.

### Fly.io

```bash
fly launch
fly deploy
```

### Docker Compose (VPS)

```bash
docker compose up -d
```

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI 0.109, Python 3.11 |
| Database | SQLAlchemy 2.0, PostgreSQL 16 / SQLite |
| Auth | JWT (python-jose), bcrypt, HttpOnly cookies |
| Task Queue | Celery 5.3, Redis 7 |
| ML | scikit-learn, XGBoost, LightGBM, (PyTorch, ONNX, TF optional) |
| Frontend | Jinja2, Chart.js, CSS3 |
| Sandbox | Docker with resource limits |
| Proxy | Nginx with security headers |

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing`)
5. Open a Pull Request

---

## License

MIT License - see [LICENSE](LICENSE) for details.
