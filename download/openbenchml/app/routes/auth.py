"""
OpenBenchML Authentication Routes
===================================
Handles user registration, login, logout via both HTML forms and JSON API.
JWT tokens are stored in HttpOnly cookies for browser clients and returned
in the response body for API consumers.
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
    oauth2_scheme,
)
from app.config import templates, SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── HTML Form Routes ─────────────────────────────────────────────────────────


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Render the registration form."""
    return templates.TemplateResponse("register.html", {"request": request})


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

    Validates that passwords match and that the username/email are not
    already taken.  On success the user is redirected to the login page.
    """
    # ── Validate passwords match ───────────────────────────────────────────
    if password != confirm_password:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Passwords do not match.",
        })

    # ── Check for existing username ────────────────────────────────────────
    existing_user = db.query(User).filter(
        (User.username == username) | (User.email == email)
    ).first()
    if existing_user:
        field = "Username" if existing_user.username == username else "Email"
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": f"{field} is already registered.",
        })

    # ── Create the user ────────────────────────────────────────────────────
    try:
        hashed = hash_password(password)
        new_user = User(
            username=username.strip(),
            email=email.strip().lower(),
            password_hash=hashed,
        )
        db.add(new_user)
        db.commit()
        logger.info("New user registered: %s", username)
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
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """Handle login form submission.

    Verifies credentials and, on success, sets an HttpOnly JWT cookie
    and redirects the user to the dashboard.
    """
    # ── Look up user by email ──────────────────────────────────────────────
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not user or not verify_password(password, user.password_hash):
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

    # Update last login timestamp
    user.last_login = datetime.utcnow()
    db.commit()

    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
    )
    logger.info("User logged in: %s", user.username)
    return response


@router.get("/logout")
async def logout():
    """Clear the access_token cookie and redirect to the landing page."""
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(key="access_token")
    logger.info("User logged out")
    return response


# ─── Cookie-based Current User Dependency ──────────────────────────────────────


async def get_current_user_from_cookie(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """FastAPI dependency that reads the access_token cookie and returns
    the current User, or ``None`` if the cookie is missing / invalid.

    This is intentionally lenient (returns None instead of raising 401)
    so that dashboard routes can redirect unauthenticated users to login
    rather than returning an error JSON payload.
    """
    token = request.cookies.get("access_token")
    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            return None
    except JWTError:
        logger.debug("Invalid JWT in cookie")
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


# ─── JSON API Routes ──────────────────────────────────────────────────────────


@router.post("/api/auth/register")
async def api_register(
    body: RegisterRequest,
    db: Session = Depends(get_db),
):
    """JSON API version of user registration.

    Accepts a JSON body and returns a JSON response indicating
    success or failure with a descriptive message.
    """
    if body.confirm_password and body.password != body.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")

    existing_user = db.query(User).filter(
        (User.username == body.username) | (User.email == body.email)
    ).first()
    if existing_user:
        field = "username" if existing_user.username == body.username else "email"
        raise HTTPException(status_code=409, detail=f"That {field} is already registered.")

    try:
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
    except Exception as exc:
        db.rollback()
        logger.error("API registration failed for %s: %s", body.username, exc)
        raise HTTPException(status_code=500, detail="Registration failed. Please try again.")

    return {
        "message": "Registration successful",
        "user": {"id": new_user.id, "username": new_user.username, "email": new_user.email},
    }


@router.post("/api/auth/login")
async def api_login(
    body: LoginRequest,
    db: Session = Depends(get_db),
):
    """JSON API version of login.

    Verifies credentials and returns the JWT token in the response body
    so that API consumers can include it in subsequent Authorization
    headers.
    """
    user = db.query(User).filter(User.email == body.email.strip().lower()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated.")

    token = create_access_token(data={"sub": str(user.id)})

    # Update last login timestamp
    user.last_login = datetime.utcnow()
    db.commit()

    logger.info("API login: %s", user.username)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "username": user.username, "email": user.email},
    }
