# openbenchml-cli

> Command-line client for [OpenBenchML](https://github.com/kartheekbvs/openbenchml) — convert Python code → pickled model → benchmark, with Kaggle-style competitions, real-time WebSocket streams, and 17 built-in datasets.

[![npm version](https://img.shields.io/badge/npm-4.0.0-blue)](https://www.npmjs.com/package/openbenchml-cli)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Install

```bash
npm install -g openbenchml-cli
# or
yarn global add openbenchml-cli
```

Requires Node.js 18+ (uses native `fetch` and `FormData`).

## Quick start

```bash
# One-shot setup — prints install cmd, walks through register, shows a sample training script
openbenchml init

# Or do it manually:
export OPENBENCHML_HOST=https://my-openbenchml.example.com
openbenchml register --username alice --email alice@example.com --password '***'

# NEW: Convert Python code → pickled model (no local Python install needed!)
cat > train.py <<'EOF'
from sklearn.ensemble import RandomForestClassifier
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
X, y = load_iris(return_X_y=True)
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
model = RandomForestClassifier(n_estimators=50, random_state=42).fit(Xtr, ytr)
acc = model.score(Xte, yte)
print(f"acc = {acc:.4f}")
EOF

openbenchml convert --file train.py --name "RF on Iris"

# Benchmark it on any of the 17 built-in datasets
openbenchml datasets                          # pick an id
openbenchml datasets --more                   # verbose with descriptions
openbenchml benchmark --model-id 1 --dataset-id 1
openbenchml results 1

# Submit to a Kaggle-style competition
openbenchml competitions
openbenchml submit --competition iris-classification-challenge --model-id 1

# NEW: Live-stream WebSocket events to your terminal
openbenchml watch --channel leaderboard --dataset-id 1
openbenchml watch --channel benchmark --job-id 42
openbenchml watch --channel notifications

# NEW: Run Python in the platform sandbox from your terminal
openbenchml notebook --code "import numpy as np; print(np.array([1,2,3]).sum())"

# View the leaderboard
openbenchml leaderboard
```

## Commands

### Setup
| Command | Description |
|---------|-------------|
| `init` | One-shot setup: prints install cmd, walks through register, shows a sample training script. |
| `login --email <email> --password <pwd>` | Authenticate and save token locally. |
| `register --username <name> --email <email> --password <pwd>` | Create a new account. |
| `whoami` | Show the currently authenticated user. |
| `logout` | Clear locally saved credentials. |

### Models
| Command | Description |
|---------|-------------|
| `upload --model <file> --name <name> --framework <fw>` | Upload a model file from disk. |
| `convert --file <path.py> \| --code <python> --name <name>` | **New in v4.** Convert Python code → server-side pickled MLModel. No local Python needed. |
| `models [--framework <fw>]` | List public models. |
| `model <id>` | Show details for a single model. |

Supported frameworks: `scikit-learn`, `pytorch`, `onnx`, `tensorflow`, `xgboost`, `lightgbm`. The `convert` command auto-detects the framework from your `model` object's class.

### Datasets, Notebook & Benchmarks
| Command | Description |
|---------|-------------|
| `datasets [--task-type <t>] [--difficulty <d>] [--more]` | List available datasets (17 built-in). `--more` shows full descriptions. |
| `notebook --file <path.py> \| --code <python> [--timeout <sec>]` | **New in v4.** Run Python in the platform sandbox from your terminal. |
| `benchmark --model-id <id> --dataset-id <id>` | Run a benchmark. |
| `job <id>` | Check the status of a benchmark job. |
| `results <job-id>` | Show full benchmark results. |

### Real-time (new in v4)
| Command | Description |
|---------|-------------|
| `watch --channel leaderboard [--dataset-id <id>]` | Live-stream leaderboard updates. |
| `watch --channel benchmark --job-id <id>` | Live-stream progress for one benchmark job. |
| `watch --channel notifications` | Live-stream in-app notifications. |

Press `Ctrl+C` to stop streaming.

### Competitions
| Command | Description |
|---------|-------------|
| `competitions [--status live\|upcoming\|ended]` | List competitions. |
| `competition <slug>` | Show a competition's detail & leaderboard. |
| `submit --competition <slug> --model-id <id> [--note <text>]` | Submit a model. |

### Other
| Command | Description |
|---------|-------------|
| `leaderboard [--dataset-id <id>] [--sort-by score\|latency\|size]` | View the global leaderboard. |
| `notifications [--unread-only]` | List your notifications. |
| `help` / `--help` / `-h` | Full command catalogue with examples. |

## Global flags

| Flag | Env var | Description |
|------|---------|-------------|
| `--host <url>` | `OPENBENCHML_HOST` | Server URL (default: `http://localhost:8000`). |
| `--token <token>` | `OPENBENCHML_TOKEN` | Auth token (alternative to `login`). |

## Programmatic use

You can also use the API client directly:

```js
const { ApiClient } = require('openbenchml-cli');

const client = new ApiClient({ host: 'http://localhost:8000' });
await client.login('me@example.com', 'password');
await client.uploadModel({
  filePath: './rf_iris.joblib',
  name: 'My RF',
  framework: 'scikit-learn',
});
const results = await client.runBenchmark({ modelId: 1, datasetId: 1 });
console.log(results);
```

## License

MIT © OpenBenchML contributors
