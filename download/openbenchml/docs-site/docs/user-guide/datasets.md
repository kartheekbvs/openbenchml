# Datasets

A dataset is what your model gets evaluated against. OpenBenchML ships with six built-in datasets and supports custom uploads.

## Built-in datasets

These are loaded directly from `scikitlearn.datasets` — no download required.

| ID | Name | Task | Samples | Features | Difficulty |
|----|------|------|---------|----------|------------|
| 1 | Iris | classification | 150 | 4 | beginner |
| 2 | Wine | classification | 178 | 13 | intermediate |
| 3 | BreastCancer | classification | 569 | 30 | intermediate |
| 4 | Digits | classification | 1,797 | 64 | intermediate |
| 5 | CaliforniaHousing | regression | 20,640 (subsampled to 2,000) | 8 | advanced |
| 6 | Diabetes | regression | 442 | 10 | beginner |

## Listing

```bash
# CLI
openbenchml datasets
openbenchml datasets --task-type regression
openbenchml datasets --difficulty beginner

# API
curl http://localhost:8000/api/datasets
curl 'http://localhost:8000/api/datasets?task_type=regression'
```

## Train/test split

Built-in datasets are split 80/20 with `random_state=42` for reproducibility. Classification datasets are stratified on `y` to preserve class distributions. If a class has fewer than 2 samples, the split falls back to non-stratified.

## Custom datasets (coming soon)

Custom dataset upload (`.npz` / `.joblib` / `.pkl`) is supported by the loader but not yet exposed in the UI. The loader expects:

- **`.npz`** — a NumPy archive with `X` and `y` arrays
- **`.joblib` / `.pkl`** — a pickled dict `{"X": ..., "y": ...}` or a tuple `(X, y)`

You can programmatically benchmark against a custom file by passing the path directly to `load_dataset`.

## What's next?

- [Benchmarks](benchmarks.md) — running an evaluation
- [Concepts](../getting-started/concepts.md) — how datasets fit into the bigger picture
