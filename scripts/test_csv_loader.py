"""Smoke-test the new CSV dataset loader against every real-world CSV."""
import sys
sys.path.insert(0, "/home/z/my-project")

from pathlib import Path
from app.benchmark_engine.loader import load_dataset, list_builtin_datasets

DATASETS_DIR = Path("/home/z/my-project/datasets")

print("=" * 70)
print("CSV dataset loader smoke test")
print("=" * 70)

csv_files = sorted(DATASETS_DIR.glob("*.csv"))
print(f"Found {len(csv_files)} CSV files in {DATASETS_DIR}")
print()

ok = 0
failed = []

for csv_path in csv_files:
    print(f"[TEST] {csv_path.name}")
    try:
        data = load_dataset(str(csv_path))
        X_test = data["X_test"]
        y_test = data["y_test"]
        X_train = data["X_train"]
        y_train = data["y_train"]
        task = data["task_type"]
        feats = data["feature_names"]

        n_classes = len(set(y_test.tolist()))
        print(f"  task={task}  train={X_train.shape}  test={X_test.shape}")
        print(f"  features={len(feats)}  classes={n_classes}  "
              f"y_test_dtype={y_test.dtype}")
        print(f"  first 3 feature names: {feats[:3]}")
        print(f"  y_test sample: {y_test[:5].tolist()}")
        ok += 1
    except Exception as exc:
        print(f"  FAILED: {type(exc).__name__}: {exc}")
        failed.append((csv_path.name, str(exc)))
    print()

print("=" * 70)
print(f"Result: {ok}/{len(csv_files)} datasets loaded successfully")
if failed:
    print("Failed:")
    for name, err in failed:
        print(f"  - {name}: {err}")
    sys.exit(1)
print("All CSV datasets loaded OK!")

print()
print("=" * 70)
print("Built-in sklearn datasets:")
print("=" * 70)
for d in list_builtin_datasets():
    print(f"  {d['name']:20s}  task={d['task_type']:14s}  synthetic={d['synthetic']}")
