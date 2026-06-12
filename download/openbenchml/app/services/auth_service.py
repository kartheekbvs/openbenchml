"""
OpenBenchML Authentication Service
====================================
Handles password hashing/verification, JWT token creation, and
user identity extraction for the FastAPI dependency injection system.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from app.database.models import User
from app.database.db import get_db

logger = logging.getLogger(__name__)

# ─── Password hashing context ─────────────────────────────────────────────────
# truncate_error=True handles the bcrypt 4.1+ "72 bytes" requirement gracefully
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
    truncate_error=True,
)

# ─── OAuth2 scheme for FastAPI security ────────────────────────────────────────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt.

    Uses passlib's CryptContext with the bcrypt scheme to generate a
    secure, salted hash suitable for persistent storage. The deprecated
    flag is set to ``"auto"`` so that older hash formats are still
    recognised during verification but new hashes always use bcrypt.

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

    hashed = pwd_context.hash(password.strip())
    logger.debug("Password hashed successfully")
    return hashed


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash.

    Uses passlib's constant-time comparison internally, which mitigates
    timing-attack vectors.  If the hash format is unrecognised (e.g. the
    database row was corrupted), the function logs a warning and returns
    ``False`` rather than propagating the exception.

    Args:
        plain_password: The plaintext password supplied by the user.
        hashed_password: The bcrypt hash stored in the database.

    Returns:
        ``True`` when the password matches the hash, ``False`` otherwise.
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
        logger.debug("Password verification failed – incorrect password")
    return result


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token.

    The token payload always includes an ``exp`` claim calculated from the
    application's ``ACCESS_TOKEN_EXPIRE_MINUTES`` setting unless an explicit
    *expires_delta* is provided.  A ``iat`` (issued-at) claim is also added
    for auditing purposes.

    Args:
        data: A dictionary of claims to embed in the token (e.g.
              ``{"sub": "user_id"}``).
        expires_delta: Optional custom expiry duration.  When ``None`` the
              default from configuration is used.

    Returns:
        An encoded JWT string.
    """
    to_encode = data.copy()

    # Determine expiry time
    if expires_delta is not None:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "iat": datetime.utcnow()})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    logger.debug(
        "JWT created for subject '%s', expires at %s",
        data.get("sub"),
        expire.isoformat(),
    )
    return encoded_jwt


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency that extracts the current authenticated user.

    Decodes the JWT from the *Authorization* header, validates its
    signature and expiry, looks the user up in the database, and raises
    a 401 if anything is amiss.  This function is intended to be used as
    a ``Depends()`` argument in route handlers.

    Args:
        token: The JWT extracted by the OAuth2PasswordBearer scheme.
        db: The database session injected by the ``get_db`` generator.

    Returns:
        The authenticated :class:`User` ORM object.

    Raises:
        HTTPException (401): When the token is invalid, expired, or the
            user does not exist / is deactivated.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # ── Decode and validate the JWT ────────────────────────────────────────
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            logger.warning("JWT payload missing 'sub' claim")
            raise credentials_exception
    except JWTError as exc:
        logger.warning("JWT decode failed: %s", exc)
        raise credentials_exception from exc

    # ── Look up the user in the database ───────────────────────────────────
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
