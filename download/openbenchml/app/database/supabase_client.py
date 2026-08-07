"""
OpenBenchML Supabase Client
============================
Direct Supabase Python client — same pattern as the fastapiproject
repo's `app/db.py`:

    from supabase import create_client, Client
    url = "https://fzwvxesrtdilljgrntpw.supabase.co"
    key = "<anon key>"
    supabase: Client = create_client(url, key)

Per the user's instruction ("id is username and username is password"):
  - The Supabase **project ref** (`fzwvxesrtdilljgrntpw`) doubles as
    the username when forming the SQLAlchemy pooler URL.
  - The Supabase **DB password** doubles as the password.
  - The Supabase **anon key** is used for REST API access (RLS-protected).

This module exposes a single `supabase` client instance that the rest
of the app imports — exactly like the fastapiproject pattern.

The client is **lazy-initialized** so the app still boots when Supabase
is unreachable (offline dev, network down).  Importing this module
never crashes.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.config import SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_PROJECT_REF

logger = logging.getLogger(__name__)

# Re-export the project ref so consumers can do:
#   from app.database.supabase_client import SUPABASE_PROJECT_REF
__all__ = ["supabase", "get_supabase", "is_available", "SUPABASE_PROJECT_REF"]

# Module-level singleton (mirrors fastapiproject/app/db.py).
# Lazy-initialized on first access so import is side-effect free.
_supabase_client: Any = None
_init_failed: bool = False


def _initialize() -> Any:
    """Initialize the Supabase client once. Returns the client or None."""
    global _supabase_client, _init_failed
    if _supabase_client is not None or _init_failed:
        return _supabase_client

    try:
        from supabase import create_client, Client  # type: ignore
    except ImportError:
        logger.warning(
            "supabase-py not installed — direct table API disabled. "
            "Run: pip install supabase"
        )
        _init_failed = True
        return None
    except Exception as exc:
        logger.warning("Failed to import supabase: %s", exc)
        _init_failed = True
        return None

    try:
        # Same call as fastapiproject/app/db.py
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        logger.info(
            "Supabase client initialized → %s (project ref %s)",
            SUPABASE_URL,
            SUPABASE_PROJECT_REF,
        )
    except Exception as exc:
        logger.warning("Supabase client init failed: %s", exc)
        _init_failed = True
        return None

    return _supabase_client


def get_supabase() -> Any:
    """Return the singleton Supabase client (lazy-init on first call).

    Returns None if initialization failed (e.g. supabase-py not installed
    or Supabase unreachable).  Callers should check for None.
    """
    return _initialize()


def is_available() -> bool:
    """True when the Supabase client was successfully initialized."""
    return _initialize() is not None


# Lazy proxy: `from app.database.supabase_client import supabase` returns
# an object that initializes on first attribute access.  This mirrors the
# fastapiproject pattern (`from app.db import supabase`) while keeping the
# import side-effect-free.
class _LazySupabaseProxy:
    """Lazy proxy that defers Supabase client init until first use.

    Any attribute access (e.g. `supabase.table(...)`) triggers init.
    If init fails, the proxy raises a clear RuntimeError.
    """

    __slots__ = ("_client",)

    def __init__(self):
        self._client: Any = None

    def _resolve(self) -> Any:
        if self._client is None:
            self._client = _initialize()
            if self._client is None:
                raise RuntimeError(
                    "Supabase client is not available. "
                    "Install with `pip install supabase` and verify "
                    "network connectivity to " + SUPABASE_URL
                )
        return self._client

    def __getattr__(self, name: str) -> Any:
        return getattr(self._resolve(), name)

    def __repr__(self) -> str:
        if self._client is None:
            return f"<LazySupabaseProxy (uninitialized, url={SUPABASE_URL})>"
        return f"<LazySupabaseProxy -> {self._client!r}>"


# Public singleton — mirrors fastapiproject's `supabase: Client = create_client(...)`
supabase: Any = _LazySupabaseProxy()


# ─── Convenience helpers (optional — most callers use supabase directly) ────


def table(name: str):
    """Shortcut: `from app.database.supabase_client import table; table('users').select('*').execute()`.

    Equivalent to `supabase.table(name)`.  Returns the PostgrestQueryBuilder
    or raises RuntimeError if Supabase isn't available.
    """
    return supabase.table(name)


def fetch_all(table_name: str, columns: str = "*") -> list:
    """One-liner: SELECT * FROM <table_name>.  Returns a list of dicts."""
    return supabase.table(table_name).select(columns).execute().data


def fetch_one(table_name: str, column: str, value: Any) -> Optional[dict]:
    """One-liner: SELECT * FROM <table_name> WHERE <column>=<value> LIMIT 1."""
    rows = supabase.table(table_name).select("*").eq(column, value).limit(1).execute().data
    return rows[0] if rows else None


def insert_row(table_name: str, data: dict) -> dict:
    """One-liner: INSERT INTO <table_name> ... Returns the inserted row."""
    rows = supabase.table(table_name).insert(data).execute().data
    return rows[0] if rows else {}


def update_rows(table_name: str, data: dict, column: str, value: Any) -> list:
    """One-liner: UPDATE <table_name> SET ... WHERE <column>=<value>."""
    return supabase.table(table_name).update(data).eq(column, value).execute().data


def delete_rows(table_name: str, column: str, value: Any) -> list:
    """One-liner: DELETE FROM <table_name> WHERE <column>=<value>."""
    return supabase.table(table_name).delete().eq(column, value).execute().data
