# Convert Code → Model

`/convert` is the **student-friendly** way to turn Python code into a benchmarkable
ML model. You don't need to install Python locally, you don't need to upload a
`.pkl` file — you just paste code that *trains* a model, hit **Convert**, and the
platform does the rest.

## How it works

```text
┌─────────────────────┐      ┌──────────────────────┐      ┌──────────────────┐
│  Your Python code   │ ──▶  │  Sandbox execution   │ ──▶  │  Pickled model   │
│  (trains `model`)   │      │  (np, pd, sklearn    │      │  saved as an     │
│                     │      │   pre-imported)      │      │  MLModel row     │
└─────────────────────┘      └──────────────────────┘      └──────────────────┘
                                       │                              │
                                       ▼                              ▼
                              stdout / stderr captured       ready to benchmark
                              + auto-detected framework       on any dataset
```

The convention is dead-simple:

> Your code must **assign the trained model to a variable named `model`**.

Anything else the platform can find (e.g. `accuracy`, `rmse`) is captured as
metadata and displayed on the model's detail page.

## A complete example

```python
from sklearn.ensemble import RandomForestClassifier
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split

X, y = load_iris(return_X_y=True)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y,
)

model = RandomForestClassifier(n_estimators=50, random_state=42)
model.fit(X_train, y_train)

acc = model.score(X_test, y_test)
print(f"Training complete — test accuracy = {acc:.4f}")
```

After Convert:

- A new `MLModel` row is created (framework auto-detected as `scikit-learn`).
- The model's detail page shows `accuracy = 0.9667` (captured from your `acc` variable).
- You can immediately run a benchmark on any of the 17 built-in datasets.

## Pre-imported libraries

To keep code short for students, the sandbox pre-imports these names —
**no `import` statement needed** for them:

| Shortcut                  | Module                       |
| ------------------------- | ---------------------------- |
| `np`                      | `numpy`                      |
| `pd`                      | `pandas`                     |
| `sklearn`                 | `scikit-learn` (top-level)   |
| `scipy`                   | `scipy`                      |
| `joblib`                  | `joblib`                     |
| `sklearn_datasets`        | `sklearn.datasets`           |
| `sklearn_linear_model`    | `sklearn.linear_model`       |
| `sklearn_ensemble`        | `sklearn.ensemble`           |
| `sklearn_tree`            | `sklearn.tree`               |
| `sklearn_svm`             | `sklearn.svm`                |
| `sklearn_neighbors`       | `sklearn.neighbors`          |
| `sklearn_neural_network`  | `sklearn.neural_network`     |
| `sklearn_metrics`         | `sklearn.metrics`            |
| `sklearn_model_selection` | `sklearn.model_selection`    |
| `sklearn_preprocessing`   | `sklearn.preprocessing`      |
| `sklearn_pipeline`        | `sklearn.pipeline`           |
| `sklearn_decomposition`   | `sklearn.decomposition`      |

You can still write `from sklearn.ensemble import RandomForestClassifier` —
the pre-imports are just shortcuts.

## Auto-detected metrics

If your code leaves any of these variables in scope, they're saved as
model metadata and shown on the model page:

| Variable name(s)             | Stored as    |
| ---------------------------- | ------------ |
| `accuracy` *or* `acc`        | `accuracy`   |
| `f1_score` *or* `f1`         | `f1_score`   |
| `rmse`                       | `rmse`       |
| `r2_score` *or* `r2`         | `r2_score`   |
| `mae`                        | `mae`        |

## Framework auto-detection

The framework is detected from your `model` object's class:

| Class module                       | Detected framework |
| ---------------------------------- | ------------------ |
| `torch.*`                          | `pytorch`          |
| `tensorflow.*` / `keras.*`         | `tensorflow`       |
| `xgboost.*`                        | `xgboost`          |
| `lightgbm.*`                       | `lightgbm`         |
| `onnx.*`                           | `onnx`             |
| (anything else)                    | `scikit-learn`     |

You can override the detection with the **Framework** dropdown on the form.

## Security

The sandbox is intentionally **permissive about ML libraries** but **strict about
everything else**. The following are blocked:

- `open()` — file I/O outside the runner's workspace
- `os.system`, `subprocess.*` — process spawning
- `socket`, `http.*`, `urllib.*` — raw network access
- `ctypes`, `shutil`, `pathlib` — filesystem/FFI operations
- `exec`, `eval`, `compile`, `globals`, `breakpoint`, `input`

Execution has a **60-second wall-clock limit** (30s for the notebook).

!!! warning "Production deployments"
    For public-facing deployments with untrusted users, layer Docker sandboxing
    on top of the in-process sandbox. See
    [Architecture → Code Sandbox](../architecture/sandbox.md).

## CLI equivalent

```bash
openbenchml convert --file train.py --name "My RF" --description "50 trees"
# or inline:
openbenchml convert --code "$(cat train.py)" --name "My RF"
```

## API equivalent

```http
POST /api/convert
Content-Type: application/json
Authorization: Bearer <token>

{
  "model_name": "My RF",
  "description": "50 trees",
  "framework": "scikit-learn",
  "code": "from sklearn..."
}
```

See [API Reference → Convert](../api/convert.md).
