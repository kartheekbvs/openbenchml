"""
OpenBenchML Database Models
============================
All SQLAlchemy ORM models for the platform.
6 core tables: users, models, datasets, benchmark_jobs, benchmark_results, leaderboard
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, ForeignKey,
    Enum, Boolean, Index
)
from sqlalchemy.orm import relationship
from app.database.db import Base


class User(Base):
    """User account for developers who submit models."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    organization = Column(String(120), nullable=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    # Relationships
    models = relationship("MLModel", back_populates="owner", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(username='{self.username}', email='{self.email}')>"


class MLModel(Base):
    """Machine learning model uploaded by a user."""
    __tablename__ = "models"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    model_name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    framework = Column(String(50), nullable=False)  # scikit-learn, pytorch, onnx, etc.
    file_path = Column(String(500), nullable=False)
    version = Column(String(20), default="v1")
    size_kb = Column(Float, default=0.0)
    is_public = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    owner = relationship("User", back_populates="models")
    jobs = relationship("BenchmarkJob", back_populates="model", cascade="all, delete-orphan")
    leaderboard_entries = relationship("Leaderboard", back_populates="model", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<MLModel(name='{self.model_name}', framework='{self.framework}')>"


class Dataset(Base):
    """Benchmark dataset available on the platform."""
    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False, unique=True)
    task_type = Column(String(50), nullable=False)  # classification, regression, clustering
    description = Column(Text, nullable=True)
    samples = Column(Integer, default=0)
    features = Column(Integer, default=0)
    file_path = Column(String(500), nullable=True)
    is_builtin = Column(Boolean, default=True)
    difficulty = Column(String(20), default="intermediate")  # beginner, intermediate, advanced
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    jobs = relationship("BenchmarkJob", back_populates="dataset", cascade="all, delete-orphan")
    leaderboard_entries = relationship("Leaderboard", back_populates="dataset", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Dataset(name='{self.name}', task_type='{self.task_type}')>"


class BenchmarkJob(Base):
    """A single benchmark run: model + dataset evaluation."""
    __tablename__ = "benchmark_jobs"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("models.id", ondelete="CASCADE"), nullable=False, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(
        Enum("pending", "running", "completed", "failed", name="job_status"),
        default="pending",
        index=True
    )
    progress = Column(Integer, default=0)  # 0-100
    error_message = Column(Text, nullable=True)
    submitted_at = Column(DateTime, default=datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    # Relationships
    model = relationship("MLModel", back_populates="jobs")
    dataset = relationship("Dataset", back_populates="jobs")
    result = relationship("BenchmarkResult", back_populates="job", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<BenchmarkJob(id={self.id}, status='{self.status}')>"


class BenchmarkResult(Base):
    """Metrics and performance data from a completed benchmark."""
    __tablename__ = "benchmark_results"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("benchmark_jobs.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # ML Metrics
    accuracy = Column(Float, nullable=True)
    precision = Column(Float, nullable=True)
    recall = Column(Float, nullable=True)
    f1_score = Column(Float, nullable=True)

    # Regression Metrics
    mae = Column(Float, nullable=True)
    rmse = Column(Float, nullable=True)
    r2_score = Column(Float, nullable=True)

    # Performance Metrics
    latency_ms = Column(Float, nullable=True)       # Average inference time in ms
    memory_mb = Column(Float, nullable=True)         # Peak memory usage in MB
    cpu_percent = Column(Float, nullable=True)       # Average CPU usage
    model_size_kb = Column(Float, nullable=True)     # Model file size in KB
    inference_count = Column(Integer, default=0)     # Number of predictions made

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    job = relationship("BenchmarkJob", back_populates="result")

    def __repr__(self):
        return f"<BenchmarkResult(job_id={self.job_id}, accuracy={self.accuracy})>"


class Leaderboard(Base):
    """Ranked entries for models on specific datasets."""
    __tablename__ = "leaderboard"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("models.id", ondelete="CASCADE"), nullable=False, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    rank = Column(Integer, nullable=True)
    score = Column(Float, nullable=True)  # Primary metric (accuracy for classification, r2 for regression)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    model = relationship("MLModel", back_populates="leaderboard_entries")
    dataset = relationship("Dataset", back_populates="leaderboard_entries")

    # Composite index for efficient leaderboard queries
    __table_args__ = (
        Index('idx_model_dataset', 'model_id', 'dataset_id', unique=True),
    )

    def __repr__(self):
        return f"<Leaderboard(model_id={self.model_id}, rank={self.rank})>"
