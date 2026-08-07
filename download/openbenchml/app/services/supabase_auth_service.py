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

logger = logging.getLogger(__name__)

# ─── Lazy Supabase client ────────────────────────────────────────────────────
_supabase_client: Any = None
_supabase_init_failed: bool = False


def _get_client() -> Any:
    """Return a singleton Supabase client, or None if init failed.

    Lazy import + lazy init so the app boots even when the `supabase`
    Python package isn't installed (e.g. minimal dev envs).
    """
    global _supabase_client, _supabase_init_failed
    if _supabase_client is not None or _supabase_init_failed:
        return _supabase_client

    try:
        # `supabase` >= 2.x exposes `create_client`
        from supabase import create_client, Client  # type: ignore
    except ImportError:
        logger.warning(
            "supabase-py not installed — Supabase Auth disabled. "
            "Run: pip install supabase"
        )
        _supabase_init_failed = True
        return None
    except Exception as exc:
        logger.warning("Failed to import supabase: %s", exc)
        _supabase_init_failed = True
        return None

    try:
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        logger.info(
            "Supabase client initialized → %s (project ref %s)",
            SUPABASE_URL,
            SUPABASE_URL.split("//")[-1].split(".")[0],
        )
    except Exception as exc:
        logger.warning("Supabase client init failed: %s", exc)
        _supabase_init_failed = True
        return None

    return _supabase_client


def is_available() -> bool:
    """True when the Supabase client was successfully initialized."""
    return _get_client() is not None


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
