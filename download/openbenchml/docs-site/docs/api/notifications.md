# Notifications API

Notifications are in-app messages triggered by platform events: a benchmark completing, a leaderboard rank change, a competition starting/ending, a comment reply, or a competition submission being received.

## List notifications

```
GET /api/notifications?unread_only={bool}&limit={n}
Authorization: Bearer <token>
```

| Param | Required | Description |
|-------|----------|-------------|
| `unread_only` | no | `true` to only return unread (default `false`) |
| `limit` | no | Max items (default 50, max 200) |

**Response (200):**

```json
[
  {
    "id": 1,
    "type": "submission_received",
    "title": "Submission received for Iris Classification Challenge",
    "body": "Score (accuracy): 1.0",
    "link": "/competitions/iris-classification-challenge",
    "is_read": false,
    "created_at": "2025-01-15T12:34:56"
  }
]
```

---

## Mark as read

```
POST /api/notifications/{id}/read
Authorization: Bearer <token>
```

Returns `{"status": "read", "id": <id>}`.

---

## Mark all as read

```
POST /api/notifications/read-all
Authorization: Bearer <token>
```

Returns `{"status": "all_read"}`.

---

## Unread count

```
GET /api/notifications/unread-count
```

Returns `{"count": <int>}`. Useful for a navbar badge.

If unauthenticated, returns `{"count": 0}` (does not error).

---

## WebSocket: real-time push

```
WS /ws/notifications
```

When a notification is created, all connected clients receive:

```json
{
  "type": "notification",
  "user_id": 1,
  "notification_type": "submission_received",
  "title": "Submission received for Iris Classification Challenge",
  "body": "Score (accuracy): 1.0",
  "link": "/competitions/iris-classification-challenge",
  "created_at": "2025-01-15T12:34:56"
}
```

Clients should filter by `user_id` and ignore notifications for other users (the broadcast is shared across all connections in this version).

---

## Notification types

| Type | When |
|------|------|
| `submission_received` | A competition submission finished benchmarking |
| `comment_reply` | Someone replied to your comment |
| `benchmark_completed` | A benchmark job finished (planned) |
| `leaderboard_changed` | Your rank on a leaderboard changed (planned) |
| `competition_started` | A competition transitioned to `live` (planned) |
| `competition_ended` | A competition transitioned to `ended` (planned) |
