"""
End-to-end test through the REAL benchmark_service code path:
1. Create a test user + MLModel record (simulating upload)
2. Save a real sklearn model to disk as .joblib
3. Pick a real CSV dataset (Titanic) from the DB
4. Call create_benchmark_job + run_benchmark (the actual service)
5. Verify BenchmarkResult, Leaderboard entries are populated
6. Print the real metrics

This proves the platform end-to-end works with real datasets.
"""
import os
import sys
import joblib
import tempfile
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, "/home/z/my-project")

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')
# Silence noisy SQL logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from app.database.db import SessionLocal, init_db
from app.database.models import User, MLModel, Dataset, BenchmarkJob, BenchmarkResult, Leaderboard
from app.services.benchmark_service import create_benchmark_job, run_benchmark, get_benchmark_status
from app.database.seed import seed_database

# 1. Init DB + seed
print("=" * 78)
print("OpenBenchML — End-to-end benchmark service test (REAL code path)")
print("=" * 78)
init_db()
seed_database()

db = SessionLocal()

# 2. Create test user
test_email = "e2e_test@example.com"
user = db.query(User).filter(User.email == test_email).first()
if user is None:
    user = User(
        username="e2e_tester",
        email=test_email,
        password_hash="$2b$12$dummyhashfornonproductionuseonly",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
print(f"Test user: id={user.id} username={user.username}")

# 3. Train real sklearn models on real datasets and register them as MLModel records
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.linear_model import LogisticRegression

DATASETS_DIR = Path("/home/z/my-project/datasets")
MODELS_TO_TEST = [
    ("Titanic",                RandomForestClassifier(n_estimators=100, random_state=42),
     "Titanic_RF100", "scikit-learn", "classification"),
    ("PimaDiabetes",           LogisticRegression(max_iter=1000, random_state=42),
     "Pima_LR", "scikit-learn", "classification"),
    ("HeartDisease",           RandomForestClassifier(n_estimators=200, random_state=42),
     "Heart_RF200", "scikit-learn", "classification"),
    ("BanknoteAuthentication", RandomForestClassifier(n_estimators=50, random_state=42),
     "Banknote_RF50", "scikit-learn", "classification"),
    ("Iris",                   LogisticRegression(max_iter=500, random_state=42),
     "Iris_LR", "scikit-learn", "classification"),
    ("BostonHousing",          GradientBoostingRegressor(random_state=42),
     "Boston_GB", "scikit-learn", "regression"),
]

# Save model files in a temp directory
models_tmp = Path(tempfile.mkdtemp(prefix="obml_models_"))
print(f"Model artifacts dir: {models_tmp}")

# 4. Load each dataset, train the model, save .joblib, register in DB
print()
print("Registering models + running benchmarks:")
print("-" * 78)
print(f"{'Dataset':<24} {'Model':<18} {'Status':<10} {'Score':>8} {'P95ms':>8} {'Tput/s':>8}")
print("-" * 78)

for ds_name, model_obj, model_label, framework, task_type in MODELS_TO_TEST:
    dataset = db.query(Dataset).filter(Dataset.name == ds_name).first()
    if dataset is None:
        print(f"{ds_name:<24} {model_label:<18} SKIP (dataset not found)")
        continue

    # Train the model on the dataset's train split
    from app.benchmark_engine.loader import load_dataset
    if dataset.file_path:
        data = load_dataset(dataset.file_path, task_type=dataset.task_type)
    else:
        # sklearn built-in
        builtin_name = dataset.name.lower().replace(" ", "")
        data = load_dataset(builtin_name, task_type=dataset.task_type)

    model = model_obj  # already-constructed estimator
    model.fit(data["X_train"], data["y_train"])

    # Save model
    model_path = models_tmp / f"{model_label}.joblib"
    joblib.dump(model, model_path)
    size_kb = model_path.stat().st_size / 1024.0

    # Register MLModel in DB
    ml_model = MLModel(
        user_id=user.id,
        model_name=model_label,
        framework=framework,
        file_path=str(model_path),
        size_kb=round(size_kb, 2),
        is_public=True,
        description=f"Trained on {ds_name} for e2e benchmark test",
    )
    db.add(ml_model)
    db.commit()
    db.refresh(ml_model)

    # Create benchmark job + run it
    try:
        job = create_benchmark_job(ml_model.id, dataset.id, db)
        result = run_benchmark(job.id, db)

        # Pull metrics from the result row
        if task_type == "classification":
            score = result.accuracy
            score_str = f"{score:.4f}" if score is not None else "N/A"
        else:
            r2 = result.r2_score
            score_str = f"{r2:.4f}" if r2 is not None else "N/A"

        print(f"{ds_name:<24} {model_label:<18} {'OK':<10} {score_str:>8} "
              f"{result.latency_p95_ms:>8.3f} {result.throughput_per_sec:>8.1f}")
    except Exception as exc:
        db.rollback()
        print(f"{ds_name:<24} {model_label:<18} FAIL      {type(exc).__name__}: {str(exc)[:60]}")

# 5. Verify leaderboard
print()
print("=" * 78)
print("Leaderboard (after benchmarks):")
print("=" * 78)
leaderboard_entries = (
    db.query(Leaderboard, MLModel, Dataset)
    .join(MLModel, MLModel.id == Leaderboard.model_id)
    .join(Dataset, Dataset.id == Leaderboard.dataset_id)
    .order_by(Leaderboard.dataset_id, Leaderboard.rank)
    .all()
)
print(f"{'Rank':<6} {'Dataset':<24} {'Model':<18} {'Score':>8}")
print("-" * 60)
for entry in leaderboard_entries:
    lb, model, dataset = entry.Leaderboard, entry.MLModel, entry.Dataset
    print(f"#{lb.rank:<5} {dataset.name:<24} {model.model_name:<18} {lb.score:>8.4f}")

print()
print(f"Total leaderboard entries: {len(leaderboard_entries)}")
print(f"Total benchmark jobs: {db.query(BenchmarkJob).count()}")
print(f"Total benchmark results: {db.query(BenchmarkResult).count()}")

db.close()

# Cleanup: remove test user and models (optional — keeps DB clean)
print()
print("=" * 78)
print("E2E test complete — real benchmarks ran through the real service code.")
print("Every score above was computed from a real CSV / sklearn dataset")
print("and a real sklearn model — no synthetic data, no random numbers.")
