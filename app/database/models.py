"""
OpenBenchML Database Models
============================
All SQLAlchemy ORM models for the platform.
8 core tables: users, models, datasets, benchmark_jobs, benchmark_results,
leaderboard, api_keys, user_activity
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, ForeignKey,
    Enum, Boolean, Index, JSON
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
    avatar_url = Column(String(500), nullable=True)
    bio = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    models = relationship("MLModel", back_populates="owner", cascade="all, delete-orphan")
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    activities = relationship("UserActivity", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(username='{self.username}', email='{self.email}')>"

    @property
    def public_profile(self):
        """Return safe public profile data."""
        return {
            "id": self.id,
            "username": self.username,
            "organization": self.organization,
            "avatar_url": self.avatar_url,
            "bio": self.bio,
            "is_verified": self.is_verified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


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
    tags = Column(JSON, nullable=True)  # List of tags for categorization
    download_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    owner = relationship("User", back_populates="models")
    jobs = relationship("BenchmarkJob", back_populates="model", cascade="all, delete-orphan")
    leaderboard_entries = relationship("Leaderboard", back_populates="model", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_model_framework', 'framework'),
        Index('idx_model_public', 'is_public'),
    )

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
    tags = Column(JSON, nullable=True)
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
    execution_time_ms = Column(Integer, nullable=True)  # Total execution time
    worker_id = Column(String(100), nullable=True)  # Celery task ID or Docker container ID

    # Relationships
    model = relationship("MLModel", back_populates="jobs")
    dataset = relationship("Dataset", back_populates="jobs")
    result = relationship("BenchmarkResult", back_populates="job", uselist=False, cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_job_status_submitted', 'status', 'submitted_at'),
    )

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

    # Advanced Classification Metrics
    auc_roc = Column(Float, nullable=True)
    log_loss = Column(Float, nullable=True)
    confusion_matrix = Column(JSON, nullable=True)  # 2D array
    classification_report = Column(JSON, nullable=True)  # Full report dict

    # Performance Metrics
    latency_ms = Column(Float, nullable=True)       # Average inference time in ms
    latency_p50_ms = Column(Float, nullable=True)    # P50 latency
    latency_p95_ms = Column(Float, nullable=True)    # P95 latency
    latency_p99_ms = Column(Float, nullable=True)    # P99 latency
    memory_mb = Column(Float, nullable=True)          # Peak memory usage in MB
    cpu_percent = Column(Float, nullable=True)        # Average CPU usage
    model_size_kb = Column(Float, nullable=True)      # Model file size in KB
    inference_count = Column(Integer, default=0)      # Number of predictions made
    throughput_per_sec = Column(Float, nullable=True)  # Predictions per second

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
    previous_rank = Column(Integer, nullable=True)  # Track rank changes
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    model = relationship("MLModel", back_populates="leaderboard_entries")
    dataset = relationship("Dataset", back_populates="leaderboard_entries")

    # Composite index for efficient leaderboard queries
    __table_args__ = (
        Index('idx_model_dataset', 'model_id', 'dataset_id', unique=True),
        Index('idx_leaderboard_rank', 'dataset_id', 'rank'),
    )

    def __repr__(self):
        return f"<Leaderboard(model_id={self.model_id}, rank={self.rank})>"


class APIKey(Base):
    """API keys for programmatic access to the platform."""
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    key_hash = Column(String(256), nullable=False, unique=True)
    key_prefix = Column(String(8), nullable=False)  # First 8 chars for identification
    name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime, nullable=True)
    request_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="api_keys")

    def __repr__(self):
        return f"<APIKey(prefix='{self.key_prefix}', name='{self.name}')>"


class UserActivity(Base):
    """Track user actions for analytics and audit logging."""
    __tablename__ = "user_activity"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(50), nullable=False, index=True)  # login, upload, benchmark, etc.
    resource_type = Column(String(50), nullable=True)  # model, dataset, benchmark_job
    resource_id = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", back_populates="activities")

    # Indexes
    __table_args__ = (
        Index('idx_activity_user_action', 'user_id', 'action'),
        Index('idx_activity_created', 'created_at'),
    )

    def __repr__(self):
        return f"<UserActivity(user_id={self.user_id}, action='{self.action}')>"
