#!/usr/bin/env node
/**
 * OpenBenchML CLI entrypoint.
 *
 * Usage:
 *   openbenchml --help
 *   openbenchml login --email user@example.com --password ****
 *   openbenchml upload --model ./rf_iris.joblib --name "My RF" --framework scikit-learn
 *   openbenchml datasets
 *   openbenchml benchmark --model-id 1 --dataset-id 1
 *   openbenchml competitions
 *   openbenchml submit --competition iris-classification-challenge --model-id 1
 *   openbenchml leaderboard
 */

const path = require('path');
const fs = require('fs');
const PKG_DIR = path.join(__dirname, '..');
const { Command } = require(path.join(PKG_DIR, 'src', 'command'));
const pkg = require(path.join(PKG_DIR, 'package.json'));

function main(argv) {
  const args = argv.slice(2);
  if (args.length === 0 || args[0] === '--help' || args[0] === '-h') {
    printHelp();
    return 0;
  }
  if (args[0] === '--version' || args[0] === '-v') {
    console.log(`openbenchml-cli v${pkg.version}`);
    return 0;
  }

  const cmd = new Command();
  return cmd.run(args);
}

function printHelp() {
  console.log(`
OpenBenchML CLI v${pkg.version}
=============================
Open-source ML model benchmarking & Kaggle-style competitions from your terminal.

USAGE
  openbenchml <command> [options]
  obml <command> [options]              (alias)

CONFIGURATION
  --host <url>          OpenBenchML server URL (default: http://localhost:8000)
                        or set OPENBENCHML_HOST env var.
  --token <token>       Auth token (alternative to 'login').
                        or set OPENBENCHML_TOKEN env var.

COMMANDS
  login                 Authenticate and save credentials locally.
  whoami                Show the currently authenticated user.
  logout                Clear locally saved credentials.

  upload                Upload a model file (.pkl, .joblib, .pt, .onnx, etc.).
  models                List your uploaded models.
  model <id>            Show details for a single model.

  datasets              List available benchmark datasets.

  benchmark             Run a benchmark on a (model, dataset) pair.
  job <id>              Check the status of a benchmark job.
  results <job-id>      Show full benchmark results.

  leaderboard           Show the global leaderboard.
  competitions          List active competitions.
  competition <slug>    Show a competition's detail & leaderboard.
  submit                Submit a model to a competition.

  notifications         List your unread notifications.

EXAMPLES
  # Login (saves token to ~/.openbenchml/credentials)
  openbenchml login --email me@example.com --password '***'

  # Upload a scikit-learn model
  openbenchml upload --model ./rf_iris.joblib --name "My RF" --framework scikit-learn

  # List datasets
  openbenchml datasets

  # Run a benchmark
  openbenchml benchmark --model-id 1 --dataset-id 1

  # Show competition leaderboard
  openbenchml competition iris-classification-challenge

  # Submit a model to a competition
  openbenchml submit --competition iris-classification-challenge --model-id 1

DOCUMENTATION
  ${pkg.homepage}

ISSUES
  ${pkg.bugs.url}
`);
}

if (require.main === module) {
  try {
    const result = main(process.argv);
    // Some commands are async (return a Promise), others return an int.
    Promise.resolve(result)
      .then((code) => process.exit(code || 0))
      .catch((err) => {
        console.error(err);
        process.exit(1);
      });
  } catch (err) {
    console.error(err);
    process.exit(1);
  }
}

module.exports = { main };
