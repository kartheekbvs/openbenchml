# Auth API

## Register

```
POST /api/auth/register
Content-Type: application/json

{
  "username": "alice",
  "email": "alice@example.com",
  "password": "secret",
  "confirm_password": "secret"
}
```

**Response (200):**

```json
{
  "message": "Registration successful",
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "user": { "id": 1, "username": "alice", "email": "alice@example.com" }
}
```

**Errors:**

- `400` — Passwords don't match, password too short, or invalid input
- `409` — Username or email already registered
- `500` — Internal error

---

## Login

```
POST /api/auth/login
Content-Type: application/json

{ "email": "alice@example.com", "password": "secret" }
```

**Response (200):**

```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": 1,
    "username": "alice",
    "email": "alice@example.com",
    "organization": null,
    "is_admin": false
  }
}
```

**Errors:**

- `401` — Invalid email or password
- `403` — Account deactivated

---

## Refresh

```
POST /api/auth/refresh
Content-Type: application/json

{ "refresh_token": "eyJ..." }
```

Returns a new `access_token` and `refresh_token`. The refresh token's `type` claim must be `"refresh"`.

---

## Current user

```
GET /api/auth/me
Authorization: Bearer <access_token>
```

Returns the user's public profile (id, username, organization, avatar_url, bio, is_verified, created_at).

**Errors:**

- `401` — Not authenticated
