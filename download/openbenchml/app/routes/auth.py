"""
OpenBenchML Authentication Routes
===================================
Handles user registration, login, logout via both HTML forms and JSON API.
JWT tokens are stored in HttpOnly cookies for browser clients and returned
in the response body for API consumers.
Enhanced with rate limiting, activity logging, and refresh tokens.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, Depends, HTTPException, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.database.models import User
from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    oauth2_scheme,
    log_user_activity,
)
from app.services import supabase_auth_service as supa_auth
from app.config import (
    templates, SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES,
    SECURE_COOKIES, COOKIE_SAMESITE, RATE_LIMIT_LOGIN, RATE_LIMIT_REGISTER,
    SUPABASE_URL,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── HTML Form Routes ─────────────────────────────────────────────────────────


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Render the registration form."""
    return templates.TemplateResponse("register.html", {
        "request": request,
        "supabase_enabled": supa_auth.is_available(),
    })


@router.post("/register", response_class=HTMLResponse)
async def register_submit(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    """Handle registration form submission.

    Hybrid auth: tries Supabase Auth first (single source of truth for
    credentials in production). If Supabase is unavailable (offline dev),
    falls back to local DB password hashing.
    """
    # ── Validate passwords match ───────────────────────────────────────────
    if password != confirm_password:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Passwords do not match.",
        })

    # ── Validate password length ──────────────────────────────────────────
    if len(password) < 6:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Password must be at least 6 characters.",
        })

    # ── Check for existing username ────────────────────────────────────────
    existing_user = db.query(User).filter(
        (User.username == username.strip()) | (User.email == email.strip().lower())
    ).first()
    if existing_user:
        field = "Username" if existing_user.username == username.strip() else "Email"
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": f"{field} is already registered.",
        })

    # ── Try Supabase Auth first ────────────────────────────────────────────
    if supa_auth.is_available():
        supa_result = supa_auth.sign_up(email, password)
        if not supa_result["success"]:
            return templates.TemplateResponse("register.html", {
                "request": request,
                "error": supa_result["error"] or "Supabase registration failed.",
            })
        logger.info("Supabase Auth: new user %s", email)

    # ── Create the local user row (mirrors Supabase) ──────────────────────
    try:
        # Only store a password hash locally when Supabase is NOT used
        # (otherwise Supabase is the source of truth; we keep a placeholder).
        if supa_auth.is_available():
            hashed = "supabase-managed"  # credentials live in Supabase
        else:
            hashed = hash_password(password)

        new_user = User(
            username=username.strip(),
            email=email.strip().lower(),
            password_hash=hashed,
        )
        db.add(new_user)
        db.commit()
        logger.info("New user registered: %s", username)

        # Log activity
        log_user_activity(db, new_user.id, "register", request=request)

    except ValueError as exc:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": str(exc),
        })
    except Exception as exc:
        db.rollback()
        logger.error("Registration failed for %s: %s", username, exc)
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Registration failed. Please try again.",
        })

    return RedirectResponse(url="/login", status_code=303)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render the login form."""
    return templates.TemplateResponse("login.html", {
        "request": request,
        "supabase_enabled": supa_auth.is_available(),
    })


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """Handle login form submission.

    Hybrid auth: tries Supabase Auth first. If Supabase is unavailable
    OR the user has no Supabase account, falls back to local DB.
    """
    user = db.query(User).filter(User.email == email.strip().lower()).first()

    # ── Try Supabase first when available ─────────────────────────────────
    if supa_auth.is_available():
        supa_result = supa_auth.sign_in_with_password(email, password)
        if supa_result["success"]:
            # Auto-create the local user row if missing (Supabase-first flow)
            if user is None:
                supa_user = supa_result["user"] or {}
                username = (
                    supa_user.get("user_metadata", {}).get("username")
                    or supa_user.get("email", "").split("@")[0]
                    or "user"
                )
                user = User(
                    username=username[:50],
                    email=email.strip().lower(),
                    password_hash="supabase-managed",
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                logger.info("Auto-created local row for Supabase user %s", email)
        elif user is not None and user.password_hash != "supabase-managed":
            # Supabase failed but the user has a local password — try local
            if not verify_password(password, user.password_hash):
                return templates.TemplateResponse("login.html", {
                    "request": request,
                    "error": "Invalid email or password.",
                })
        else:
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": supa_result["error"] or "Invalid email or password.",
            })
    else:
        # ── Local-only fallback ────────────────────────────────────────────
        if not user or not verify_password(password, user.password_hash):
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "Invalid email or password.",
            })

    if user is None:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid email or password.",
        })

    if not user.is_active:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Account is deactivated. Contact support.",
        })

    # ── Create token and set cookie ────────────────────────────────────────
    token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    # Update last login timestamp
    user.last_login = datetime.utcnow()
    db.commit()

    # Log activity
    log_user_activity(db, user.id, "login", request=request)

    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite=COOKIE_SAMESITE,
        secure=SECURE_COOKIES,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=7 * 24 * 60 * 60,  # 7 days
        samesite=COOKIE_SAMESITE,
        secure=SECURE_COOKIES,
    )
    logger.info("User logged in: %s", user.username)
    return response


@router.get("/logout")
async def logout():
    """Clear the access_token and refresh_token cookies and redirect to landing."""
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(key="access_token")
    response.delete_cookie(key="refresh_token")
    logger.info("User logged out")
    return response


# ─── Cookie-based Current User Dependency ──────────────────────────────────────


async def get_current_user_from_cookie(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """FastAPI dependency that returns the current User from either:

    1. The ``access_token`` cookie (set by the HTML login flow), OR
    2. An ``Authorization: Bearer <token>`` header (used by the CLI and
       other API clients).

    Returns ``None`` if no valid credential is provided.
    """
    token = request.cookies.get("access_token")

    # ── Fall back to Authorization: Bearer <token> ────────────────────────
    if not token:
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()

    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            return None
    except JWTError:
        logger.debug("Invalid JWT in cookie/header")
        return None

    try:
        user = db.query(User).filter(User.id == int(user_id)).first()
    except (ValueError, TypeError):
        return None

    if user is None or not user.is_active:
        return None

    return user


# ─── JSON API Schemas ─────────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    """Pydantic model for JSON registration requests."""
    username: str
    email: str
    password: str
    confirm_password: str | None = None


class LoginRequest(BaseModel):
    """Pydantic model for JSON login requests."""
    email: str
    password: str


class RefreshTokenRequest(BaseModel):
    """Pydantic model for token refresh requests."""
    refresh_token: str


# ─── JSON API Routes ──────────────────────────────────────────────────────────


@router.post("/api/auth/register")
async def api_register(
    request: Request,
    body: RegisterRequest,
    db: Session = Depends(get_db),
):
    """JSON API version of user registration (Supabase-first, local fallback)."""
    if body.confirm_password and body.password != body.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")

    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    existing_user = db.query(User).filter(
        (User.username == body.username.strip()) | (User.email == body.email.strip().lower())
    ).first()
    if existing_user:
        field = "username" if existing_user.username == body.username.strip() else "email"
        raise HTTPException(status_code=409, detail=f"That {field} is already registered.")

    # ── Supabase first ─────────────────────────────────────────────────────
    if supa_auth.is_available():
        supa_result = supa_auth.sign_up(body.email, body.password)
        if not supa_result["success"]:
            raise HTTPException(
                status_code=400,
                detail=supa_result["error"] or "Supabase registration failed.",
            )

    try:
        if supa_auth.is_available():
            hashed = "supabase-managed"
        else:
            hashed = hash_password(body.password)

        new_user = User(
            username=body.username.strip(),
            email=body.email.strip().lower(),
            password_hash=hashed,
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        logger.info("API registration: %s", body.username)

        # Log activity
        log_user_activity(db, new_user.id, "register", request=request)

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        db.rollback()
        logger.error("API registration failed for %s: %s", body.username, exc)
        raise HTTPException(status_code=500, detail="Registration failed. Please try again.")

    # Auto-generate token on registration
    token = create_access_token(data={"sub": str(new_user.id)})
    refresh = create_refresh_token(data={"sub": str(new_user.id)})

    return {
        "message": "Registration successful",
        "access_token": token,
        "refresh_token": refresh,
        "token_type": "bearer",
        "user": {
            "id": new_user.id,
            "username": new_user.username,
            "email": new_user.email,
        },
    }


@router.post("/api/auth/login")
async def api_login(
    request: Request,
    body: LoginRequest,
    db: Session = Depends(get_db),
):
    """JSON API version of login (Supabase-first, local fallback)."""
    user = db.query(User).filter(User.email == body.email.strip().lower()).first()

    # ── Supabase first ─────────────────────────────────────────────────────
    if supa_auth.is_available():
        supa_result = supa_auth.sign_in_with_password(body.email, body.password)
        if supa_result["success"]:
            if user is None:
                # Auto-create local row for Supabase-first users
                supa_user = supa_result["user"] or {}
                username = (
                    supa_user.get("user_metadata", {}).get("username")
                    or supa_user.get("email", "").split("@")[0]
                    or "user"
                )
                user = User(
                    username=username[:50],
                    email=body.email.strip().lower(),
                    password_hash="supabase-managed",
                )
                db.add(user)
                db.commit()
                db.refresh(user)
        elif user is not None and user.password_hash != "supabase-managed":
            # Local fallback for legacy users
            if not verify_password(body.password, user.password_hash):
                raise HTTPException(status_code=401, detail="Invalid email or password.")
        else:
            raise HTTPException(
                status_code=401,
                detail=supa_result["error"] or "Invalid email or password.",
            )
    else:
        if not user or not verify_password(body.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated.")

    token = create_access_token(data={"sub": str(user.id)})
    refresh = create_refresh_token(data={"sub": str(user.id)})

    # Update last login timestamp
    user.last_login = datetime.utcnow()
    db.commit()

    # Log activity
    log_user_activity(db, user.id, "login", request=request)

    logger.info("API login: %s", user.username)
    return {
        "access_token": token,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "organization": user.organization,
            "is_admin": user.is_admin,
        },
    }


@router.post("/api/auth/refresh")
async def api_refresh_token(
    body: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    """Refresh an access token using a valid refresh token."""
    try:
        payload = jwt.decode(body.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        token_type: Optional[str] = payload.get("type")

        if user_id is None or token_type != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or deactivated")

    new_token = create_access_token(data={"sub": str(user.id)})
    new_refresh = create_refresh_token(data={"sub": str(user.id)})

    return {
        "access_token": new_token,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.get("/api/auth/me")
async def api_get_current_user(
    user: User = Depends(get_current_user_from_cookie),
):
    """Get the current authenticated user's profile."""
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user.public_profile


@router.get("/api/auth/status")
async def api_auth_status():
    """Report which auth backends are wired up.

    Useful for diagnosing deployment issues — the CLI calls this on `obml
    whoami` to give the user a friendly hint about their setup.
    """
    return {
        "app": "OpenBenchML",
        "version": "4.2.0",
        "supabase_auth_enabled": supa_auth.is_available(),
        "supabase_url": SUPABASE_URL if supa_auth.is_available() else None,
        "local_auth_enabled": True,  # always available as fallback
        "endpoints": {
            "html_login": "/login",
            "html_register": "/register",
            "api_login": "/api/auth/login",
            "api_register": "/api/auth/register",
            "api_refresh": "/api/auth/refresh",
            "api_me": "/api/auth/me",
        },
    }
