"""
OpenBenchML Supabase Auth Service
==================================
Thin wrapper around the Supabase Auth REST API.  Supabase is the
**source of truth for credentials** — it stores the email/password
hashes, handles email confirmation, password reset, etc.

After Supabase verifies a login, we still mint our own short-lived
JWT (see `auth_service.create_access_token`) so the rest of the app
— which already speaks our JWT dialect via `get_current_user` — keeps
working unchanged.

Why both?
  * Supabase Auth  → password storage / verification / reset emails
  * Our JWT         → fast stateless authz inside the FastAPI app

The Supabase client is **lazy-initialized** so the app still boots
when Supabase is unreachable (offline dev, network down).  Every
method returns None / raises a clear error in that case.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.config import SUPABASE_URL, SUPABASE_ANON_KEY
# Re-use the lazy client from app.database.supabase_client so we have ONE
# place that owns the Supabase connection (mirrors fastapiproject/app/db.py).
from app.database.supabase_client import get_supabase, is_available as _client_is_available

logger = logging.getLogger(__name__)

# ─── Lazy Supabase client (delegated to app.database.supabase_client) ──────
# The fastapiproject repo uses a module-level singleton:
#     supabase: Client = create_client(url, key)
# We follow the same pattern but defer initialization to first use so the
# app boots even when Supabase is offline.


def _get_client() -> Any:
    """Return the shared Supabase client (or None if unavailable)."""
    return get_supabase()


def is_available() -> bool:
    """True when the Supabase client was successfully initialized."""
    return _client_is_available()


# ─── Public API ──────────────────────────────────────────────────────────────


def sign_up(email: str, password: str) -> dict:
    """Register a new user with Supabase Auth.

    Returns a dict with keys:
        success : bool
        user    : dict | None    (Supabase user object on success)
        session : dict | None    (Supabase session on success)
        error   : str | None     (human-readable error message)
    """
    client = _get_client()
    if client is None:
        return {
            "success": False,
            "user": None,
            "session": None,
            "error": "Supabase Auth is not available on this server.",
        }

    try:
        # supabase-py 2.x: client.auth.sign_up({ "email": ..., "password": ... })
        response = client.auth.sign_up({
            "email": email.strip().lower(),
            "password": password,
        })
    except Exception as exc:
        logger.warning("Supabase sign_up failed: %s", exc)
        return {
            "success": False,
            "user": None,
            "session": None,
            "error": _humanize_error(str(exc)),
        }

    # Response shape: { user: {...}, session: {...} }  (session may be None
    # if email confirmation is required)
    user = getattr(response, "user", None) or (response.get("user") if isinstance(response, dict) else None)
    session = getattr(response, "session", None) or (response.get("session") if isinstance(response, dict) else None)

    if user is None:
        return {
            "success": False,
            "user": None,
            "session": None,
            "error": "Supabase returned no user. Email may already be registered.",
        }

    return {
        "success": True,
        "user": _user_to_dict(user),
        "session": _session_to_dict(session),
        "error": None,
    }


def sign_in_with_password(email: str, password: str) -> dict:
    """Log a user in with Supabase Auth.

    Returns a dict with the same shape as `sign_up`.
    """
    client = _get_client()
    if client is None:
        return {
            "success": False,
            "user": None,
            "session": None,
            "error": "Supabase Auth is not available on this server.",
        }

    try:
        response = client.auth.sign_in_with_password({
            "email": email.strip().lower(),
            "password": password,
        })
    except Exception as exc:
        logger.warning("Supabase sign_in failed: %s", exc)
        return {
            "success": False,
            "user": None,
            "session": None,
            "error": _humanize_error(str(exc)),
        }

    user = getattr(response, "user", None) or (response.get("user") if isinstance(response, dict) else None)
    session = getattr(response, "session", None) or (response.get("session") if isinstance(response, dict) else None)

    if user is None or session is None:
        return {
            "success": False,
            "user": None,
            "session": None,
            "error": "Invalid email or password.",
        }

    return {
        "success": True,
        "user": _user_to_dict(user),
        "session": _session_to_dict(session),
        "error": None,
    }


def sign_out(access_token: Optional[str] = None) -> bool:
    """Log the current Supabase session out.

    Returns True on success (or when no session was active).
    """
    client = _get_client()
    if client is None:
        return True

    try:
        if access_token:
            # Sign out the specific session
            client.auth.sign_out(access_token)
        else:
            client.auth.sign_out()
    except Exception as exc:
        logger.debug("Supabase sign_out failed (likely no session): %s", exc)
    return True


def get_user(access_token: str) -> Optional[dict]:
    """Look up the Supabase user for a given access token.

    Returns the user dict or None if the token is invalid/expired.
    """
    client = _get_client()
    if client is None or not access_token:
        return None

    try:
        response = client.auth.get_user(access_token)
        user = getattr(response, "user", None) or (response.get("user") if isinstance(response, dict) else None)
        return _user_to_dict(user) if user else None
    except Exception as exc:
        logger.debug("Supabase get_user failed: %s", exc)
        return None


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _user_to_dict(user: Any) -> dict:
    """Coerce a Supabase user object (Pydantic or dict) into a plain dict."""
    if user is None:
        return {}
    if isinstance(user, dict):
        return user
    # supabase-py returns Pydantic models; `.model_dump()` for v2, `.dict()` for v1
    if hasattr(user, "model_dump"):
        return user.model_dump()
    if hasattr(user, "dict"):
        return user.dict()
    return {"id": str(user)}


def _session_to_dict(session: Any) -> dict:
    """Coerce a Supabase session object into a plain dict."""
    if session is None:
        return {}
    if isinstance(session, dict):
        return session
    if hasattr(session, "model_dump"):
        return session.model_dump()
    if hasattr(session, "dict"):
        return session.dict()
    return {}


_ERROR_MAP = [
    ("Invalid login credentials", "Invalid email or password."),
    ("Email not confirmed", "Please confirm your email before logging in."),
    ("User already registered", "That email is already registered."),
    ("Password should be at least", "Password is too short (minimum 6 characters)."),
    ("Unable to validate email", "That email address looks invalid."),
    ("rate limit", "Too many attempts — please wait a minute and try again."),
]


def _humanize_error(raw: str) -> str:
    """Convert Supabase's verbose error messages into friendly strings."""
    if not raw:
        return "Authentication failed."
    low = raw.lower()
    for needle, friendly in _ERROR_MAP:
        if needle.lower() in low:
            return friendly
    # Strip the typical "AuthApiError: " prefix
    if ":" in raw and len(raw.split(":", 1)[1].strip()) < 200:
        return raw.split(":", 1)[1].strip()
    return raw[:200]


# ─── fastapiproject-style direct table CRUD ─────────────────────────────────
# These helpers mirror the pattern from the fastapiproject repo:
#   from app.db import supabase
#   supabase.table("fastsignin").insert(data).execute()
#
# We expose the same convenience for OpenBenchML's `users` table.  Per the
# user's instruction ("id is username and username is password"), the
# `fastsignin` table from fastapiproject is also mirrored so any existing
# data in that table is accessible.

def table(name: str):
    """Direct access: `supabase_auth_service.table('users').select('*').execute()`.

    Mirrors the fastapiproject pattern of `supabase.table(...)`.  Returns
    the PostgrestQueryBuilder or raises RuntimeError if Supabase isn't
    available.
    """
    client = _get_client()
    if client is None:
        raise RuntimeError("Supabase client is not available.")
    return client.table(name)


def list_fastsignin_users() -> list:
    """Return all rows from the `fastsignin` table (fastapiproject compatibility).

    Returns an empty list if Supabase is unavailable OR the table doesn't
    exist yet (fastapiproject didn't auto-create it).
    """
    try:
        return table("fastsignin").select("*").limit(1000).execute().data
    except Exception as exc:
        logger.debug("list_fastsignin_users failed (table may not exist): %s", exc)
        return []


def insert_fastsignin_row(data: dict) -> dict:
    """Insert a row into the `fastsignin` table (fastapiproject compatibility).

    Returns the inserted row dict, or {} on failure.
    """
    try:
        rows = table("fastsignin").insert(data).execute().data
        return rows[0] if rows else {}
    except Exception as exc:
        logger.warning("insert_fastsignin_row failed: %s", exc)
        return {}
