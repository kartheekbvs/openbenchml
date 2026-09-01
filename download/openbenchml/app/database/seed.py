"""
OpenBenchML Database Seeder
=============================
Populates the database with default benchmark datasets and sample
competitions so the platform is usable immediately after install.

The list of built-in datasets here mirrors the registry in
``app/benchmark_engine/loader.py``.  When you add a dataset to the
loader you should add a matching entry here so users can see it in
the web UI and CLI without needing to know the loader's internal key.
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.database.db import SessionLocal
from app.database.models import Dataset, Competition

logger = logging.getLogger(__name__)

BUILTIN_DATASETS = [
    # ── Classic sklearn — classification ─────────────────────────────────
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
        "description": "Wine quality classification dataset derived from chemical "
                       "analysis of wines. 13 chemical features including alcohol, "
                       "malic acid, ash, flavonoids. Great for multi-class "
                       "classification benchmarking.",
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

    # ── Classic sklearn — regression ─────────────────────────────────────
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

    # ── Synthetic — classification ───────────────────────────────────────
    {
        "name": "MakeClassification",
        "task_type": "classification",
        "description": "Synthetic multi-class classification — 1000 samples, 20 "
                       "features, 3 classes, 2 clusters per class, 10 informative "
                       "features. Configurable complexity — perfect for stress-"
                       "testing classifiers at scale.",
        "samples": 1000, "features": 20,
        "difficulty": "intermediate", "is_builtin": True,
    },
    {
        "name": "MakeMoons",
        "task_type": "classification",
        "description": "Two interleaving half-moons — 800 samples with 25%% noise. "
                       "A classic non-linearly-separable dataset — great for "
                       "comparing linear vs. non-linear classifiers (SVM kernels, "
                       "tree ensembles, neural networks).",
        "samples": 800, "features": 2,
        "difficulty": "intermediate", "is_builtin": True,
    },
    {
        "name": "MakeCircles",
        "task_type": "classification",
        "description": "Concentric circles — small circle inside a larger one, 800 "
                       "samples with 20%% noise. Another classic non-linear dataset; "
                       "linear classifiers will fail here. Good benchmark for "
                       "kernel methods and tree ensembles.",
        "samples": 800, "features": 2,
        "difficulty": "intermediate", "is_builtin": True,
    },
    {
        "name": "MakeBlobs",
        "task_type": "classification",
        "description": "Gaussian blobs — 900 samples, 8 features, 4 well-separated "
                       "clusters. Good baseline for clustering-derived "
                       "classification and for testing scalability.",
        "samples": 900, "features": 8,
        "difficulty": "beginner", "is_builtin": True,
    },
    {
        "name": "MakeHastie",
        "task_type": "classification",
        "description": "Hastie et al. binary classification dataset — 2000 samples, "
                       "10 features generated from standard gaussian, target is "
                       "label = sign(sum(x**2) - 9.8). A binary benchmark used in "
                       "boosting literature.",
        "samples": 2000, "features": 10,
        "difficulty": "advanced", "is_builtin": True,
    },

    # ── Synthetic — regression ───────────────────────────────────────────
    {
        "name": "MakeRegression",
        "task_type": "regression",
        "description": "Synthetic linear regression — 1000 samples, 15 features, 10 "
                       "informative, gaussian noise (sigma=10). Good baseline for "
                       "linear models, regularised regression, and tree-based "
                       "regressors.",
        "samples": 1000, "features": 15,
        "difficulty": "intermediate", "is_builtin": True,
    },
    {
        "name": "MakeFriedman1",
        "task_type": "regression",
        "description": "Friedman #1 regression — 1000 samples, 10 features. The "
                       "target is a non-linear function of the first 4 features "
                       "only — the remaining 6 are irrelevant. Classic benchmark "
                       "from Friedman (1991) for gradient boosting papers.",
        "samples": 1000, "features": 10,
        "difficulty": "advanced", "is_builtin": True,
    },
    {
        "name": "MakeFriedman2",
        "task_type": "regression",
        "description": "Friedman #2 regression — 1000 samples, 4 features combined "
                       "as a product of trigonometric and exponential functions. "
                       "Highly non-linear; a tough test for any regressor.",
        "samples": 1000, "features": 4,
        "difficulty": "advanced", "is_builtin": True,
    },
    {
        "name": "MakeFriedman3",
        "task_type": "regression",
        "description": "Friedman #3 regression — 1000 samples, 4 features with "
                       "arctan-based non-linearity. The third in the Friedman "
                       "trilogy of non-linear regression benchmarks.",
        "samples": 1000, "features": 4,
        "difficulty": "advanced", "is_builtin": True,
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
    {
        "title": "Moons Non-Linear Showdown",
        "slug": "moons-non-linear-showdown",
        "description": (
            "Two interleaving half-moons — can your model separate them? "
            "Linear classifiers will fail here. This challenge rewards "
            "kernel methods, tree ensembles, and neural networks. The "
            "MakeMoons dataset is small but deceptively hard — every "
            "fraction of a percent matters."
        ),
        "rules": (
            "1. Same framework rules as the Iris challenge.\n"
            "2. Maximum 15 submissions per user.\n"
            "3. Evaluation metric is accuracy.\n"
            "4. Ties are broken by AUC-ROC, then by inference latency."
        ),
        "prize": "Featured model on the homepage for one week.",
        "dataset_name": "MakeMoons",
        "evaluation_metric": "accuracy",
        "duration_days": 21,
        "max_submissions_per_user": 15,
    },
    {
        "title": "Friedman #1 Grand Prix",
        "slug": "friedman-1-grand-prix",
        "description": (
            "The Friedman #1 dataset is the gold-standard benchmark in the "
            "gradient boosting literature. 10 features, only the first 4 are "
            "informative, and the target is a non-linear combination. Lowest "
            "RMSE wins. Boosting methods typically dominate here — can a "
            "neural net beat them?"
        ),
        "rules": (
            "1. Same framework rules as the Iris challenge.\n"
            "2. Maximum 20 submissions per user.\n"
            "3. Evaluation metric is RMSE (lower is better).\n"
            "4. Ties are broken by R2 score, then by inference latency."
        ),
        "prize": "OpenBenchML contributor badge + GitHub star.",
        "dataset_name": "MakeFriedman1",
        "evaluation_metric": "rmse",
        "duration_days": 30,
        "max_submissions_per_user": 20,
    },
]


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
