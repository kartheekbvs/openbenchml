"""
OpenBenchML Database Seeder
=============================
Populates the database with default benchmark datasets.
"""

import logging
from sqlalchemy.orm import Session
from app.database.db import SessionLocal
from app.database.models import Dataset

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


def seed_database():
    """Seed the database with default datasets if they don't already exist."""
    db: Session = SessionLocal()
    try:
        existing_count = db.query(Dataset).count()
        if existing_count > 0:
            logger.info(f"Database already has {existing_count} datasets, skipping seed")
            return

        for dataset_data in BUILTIN_DATASETS:
            dataset = Dataset(**dataset_data)
            db.add(dataset)

        db.commit()
        logger.info(f"Seeded {len(BUILTIN_DATASETS)} default datasets")
    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding database: {e}")
    finally:
        db.close()
