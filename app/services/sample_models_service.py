"""
OpenBenchML Sample Models Service
===================================
Ensures the platform always has a set of *real*, pre-trained sample
ML models — one per built-in/CSV dataset — so that any visitor can
run a real benchmark immediately without first having to upload a
model of their own.

Key design points:

* **Real training, not random numbers** — Each sample model is
  trained on the actual dataset it will be benchmarked against, using
  the same ``load_dataset`` pipeline the benchmark engine uses.  So
  the metrics a user sees are the genuine train/test accuracy of a
  sensible baseline model on that dataset.

* **Persistent storage** — Sample model files are written to
  ``UPLOAD_DIR / "sample_models"`` so they survive deploys and
  container restarts.  The path stored in the DB is absolute.

* **Idempotent** — Calling :func:`ensure_sample_models` multiple
  times is safe.  If a sample model for a given dataset already
  exists (matched by ``model_name`` prefix ``[sample]``), it is
  reused.  If the underlying file has gone missing from disk, the
  DB row is recreated.

* **Owned by a system user** — Sample models are attached to a
  dedicated ``openbenchml_system`` user so they don't pollute a
  real user's library.  The system user is auto-created if missing.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.config import UPLOAD_DIR
from app.database.models import User, MLModel, Dataset
from app.benchmark_engine.loader import load_dataset

logger = logging.getLogger(__name__)

# Where sample model files live on disk.
SAMPLE_MODELS_DIR: Path = UPLOAD_DIR / "sample_models"

# Username for the system account that owns sample models.
SYSTEM_USERNAME = "openbenchml_system"
SYSTEM_EMAIL = "system@openbenchml.local"

# Prefix added to sample model names so they can be identified easily.
SAMPLE_MODEL_NAME_PREFIX = "[sample] "


# ─── Model recipes ────────────────────────────────────────────────────────────
# One entry per dataset.  ``factory`` returns a fresh, untrained sklearn
# estimator.  We pick small, sensible baselines — not state-of-the-art —
# so the metrics users see match a realistic "first attempt" rather
# than an unrealistic ceiling.
#
# The factory is called inside :func:`_train_one` with the actual
# dataset's X_train / y_train so the trained model is genuinely fit
# on the data it will be benchmarked against.

def _rf(n: int = 100, **kw):
    from sklearn.ensemble import RandomForestClassifier
    return RandomForestClassifier(n_estimators=n, random_state=42, n_jobs=1, **kw)


def _gbr(**kw):
    from sklearn.ensemble import GradientBoostingRegressor
    return GradientBoostingRegressor(random_state=42, **kw)


def _lr(**kw):
    from sklearn.linear_model import LogisticRegression
    return LogisticRegression(max_iter=1000, random_state=42, **kw)


def _svc(**kw):
    from sklearn.svm import SVC
    return SVC(kernel="rbf", probability=True, random_state=42, **kw)


def _ridge(**kw):
    from sklearn.linear_model import Ridge
    return Ridge(alpha=1.0, random_state=42, **kw)


# Map: dataset name -> (model_name, framework, factory, task_type_hint)
# task_type_hint is informational only — the actual task type is read
# from the dataset row in the DB.
SAMPLE_MODEL_RECIPES: Dict[str, Tuple[str, str, callable]] = {
    # ── sklearn built-ins ────────────────────────────────────────────────
    "Iris":              ("LogisticRegression", "scikit-learn", _lr),
    "Wine":              ("RandomForest(80)",   "scikit-learn", lambda: _rf(80)),
    "BreastCancer":      ("RandomForest(100)",  "scikit-learn", lambda: _rf(100)),
    "Digits":            ("RandomForest(100)",  "scikit-learn", lambda: _rf(100)),
    "OlivettiFaces":     ("LogisticRegression", "scikit-learn", _lr),
    "Diabetes":          ("Ridge",              "scikit-learn", _ridge),
    "CaliforniaHousing": ("GradientBoosting",   "scikit-learn", _gbr),
    "Linnerud":          ("Ridge",              "scikit-learn", _ridge),

    # ── Real-world CSV datasets ──────────────────────────────────────────
    "Titanic":                ("RandomForest(100)", "scikit-learn", lambda: _rf(100)),
    "PimaDiabetes":           ("LogisticRegression", "scikit-learn", _lr),
    "HeartDisease":           ("RandomForest(200)",  "scikit-learn", lambda: _rf(200)),
    "SonarMinesVsRocks":      ("SVC(rbf,proba)",     "scikit-learn", _svc),
    "BanknoteAuthentication": ("RandomForest(50)",   "scikit-learn", lambda: _rf(50)),
    "WineQualityRed":         ("RandomForest(150)",  "scikit-learn", lambda: _rf(150)),
    "WineQualityWhite":       ("RandomForest(150)",  "scikit-learn", lambda: _rf(150)),
    "IrisCSV":                ("LogisticRegression", "scikit-learn", _lr),
    "PalmerPenguins":         ("RandomForest(100)",  "scikit-learn", lambda: _rf(100)),
    "AutoMPG":                ("GradientBoosting",   "scikit-learn", _gbr),
    "BostonHousing":          ("GradientBoosting",   "scikit-learn", _gbr),
    "CaliforniaHousingCSV":   ("GradientBoosting",   "scikit-learn", _gbr),
}


# ─── Public API ───────────────────────────────────────────────────────────────


def ensure_sample_models(db: Session) -> Dict[str, int]:
    """Create or refresh every sample model.

    Returns a dict with counts: ``created``, ``reused``, ``failed``,
    ``total``.  Safe to call at startup; idempotent.
    """
    stats = {"created": 0, "reused": 0, "failed": 0, "total": 0}

    SAMPLE_MODELS_DIR.mkdir(parents=True, exist_ok=True)

    system_user = _ensure_system_user(db)
    if system_user is None:
        logger.error("Could not create/find system user — skipping sample model seeding")
        return stats

    all_datasets: List[Dataset] = db.query(Dataset).all()

    for ds in all_datasets:
        recipe = SAMPLE_MODEL_RECIPES.get(ds.name)
        if recipe is None:
            logger.debug("No sample-model recipe for dataset '%s' — skipping", ds.name)
            continue

        stats["total"] += 1
        model_name_base, framework, factory = recipe
        full_name = f"{SAMPLE_MODEL_NAME_PREFIX}{model_name_base} on {ds.name}"

        # ── Check if a sample model row already exists for this dataset ──
        existing: Optional[MLModel] = (
            db.query(MLModel)
            .filter(
                MLModel.user_id == system_user.id,
                MLModel.model_name == full_name,
            )
            .first()
        )

        target_path = SAMPLE_MODELS_DIR / f"sample_{ds.id}_{ds.name.lower().replace('-', '_')}.joblib"

        if existing is not None:
            # If the file is missing, retrain it
            if existing.file_path and os.path.isfile(existing.file_path):
                stats["reused"] += 1
                continue
            else:
                logger.info(
                    "Sample model '%s' exists in DB but file is missing — retraining",
                    full_name,
                )
                # Drop the stale row; we'll recreate below
                db.delete(existing)
                db.commit()

        # ── Train a real model on the dataset ───────────────────────────────
        try:
            file_path, size_kb = _train_one(
                dataset=ds,
                factory=factory,
                target_path=str(target_path),
            )
        except Exception as exc:
            logger.error(
                "Failed to train sample model for '%s': %s — %s",
                ds.name, type(exc).__name__, exc,
            )
            stats["failed"] += 1
            continue

        # ── Persist the DB row ──────────────────────────────────────────────
        try:
            new_model = MLModel(
                user_id=system_user.id,
                model_name=full_name,
                description=(
                    f"Auto-generated sample model trained on the real '{ds.name}' "
                    f"dataset ({ds.samples} samples, {ds.features} features, "
                    f"task={ds.task_type}).  Use this to run a real benchmark "
                    f"without uploading anything."
                ),
                framework=framework,
                file_path=file_path,
                size_kb=size_kb,
                is_public=True,
                version="v1",
                tags=["sample", "baseline", "auto-trained"],
            )
            db.add(new_model)
            db.commit()
            db.refresh(new_model)
            stats["created"] += 1
            logger.info(
                "Created sample model id=%d '%s' (%.1f KB) for dataset '%s'",
                new_model.id, full_name, size_kb, ds.name,
            )
        except Exception as exc:
            db.rollback()
            logger.error("Could not persist sample model row for '%s': %s", ds.name, exc)
            stats["failed"] += 1

    logger.info(
        "Sample-model seeding done: created=%d reused=%d failed=%d total=%d",
        stats["created"], stats["reused"], stats["failed"], stats["total"],
    )
    return stats


def find_sample_model_for_dataset(dataset: Dataset, db: Session) -> Optional[MLModel]:
    """Find the sample model row associated with a given dataset.

    Looks for an MLModel owned by the system user whose name follows
    the ``[sample] <algo> on <dataset_name>`` pattern.
    """
    system_user = (
        db.query(User).filter(User.username == SYSTEM_USERNAME).first()
    )
    if system_user is None:
        return None

    expected_name = f"{SAMPLE_MODEL_NAME_PREFIX}"
    # Match any sample model whose name ends with " on <dataset.name>"
    suffix = f" on {dataset.name}"
    rows: List[MLModel] = (
        db.query(MLModel)
        .filter(
            MLModel.user_id == system_user.id,
            MLModel.model_name.like(f"{expected_name}%{suffix}"),
        )
        .all()
    )
    for row in rows:
        if row.model_name.endswith(suffix) and row.file_path and os.path.isfile(row.file_path):
            return row
    # If none with file present, return any row (will be retrained lazily)
    return rows[0] if rows else None


def list_sample_models(db: Session) -> List[MLModel]:
    """Return all sample models (system-owned, name starts with [sample])."""
    system_user = (
        db.query(User).filter(User.username == SYSTEM_USERNAME).first()
    )
    if system_user is None:
        return []
    return (
        db.query(MLModel)
        .filter(
            MLModel.user_id == system_user.id,
            MLModel.model_name.like(f"{SAMPLE_MODEL_NAME_PREFIX}%"),
        )
        .order_by(MLModel.model_name.asc())
        .all()
    )


# ─── Internal helpers ─────────────────────────────────────────────────────────


def _ensure_system_user(db: Session) -> Optional[User]:
    """Get or create the system user that owns sample models."""
    existing = db.query(User).filter(User.username == SYSTEM_USERNAME).first()
    if existing is not None:
        return existing

    # Create a system user with a random unusable password hash.
    import secrets
    random_pw = secrets.token_urlsafe(48)
    try:
        from app.services.auth_service import hash_password
        pw_hash = hash_password(random_pw)
    except Exception:
        # Fallback: store a clearly-invalid hash
        pw_hash = "!disabled!"

    user = User(
        username=SYSTEM_USERNAME,
        email=SYSTEM_EMAIL,
        password_hash=pw_hash,
        organization="OpenBenchML",
        bio="System account — owns auto-generated sample models used for one-click benchmarks.",
        is_active=False,   # cannot log in
        is_admin=False,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Created system user '%s' (id=%d)", SYSTEM_USERNAME, user.id)
    return user


def _train_one(
    dataset: Dataset,
    factory: callable,
    target_path: str,
) -> Tuple[str, float]:
    """Train a real sklearn model on the dataset and save it to disk.

    Returns ``(file_path, size_kb)``.
    """
    # Determine the dataset source key
    if dataset.file_path:
        source = dataset.file_path
    else:
        source = (dataset.name or "").lower().replace("-", "_").replace(" ", "_")

    logger.info("Training sample model for '%s' (source=%s)", dataset.name, source)

    # Load real dataset via the same pipeline as the benchmark engine
    data = load_dataset(source, task_type=dataset.task_type)

    X_train = np.asarray(data["X_train"])
    y_train = np.asarray(data["y_train"])

    if X_train.shape[0] == 0:
        raise ValueError(f"Dataset '{dataset.name}' has 0 training samples")

    # Build & fit the model
    model = factory()
    model.fit(X_train, y_train)

    # Persist with joblib (atomic-ish: write to .tmp then rename)
    tmp_path = target_path + ".tmp"
    joblib.dump(model, tmp_path, compress=3)

    # Move into place
    os.replace(tmp_path, target_path)

    size_kb = round(os.path.getsize(target_path) / 1024.0, 2)
    logger.info(
        "Sample model trained for '%s': %d train samples, %d features, size=%.1f KB",
        dataset.name, X_train.shape[0], X_train.shape[1], size_kb,
    )
    return target_path, size_kb
