# CLI Commands

Full reference for every `openbenchml` command (v4.0.0).

## Global flags

Available on every command:

| Flag | Env var | Default | Description |
|------|---------|---------|-------------|
| `--host <url>` | `OPENBENCHML_HOST` | `http://localhost:8000` | Server URL |
| `--token <token>` | `OPENBENCHML_TOKEN` | (none) | Auth token (alternative to `login`) |

---

## `init`

One-shot setup: prints `npm install -g openbenchml-cli`, walks through register/login, and shows a minimum-viable Python training example.

```bash
openbenchml init
# Or with everything pre-filled:
openbenchml init --username alice --email alice@example.com --password '***'
```

| Flag | Required | Description |
|------|----------|-------------|
| `--username` | no | If set with `--email` and `--password`, runs `register` in step 3 |
| `--email`    | no | Same as above |
| `--password` | no | Same as above |

---

## `login`

Authenticate and save credentials to `~/.openbenchml/credentials.json`.

```bash
openbenchml login --email me@example.com --password '***'
```

| Flag | Required | Description |
|------|----------|-------------|
| `--email` | yes | Account email |
| `--password` | yes | Account password |

---

## `register`

Create a new account and save credentials.

```bash
openbenchml register --username alice --email alice@example.com --password '***'
```

| Flag | Required | Description |
|------|----------|-------------|
| `--username` | yes | Unique username |
| `--email` | yes | Email address |
| `--password` | yes | Password (min 6 chars) |

---

## `whoami`

Show the currently authenticated user.

```bash
openbenchml whoami
```

---

## `logout`

Clear locally saved credentials.

```bash
openbenchml logout
```

---

## `upload`

Upload a model file from disk.

```bash
openbenchml upload \
  --model ./rf_iris.joblib \
  --name "RandomForest Iris" \
  --framework scikit-learn \
  --description "50-tree RF, default hyperparams"
```

| Flag | Required | Description |
|------|----------|-------------|
| `--model` | yes | Path to the model file |
| `--name` | yes | Display name |
| `--framework` | yes | One of: `scikit-learn`, `pytorch`, `onnx`, `tensorflow`, `xgboost`, `lightgbm` |
| `--description` | no | Optional description |

---

## `convert`

**New in v4.0.** Convert Python code into a server-side MLModel — no local Python install needed. The code must train a model and assign it to a variable named `model`.

```bash
# From a file:
openbenchml convert --file train.py --name "My RF on Iris"

# Inline:
openbenchml convert --code "$(cat train.py)" --name "My RF on Iris" --description "50 trees"

# Override auto-detected framework:
openbenchml convert --file train.py --name "My XGB" --framework xgboost
```

| Flag | Required | Description |
|------|----------|-------------|
| `--file` | one of `--file` / `--code` | Path to a `.py` file |
| `--code` | one of `--file` / `--code` | Inline Python source |
| `--name` | yes | Display name for the new MLModel |
| `--description` | no | Optional description |
| `--framework` | no | Override auto-detection |

---

## `models`

List public models.

```bash
openbenchml models
openbenchml models --framework onnx
```

| Flag | Required | Description |
|------|----------|-------------|
| `--framework` | no | Filter by framework |

---

## `model <id>`

Show details for a single model.

```bash
openbenchml model 42
```

---

## `datasets`

List available benchmark datasets (17 built-in).

```bash
openbenchml datasets
openbenchml datasets --more                       # verbose with descriptions
openbenchml datasets --task-type regression
openbenchml datasets --difficulty beginner
```

| Flag | Required | Description |
|------|----------|-------------|
| `--task-type` | no | Filter by task type (`classification` / `regression` / `clustering`) |
| `--difficulty` | no | Filter by difficulty (`beginner` / `intermediate` / `advanced`) |
| `--more` | no | Verbose listing with full descriptions |

---

## `notebook`

**New in v4.0.** Run Python code in the platform sandbox from the terminal.

```bash
# Inline code:
openbenchml notebook --code "print('hello')"

# From a file:
openbenchml notebook --file my_script.py

# With a longer timeout (max 120s):
openbenchml notebook --file heavy_script.py --timeout 120
```

| Flag | Required | Description |
|------|----------|-------------|
| `--file` | one of `--file` / `--code` | Path to a `.py` file |
| `--code` | one of `--file` / `--code` | Inline Python source |
| `--timeout` | no | Wall-clock limit in seconds (default 30, max 120) |

---

## `benchmark`

Run a benchmark on a (model, dataset) pair.

```bash
openbenchml benchmark --model-id 1 --dataset-id 1
```

| Flag | Required | Description |
|------|----------|-------------|
| `--model-id` | yes | Model ID |
| `--dataset-id` | yes | Dataset ID |

---

## `job <id>`

Show the status of a benchmark job.

```bash
openbenchml job 1
```

---

## `results <job-id>`

Show full benchmark results for a completed job.

```bash
openbenchml results 1
```

---

## `leaderboard`

Show the global leaderboard.

```bash
openbenchml leaderboard
openbenchml leaderboard --dataset-id 1
openbenchml leaderboard --sort-by latency
openbenchml leaderboard --sort-by size
openbenchml leaderboard --limit 10
```

| Flag | Required | Description |
|------|----------|-------------|
| `--dataset-id` | no | Filter to a single dataset |
| `--sort-by` | no | `score` (default) / `latency` / `size` |
| `--limit` | no | Max rows (default 50, max 200) |

---

## `watch`

**New in v4.0.** Live-stream WebSocket events to stdout.

```bash
# Leaderboard updates for a specific dataset:
openbenchml watch --channel leaderboard --dataset-id 1

# Benchmark progress for a specific job:
openbenchml watch --channel benchmark --job-id 42

# In-app notifications:
openbenchml watch --channel notifications
```

| Flag | Required | Description |
|------|----------|-------------|
| `--channel` | yes | `leaderboard` / `benchmark` / `notifications` |
| `--dataset-id` | only for `--channel leaderboard` | Filter to a single dataset |
| `--job-id` | only for `--channel benchmark` | Filter to a single job |

Press `Ctrl+C` to stop streaming.

---

## `competitions`

List competitions.

```bash
openbenchml competitions
openbenchml competitions --status live
```

| Flag | Required | Description |
|------|----------|-------------|
| `--status` | no | Filter by status (`upcoming` / `live` / `ended`) |

---

## `competition <slug>`

Show a competition's detail and leaderboard.

```bash
openbenchml competition iris-classification-challenge
```

---

## `submit`

Submit a model to a competition. Auto-runs a benchmark and updates the leaderboard.

```bash
openbenchml submit \
  --competition iris-classification-challenge \
  --model-id 1 \
  --note "First attempt"
```

| Flag | Required | Description |
|------|----------|-------------|
| `--competition` | yes | Competition slug |
| `--model-id` | yes | ID of one of your uploaded models |
| `--note` | no | Optional submission note |

---

## `notifications`

List your notifications (most recent first).

```bash
openbenchml notifications
openbenchml notifications --unread-only
```

| Flag | Required | Description |
|------|----------|-------------|
| `--unread-only` | no | Only show unread notifications |

---

## `help`

Print the full command catalogue with examples.

```bash
openbenchml help
openbenchml --help
openbenchml -h
```
