# Models

A model is a serialized ML artifact that you upload to OpenBenchML. Once uploaded, it can be benchmarked against any dataset, submitted to competitions, and shared with other users.

## Supported frameworks

| Framework | Identifier | File extensions | Notes |
|-----------|-----------|-----------------|-------|
| scikit-learn | `scikit-learn` | `.pkl`, `.joblib` | Default; ships with the base install. |
| PyTorch | `pytorch` | `.pt`, `.pth` | Requires `pip install torch`. Loads with `torch.load(map_location="cpu")`. |
| ONNX | `onnx` | `.onnx` | Requires `pip install onnxruntime`. |
| TensorFlow / Keras | `tensorflow` | `.h5`, `.pb` (SavedModel dir) | Requires `pip install tensorflow`. |
| XGBoost | `xgboost` | `.json`, `.ubj`, `.bin`, `.joblib` | Native format tried first, then joblib fallback. |
| LightGBM | `lightgbm` | `.txt`, `.model`, `.joblib` | Native format tried first, then joblib fallback. |

## Uploading

### Via the CLI

```bash
openbenchml upload \
  --model ./rf_iris.joblib \
  --name "RandomForest Iris v1" \
  --framework scikit-learn \
  --description "50-tree RF, default hyperparams, trained on full Iris"
```

### Via the API

```bash
curl -X POST http://localhost:8000/models/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "model_name=RandomForest Iris v1" \
  -F "framework=scikit-learn" \
  -F "description=50-tree RF" \
  -F "file=@./rf_iris.joblib"
```

### Via the web UI

Browse to `/models/upload` while logged in. Drag your file into the form, pick a framework, and submit.

## Listing & viewing

```bash
# CLI
openbenchml models                  # list public models
openbenchml models --framework onnx # filter by framework
openbenchml model 42                # view a single model
```

```bash
# API
curl http://localhost:8000/api/models
curl http://localhost:8000/api/models/42
```

## Privacy

Models have an `is_public` flag (default `True`). Private models are only visible to their owner. Toggle this in the upload form or by editing the model from the "My Models" page.

## Deleting

Models can be deleted from the "My Models" page (trash icon) or via a `DELETE` to `/api/models/{id}` (not yet exposed — coming soon). Deleting a model also removes its benchmark jobs and leaderboard entries via cascade.

## File safety

- Uploads are confined to `UPLOAD_DIR` (`uploads/` by default).
- The server resolves each path and verifies it stays inside `UPLOAD_DIR` before reading or deleting — path traversal attempts are rejected.
- Files are written atomically (`.tmp` → rename) so partial uploads don't leave corrupt files.

## Size limits

Default max file size is 500 MB (`MAX_MODEL_SIZE_MB`). Override via env var.

## What's next?

- [Benchmarks](benchmarks.md) — how to actually evaluate a model.
- [Competitions](competitions.md) — submit your model to a Kaggle-style competition.
