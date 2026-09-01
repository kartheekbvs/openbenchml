# Competitions API

## List competitions

```
GET /api/competitions?status={status}
```

| Param | Required | Description |
|-------|----------|-------------|
| `status` | no | Filter by status (`upcoming`, `live`, `ended`) |

**Response (200):**

```json
[
  {
    "id": 1,
    "title": "Iris Classification Challenge",
    "slug": "iris-classification-challenge",
    "description": "...",
    "dataset_id": 1,
    "evaluation_metric": "accuracy",
    "task_type": "classification",
    "starts_at": "2025-01-15T00:00:00",
    "ends_at": "2025-02-14T00:00:00",
    "status": "live",
    "max_submissions_per_user": 10
  }
]
```

---

## Competition detail

```
GET /api/competitions/{slug}
```

Returns full competition metadata plus the current leaderboard.

**Response (200):**

```json
{
  "id": 1,
  "title": "Iris Classification Challenge",
  "slug": "iris-classification-challenge",
  "description": "...",
  "rules": "...",
  "prize": "...",
  "dataset_id": 1,
  "evaluation_metric": "accuracy",
  "task_type": "classification",
  "starts_at": "2025-01-15T00:00:00",
  "ends_at": "2025-02-14T00:00:00",
  "status": "live",
  "max_submissions_per_user": 10,
  "leaderboard": [
    {
      "rank": 1,
      "user_id": 1,
      "username": "alice",
      "model_id": 1,
      "model_name": "RandomForest Iris",
      "score": 1.0,
      "submitted_at": "2025-01-15T12:34:56"
    }
  ],
  "total_submissions": 1,
  "unique_participants": 1
}
```

**Errors:**

- `404` — Competition not found

---

## Competition leaderboard

```
GET /api/competitions/{slug}/leaderboard
```

Returns just the leaderboard (best submission per user). Useful for live polling.

**Response (200):** Same shape as the `leaderboard` array above.

---

## Submit a model

```
POST /competitions/{slug}/submit
Content-Type: application/x-www-form-urlencoded
Authorization: Bearer <token>

model_id=1&submission_note=First attempt
```

**Response (303):** Redirects to `/competitions/{slug}` on success.

The endpoint:

1. Validates the competition is `live`.
2. Validates the model belongs to the submitter.
3. Checks the user hasn't exceeded `max_submissions_per_user`.
4. Creates a benchmark job and runs it.
5. Extracts the score using `evaluation_metric`.
6. Persists a `CompetitionSubmission`.
7. Recomputes the per-competition leaderboard (marks `is_best` on the user's best submission).
8. Sends a `submission_received` notification to the user.

**Errors:**

- `400` — Competition not live, or submission limit reached
- `401` — Not authenticated
- `404` — Competition or model not found

---

## Create a competition

Admins create competitions via the HTML form at `/competitions/create`. There's no JSON endpoint for this yet (planned).
