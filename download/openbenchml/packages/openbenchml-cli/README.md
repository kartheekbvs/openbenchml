# openbenchml-cli

> Command-line client for [OpenBenchML](https://github.com/kartheekbvs/openbenchml) — open-source ML model benchmarking & Kaggle-style competitions.

[![npm version](https://img.shields.io/badge/npm-3.0.0-blue)](https://www.npmjs.com/package/openbenchml-cli)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Install

```bash
npm install -g openbenchml-cli
# or
yarn global add openbenchml-cli
```

Requires Node.js 16+.

## Quick start

```bash
# Point at your server (default: http://localhost:8000)
export OPENBENCHML_HOST=https://my-openbenchml.example.com

# Login (saves token to ~/.openbenchml/credentials.json)
openbenchml login --email me@example.com --password '***'

# Upload a model
openbenchml upload \
  --model ./rf_iris.joblib \
  --name "RandomForest Iris" \
  --framework scikit-learn

# List datasets and run a benchmark
openbenchml datasets
openbenchml benchmark --model-id 1 --dataset-id 1

# Submit to a competition
openbenchml competitions
openbenchml submit --competition iris-classification-challenge --model-id 1

# View the leaderboard
openbenchml leaderboard
```

## Commands

### Auth
| Command | Description |
|---------|-------------|
| `login --email <email> --password <pwd>` | Authenticate and save token locally. |
| `register --username <name> --email <email> --password <pwd>` | Create a new account. |
| `whoami` | Show the currently authenticated user. |
| `logout` | Clear locally saved credentials. |

### Models
| Command | Description |
|---------|-------------|
| `upload --model <file> --name <name> --framework <fw>` | Upload a model file. |
| `models [--framework <fw>]` | List public models. |
| `model <id>` | Show details for a single model. |

Supported frameworks: `scikit-learn`, `pytorch`, `onnx`, `tensorflow`, `xgboost`, `lightgbm`.

### Datasets & Benchmarks
| Command | Description |
|---------|-------------|
| `datasets [--task-type <t>] [--difficulty <d>]` | List available datasets. |
| `benchmark --model-id <id> --dataset-id <id>` | Run a benchmark. |
| `job <id>` | Check the status of a benchmark job. |
| `results <job-id>` | Show full benchmark results. |

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
