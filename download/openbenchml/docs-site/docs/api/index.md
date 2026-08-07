# API Reference

OpenBenchML exposes a REST API under `/api/*`. All list endpoints return JSON arrays; detail endpoints return JSON objects. Authentication uses JWT tokens passed as either a cookie (`access_token`) or an `Authorization: Bearer <token>` header.

## Base URL

```
http://localhost:8000
```

## Authentication

```bash
# Register
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","email":"alice@example.com","password":"secret","confirm_password":"secret"}'

# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"secret"}'

# Refresh
curl -X POST http://localhost:8000/api/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<refresh_token>"}'

# Current user
curl http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer <access_token>"
```

## Endpoints at a glance

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Register a new user |
| POST | `/api/auth/login` | Login |
| POST | `/api/auth/refresh` | Refresh access token |
| GET | `/api/auth/me` | Current user |
| GET | `/api/models` | List public models |
| GET | `/api/models/{id}` | Model detail |
| GET | `/api/datasets` | List datasets |
| GET | `/api/jobs` | List benchmark jobs |
| GET | `/api/results/{job_id}` | Benchmark results |
| GET | `/api/leaderboard` | Global leaderboard |
| GET | `/api/competitions` | List competitions |
| GET | `/api/competitions/{slug}` | Competition detail + leaderboard |
| GET | `/api/competitions/{slug}/leaderboard` | Competition leaderboard only |
| GET | `/api/comments` | List comments (model or competition) |
| POST | `/comments` | Create a comment (form-encoded) |
| DELETE | `/api/comments/{id}` | Delete a comment |
| GET | `/api/notifications` | List notifications |
| POST | `/api/notifications/{id}/read` | Mark notification as read |
| POST | `/api/notifications/read-all` | Mark all as read |
| GET | `/api/notifications/unread-count` | Unread count |
| GET | `/health` | Health check |
| GET | `/api/info` | API metadata |
| WS | `/ws/benchmark` | Live benchmark progress |
| WS | `/ws/leaderboard` | Leaderboard change notifications |
| WS | `/ws/notifications` | Real-time notifications |

## Interactive docs

The server ships with auto-generated OpenAPI docs at:

- `/docs` — Swagger UI
- `/redoc` — ReDoc
- `/openapi.json` — Raw OpenAPI spec

## Sub-pages

- [Auth](auth.md)
- [Models](models.md)
- [Benchmarks](benchmarks.md)
- [Leaderboard](leaderboard.md)
- [Competitions](competitions.md)
- [Notifications](notifications.md)
