# CLI Reference

The `openbenchml-cli` npm package is a terminal client for the OpenBenchML server. It supports every workflow the web UI supports, plus scripting.

## Install

```bash
npm install -g openbenchml-cli
# or
npx openbenchml-cli --help
```

Requires Node.js 16+ (Node 18+ recommended for native `fetch`).

## Configuration

The CLI reads from (in priority order):

1. Command-line flags (`--host`, `--token`)
2. Environment variables (`OPENBENCHML_HOST`, `OPENBENCHML_TOKEN`)
3. Saved credentials at `~/.openbenchml/credentials.json` (written by `login` / `register`)

## Commands at a glance

| Command | Description |
|---------|-------------|
| `login` | Authenticate and save credentials |
| `register` | Create a new account |
| `whoami` | Show current user |
| `logout` | Clear saved credentials |
| `upload` | Upload a model file |
| `models` | List public models |
| `model <id>` | Show model details |
| `datasets` | List datasets |
| `benchmark` | Run a benchmark |
| `job <id>` | Show job status |
| `results <job-id>` | Show benchmark results |
| `leaderboard` | Show global leaderboard |
| `competitions` | List competitions |
| `competition <slug>` | Show competition detail & leaderboard |
| `submit` | Submit a model to a competition |
| `notifications` | List your notifications |

## Programmatic use

The CLI also exports an `ApiClient` class for use in your own Node.js scripts:

```js
const { ApiClient } = require('openbenchml-cli');

const client = new ApiClient({ host: 'http://localhost:8000' });
await client.login('me@example.com', 'password');
await client.uploadModel({
  filePath: './rf.joblib',
  name: 'My RF',
  framework: 'scikit-learn',
});
const results = await client.runBenchmark({ modelId: 1, datasetId: 1 });
console.log(results);
```

See the [Commands page](commands.md) for full command-by-command documentation.
