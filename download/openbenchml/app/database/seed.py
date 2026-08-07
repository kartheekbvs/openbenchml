"""
OpenBenchML Database Seeder
=============================
Populates the database with default benchmark datasets and a sample
competition so the platform is usable immediately after install.
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.database.db import SessionLocal
from app.database.models import Dataset, Competition

logger = logging.getLogger(__name__)

BUILTIN_DATASETS = [
    {
        "name": "Iris",
        "task_type": "classification",
        "description": "Classic flower classification dataset with 3 species of iris flowers. "
                       "Features include sepal length, sepal width, petal length, and petal width. "
                       "Ideal for testing classification algorithms and benchmarking model accuracy.",
        "samples": 150,
        "features": 4,
        "difficulty": "beginner",
        "is_builtin": True,
    },
    {
        "name": "Wine",
        "task_type": "classification",
        "description": "Wine quality classification dataset derived from chemical analysis of wines. "
                       "Contains 13 chemical features including alcohol content, malic acid, ash, and flavonoids. "
                       "Great for multi-class classification benchmarking.",
        "samples": 178,
        "features": 13,
        "difficulty": "intermediate",
        "is_builtin": True,
    },
    {
        "name": "BreastCancer",
        "task_type": "classification",
        "description": "Binary classification dataset for breast cancer diagnosis. "
                       "Features computed from digitized images of fine needle aspirates of breast masses. "
                       "30 numeric features describing characteristics of cell nuclei. "
                       "Excellent for medical ML benchmarking.",
        "samples": 569,
        "features": 30,
        "difficulty": "intermediate",
        "is_builtin": True,
    },
    {
        "name": "Digits",
        "task_type": "classification",
        "description": "Handwritten digit classification dataset with 8x8 pixel images of digits 0-9. "
                       "64 features per sample representing pixel intensities. "
                       "A lighter alternative to MNIST for quick benchmarking.",
        "samples": 1797,
        "features": 64,
        "difficulty": "intermediate",
        "is_builtin": True,
    },
    {
        "name": "CaliforniaHousing",
        "task_type": "regression",
        "description": "California housing price prediction dataset. "
                       "20640 samples with 8 features including median income, house age, "
                       "average rooms, average bedrooms, population, and location coordinates. "
                       "The target is median house value. Excellent for regression benchmarking.",
        "samples": 20640,
        "features": 8,
        "difficulty": "advanced",
        "is_builtin": True,
    },
    {
        "name": "Diabetes",
        "task_type": "regression",
        "description": "Diabetes progression dataset for regression. "
                       "442 samples with 10 baseline features including age, sex, BMI, blood pressure, "
                       "and 6 blood serum measurements. Target is disease progression one year after baseline. "
                       "Good for small-scale regression benchmarking.",
        "samples": 442,
        "features": 10,
        "difficulty": "beginner",
        "is_builtin": True,
    },
]

# Default sample competitions seeded on first run
DEFAULT_COMPETITIONS = [
    {
        "title": "Iris Classification Challenge",
        "slug": "iris-classification-challenge",
        "description": (
            "Welcome to the inaugural OpenBenchML competition! Build the most "
            "accurate classifier you can on the classic Iris dataset. This is "
            "a beginner-friendly challenge — perfect for your first submission. "
            "Top-3 finishers get a shout-out in the next release notes."
        ),
        "rules": (
            "1. Only scikit-learn / xgboost / lightgbm / pytorch / onnx / tensorflow models are accepted.\n"
            "2. Maximum 10 submissions per user.\n"
            "3. Submissions are auto-benchmarked on the standard Iris test split.\n"
            "4. The evaluation metric is accuracy.\n"
            "5. Ties are broken by inference latency (lower is better)."
        ),
        "prize": "Top-3 leaderboard shout-out in the next release notes.",
        "dataset_name": "Iris",
        "evaluation_metric": "accuracy",
        "duration_days": 30,
        "max_submissions_per_user": 10,
    },
    {
        "title": "Diabetes Regression Sprint",
        "slug": "diabetes-regression-sprint",
        "description": (
            "Predict diabetes disease progression one year after baseline "
            "using 10 features. Lowest RMSE wins. The Diabetes dataset is "
            "small (442 samples) so you can iterate quickly — perfect for "
            "experimenting with regularisation and feature engineering."
        ),
        "rules": (
            "1. Same framework rules as the Iris challenge.\n"
            "2. Maximum 10 submissions per user.\n"
            "3. Evaluation metric is RMSE (lower is better).\n"
            "4. Ties are broken by R2 score (higher is better)."
        ),
        "prize": "Bragging rights and a GitHub star.",
        "dataset_name": "Diabetes",
        "evaluation_metric": "rmse",
        "duration_days": 14,
        "max_submissions_per_user": 10,
    },
]


def seed_database():
    """Seed the database with default datasets and competitions."""
    db: Session = SessionLocal()
    try:
        # ── Datasets ───────────────────────────────────────────────────────
        existing_count = db.query(Dataset).count()
        if existing_count == 0:
            for dataset_data in BUILTIN_DATASETS:
                db.add(Dataset(**dataset_data))
            db.commit()
            logger.info(f"Seeded {len(BUILTIN_DATASETS)} default datasets")
        else:
            logger.info(f"Database already has {existing_count} datasets, skipping dataset seed")

        # ── Competitions ───────────────────────────────────────────────────
        existing_comps = db.query(Competition).count()
        if existing_comps == 0:
            now = datetime.utcnow()
            for c_data in DEFAULT_COMPETITIONS:
                dataset = (
                    db.query(Dataset)
                    .filter(Dataset.name == c_data["dataset_name"])
                    .first()
                )
                if dataset is None:
                    logger.warning(f"Dataset '{c_data['dataset_name']}' not found, skipping competition")
                    continue

                starts_at = now - timedelta(hours=1)  # already live
                ends_at = now + timedelta(days=c_data["duration_days"])

                comp = Competition(
                    title=c_data["title"],
                    slug=c_data["slug"],
                    description=c_data["description"],
                    rules=c_data["rules"],
                    prize=c_data["prize"],
                    dataset_id=dataset.id,
                    evaluation_metric=c_data["evaluation_metric"],
                    task_type=dataset.task_type,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    status="live",
                    max_submissions_per_user=c_data["max_submissions_per_user"],
                )
                db.add(comp)
            db.commit()
            logger.info(f"Seeded {len(DEFAULT_COMPETITIONS)} default competitions")
        else:
            logger.info(f"Database already has {existing_comps} competitions, skipping competition seed")

    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding database: {e}")
    finally:
        db.close()
