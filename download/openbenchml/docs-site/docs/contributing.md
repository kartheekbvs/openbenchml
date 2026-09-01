# Contributing

OpenBenchML is open source under the MIT License. Contributions are welcome — bug reports, feature requests, documentation improvements, and code PRs.

## Ways to contribute

- **Bug reports** — open an issue with reproduction steps
- **Feature requests** — open an issue with the `enhancement` label
- **Documentation** — edit files in `docs-site/docs/` and submit a PR
- **Code** — pick an issue labeled `good-first-issue` or `help-wanted`

## Development setup

```bash
git clone https://github.com/kartheekbvs/openbenchml.git
cd openbenchml

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pytest pytest-asyncio black flake8

# Run the server in dev mode
python run.py

# In another terminal, run the smoke tests
.venv/bin/python scripts/smoke_test_core.py
```

## Code style

- Python: Black formatting (line length 100), Flake8 for linting
- JavaScript (CLI): 2-space indent, single quotes, no semicolons (Node 18+ features OK)
- Markdown (docs): Standard CommonMark + mkdocs-Material extensions

Run the formatters:

```bash
black app/ scripts/
flake8 app/ --max-line-length=100
```

## Project structure

```text
openbenchml/
├── app/
│   ├── main.py                  ← FastAPI app + WebSocket endpoints
│   ├── config.py                ← All settings (env vars + defaults)
│   ├── database/
│   │   ├── db.py                ← Engine, SessionLocal, Base
│   │   ├── models.py            ← 14 SQLAlchemy models
│   │   └── seed.py              ← Default datasets + competitions
│   ├── routes/
│   │   ├── auth.py              ← /api/auth/*
│   │   ├── models.py            ← /api/models, /models/upload
│   │   ├── datasets.py          ← /api/datasets
│   │   ├── benchmark.py         ← /benchmark, /api/jobs, /api/results
│   │   ├── leaderboard.py       ← /api/leaderboard
│   │   ├── competitions.py      ← /api/competitions, /competitions/*
│   │   └── comments.py          ← /api/comments, /api/notifications
│   ├── services/
│   │   ├── auth_service.py      ← Password hashing, JWT, API keys
│   │   ├── upload_service.py    ← File validation, save, delete
│   │   └── benchmark_service.py ← Job orchestration + leaderboard
│   └── benchmark_engine/
│       ├── loader.py            ← load_model, load_dataset
│       ├── evaluator.py         ← evaluate_model orchestrator
│       └── metrics.py           ← All metric computations
├── templates/                   ← Jinja2 HTML templates
├── static/                      ← CSS, JS, images
├── scripts/
│   ├── smoke_test_core.py       ← Headless engine test
│   └── smoke_test_http.py       ← Full HTTP e2e test
├── packages/
│   └── openbenchml-cli/         ← NPM CLI package
├── docs-site/                   ← mkdocs-material documentation
├── tests/                       ← Pytest unit tests (planned)
├── requirements.txt
├── Dockerfile / docker-compose.yml
├── railway.toml / render.yaml / fly.toml
└── run.py
```

## Pull request workflow

1. Fork the repo and create a feature branch: `git checkout -b feat/my-feature`
2. Make your changes. Add tests if applicable.
3. Run the smoke tests:
   ```bash
   .venv/bin/python scripts/smoke_test_core.py
   ```
4. Run the linters:
   ```bash
   black --check app/ scripts/
   flake8 app/ --max-line-length=100
   ```
5. Commit with a clear message:
   ```
   feat(benchmark): add per-class AUC-ROC support
   ```
6. Push and open a PR. Reference any related issues (`Closes #42`).

## Commit message conventions

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`.

Scopes: `benchmark`, `models`, `datasets`, `leaderboard`, `competitions`, `auth`, `cli`, `docs`, `infra`.

## Reporting security issues

**Do not open a public GitHub issue for security vulnerabilities.** Email `kartheekbvs@users.noreply.github.com` instead. We'll acknowledge within 48 hours and work with you on a fix and disclosure timeline.

## Code of conduct

Be kind. Be patient. Assume good intent. We're all here to build something useful.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
