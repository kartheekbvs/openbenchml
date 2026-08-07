# Quick Start

Have a benchmark running in 60 seconds. Assumes you've already [installed](installation.md) the server and CLI.

## 1. Start the server

```bash
cd openbenchml
source .venv/bin/activate
python run.py
```

Leave this running in a terminal. The server is now listening on `http://localhost:8000`.

## 2. Train a model

In a separate terminal, train a quick RandomForest on Iris and save it as a joblib file:

```python
# train.py
import joblib
from sklearn.datasets import load_iris
from sklearn.ensemble import RandomForestClassifier

X, y = load_iris(return_X_y=True)
clf = RandomForestClassifier(n_estimators=50, random_state=42)
clf.fit(X, y)
joblib.dump(clf, 'rf_iris.joblib')
print('Saved rf_iris.joblib')
```

```bash
python train.py
```

## 3. Register and upload via the CLI

```bash
# Register (saves token to ~/.openbenchml/credentials.json)
openbenchml register \
  --username alice \
  --email alice@example.com \
  --password 'supersecret'

# List available benchmark datasets
openbenchml datasets

# Upload the model
openbenchml upload \
  --model ./rf_iris.joblib \
  --name "RandomForest Iris" \
  --framework scikit-learn \
  --description "50-tree RF, default hyperparams"
```

## 4. Run a benchmark

```bash
openbenchml benchmark --model-id 1 --dataset-id 1
```

Output (abbreviated):

```
✓ Benchmark submitted (job_id=1)

Job 1 — COMPLETED
Model: RandomForest Iris   Dataset: Iris

── ML Metrics ──────────────────────────────
  Accuracy:        100.00%
  Precision:       1.0000
  Recall:          1.0000
  F1 Score:        1.0000
  AUC-ROC:         1.0000
  Log Loss:        0.0521

── Performance (real per-sample percentiles) ──
  Latency mean:    1.898 ms
  Latency p50:     1.869 ms
  Latency p95:     2.113 ms
  Latency p99:     2.575 ms
  Throughput:      496.3 /s
  Memory:          0.27 MB
  Model size:      37.4 KB
  Inferences:      50
```

Notice that **P50 ≤ P95 ≤ P99** — these are real per-sample percentiles measured over 50 timed forward passes, not synthetic approximations.

## 5. Submit to a competition

Out of the box, OpenBenchML ships with two sample competitions. Submit your model to one:

```bash
openbenchml submit \
  --competition iris-classification-challenge \
  --model-id 1 \
  --note "First attempt — default RF hyperparams"
```

Output:

```
✓ Submitted model 1 to iris-classification-challenge

── Current Leaderboard ──────────────────────
  #1  alice  RandomForest Iris  score=1.0000
```

## 6. View the global leaderboard

```bash
openbenchml leaderboard
```

## What just happened?

1. You trained a model locally.
2. You uploaded it to OpenBenchML via the CLI.
3. The CLI called the `/benchmark` endpoint, which:
   - Loaded your model with `joblib.load`
   - Loaded the Iris dataset (built-in) and split it 80/20 stratified
   - Ran 5 warmup + 50 timed forward passes
   - Computed accuracy, precision, recall, F1, AUC-ROC, log-loss, confusion matrix
   - Computed per-sample latencies and derived P50/P95/P99 from them
   - Computed throughput, peak memory, CPU usage
   - Persisted the result and updated the leaderboard
4. The CLI submitted your model to the Iris Classification Challenge, which re-ran the benchmark and recorded your score on the competition leaderboard.

## Next steps

- [Concepts](concepts.md) — understand models vs datasets vs jobs vs competitions
- [CLI Reference](../cli/index.md) — every command documented
- [API Reference](../api/index.md) — the underlying REST API
