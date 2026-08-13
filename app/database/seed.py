"""
OpenBenchML Database Seeder
=============================
Populates the database with REAL benchmark datasets (downloaded from
GitHub raw / UCI ML repository) and sample competitions so the platform
is usable immediately after install.

All datasets here are REAL — no synthetic ``make_*`` generators.  The
list of sklearn classics mirrors the registry in
``app/benchmark_engine/loader.py``.  The CSV datasets are downloaded
by ``scripts/download_real_datasets.py`` and stored in
``datasets/<slug>.csv`` with companion ``<slug>.meta.json`` sidecars.

If a CSV file is missing (e.g. the download script hasn't been run yet),
the seeder logs a warning and skips that dataset — it does NOT crash.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy.orm import Session
from app.database.db import SessionLocal
from app.database.models import Dataset, Competition
from app.config import BASE_DIR

logger = logging.getLogger(__name__)

DATASETS_DIR = BASE_DIR / "datasets"

# ─── Sklearn classic built-ins (in-memory loaders, no file_path) ──────────────
# These mirror the registry in app/benchmark_engine/loader.py.
SKLEARN_BUILTINS = [
    {
        "name": "Iris",
        "task_type": "classification",
        "description": "Classic flower classification dataset with 3 species of iris "
                       "flowers. Features include sepal length, sepal width, petal "
                       "length, and petal width. Ideal for testing classification "
                       "algorithms and benchmarking model accuracy.",
        "samples": 150, "features": 4,
        "difficulty": "beginner", "is_builtin": True,
    },
    {
        "name": "Wine",
        "task_type": "classification",
        "description": "Wine cultivar classification dataset derived from chemical "
                       "analysis of wines grown in the same region in Italy. 13 "
                       "chemical features including alcohol, malic acid, ash, "
                       "flavonoids. Great for multi-class classification benchmarking.",
        "samples": 178, "features": 13,
        "difficulty": "intermediate", "is_builtin": True,
    },
    {
        "name": "BreastCancer",
        "task_type": "classification",
        "description": "Binary classification for breast cancer diagnosis. 30 numeric "
                       "features computed from digitized images of fine needle "
                       "aspirates of breast masses. Excellent for medical ML "
                       "benchmarking.",
        "samples": 569, "features": 30,
        "difficulty": "intermediate", "is_builtin": True,
    },
    {
        "name": "Digits",
        "task_type": "classification",
        "description": "Handwritten digit classification with 8x8 pixel images of "
                       "digits 0-9. 64 features per sample representing pixel "
                       "intensities. A lighter alternative to MNIST for quick "
                       "benchmarking.",
        "samples": 1797, "features": 64,
        "difficulty": "intermediate", "is_builtin": True,
    },
    {
        "name": "OlivettiFaces",
        "task_type": "classification",
        "description": "Face recognition dataset — 40 distinct subjects, 10 images "
                       "each, 64x64 grayscale. Images were taken at different times, "
                       "varying lighting, facial expressions (open/closed eyes, "
                       "smiling/not smiling) and facial details (glasses/no glasses).",
        "samples": 400, "features": 4096,
        "difficulty": "advanced", "is_builtin": True,
    },
    {
        "name": "Diabetes",
        "task_type": "regression",
        "description": "Diabetes progression dataset for regression. 442 samples with "
                       "10 baseline features including age, sex, BMI, blood pressure, "
                       "and 6 blood serum measurements. Target is disease progression "
                       "one year after baseline.",
        "samples": 442, "features": 10,
        "difficulty": "beginner", "is_builtin": True,
    },
    {
        "name": "CaliforniaHousing",
        "task_type": "regression",
        "description": "California housing price prediction. 8 features including "
                       "median income, house age, average rooms/bedrooms, population, "
                       "and location coordinates. Target is median house value. "
                       "Subsampled to 2000 rows for fast benchmarks.",
        "samples": 20640, "features": 8,
        "difficulty": "advanced", "is_builtin": True,
    },
    {
        "name": "Linnerud",
        "task_type": "regression",
        "description": "Multi-output regression dataset — 20 samples of physical "
                       "exercise measurements (3 exercise variables: chins, situps, "
                       "jumps) against 3 physiological variables (weight, waist, "
                       "pulse). Classic small multi-target regression benchmark.",
        "samples": 20, "features": 3,
        "difficulty": "beginner", "is_builtin": True,
    },
]


# ─── Real-world CSV datasets (downloaded by scripts/download_real_datasets.py) ─
# Each entry expects a corresponding datasets/<slug>.csv + <slug>.meta.json pair.
# If the CSV file is missing, the seeder logs a warning and skips it.
REAL_CSV_DATASETS = [
    {
        "slug": "titanic",
        "name": "Titanic",
        "task_type": "classification",
        "description": "Real passenger data from the RMS Titanic disaster (April 1912). "
                       "891 passengers with features including class, sex, age, "
                       "siblings/spouses aboard, parents/children aboard, fare paid, "
                       "and embarkation port. Predict survival (0 = died, 1 = survived). "
                       "A classic Kaggle starter dataset with mixed numeric and "
                       "categorical features and missing values.",
        "samples": 891, "features": 10,
        "difficulty": "beginner",
    },
    {
        "slug": "pima_diabetes",
        "name": "PimaDiabetes",
        "task_type": "classification",
        "description": "Real clinical data from the Pima Indians of Arizona — a "
                       "population with one of the highest rates of type-2 diabetes "
                       "in the world. 768 female patients, 8 features including "
                       "plasma glucose, blood pressure, BMI, insulin, and diabetes "
                       "pedigree. Binary target: diabetes onset within 5 years. "
                       "Originally from the National Institute of Diabetes and "
                       "Digestive and Kidney Diseases.",
        "samples": 768, "features": 8,
        "difficulty": "intermediate",
    },
    {
        "slug": "heart_disease",
        "name": "HeartDisease",
        "task_type": "classification",
        "description": "Real clinical data from the Cleveland Clinic Foundation, "
                       "originally from the UCI ML repository. 303 patients with 13 "
                       "features including age, sex, chest pain type, resting blood "
                       "pressure, cholesterol, ECG results, max heart rate, exercise-"
                       "induced angina, ST depression, slope, number of major vessels, "
                       "and thal. Binary target: presence of heart disease.",
        "samples": 303, "features": 13,
        "difficulty": "intermediate",
    },
    {
        "slug": "sonar_mines_vs_rocks",
        "name": "SonarMinesVsRocks",
        "task_type": "classification",
        "description": "Real sonar signal data from the UCI ML repository. 208 patterns "
                       "obtained by bouncing sonar signals off metal cylinders (mines) "
                       "and rocks at various angles and under various conditions. 60 "
                       "numeric features in the range 0.0–1.0 represent energy in a "
                       "particular frequency band. Binary target: mine vs rock. A "
                       "classic benchmark for pattern classification.",
        "samples": 208, "features": 60,
        "difficulty": "intermediate",
    },
    {
        "slug": "banknote_authentication",
        "name": "BanknoteAuthentication",
        "task_type": "classification",
        "description": "Real data from the UCI ML repository. 1372 banknote images "
                       "were wavelet-transformed to extract 4 features: variance, "
                       "skewness, curtosis, and entropy of the image. Binary target: "
                       "genuine vs forged. A clean, easy-to-classify dataset — "
                       "perfect for verifying that a model framework's predict() "
                       "pipeline is wired correctly.",
        "samples": 1372, "features": 4,
        "difficulty": "beginner",
    },
    {
        "slug": "wine_quality_red",
        "name": "WineQualityRed",
        "task_type": "classification",
        "description": "Real physicochemical data from the UCI ML repository. 1599 red "
                       "Vinho Verde wines from northern Portugal, 11 features "
                       "including fixed acidity, volatile acidity, citric acid, "
                       "residual sugar, chlorides, free SO2, total SO2, density, pH, "
                       "sulphates, alcohol. Target: quality score 0–10 (sensory panel "
                       "median). Multi-class classification.",
        "samples": 1599, "features": 11,
        "difficulty": "intermediate",
    },
    {
        "slug": "wine_quality_white",
        "name": "WineQualityWhite",
        "task_type": "classification",
        "description": "Real physicochemical data from the UCI ML repository. 4898 white "
                       "Vinho Verde wines from northern Portugal, same 11 features as "
                       "the red wine dataset. Target: quality score 0–10. Larger and "
                       "slightly more imbalanced than the red variant — a tougher "
                       "multi-class benchmark.",
        "samples": 4898, "features": 11,
        "difficulty": "advanced",
    },
    {
        "slug": "iris_csv",
        "name": "IrisCSV",
        "task_type": "classification",
        "description": "The classic Iris dataset — but loaded from the real CSV used "
                       "by seaborn (not the sklearn Bunch). 150 samples, 4 features "
                       "(sepal length, sepal width, petal length, petal width). "
                       "Target: 3 species (setosa, versicolor, virginica). Useful as "
                       "a sanity check that the CSV-loading pipeline produces identical "
                       "numbers to sklearn's built-in version.",
        "samples": 150, "features": 4,
        "difficulty": "beginner",
    },
    {
        "slug": "penguins",
        "name": "PalmerPenguins",
        "task_type": "classification",
        "description": "Real data collected at Palmer Station, Antarctica by Dr. "
                       "Kristen Gorman. 344 penguins from 3 islands in the Palmer "
                       "Archipelago, with features including bill length, bill depth, "
                       "flipper length, body mass, sex, and island. Target: 3 species "
                       "(Adelie, Chinstrap, Gentoo). A modern alternative to Iris with "
                       "mixed numeric and categorical features and some missing values.",
        "samples": 344, "features": 9,
        "difficulty": "beginner",
    },
    {
        "slug": "auto_mpg",
        "name": "AutoMPG",
        "task_type": "regression",
        "description": "Real data from the UCI ML repository. 398 cars from the 1970s "
                       "and 1980s, 7 features including cylinders, displacement, "
                       "horsepower, weight, acceleration, model year, and origin. "
                       "Target: miles-per-gallon fuel efficiency. Contains some "
                       "missing values marked as '?'.",
        "samples": 398, "features": 7,
        "difficulty": "intermediate",
    },
    {
        "slug": "boston_housing",
        "name": "BostonHousing",
        "task_type": "regression",
        "description": "Real data from the classic Harrison & Rubinfeld (1978) study "
                       "of Boston house prices. 506 suburbs, 13 features including "
                       "crime rate, residential land zoning, industrial proportion, "
                       "nitric oxides concentration, average rooms, age of housing, "
                       "distance to employment centres, accessibility to radial "
                       "highways, property tax rate, pupil-teacher ratio, proportion "
                       "of Black residents, lower-status population proportion. "
                       "Target: median home value in $1000s.",
        "samples": 506, "features": 13,
        "difficulty": "intermediate",
    },
    {
        "slug": "real_estate",
        "name": "CaliforniaHousingCSV",
        "task_type": "regression",
        "description": "Real California census data from the 1990 California Housing "
                       "dataset (Pace & Barry, 1997). 20640 suburbs, 9 features "
                       "including median income, housing median age, total rooms, "
                       "total bedrooms, population, households, latitude, longitude, "
                       "and ocean proximity. Target: median house value. The same "
                       "dataset sklearn fetches — but here as a real CSV so the "
                       "benchmark path is fully transparent.",
        "samples": 20640, "features": 13,
        "difficulty": "advanced",
    },
]


# Default sample competitions seeded on first run
DEFAULT_COMPETITIONS = [
    {
        "title": "Titanic Survival Challenge",
        "slug": "titanic-survival-challenge",
        "description": (
            "Build the most accurate classifier you can on the legendary Titanic "
            "dataset. Predict which passengers survived the disaster based on class, "
            "sex, age, family aboard, fare, and embarkation port. This is the "
            "canonical Kaggle starter problem — perfect for your first submission. "
            "Top-3 finishers get a shout-out in the next release notes."
        ),
        "rules": (
            "1. Only scikit-learn / xgboost / lightgbm / pytorch / onnx / tensorflow models are accepted.\n"
            "2. Maximum 10 submissions per user.\n"
            "3. Submissions are auto-benchmarked on the standard Titanic test split.\n"
            "4. The evaluation metric is accuracy.\n"
            "5. Ties are broken by inference latency (lower is better)."
        ),
        "prize": "Top-3 leaderboard shout-out in the next release notes.",
        "dataset_name": "Titanic",
        "evaluation_metric": "accuracy",
        "duration_days": 30,
        "max_submissions_per_user": 10,
    },
    {
        "title": "Pima Indians Diabetes Prediction",
        "slug": "pima-diabetes-prediction",
        "description": (
            "Predict diabetes onset within 5 years for female Pima Indians patients "
            "using 8 clinical features (glucose, BMI, insulin, blood pressure, etc.). "
            "Lowest log-loss wins. A real clinical ML benchmark with imbalanced "
            "classes — perfect for experimenting with threshold tuning and "
            "calibration."
        ),
        "rules": (
            "1. Same framework rules as the Titanic challenge.\n"
            "2. Maximum 10 submissions per user.\n"
            "3. Evaluation metric is accuracy.\n"
            "4. Ties are broken by AUC-ROC, then by inference latency."
        ),
        "prize": "Bragging rights and a GitHub star.",
        "dataset_name": "PimaDiabetes",
        "evaluation_metric": "accuracy",
        "duration_days": 14,
        "max_submissions_per_user": 10,
    },
    {
        "title": "Heart Disease Detection",
        "slug": "heart-disease-detection",
        "description": (
            "Detect the presence of heart disease from 13 clinical features "
            "(age, sex, chest pain type, cholesterol, ECG, max heart rate, etc.). "
            "Highest F1 score wins — accuracy is misleading for imbalanced medical "
            "data. A real-world medical ML benchmark from the Cleveland Clinic."
        ),
        "rules": (
            "1. Same framework rules as the Titanic challenge.\n"
            "2. Maximum 15 submissions per user.\n"
            "3. Evaluation metric is F1 score (higher is better).\n"
            "4. Ties are broken by AUC-ROC, then by inference latency."
        ),
        "prize": "Featured model on the homepage for one week.",
        "dataset_name": "HeartDisease",
        "evaluation_metric": "f1_score",
        "duration_days": 21,
        "max_submissions_per_user": 15,
    },
    {
        "title": "Boston Housing Price Prediction",
        "slug": "boston-housing-price-prediction",
        "description": (
            "Predict median home values in Boston suburbs from 13 features "
            "(crime rate, rooms, age, tax rate, pupil-teacher ratio, etc.). "
            "Lowest RMSE wins. The classic regression benchmark — every ML "
            "textbook uses it. Now you can compete on it for real."
        ),
        "rules": (
            "1. Same framework rules as the Titanic challenge.\n"
            "2. Maximum 20 submissions per user.\n"
            "3. Evaluation metric is RMSE (lower is better).\n"
            "4. Ties are broken by R2 score, then by inference latency."
        ),
        "prize": "OpenBenchML contributor badge + GitHub star.",
        "dataset_name": "BostonHousing",
        "evaluation_metric": "rmse",
        "duration_days": 30,
        "max_submissions_per_user": 20,
    },
]


def _resolve_csv_path(slug: str) -> str:
    """Return the absolute path to datasets/<slug>.csv."""
    return str(DATASETS_DIR / f"{slug}.csv")


def _csv_exists(slug: str) -> bool:
    """Check whether the CSV file for a slug exists on disk."""
    return (DATASETS_DIR / f"{slug}.csv").is_file()


def seed_database():
    """Seed the database with default datasets and competitions.

    Safe to call multiple times — only inserts when the relevant table
    is empty.  Logs what it skipped so you can see at startup whether
    the seed ran or not.
    """
    db: Session = SessionLocal()
    try:
        # ── Datasets ───────────────────────────────────────────────────────
        existing_count = db.query(Dataset).count()
        if existing_count == 0:
            seeded = 0
            skipped = 0

            # 1. Sklearn built-ins (no file_path)
            for ds in SKLEARN_BUILTINS:
                db.add(Dataset(**ds))
                seeded += 1

            # 2. Real CSV datasets (with file_path pointing to local CSV)
            for csv_ds in REAL_CSV_DATASETS:
                if not _csv_exists(csv_ds["slug"]):
                    logger.warning(
                        f"CSV file for '{csv_ds['slug']}' not found in {DATASETS_DIR} "
                        f"— skipping. Run scripts/download_real_datasets.py to fetch it."
                    )
                    skipped += 1
                    continue
                db.add(Dataset(
                    name=csv_ds["name"],
                    task_type=csv_ds["task_type"],
                    description=csv_ds["description"],
                    samples=csv_ds["samples"],
                    features=csv_ds["features"],
                    file_path=_resolve_csv_path(csv_ds["slug"]),
                    is_builtin=True,  # built-in to the platform (managed by us)
                    difficulty=csv_ds["difficulty"],
                ))
                seeded += 1

            db.commit()
            logger.info(
                f"Seeded {seeded} datasets ({skipped} CSV datasets skipped — "
                f"run scripts/download_real_datasets.py to fetch them)"
            )
        else:
            logger.info(f"Database already has {existing_count} datasets, skipping dataset seed")

        # ── Competitions ───────────────────────────────────────────────────
        existing_comps = db.query(Competition).count()
        if existing_comps == 0:
            now = datetime.utcnow()
            seeded = 0
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
                seeded += 1
            db.commit()
            logger.info(f"Seeded {seeded} default competitions")
        else:
            logger.info(f"Database already has {existing_comps} competitions, skipping competition seed")

    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding database: {e}")
    finally:
        db.close()
