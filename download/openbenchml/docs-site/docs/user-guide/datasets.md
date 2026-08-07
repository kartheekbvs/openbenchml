# Datasets

A dataset is what your model gets evaluated against. OpenBenchML v4.0 ships with **17 built-in datasets** spanning classic sklearn loaders, fetchers, and synthetic generators — no download required.

## Built-in datasets

### Classic sklearn — classification

| ID | Name | Samples | Features | Difficulty |
|----|------|---------|----------|------------|
| 1  | Iris | 150 | 4 | beginner |
| 2  | Wine | 178 | 13 | intermediate |
| 3  | BreastCancer | 569 | 30 | intermediate |
| 4  | Digits | 1,797 | 64 | intermediate |
| 5  | OlivettiFaces | 400 (subsampled to 200) | 4,096 | advanced |

### Classic sklearn — regression

| ID | Name | Samples | Features | Difficulty |
|----|------|---------|----------|------------|
| 6  | Diabetes | 442 | 10 | beginner |
| 7  | CaliforniaHousing | 20,640 (subsampled to 2,000) | 8 | advanced |
| 8  | Linnerud | 20 | 3 (multi-output) | beginner |

### Synthetic — classification

| ID | Name | Samples | Features | Difficulty |
|----|------|---------|----------|------------|
| 9  | MakeClassification | 1,000 | 20 | intermediate |
| 10 | MakeMoons | 800 | 2 | intermediate |
| 11 | MakeCircles | 800 | 2 | intermediate |
| 12 | MakeBlobs | 900 | 8 | beginner |
| 13 | MakeHastie | 2,000 | 10 | advanced |

### Synthetic — regression

| ID | Name | Samples | Features | Difficulty |
|----|------|---------|----------|------------|
| 14 | MakeRegression | 1,000 | 15 | intermediate |
| 15 | MakeFriedman1 | 1,000 | 10 | advanced |
| 16 | MakeFriedman2 | 1,000 | 4 | advanced |
| 17 | MakeFriedman3 | 1,000 | 4 | advanced |

## Listing

```bash
# CLI — compact table
openbenchml datasets

# CLI — verbose listing with descriptions
openbenchml datasets --more

# Filter by task type or difficulty
openbenchml datasets --task-type regression
openbenchml datasets --difficulty beginner

# API
curl http://localhost:8000/api/datasets
curl 'http://localhost:8000/api/datasets?task_type=regression'
```

## Train/test split

Built-in datasets are split 80/20 with `random_state=42` for reproducibility. Classification datasets are stratified on `y` to preserve class distributions. If a class has fewer than 2 samples, the split falls back to non-stratified.

Large datasets (CaliforniaHousing, OlivettiFaces) are subsampled to a fixed cap (2,000 / 200 samples respectively) for fast benchmarks in shared environments.

## Custom datasets

Custom dataset upload (`.npz` / `.joblib` / `.pkl`) is supported by the loader. The loader expects:

- **`.npz`** — a NumPy archive with `X` and `y` arrays
- **`.joblib` / `.pkl`** — a pickled dict `{"X": ..., "y": ...}` or a tuple `(X, y)`

You can programmatically benchmark against a custom file by passing the path directly to `load_dataset`.

## What's next?

- [Benchmarks](benchmarks.md) — running an evaluation
- [Notebook](notebook.md) — explore any dataset in the browser before benchmarking
- [Concepts](../getting-started/concepts.md) — how datasets fit into the bigger picture
