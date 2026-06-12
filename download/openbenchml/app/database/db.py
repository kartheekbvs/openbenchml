"""
OpenBenchML Database Setup
===========================
SQLAlchemy engine, session, and base model configuration.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from app.config import SQLALCHEMY_DATABASE_URL, DEBUG

# Create SQLAlchemy engine
connect_args = {}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=connect_args,
    echo=DEBUG,
    pool_pre_ping=True,
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency that provides a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables in the database."""
    Base.metadata.create_all(bind=engine)
