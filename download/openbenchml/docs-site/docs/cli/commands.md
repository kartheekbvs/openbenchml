# CLI Commands

Full reference for every `openbenchml` command.

## Global flags

Available on every command:

| Flag | Env var | Default | Description |
|------|---------|---------|-------------|
| `--host <url>` | `OPENBENCHML_HOST` | `http://localhost:8000` | Server URL |
| `--token <token>` | `OPENBENCHML_TOKEN` | (none) | Auth token (alternative to `login`) |

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

Upload a model file.

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

List available benchmark datasets.

```bash
openbenchml datasets
openbenchml datasets --task-type regression
openbenchml datasets --difficulty beginner
```

| Flag | Required | Description |
|------|----------|-------------|
| `--task-type` | no | Filter by task type (`classification` / `regression` / `clustering`) |
| `--difficulty` | no | Filter by difficulty (`beginner` / `intermediate` / `advanced`) |

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
