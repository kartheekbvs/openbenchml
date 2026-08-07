# Notebook

The in-browser **Python Notebook** at `/notebook` is a single-cell playground
for quick experimentation. It's intentionally simpler than Jupyter — perfect
for trying a dataset, prototyping features, or just learning `sklearn`
without installing anything.

## What it is

A textarea where you type Python, a **Run** button, and an output pane.
Behind the scenes your code is sent to `POST /api/notebook/run`, executed in
the same sandbox as `/convert`, and the captured `stdout` / `stderr` is
returned to the browser.

## What's pre-imported

Same as `/convert` — `np`, `pd`, `sklearn`, `scipy`, `joblib`, plus all the
`sklearn_*` shortcuts. See [Convert → Pre-imported libraries](./convert.md#pre-imported-libraries).

## Built-in presets

The notebook ships with **6 one-click presets** so you can see what's
possible without typing anything:

| Preset                    | What it does                                          |
| ------------------------- | ----------------------------------------------------- |
| Iris: explore the dataset | Load Iris, print shapes & classes                     |
| Train a RandomForest      | Train + score on Iris test split                      |
| Confusion matrix          | Visualize BreastCancer classifier errors              |
| Diabetes regression       | Compare LinearRegression vs Ridge                     |
| 5-fold cross-validation   | Compare 3 classifiers on Wine                         |
| Survey all datasets       | Print shapes of every built-in                        |

## Timeout

The notebook has a configurable timeout (10s / 30s / 60s / 120s). The default
is **30 seconds** — plenty for any of the built-in datasets. If your code
exceeds the limit you'll see a `TimeoutError` in the output pane.

## Limitations vs. Jupyter

The notebook is intentionally **single-cell**:

- ❌ No persistent kernel — each Run is a fresh namespace.
- ❌ No `IPython.display` rich outputs (HTML, plots, tables). Print text only.
- ❌ No `%magic` commands.
- ❌ No variable inspector.

If you need a real Jupyter, install one locally. The notebook is for *quick*
experiments, not for building pipelines.

## CLI equivalent

```bash
# Run a Python file:
openbenchml notebook --file my_script.py

# Run inline code:
openbenchml notebook --code "print('hello from CLI')"

# With a longer timeout:
openbenchml notebook --file heavy_script.py --timeout 120
```

## Security

Same sandbox as `/convert`. See
[Convert → Security](./convert.md#security) for the full list of blocked
modules and builtins.
