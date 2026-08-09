# Discussions

OpenBenchML supports threaded comments on both models and competitions. Comments support replies (one level deep), pinning (admin only), and soft deletion.

## Posting a comment

### Via the web UI

Each model detail page (`/models/{id}`) and competition detail page (`/competitions/{slug}`) has a discussion section at the bottom. Use the form to post a top-level comment, or click "Reply" on any existing comment to post a reply.

### Via the API

```bash
# Top-level comment on a competition
curl -X POST http://localhost:8000/comments \
  -H "Authorization: Bearer $TOKEN" \
  -d "body=Great competition! Looking forward to it." \
  -d "competition_id=1"

# Reply to an existing comment
curl -X POST http://localhost:8000/comments \
  -H "Authorization: Bearer $TOKEN" \
  -d "body=Thanks for the tip!" \
  -d "parent_id=5"
```

## Listing comments

```bash
# All top-level comments on a competition (with replies nested)
curl 'http://localhost:8000/api/comments?competition_id=1'

# Comments on a model
curl 'http://localhost:8000/api/comments?model_id=42'
```

Response shape:

```json
[
  {
    "id": 1,
    "author_id": 1,
    "author_username": "alice",
    "body": "First to comment!",
    "is_pinned": false,
    "created_at": "2025-01-15T12:34:56",
    "depth": 0,
    "replies": [
      {
        "id": 2,
        "author_id": 2,
        "author_username": "bob",
        "body": "Welcome!",
        "depth": 1,
        "replies": []
      }
    ]
  }
]
```

## Deleting a comment

Only the author or an admin can delete a comment. Deletion cascades to replies.

```bash
curl -X DELETE http://localhost:8000/api/comments/5 \
  -H "Authorization: Bearer $TOKEN"
```

## Notifications

When you reply to someone else's comment, the parent comment's author receives a `comment_reply` notification. See [Notifications](../api/notifications.md) for the full notification API.
