"""
Cross-domain auth bridge: Render ↔ Hugging Face Spaces.

Problem:
  Render hosts the main app at openbenchml.onrender.com (sets HttpOnly JWT cookie).
  HF Spaces hosts the notebook at openbenchml.hf.space (separate domain, separate cookie jar).
  Browsers won't send Render's cookie to HF, so the user would have to log in twice.

Solution:
  1. User on Render clicks "Open Notebook". Frontend calls
     /api/auth/bridge_token (must be logged in) → gets a short-lived (5-min)
     one-time JWT signed with the shared SECRET_KEY.
  2. Frontend redirects to https://openbenchml.hf.space/auth/bridge?token=...&redirect=/notebook
  3. HF decodes the token (verifies signature with same SECRET_KEY), upserts
     a stub user in its local SQLite DB (so the existing `current_user`
     dependency works unchanged), mints a fresh access_token, sets it as
     an HttpOnly cookie on the HF domain, and redirects to /notebook.

Security:
  - Token is short-lived (5 min) — reduces risk of URL leakage.
  - Token is single-use (we track consumed JTI in an in-memory set).
  - SECRET_KEY is shared between Render and HF (set via env vars on both).
  - Stub user's password_hash is "BRIDGED" — cannot be used to log in
    directly on HF (the regular /login route rejects it).
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from app.database.db import get_db
from app.database.models import User
from app.services.auth_service import create_access_token, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

# ─── Constants ───────────────────────────────────────────────────────────────
BRIDGE_TOKEN_TTL_SECONDS = 5 * 60  # 5 minutes
BRIDGE_TOKEN_TYPE = "bridge"
CONSUMED_JTI_TTL_SECONDS = 10 * 60  # keep consumed JTIs for 10 min, then evict

# In-memory set of consumed JTI (JWT ID) values to enforce single-use.
# This is per-process — on HF Spaces single-worker deployment, that's fine.
# (If we ever scale to multiple workers, switch to Redis.)
_consumed_jtis: dict[str, float] = {}  # jti → consumed_at_epoch


def _evict_consumed_jtis() -> None:
    """Drop consumed JTIs older than the TTL to keep the set bounded."""
    now = time.time()
    cutoff = now - CONSUMED_JTI_TTL_SECONDS
    expired = [jti for jti, ts in _consumed_jtis.items() if ts < cutoff]
    for jti in expired:
        _consumed_jtis.pop(jti, None)


# ─── Render-side: issue a bridge token ───────────────────────────────────────

class BridgeTokenResponse(BaseModel):
    token: str
    url: str
    expires_in_seconds: int


@router.get("/api/auth/bridge_token", response_model=BridgeTokenResponse)
async def issue_bridge_token(
    request: Request,
    user: User = Depends(get_current_user),
) -> BridgeTokenResponse:
    """Issue a one-time, short-lived token that lets the user skip login on HF.

    The frontend should call this endpoint, then redirect the browser to the
    returned `url` (which points at the HF Space's /auth/bridge route).
    """
    import os, uuid
    hf_url = os.environ.get("HF_SPACES_URL", "").rstrip("/")
    if not hf_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="HF_SPACES_URL is not configured on the server. The notebook "
                   "is running on Render only.",
        )

    jti = str(uuid.uuid4())
    now = datetime.utcnow()
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "email": user.email,
        "iat": now,
        "exp": now + timedelta(seconds=BRIDGE_TOKEN_TTL_SECONDS),
        "type": BRIDGE_TOKEN_TYPE,
        "jti": jti,
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    logger.info("Issued bridge token for user_id=%s (jti=%s)", user.id, jti)

    return BridgeTokenResponse(
        token=token,
        url=f"{hf_url}/auth/bridge?token={token}&redirect=/notebook",
        expires_in_seconds=BRIDGE_TOKEN_TTL_SECONDS,
    )


# ─── HF-side: consume a bridge token, set local cookie ──────────────────────

@router.get("/auth/bridge")
async def consume_bridge_token(
    token: str,
    redirect: str = "/notebook",
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Validate a bridge token from Render, upsert a stub user, set cookie, redirect.

    This route is called when the user is redirected from Render to HF with
    a one-time bridge token. After consuming the token, we set a normal
    HttpOnly access_token cookie on the HF domain so all subsequent notebook
    requests are authenticated.
    """
    # Validate redirect target — must be a relative path, no // to prevent open-redirect
    if not redirect.startswith("/") or redirect.startswith("//"):
        redirect = "/notebook"

    # Decode + verify the JWT
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as e:
        logger.warning("Bridge token decode failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bridge token is invalid or expired. Please return to the main site and try again.",
        )

    if payload.get("type") != BRIDGE_TOKEN_TYPE:
        logger.warning("Bridge token has wrong type: %s", payload.get("type"))
        raise HTTPException(status_code=401, detail="Invalid token type.")

    jti = payload.get("jti")
    if not jti:
        raise HTTPException(status_code=401, detail="Token missing JTI.")

    # Enforce single-use
    _evict_consumed_jtis()
    if jti in _consumed_jtis:
        logger.warning("Bridge token reuse attempt: jti=%s", jti)
        raise HTTPException(
            status_code=401,
            detail="This sign-in link has already been used. Please return to the main site and click Open Notebook again.",
        )
    _consumed_jtis[jti] = time.time()

    user_id_str = payload.get("sub")
    username = payload.get("username")
    email = payload.get("email")
    if not user_id_str or not username or not email:
        raise HTTPException(status_code=401, detail="Token missing required claims.")

    try:
        user_id = int(user_id_str)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Token has malformed user_id.")

    # Upsert stub user in local DB
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        # Update username/email in case they changed on Render
        user.username = username
        user.email = email
        user.last_login = datetime.utcnow()
    else:
        # Create stub — password_hash="BRIDGED" makes it impossible to log in
        # via the normal /login route on HF (which calls verify_password).
        user = User(
            id=user_id,
            username=username,
            email=email,
            password_hash="BRIDGED",
            is_active=True,
            is_verified=True,
            created_at=datetime.utcnow(),
            last_login=datetime.utcnow(),
        )
        db.add(user)
        logger.info("Created bridged stub user: id=%s username=%s", user_id, username)
    db.commit()

    # Mint a normal access token (1-hour expiry, same as regular login)
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username}
    )

    # Build redirect response with HttpOnly cookie
    import os
    secure_cookies = os.environ.get("SECURE_COOKIES", "true").lower() == "true"
    cookie_samesite = os.environ.get("COOKIE_SAMESITE", "lax")
    response = RedirectResponse(url=redirect, status_code=303)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite=cookie_samesite,
        secure=secure_cookies,
    )
    # Refresh token not needed on HF — users always re-bridge from Render
    logger.info("Bridge successful: user_id=%s → cookie set, redirecting to %s",
                user_id, redirect)
    return response


# ─── Health check for the bridge itself ──────────────────────────────────────

@router.get("/api/auth/bridge_status")
async def bridge_status():
    """Reports whether this instance is configured for cross-domain bridging.

    Render should report: {can_issue: true, can_consume: false}
    HF should report:     {can_issue: false, can_consume: true}
    """
    import os
    return {
        "can_issue": bool(os.environ.get("HF_SPACES_URL")),
        "can_consume": True,  # always — the /auth/bridge route is always mounted
        "bridge_token_ttl_seconds": BRIDGE_TOKEN_TTL_SECONDS,
    }
