"""
OpenBenchML Database Setup
===========================
SQLAlchemy engine, session, and base model configuration.
Enhanced with connection pooling and production-ready settings.
"""

import logging
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from app.config import (
    SQLALCHEMY_DATABASE_URL, DEBUG,
    DB_POOL_SIZE, DB_MAX_OVERFLOW, DB_POOL_RECYCLE, DB_POOL_PRE_PING,
)

logger = logging.getLogger(__name__)

# ─── Engine Configuration ─────────────────────────────────────────────────────
connect_args = {}
engine_kwargs = {
    "echo": DEBUG,
    "pool_pre_ping": DB_POOL_PRE_PING,
}

# SQLite-specific settings
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    # SQLite does not support pool size settings
    logger.info("Using SQLite database (development mode)")
else:
    # PostgreSQL / MySQL pool settings
    engine_kwargs.update({
        "pool_size": DB_POOL_SIZE,
        "max_overflow": DB_MAX_OVERFLOW,
        "pool_recycle": DB_POOL_RECYCLE,
    })
    logger.info("Using PostgreSQL database (production mode)")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=connect_args,
    **engine_kwargs,
)

# ─── SQLite WAL mode for better concurrent performance ────────────────────────
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Enable WAL journal mode and foreign keys for SQLite."""
    if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency that provides a database session per request.
    
    Uses a try/finally pattern to ensure the session is always closed,
    even if an exception occurs during request processing.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """Create all tables in the database.
    
    This is called during application startup. In production, you should
    use Alembic migrations instead.
    """
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized")
