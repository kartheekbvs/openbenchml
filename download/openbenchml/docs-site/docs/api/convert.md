# Convert API

`POST /api/convert` runs user-supplied Python code in the sandbox, pickles
the resulting `model` variable, and registers it as an `MLModel`.

!!! note "Authentication required"
    All endpoints on this page require a `Bearer` token (returned by
    `POST /api/auth/login` or `POST /api/auth/register`).

## Convert code → pickled MLModel

```http
POST /api/convert
Content-Type: application/json
Authorization: Bearer <token>
```

### Request body

| Field         | Type   | Required | Default         | Notes                                                          |
| ------------- | ------ | -------- | --------------- | -------------------------------------------------------------- |
| `model_name`  | string | yes      | —               | 1–120 chars. Used for display + safe filename.                 |
| `description` | string | no       | `""`            | Up to 2000 chars.                                              |
| `framework`   | string | no       | `"scikit-learn"`| One of: `scikit-learn`, `pytorch`, `onnx`, `tensorflow`, `xgboost`, `lightgbm`. Auto-detection overrides this if it succeeds. |
| `code`        | string | yes      | —               | 1–50,000 chars. Must assign `model` to a trained estimator.    |

### Example

```bash
curl -X POST http://localhost:8000/api/convert \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "RF on Iris",
    "description": "50 trees, stratified split",
    "framework": "scikit-learn",
    "code": "from sklearn.ensemble import RandomForestClassifier\nfrom sklearn.datasets import load_iris\nfrom sklearn.model_selection import train_test_split\nX, y = load_iris(return_X_y=True)\nXtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)\nmodel = RandomForestClassifier(n_estimators=50, random_state=42).fit(Xtr, ytr)\nacc = model.score(Xte, yte)\nprint(f\"acc={acc:.4f}\")"
  }'
```

### Response — `200 OK`

```json
{
  "id": 17,
  "model_name": "RF on Iris",
  "framework": "scikit-learn",
  "size_kb": 18.34,
  "detected_framework": "scikit-learn",
  "model_class": "RandomForestClassifier",
  "stdout": "acc=0.9667\n",
  "stderr": "",
  "metrics_in_code": {
    "accuracy": 0.9666666666666667
  }
}
```

### Response — `400 Bad Request`

Returned when:

- Code execution fails (syntax error, runtime error, timeout).
- No `model` variable is left in the namespace.
- `framework` is not in the supported list.

```json
{
  "detail": "No 'model' variable found in the code's namespace. Please assign your trained model to a variable named 'model'. Variables we did find: ['X', 'X_test', 'X_train', 'y', 'y_test', 'y_train', 'clf']"
}
```

### Response — `401 Unauthorized`

```json
{ "detail": "Authentication required" }
```

## Errors & troubleshooting

| Symptom                                              | Fix                                                                      |
| ---------------------------------------------------- | ------------------------------------------------------------------------ |
| `ImportError: Import of 'X' is blocked by sandbox`   | Remove the import; the platform blocks `subprocess`, `socket`, `http`, `urllib`, `ctypes`, `shutil`, `pathlib`. |
| `TimeoutError: Code execution exceeded 60s limit`    | Reduce dataset size, reduce `n_estimators`, simplify feature engineering.|
| `No 'model' variable found`                          | Make sure your final line is `model = SomeEstimator().fit(X, y)`.        |
| Detected framework is wrong                          | Pass `framework` explicitly in the request body.                         |
