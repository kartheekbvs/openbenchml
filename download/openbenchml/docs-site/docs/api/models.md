# Models API

## List public models

```
GET /api/models?framework={framework}
```

| Param | Required | Description |
|-------|----------|-------------|
| `framework` | no | Filter by framework (`scikit-learn`, `pytorch`, `onnx`, `tensorflow`, `xgboost`, `lightgbm`) |

**Response (200):**

```json
[
  {
    "id": 1,
    "model_name": "RandomForest Iris",
    "framework": "scikit-learn",
    "size_kb": 37.36,
    "version": "v1",
    "is_public": true,
    "created_at": "2025-01-15T12:34:56.789000"
  }
]
```

---

## Get model detail

```
GET /api/models/{model_id}
```

Returns full model metadata, owner info, and benchmark summary.

**Response (200):**

```json
{
  "id": 1,
  "model_name": "RandomForest Iris",
  "description": "50-tree RF on Iris",
  "framework": "scikit-learn",
  "size_kb": 37.36,
  "version": "v1",
  "is_public": true,
  "owner": "alice",
  "created_at": "2025-01-15T12:34:56.789000",
  "updated_at": "2025-01-15T12:34:56.789000",
  "benchmark_summary": { "completed": 3, "failed": 1 }
}
```

**Errors:**

- `404` — Model not found (or model is private and you're not the owner)

---

## Upload a model

```
POST /models/upload
Content-Type: multipart/form-data
Authorization: Bearer <token> (or access_token cookie)

model_name: RandomForest Iris
framework: scikit-learn
description: 50-tree RF
file: <binary file>
```

**Response (303):**

Redirects to `/my-models` on success. The CLI parses the redirect and then fetches the new model from `/api/models`.

**Errors:**

- `400` — Invalid file extension or framework
- `401` — Not authenticated
- `413` — File too large
- `422` — Form validation error

---

## Delete a model

```
POST /models/{model_id}/delete
Authorization: Bearer <token>
```

(HTML form-only — redirects to `/my-models` on success.)

Only the model owner can delete. Cascade removes benchmark jobs and leaderboard entries.
