"""
OpenBenchML Authentication Service
====================================
Handles password hashing/verification, JWT token creation, and
user identity extraction for the FastAPI dependency injection system.
Enhanced with refresh tokens, API key support, and activity logging.
"""

import logging
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import (
    SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS, SECURE_COOKIES, COOKIE_SAMESITE,
    BCRYPT_ROUNDS,
)
from app.database.models import User, APIKey, UserActivity
from app.database.db import get_db

logger = logging.getLogger(__name__)

# ─── Password hashing context ─────────────────────────────────────────────────
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=BCRYPT_ROUNDS,
    truncate_error=True,
)

# ─── OAuth2 scheme for FastAPI security ────────────────────────────────────────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt.

    Uses passlib's CryptContext with the bcrypt scheme to generate a
    secure, salted hash suitable for persistent storage.

    Args:
        password: The plaintext password string to hash.

    Returns:
        A bcrypt hash string that can be stored in the database.

    Raises:
        ValueError: If *password* is empty or consists only of whitespace.
    """
    if not password or not password.strip():
        logger.warning("Attempted to hash an empty password")
        raise ValueError("Password must not be empty")

    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters")

    hashed = pwd_context.hash(password.strip())
    logger.debug("Password hashed successfully")
    return hashed


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash.

    Uses passlib's constant-time comparison internally, which mitigates
    timing-attack vectors.

    Args:
        plain_password: The plaintext password supplied by the user.
        hashed_password: The bcrypt hash stored in the database.

    Returns:
        True when the password matches the hash, False otherwise.
    """
    if not plain_password or not hashed_password:
        logger.warning("verify_password called with empty argument(s)")
        return False

    try:
        result = pwd_context.verify(plain_password, hashed_password)
    except Exception as exc:
        logger.warning("Password verification failed unexpectedly: %s", exc)
        return False

    if result:
        logger.debug("Password verified successfully")
    else:
        logger.debug("Password verification failed - incorrect password")
    return result


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token.

    The token payload always includes an exp claim calculated from the
    application's ACCESS_TOKEN_EXPIRE_MINUTES setting unless an explicit
    expires_delta is provided.

    Args:
        data: A dictionary of claims to embed in the token.
        expires_delta: Optional custom expiry duration.

    Returns:
        An encoded JWT string.
    """
    to_encode = data.copy()

    if expires_delta is not None:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access",
    })

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    logger.debug("JWT created for subject '%s', expires at %s", data.get("sub"), expire.isoformat())
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create a signed JWT refresh token with longer expiry.

    Args:
        data: A dictionary of claims to embed in the token.

    Returns:
        An encoded JWT refresh token string.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh",
    })

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    logger.debug("Refresh token created for subject '%s'", data.get("sub"))
    return encoded_jwt


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency that extracts the current authenticated user.

    Supports both Bearer token (API) and cookie-based (browser) auth.
    Decodes the JWT, validates its signature and expiry, looks the user
    up in the database, and raises 401 if anything is amiss.

    Args:
        token: The JWT extracted by the OAuth2PasswordBearer scheme.
        db: The database session.

    Returns:
        The authenticated User ORM object.

    Raises:
        HTTPException (401): When the token is invalid, expired, or user not found.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        token_type: Optional[str] = payload.get("type", "access")
        if user_id is None:
            logger.warning("JWT payload missing 'sub' claim")
            raise credentials_exception
        if token_type != "access":
            logger.warning("Invalid token type: %s", token_type)
            raise credentials_exception
    except JWTError as exc:
        logger.warning("JWT decode failed: %s", exc)
        raise credentials_exception from exc

    try:
        user = db.query(User).filter(User.id == int(user_id)).first()
    except (ValueError, TypeError) as exc:
        logger.warning("Invalid user_id in token subject: %s", user_id)
        raise credentials_exception from exc

    if user is None:
        logger.warning("User with id=%s not found in database", user_id)
        raise credentials_exception

    if not user.is_active:
        logger.warning("Inactive user id=%s attempted authentication", user_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    logger.debug("Authenticated user: %s (id=%s)", user.username, user.id)
    return user


def generate_api_key() -> tuple[str, str]:
    """Generate a new API key and its hash.

    Returns:
        A tuple of (raw_key, key_hash). The raw_key should be shown to
        the user once; the key_hash should be stored in the database.
    """
    raw_key = f"obml_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:8]
    return raw_key, key_hash, key_prefix


def verify_api_key(raw_key: str, key_hash: str) -> bool:
    """Verify an API key against its stored hash.

    Args:
        raw_key: The API key provided by the client.
        key_hash: The SHA-256 hash stored in the database.

    Returns:
        True if the key matches the hash.
    """
    return hashlib.sha256(raw_key.encode()).hexdigest() == key_hash


def log_user_activity(
    db: Session,
    user_id: Optional[int],
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    details: Optional[dict] = None,
    request: Optional[Request] = None,
) -> None:
    """Log a user activity for analytics and audit purposes.

    Args:
        db: Active database session.
        user_id: The user performing the action (None for anonymous).
        action: The action type (e.g. 'login', 'upload', 'benchmark').
        resource_type: Type of resource affected.
        resource_id: ID of the resource affected.
        details: Optional JSON-serializable details dict.
        request: Optional FastAPI Request for IP and user agent.
    """
    try:
        activity = UserActivity(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent", "")[:500] if request else None,
        )
        db.add(activity)
        db.commit()
        logger.debug("Activity logged: user=%s, action=%s", user_id, action)
    except Exception as exc:
        logger.warning("Failed to log activity: %s", exc)
        db.rollback()
