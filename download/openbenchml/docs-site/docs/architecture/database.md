# Database Schema

OpenBenchML uses 14 tables. SQLite for development (zero-config), PostgreSQL for production.

## ER diagram (textual)

```text
users ─┬─< models ─┬─< benchmark_jobs ─< benchmark_results
       │           ├─< leaderboard
       │           ├─< competition_submissions >─ competitions
       │           └─< comments
       ├─< api_keys
       ├─< user_activity
       ├─< team_members >─ teams >─ competitions
       └─< notifications

datasets ─┬─< benchmark_jobs
          ├─< leaderboard
          └─< competitions

competitions ─┬─< competition_submissions
              ├─< teams
              └─< comments

comments ──< comments  (self-referential for replies)
```

## Tables

### `users`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| username | VARCHAR(50) UNIQUE | |
| email | VARCHAR(120) UNIQUE | Lower-cased |
| password_hash | VARCHAR(256) | bcrypt |
| organization | VARCHAR(120) | Nullable |
| avatar_url | VARCHAR(500) | Nullable |
| bio | TEXT | Nullable |
| is_active | BOOLEAN | Default true |
| is_admin | BOOLEAN | Default false |
| is_verified | BOOLEAN | Default false |
| created_at / last_login / updated_at | DATETIME | |

### `models`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| user_id | FK → users.id | CASCADE on delete |
| model_name | VARCHAR(120) | |
| description | TEXT | Nullable |
| framework | VARCHAR(50) | scikit-learn, pytorch, onnx, etc. |
| file_path | VARCHAR(500) | Absolute path under UPLOAD_DIR |
| version | VARCHAR(20) | Default "v1" |
| size_kb | FLOAT | |
| is_public | BOOLEAN | Default true |
| tags | JSON | List of strings |
| download_count | INTEGER | Default 0 |

### `datasets`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| name | VARCHAR(120) UNIQUE | e.g. "Iris" |
| task_type | VARCHAR(50) | classification / regression / clustering |
| description | TEXT | |
| samples | INTEGER | |
| features | INTEGER | |
| file_path | VARCHAR(500) | Nullable (None for built-in) |
| is_builtin | BOOLEAN | Default true |
| difficulty | VARCHAR(20) | beginner / intermediate / advanced |
| tags | JSON | |

### `benchmark_jobs`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| model_id | FK → models.id | CASCADE |
| dataset_id | FK → datasets.id | CASCADE |
| status | ENUM | pending / running / completed / failed |
| progress | INTEGER | 0–100 |
| error_message | TEXT | Nullable |
| submitted_at / started_at / finished_at | DATETIME | |
| execution_time_ms | INTEGER | |
| worker_id | VARCHAR(100) | Celery task ID (future) |

### `benchmark_results`
One row per completed job (1:1 with `benchmark_jobs`).

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| job_id | FK → benchmark_jobs.id | UNIQUE |
| accuracy / precision / recall / f1_score | FLOAT | Classification |
| mae / rmse / r2_score | FLOAT | Regression |
| auc_roc / log_loss | FLOAT | Advanced classification |
| confusion_matrix | JSON | 2D array |
| classification_report | JSON | Per-class dict |
| latency_ms | FLOAT | Mean per-sample |
| latency_p50_ms / latency_p95_ms / latency_p99_ms | FLOAT | True percentiles |
| memory_mb / cpu_percent / model_size_kb | FLOAT | |
| inference_count | INTEGER | |
| throughput_per_sec | FLOAT | |

### `leaderboard`
Per (model, dataset) ranking. Unique on (model_id, dataset_id).

| Column | Type | Notes |
|--------|------|-------|
| model_id | FK → models.id | |
| dataset_id | FK → datasets.id | |
| rank | INTEGER | Dense ranking |
| score | FLOAT | Accuracy for classification, R² for regression |
| previous_rank | INTEGER | For "▲ 2" / "▼ 1" indicators |
| updated_at | DATETIME | |

### `competitions`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| title / slug | VARCHAR(200) | slug is UNIQUE |
| description / rules / prize | TEXT | |
| dataset_id | FK → datasets.id | RESTRICT on delete |
| evaluation_metric | VARCHAR(50) | accuracy / f1_score / auc_roc / r2_score / rmse / mae / latency_ms / log_loss |
| task_type | VARCHAR(50) | |
| starts_at / ends_at | DATETIME | |
| status | VARCHAR(20) | upcoming / live / ended (derived) |
| max_submissions_per_user | INTEGER | Default 10 |
| created_by | FK → users.id | SET NULL on delete |

### `competition_submissions`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| competition_id | FK → competitions.id | CASCADE |
| user_id | FK → users.id | CASCADE |
| model_id | FK → models.id | CASCADE |
| team_id | FK → teams.id | SET NULL |
| benchmark_job_id | FK → benchmark_jobs.id | SET NULL |
| score | FLOAT | Extracted from benchmark result |
| is_best | BOOLEAN | True for the user's best submission |
| submission_note | TEXT | |
| submitted_at | DATETIME | |

Unique on `(competition_id, user_id, model_id)`.

### `teams` / `team_members`
For team-based competitions (not yet exposed in the UI). `team_members` has a unique constraint on `(team_id, user_id)` and a `role` field (`owner` / `member`).

### `comments`
Threaded comments on models OR competitions.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| author_id | FK → users.id | CASCADE |
| parent_id | FK → comments.id | CASCADE, self-reference for replies |
| model_id | FK → models.id | CASCADE, nullable |
| competition_id | FK → competitions.id | CASCADE, nullable |
| body | TEXT | |
| is_pinned | BOOLEAN | Default false |
| created_at / updated_at | DATETIME | |

### `notifications`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| user_id | FK → users.id | CASCADE |
| type | VARCHAR(50) | submission_received / comment_reply / ... |
| title / body / link | VARCHAR/TEXT | |
| is_read | BOOLEAN | Default false |
| created_at | DATETIME | |

### `api_keys` / `user_activity`
Supporting tables for programmatic API access and audit logging. `api_keys` stores hashed keys with a prefix for identification; `user_activity` records login/upload/benchmark events with IP and user-agent.

## Indexes

The schema includes composite indexes on:

- `(model_id, dataset_id)` unique on `leaderboard`
- `(dataset_id, rank)` on `leaderboard`
- `(status, submitted_at)` on `benchmark_jobs`
- `(user_id, action)` on `user_activity`
- `(competition_id, score)` on `competition_submissions`
- `(team_id, user_id)` unique on `team_members`

## Migrations

Development uses `Base.metadata.create_all()` (auto-creates all tables on startup). For production, use Alembic (configured in `requirements.txt` but migrations not yet written — planned for v3.1).
