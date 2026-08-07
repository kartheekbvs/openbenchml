/**
 * Command dispatcher & pretty-printers.
 */

const { ApiClient } = require('./client');

const FORMATS = {
  // Numeric formats for display
  pct: (v) => v == null ? '-' : (v * 100).toFixed(2) + '%',
  float4: (v) => v == null ? '-' : v.toFixed(4),
  float2: (v) => v == null ? '-' : v.toFixed(2),
  ms: (v) => v == null ? '-' : v.toFixed(3) + ' ms',
  size: (kb) => {
    if (kb == null) return '-';
    if (kb < 1024) return kb.toFixed(1) + ' KB';
    return (kb / 1024).toFixed(2) + ' MB';
  },
  date: (iso) => {
    if (!iso) return '-';
    const d = new Date(iso);
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  },
};

// Indent every line of a multi-line string — used for nested output.
function indent(str, prefix) {
  return String(str).split('\n').map(l => prefix + l).join('\n');
}

function parseFlags(args) {
  const flags = {};
  const positional = [];
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a.startsWith('--')) {
      const key = a.slice(2);
      const next = args[i + 1];
      if (next !== undefined && !next.startsWith('--')) {
        flags[key] = next; i++;
      } else {
        flags[key] = true;
      }
    } else {
      positional.push(a);
    }
  }
  return { flags, positional };
}

class Command {
  constructor() {
    this.client = new ApiClient();
  }

  run(args) {
    const cmd = args[0];
    const rest = args.slice(1);
    const { flags, positional } = parseFlags(rest);

    // Allow --host / --token overrides on any command.
    if (flags.host) this.client.host = flags.host.replace(/\/$/, '');
    if (flags.token) this.client.token = flags.token;

    switch (cmd) {
      case 'login': return this.login(flags);
      case 'register': return this.register(flags);
      case 'whoami': return this.whoami();
      case 'logout': return this.logout();
      case 'init': return this.init(flags);

      case 'upload': return this.upload(flags);
      case 'convert': return this.convert(flags);
      case 'models': return this.models(flags);
      case 'model': return this.model(positional[0]);

      case 'datasets': return this.datasets(flags);
      case 'notebook': return this.notebook(flags);

      case 'benchmark': return this.benchmark(flags);
      case 'job': return this.job(positional[0]);
      case 'results': return this.results(positional[0]);

      case 'leaderboard': return this.leaderboard(flags);
      case 'watch': return this.watch(flags);

      case 'competitions': return this.competitions(flags);
      case 'competition': return this.competition(positional[0]);
      case 'submit': return this.submit(flags);

      case 'notifications': return this.notifications(flags);

      case 'help': case '--help': case '-h': return this.help();

      default:
        console.error(`Unknown command: ${cmd}`);
        console.error('Run "openbenchml help" for usage.');
        return 1;
    }
  }

  help() {
    console.log(`openbenchml v4.0.0 — Command-line client for OpenBenchML

USAGE
  openbenchml <command> [--flags]

SETUP
  init        One-shot setup: prints npm install cmd + interactive register
  login       Login with email + password
  register    Create a new account
  whoami      Show current user
  logout      Clear saved credentials

MODELS
  upload      Upload a .pkl/.joblib/.onnx/.pt model file
  convert     Convert Python code → pickled model (no Python install needed)
  models      List public models
  model       Show details for one model

DATASETS & NOTEBOOK
  datasets    List built-in datasets (--more for full descriptions)
  notebook    Run a Python snippet in the sandbox (--file or --code)

BENCHMARKS
  benchmark   Run a benchmark on (model, dataset)
  job         Show one job's status
  results     Show full results for a job

LEADERBOARD & REAL-TIME
  leaderboard Show ranked entries
  watch       Live-stream WebSocket events (channel=leaderboard|benchmark|notifications)

COMPETITIONS
  competitions List all competitions
  competition  Show one competition + its leaderboard
  submit       Submit a model to a competition

NOTIFICATIONS
  notifications List in-app notifications (--unread-only)

GLOBAL FLAGS
  --host <url>     Override OPENBENCHML_HOST (default http://localhost:8000)
  --token <tok>    Override saved auth token

EXAMPLES
  openbenchml init
  openbenchml convert --file train.py --name "RF on Iris"
  openbenchml notebook --code "print('hello')"
  openbenchml watch --channel leaderboard --dataset-id 1
`);
    return 0;
  }

  // ─── init: npm install + register in one shot ─────────────────────────────

  async init(flags) {
    console.log('╔════════════════════════════════════════════════════════════╗');
    console.log('║  OpenBenchML — one-shot setup                              ║');
    console.log('╚════════════════════════════════════════════════════════════╝');
    console.log();
    console.log('Step 1 — install the CLI globally:');
    console.log('  npm install -g openbenchml-cli');
    console.log();
    console.log('  (Already installed? Skip to step 2.)');
    console.log();
    console.log('Step 2 — point the CLI at a server (default http://localhost:8000):');
    if (!flags.host) {
      console.log('  export OPENBENCHML_HOST=https://your-server.example.com');
      console.log('  — or pass --host on every command');
    } else {
      console.log(`  using host: ${flags.host}`);
    }
    console.log();
    console.log('Step 3 — register an account:');
    if (flags.username && flags.email && flags.password) {
      return this.register(flags);
    }
    console.log('  openbenchml register --username <name> --email <email> --password <pwd>');
    console.log();
    console.log('Step 4 — verify with whoami:');
    console.log('  openbenchml whoami');
    console.log();
    console.log('Step 5 — your first benchmark, the easy way:');
    console.log('  openbenchml convert --file train.py --name "My First Model"');
    console.log('  openbenchml datasets            # pick a dataset id');
    console.log('  openbenchml benchmark --model-id <id> --dataset-id <id>');
    console.log('  openbenchml results <job-id>');
    console.log();
    console.log('Need the Python training file? Visit /notebook in the web UI for');
    console.log('a ready-to-use template, or copy this minimum viable example:');
    console.log();
    console.log('  from sklearn.ensemble import RandomForestClassifier');
    console.log('  from sklearn.datasets import load_iris');
    console.log('  from sklearn.model_selection import train_test_split');
    console.log('  X, y = load_iris(return_X_y=True)');
    console.log('  Xtr, Xte, ytr, yte = train_test_split(X, y, random_state=42)');
    console.log('  model = RandomForestClassifier(random_state=42).fit(Xtr, ytr)');
    console.log();
    return 0;
  }

  // ─── convert: code → pickled model ────────────────────────────────────────

  async convert(flags) {
    if (!flags.name) {
      console.error('Usage: openbenchml convert --file <path.py> --name <model-name> [--description <text>] [--framework <fw>]');
      console.error('   or: openbenchml convert --code <inline-python> --name <model-name>');
      return 1;
    }
    let code;
    if (flags.file) {
      try { code = require('fs').readFileSync(flags.file, 'utf8'); }
      catch (e) { console.error(`✗ Could not read ${flags.file}: ${e.message}`); return 1; }
    } else if (flags.code) {
      code = flags.code;
    } else {
      console.error('Provide either --file <path.py> or --code <inline-python>');
      return 1;
    }
    try {
      const r = await this.client.convertCode({
        code,
        modelName: flags.name,
        description: flags.description || '',
        framework: flags.framework || 'scikit-learn',
      });
      console.log(`✓ Converted code → model`);
      console.log(`  id:         ${r.id}`);
      console.log(`  name:       ${r.model_name}`);
      console.log(`  framework:  ${r.framework} (detected: ${r.detected_framework}, class: ${r.model_class})`);
      console.log(`  size:       ${FORMATS.size(r.size_kb)}`);
      if (r.stdout) console.log(`  stdout:`), console.log(indent(r.stdout, '    '));
      const m = r.metrics_in_code || {};
      const metricKeys = Object.keys(m);
      if (metricKeys.length) {
        console.log('  metrics from code:');
        for (const k of metricKeys) console.log(`    ${k} = ${m[k]}`);
      }
      console.log();
      console.log('  Next:');
      console.log(`    openbenchml datasets`);
      console.log(`    openbenchml benchmark --model-id ${r.id} --dataset-id <id>`);
    } catch (e) {
      console.error(`✗ Convert failed: ${e.message}`);
      if (e.data && e.data.detail) console.error(`  detail: ${e.data.detail}`);
      return 1;
    }
  }

  // ─── notebook: run Python in the sandbox ──────────────────────────────────

  async notebook(flags) {
    let code;
    if (flags.file) {
      try { code = require('fs').readFileSync(flags.file, 'utf8'); }
      catch (e) { console.error(`✗ Could not read ${flags.file}: ${e.message}`); return 1; }
    } else if (flags.code) {
      code = flags.code;
    } else {
      console.error('Usage: openbenchml notebook --code <python> [--timeout <sec>]');
      console.error('   or: openbenchml notebook --file <path.py>');
      return 1;
    }
    try {
      const r = await this.client.runCode({
        code,
        timeoutSeconds: parseInt(flags.timeout || '30', 10),
      });
      if (r.stdout) process.stdout.write(r.stdout);
      if (r.stderr) process.stderr.write(r.stderr);
      if (!r.ok) {
        console.error(`\n✗ Execution ${r.timed_out ? 'timed out' : 'failed'}: ${r.error || ''}`);
        return 1;
      }
    } catch (e) {
      console.error(`✗ ${e.message}`);
      return 1;
    }
  }

  // ─── watch: stream real-time WebSocket events ─────────────────────────────

  async watch(flags) {
    const channel = flags.channel || 'leaderboard';
    let ws;
    try {
      if (channel === 'leaderboard') {
        ws = this.client.streamLeaderboard(
          { datasetId: flags['dataset-id'] ? parseInt(flags['dataset-id'], 10) : undefined },
          (msg) => this._printWatchEvent(msg),
        );
      } else if (channel === 'benchmark') {
        if (!flags['job-id']) {
          console.error('Usage: openbenchml watch --channel benchmark --job-id <id>');
          return 1;
        }
        ws = this.client.streamBenchmark(
          { jobId: parseInt(flags['job-id'], 10) },
          (msg) => this._printWatchEvent(msg),
        );
      } else if (channel === 'notifications') {
        ws = this.client.streamNotifications((msg) => this._printWatchEvent(msg));
      } else {
        console.error(`Unknown channel '${channel}'. Use leaderboard | benchmark | notifications`);
        return 1;
      }
    } catch (e) {
      console.error(`✗ ${e.message}`);
      return 1;
    }
    console.log(`# streaming ${channel} from ${this.client.host} — Ctrl+C to stop`);
    process.on('SIGINT', () => { try { ws.close(); } catch (_) {} process.exit(0); });
  }

  _printWatchEvent(msg) {
    const ts = new Date().toLocaleTimeString([], { hour12: false });
    console.log(`[${ts}] ${msg.type || 'event'}  ${JSON.stringify(msg).slice(0, 200)}`);
  }

  // ─── Auth ──────────────────────────────────────────────────────────────────

  async login(flags) {
    if (!flags.email || !flags.password) {
      console.error('Usage: openbenchml login --email <email> --password <password>');
      return 1;
    }
    try {
      const r = await this.client.login(flags.email, flags.password);
      console.log(`✓ Logged in as ${r.user.username} (${r.user.email})`);
      console.log(`  Token saved to ~/.openbenchml/credentials.json`);
    } catch (e) {
      console.error(`✗ Login failed: ${e.message}`);
      return 1;
    }
  }

  async register(flags) {
    if (!flags.username || !flags.email || !flags.password) {
      console.error('Usage: openbenchml register --username <name> --email <email> --password <pwd>');
      return 1;
    }
    try {
      const r = await this.client.register(flags);
      console.log(`✓ Registered and logged in as ${r.user.username}`);
    } catch (e) {
      console.error(`✗ Registration failed: ${e.message}`);
      return 1;
    }
  }

  async whoami() {
    if (!this.client.token) {
      console.error('Not logged in. Run "openbenchml login" first.');
      return 1;
    }
    try {
      const u = await this.client.whoami();
      console.log(`User:   ${u.username}`);
      console.log(`ID:     ${u.id}`);
      if (u.organization) console.log(`Org:    ${u.organization}`);
      console.log(`Joined: ${FORMATS.date(u.created_at)}`);
    } catch (e) {
      console.error(`✗ ${e.message}`);
      return 1;
    }
  }

  logout() {
    this.client.clearSavedToken();
    console.log('✓ Logged out. Credentials removed.');
  }

  // ─── Models ────────────────────────────────────────────────────────────────

  async upload(flags) {
    if (!flags.model || !flags.name || !flags.framework) {
      console.error('Usage: openbenchml upload --model <file> --name <name> --framework <fw>');
      console.error('Frameworks: scikit-learn, pytorch, onnx, tensorflow, xgboost, lightgbm');
      return 1;
    }
    try {
      const r = await this.client.uploadModel({
        filePath: flags.model,
        name: flags.name,
        description: flags.description || '',
        framework: flags.framework,
      });
      console.log(`✓ Uploaded: ${r.model_name} (id=${r.id}, framework=${r.framework}, size=${FORMATS.size(r.size_kb)})`);
    } catch (e) {
      console.error(`✗ Upload failed: ${e.message}`);
      return 1;
    }
  }

  async models(flags) {
    try {
      const list = await this.client.listModels({ framework: flags.framework });
      if (!list.length) { console.log('No models found.'); return 0; }
      console.log('ID   Framework      Size         Name');
      console.log('---  -------------  -----------  ----------------');
      for (const m of list) {
        console.log(
          `${String(m.id).padEnd(4)} ${m.framework.padEnd(13)}  ${FORMATS.size(m.size_kb).padEnd(11)}  ${m.model_name}`
        );
      }
    } catch (e) {
      console.error(`✗ ${e.message}`); return 1;
    }
  }

  async model(id) {
    if (!id) { console.error('Usage: openbenchml model <id>'); return 1; }
    try {
      const m = await this.client.getModel(parseInt(id, 10));
      console.log(`ID:          ${m.id}`);
      console.log(`Name:        ${m.model_name}`);
      console.log(`Framework:   ${m.framework}`);
      console.log(`Size:        ${FORMATS.size(m.size_kb)}`);
      console.log(`Version:     ${m.version}`);
      console.log(`Owner:       ${m.owner}`);
      console.log(`Created:     ${FORMATS.date(m.created_at)}`);
      console.log(`Benchmark summary:`, m.benchmark_summary || {});
    } catch (e) {
      console.error(`✗ ${e.message}`); return 1;
    }
  }

  // ─── Datasets ──────────────────────────────────────────────────────────────

  async datasets(flags) {
    try {
      const list = await this.client.listDatasets({
        taskType: flags['task-type'],
        difficulty: flags.difficulty,
      });
      if (flags.more) {
        // Verbose listing with descriptions — useful when picking a dataset
        console.log(`${list.length} datasets available\n`);
        for (const d of list) {
          console.log(`── #${d.id}  ${d.name}  (${d.task_type}, ${d.difficulty}) ──`);
          console.log(`  samples: ${d.samples}, features: ${d.features}`);
          if (d.description) console.log(`  ${d.description.slice(0, 240)}${d.description.length > 240 ? '…' : ''}`);
          console.log();
        }
      } else {
        console.log('ID  Name                  Task            Samples   Features  Difficulty');
        console.log('--  --------------------  --------------  --------  --------  -----------');
        for (const d of list) {
          console.log(
            `${String(d.id).padEnd(3)} ${d.name.padEnd(20)}  ${d.task_type.padEnd(14)}  ${String(d.samples).padEnd(8)}  ${String(d.features).padEnd(8)}  ${d.difficulty}`
          );
        }
        console.log('\nTip: pass --more for full descriptions.');
      }
    } catch (e) {
      console.error(`✗ ${e.message}`); return 1;
    }
  }

  // ─── Benchmarks ────────────────────────────────────────────────────────────

  async benchmark(flags) {
    if (!flags['model-id'] || !flags['dataset-id']) {
      console.error('Usage: openbenchml benchmark --model-id <id> --dataset-id <id>');
      return 1;
    }
    try {
      const r = await this.client.runBenchmark({
        modelId: parseInt(flags['model-id'], 10),
        datasetId: parseInt(flags['dataset-id'], 10),
      });
      console.log(`✓ Benchmark submitted (job_id=${r.job_id})`);
      console.log(`  Fetching results...`);
      const results = await this.client.getResults(r.job_id);
      this._printResults(results);
    } catch (e) {
      console.error(`✗ ${e.message}`); return 1;
    }
  }

  async job(id) {
    if (!id) { console.error('Usage: openbenchml job <id>'); return 1; }
    try {
      const j = await this.client.getJob(parseInt(id, 10));
      if (!j) { console.error('Job not found'); return 1; }
      console.log(`Job ID:        ${j.id}`);
      console.log(`Status:        ${j.status}`);
      console.log(`Progress:      ${j.progress}%`);
      console.log(`Model:         ${j.model_name}`);
      console.log(`Dataset:       ${j.dataset_name}`);
      console.log(`Submitted:     ${FORMATS.date(j.submitted_at)}`);
      console.log(`Finished:      ${FORMATS.date(j.finished_at)}`);
      if (j.error_message) console.log(`Error:         ${j.error_message}`);
    } catch (e) {
      console.error(`✗ ${e.message}`); return 1;
    }
  }

  async results(jobId) {
    if (!jobId) { console.error('Usage: openbenchml results <job-id>'); return 1; }
    try {
      const r = await this.client.getResults(parseInt(jobId, 10));
      this._printResults(r);
    } catch (e) {
      console.error(`✗ ${e.message}`); return 1;
    }
  }

  _printResults(r) {
    console.log('');
    console.log(`Job ${r.job_id} — ${r.status.toUpperCase()}`);
    console.log(`Model: ${r.model_name}   Dataset: ${r.dataset_name}`);
    console.log(`Finished: ${FORMATS.date(r.finished_at)}`);
    if (r.error_message) {
      console.log(`Error: ${r.error_message}`);
      return;
    }
    if (!r.metrics) { console.log('No metrics available.'); return; }
    const m = r.metrics;
    console.log('');
    console.log('── ML Metrics ──────────────────────────────');
    if (m.accuracy != null) console.log(`  Accuracy:        ${FORMATS.pct(m.accuracy)}`);
    if (m.precision != null) console.log(`  Precision:       ${FORMATS.float4(m.precision)}`);
    if (m.recall != null) console.log(`  Recall:          ${FORMATS.float4(m.recall)}`);
    if (m.f1_score != null) console.log(`  F1 Score:        ${FORMATS.float4(m.f1_score)}`);
    if (m.auc_roc != null) console.log(`  AUC-ROC:         ${FORMATS.float4(m.auc_roc)}`);
    if (m.log_loss != null) console.log(`  Log Loss:        ${FORMATS.float4(m.log_loss)}`);
    if (m.mae != null) console.log(`  MAE:             ${FORMATS.float4(m.mae)}`);
    if (m.rmse != null) console.log(`  RMSE:            ${FORMATS.float4(m.rmse)}`);
    if (m.r2_score != null) console.log(`  R² Score:        ${FORMATS.float4(m.r2_score)}`);

    console.log('');
    console.log('── Performance (real per-sample percentiles) ──');
    console.log(`  Latency mean:    ${FORMATS.ms(m.latency_ms)}`);
    console.log(`  Latency p50:     ${FORMATS.ms(m.latency_p50_ms)}`);
    console.log(`  Latency p95:     ${FORMATS.ms(m.latency_p95_ms)}`);
    console.log(`  Latency p99:     ${FORMATS.ms(m.latency_p99_ms)}`);
    console.log(`  Throughput:      ${m.throughput_per_sec != null ? m.throughput_per_sec.toFixed(1) + ' /s' : '-'}`);
    console.log(`  Memory:          ${FORMATS.float2(m.memory_mb)} MB`);
    console.log(`  Model size:      ${FORMATS.size(m.model_size_kb)}`);
    console.log(`  Inferences:      ${m.inference_count}`);
  }

  // ─── Leaderboard ───────────────────────────────────────────────────────────

  async leaderboard(flags) {
    try {
      const rows = await this.client.getLeaderboard({
        datasetId: flags['dataset-id'] ? parseInt(flags['dataset-id'], 10) : undefined,
        sortBy: flags['sort-by'],
        limit: flags.limit ? parseInt(flags.limit, 10) : 50,
      });
      if (!rows.length) { console.log('Leaderboard is empty.'); return 0; }
      console.log('Rank  Score      Latency      Size         Owner          Model');
      console.log('----  ---------  -----------  -----------  -------------  ----------------');
      for (const r of rows) {
        console.log(
          `${String(r.rank).padEnd(5)} ${(r.score != null ? r.score.toFixed(4) : '-').padEnd(9)}  ` +
          `${FORMATS.ms(r.latency_ms).padEnd(11)}  ${FORMATS.size(r.model_size_kb).padEnd(11)}  ` +
          `${(r.owner || '-').padEnd(13)}  ${r.model_name}`
        );
      }
    } catch (e) {
      console.error(`✗ ${e.message}`); return 1;
    }
  }

  // ─── Competitions ──────────────────────────────────────────────────────────

  async competitions(flags) {
    try {
      const list = await this.client.listCompetitions({ status: flags.status });
      if (!list.length) { console.log('No competitions found.'); return 0; }
      console.log('Status    Metric       Title');
      console.log('--------  -----------  ----------------------------------------');
      for (const c of list) {
        console.log(`${c.status.padEnd(8)}  ${c.evaluation_metric.padEnd(11)}  ${c.title}`);
      }
    } catch (e) {
      console.error(`✗ ${e.message}`); return 1;
    }
  }

  async competition(slug) {
    if (!slug) { console.error('Usage: openbenchml competition <slug>'); return 1; }
    try {
      const c = await this.client.getCompetition(slug);
      console.log(`Title:    ${c.title}`);
      console.log(`Status:   ${c.status}`);
      console.log(`Metric:   ${c.evaluation_metric}`);
      console.log(`Task:     ${c.task_type}`);
      console.log(`Starts:   ${FORMATS.date(c.starts_at)}`);
      console.log(`Ends:     ${FORMATS.date(c.ends_at)}`);
      console.log(`Submissions: ${c.total_submissions}  Participants: ${c.unique_participants}`);
      if (c.prize) console.log(`Prize:    ${c.prize}`);
      console.log('');
      if (!c.leaderboard.length) {
        console.log('Leaderboard is empty — be the first to submit!');
        return 0;
      }
      console.log('── Leaderboard ──────────────────────────────');
      console.log('Rank  Score      User            Model');
      console.log('----  ---------  --------------  ----------------');
      for (const r of c.leaderboard) {
        console.log(
          `${String(r.rank).padEnd(5)} ${(r.score != null ? r.score.toFixed(4) : '-').padEnd(9)}  ` +
          `${(r.username || '-').padEnd(13)}  ${r.model_name}`
        );
      }
    } catch (e) {
      console.error(`✗ ${e.message}`); return 1;
    }
  }

  async submit(flags) {
    if (!flags.competition || !flags['model-id']) {
      console.error('Usage: openbenchml submit --competition <slug> --model-id <id>');
      return 1;
    }
    try {
      const r = await this.client.submitToCompetition(flags.competition, {
        modelId: parseInt(flags['model-id'], 10),
        note: flags.note || '',
      });
      console.log(`✓ Submitted model ${flags['model-id']} to ${flags.competition}`);
      console.log('  The model has been auto-benchmarked and added to the leaderboard.');

      // Fetch updated leaderboard
      const c = await this.client.getCompetition(flags.competition);
      console.log('');
      console.log(`Total submissions: ${c.total_submissions}  Participants: ${c.unique_participants}`);
      if (c.leaderboard.length) {
        console.log('');
        console.log('── Current Leaderboard ──────────────────────');
        for (const r of c.leaderboard) {
          console.log(`  #${r.rank}  ${r.username}  ${r.model_name}  score=${r.score != null ? r.score.toFixed(4) : '-'}`);
        }
      }
    } catch (e) {
      console.error(`✗ ${e.message}`); return 1;
    }
  }

  // ─── Notifications ─────────────────────────────────────────────────────────

  async notifications(flags) {
    try {
      const list = await this.client.listNotifications({ unreadOnly: flags['unread-only'] || flags.unread });
      if (!list.length) { console.log('No notifications.'); return 0; }
      for (const n of list) {
        const marker = n.is_read ? '  ' : '● ';
        console.log(`${marker}${FORMATS.date(n.created_at)}  ${n.title}`);
        if (n.body) console.log(`    ${n.body}`);
        if (n.link) console.log(`    → ${n.link}`);
      }
    } catch (e) {
      console.error(`✗ ${e.message}`); return 1;
    }
  }
}

module.exports = { Command, FORMATS, indent };
