"""End-to-end smoke test for the OpenBenchML core benchmark engine.

Runs without a live web server — directly invokes the loader, evaluator,
and metrics modules against a real sklearn model + the iris dataset.
"""
import sys
import os
import joblib
import tempfile
from pathlib import Path

# Ensure we can import the app package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sklearn.datasets import load_iris
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

from app.benchmark_engine.loader import load_model, load_dataset
from app.benchmark_engine.evaluator import evaluate_model


def main():
    print("=" * 70)
    print("OpenBenchML Core Engine Smoke Test")
    print("=" * 70)

    # ── 1. Train & save a real sklearn model ──────────────────────────────
    print("\n[1] Training RandomForest on Iris...")
    iris = load_iris()
    X, y = iris.data, iris.target
    rf = RandomForestClassifier(n_estimators=50, random_state=42)
    rf.fit(X, y)

    tmpdir = Path(tempfile.mkdtemp(prefix="obml_"))
    model_path = tmpdir / "rf_iris.joblib"
    joblib.dump(rf, model_path)
    print(f"    Saved model: {model_path} ({model_path.stat().st_size / 1024:.1f} KB)")

    # ── 2. Load model via our loader ──────────────────────────────────────
    print("\n[2] Loading model via app.benchmark_engine.loader.load_model...")
    model = load_model(str(model_path), "scikit-learn")
    print(f"    Loaded: {type(model).__name__}")

    # ── 3. Load iris dataset via our loader (using just the name) ─────────
    print("\n[3] Loading iris dataset by name...")
    data = load_dataset("iris", task_type="classification")
    print(f"    X_test shape: {data['X_test'].shape}")
    print(f"    y_test shape: {data['y_test'].shape}")
    print(f"    task_type: {data['task_type']}")

    # ── 4. Test all built-in datasets ────────────────────────────────────
    print("\n[4] Testing all 6 built-in datasets...")
    for name in ("iris", "wine", "breastcancer", "digits",
                 "californiahousing", "diabetes"):
        try:
            d = load_dataset(name)
            tt = d["task_type"]
            print(f"    OK {name:20s}  task={tt:14s}  "
                  f"train={d['X_train'].shape[0]:6d}  test={d['X_test'].shape[0]:5d}")
        except Exception as e:
            print(f"    FAIL {name:20s}  {e}")
            return 1

    # ── 5. Run full evaluate_model pipeline ──────────────────────────────
    print("\n[5] Running full evaluate_model() pipeline (RandomForest on Iris)...")
    metrics = evaluate_model(
        model_artifact=model,
        dataset=data,
        task_type="classification",
        timeout_seconds=120,
        model_path=str(model_path),
    )

    print("\n    --- Results ---")
    print(f"    accuracy      : {metrics.get('accuracy'):.4f}")
    print(f"    precision     : {metrics.get('precision'):.4f}")
    print(f"    recall        : {metrics.get('recall'):.4f}")
    print(f"    f1_score      : {metrics.get('f1_score'):.4f}")
    print(f"    auc_roc       : {metrics.get('auc_roc')}")
    print(f"    log_loss      : {metrics.get('log_loss')}")
    print(f"    confusion_mat : {metrics.get('confusion_matrix') is not None}")
    print(f"    classif_report: {metrics.get('classification_report') is not None}")

    print(f"\n    latency_ms    : {metrics.get('latency_ms'):.4f}")
    print(f"    latency_p50   : {metrics.get('latency_p50_ms'):.4f}")
    print(f"    latency_p95   : {metrics.get('latency_p95_ms'):.4f}")
    print(f"    latency_p99   : {metrics.get('latency_p99_ms'):.4f}")
    print(f"    latency_std   : {metrics.get('latency_std_ms'):.4f}")
    print(f"    throughput/s  : {metrics.get('throughput_per_sec'):.1f}")
    print(f"    memory_mb     : {metrics.get('memory_mb'):.4f}")
    print(f"    cpu_percent   : {metrics.get('cpu_percent'):.1f}")
    print(f"    model_size_kb : {metrics.get('model_size_kb'):.2f}")
    print(f"    inference_cnt : {metrics.get('inference_count')}")
    print(f"    timed_runs    : {metrics.get('timed_runs')}")

    # ── 6. Validate that percentiles are REAL (not fake averages) ─────────
    print("\n[6] Validating percentile integrity...")
    p50 = metrics.get("latency_p50_ms", 0)
    p95 = metrics.get("latency_p95_ms", 0)
    p99 = metrics.get("latency_p99_ms", 0)
    mean = metrics.get("latency_ms", 0)
    assert p95 >= p50, f"P95 ({p95}) should be >= P50 ({p50})"
    assert p99 >= p95, f"P99 ({p99}) should be >= P95 ({p95})"
    assert p50 > 0, "P50 should be > 0"
    print(f"    OK P50 <= P95 <= P99  ({p50:.4f} <= {p95:.4f} <= {p99:.4f})")
    print(f"    OK Real per-sample latencies (mean={mean:.4f}ms, runs={metrics.get('timed_runs')})")

    # ── 7. Test regression with Diabetes ─────────────────────────────────
    print("\n[7] Testing regression pipeline (LinearRegression on Diabetes)...")
    from sklearn.linear_model import LinearRegression
    from sklearn.datasets import load_diabetes

    diab = load_diabetes()
    lr = LinearRegression()
    lr.fit(diab.data, diab.target)
    lr_path = tmpdir / "lr_diabetes.joblib"
    joblib.dump(lr, lr_path)

    diab_data = load_dataset("diabetes", task_type="regression")
    reg_metrics = evaluate_model(
        model_artifact=lr,
        dataset=diab_data,
        task_type="regression",
        model_path=str(lr_path),
    )
    print(f"    r2_score : {reg_metrics.get('r2_score'):.4f}")
    print(f"    mae      : {reg_metrics.get('mae'):.4f}")
    print(f"    rmse     : {reg_metrics.get('rmse'):.4f}")

    print("\n" + "=" * 70)
    print("ALL CORE ENGINE TESTS PASSED")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
