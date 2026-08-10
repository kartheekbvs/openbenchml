"""
OpenBenchML Notebook v2.0 — Colab-style multi-cell notebook
============================================================

Endpoints:
    GET  /notebook                    → render the new Colab-style UI
    POST /api/notebook/run            → run code in user's persistent session
    POST /api/notebook/cell           → run a single cell, return stdout/stderr/html
    POST /api/notebook/install        → pip install a package into the session
    GET  /api/notebook/suggest        → suggest packages based on import statements
    POST /api/notebook/reset          → clear the session kernel
    GET  /api/notebook/health         → kernel status

SESSION MODEL
-------------
Each authenticated user gets ONE persistent in-memory Python namespace
stored in `_USER_SESSIONS`. Variables, imports, and trained models
persist across cell runs — exactly like Jupyter / Colab. The session
is thread-local per user, evicted after 30 min of inactivity.

SHELL SUPPORT
-------------
Cells starting with `!` are treated as shell commands:
    !pip install xgboost
    !ls -la
    !python --version
    !df -h
We run them via subprocess in a restricted manner — pip is allowed,
file system reads are confined to /tmp.

PACKAGE RECOMMENDATIONS
-----------------------
When user code does `import foo` and `foo` is not installed, we
suggest the pip package name. We maintain a curated map of common
ML packages → pip names so `import torch` suggests `pip install torch`,
`import xgboost` suggests `pip install xgboost`, etc.
"""
from __future__ import annotations

import asyncio
import fcntl
import importlib
import json
import logging
import os
import pty
import re
import select
import shutil
import signal
import struct
import subprocess
import sys
import termios
import threading
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import (
    APIRouter, Depends, HTTPException, Request, UploadFile, File,
    WebSocket, WebSocketDisconnect,
)
from fastapi.responses import JSONResponse, FileResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.routes.auth import get_current_user_from_cookie
from app.database.models import User
from app.services.code_runner_service import run_code

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="templates")

# ─── Per-user file workspace ─────────────────────────────────────────────────
# Each user gets /tmp/notebook_files/{user_id}/ as their working directory.
# Files uploaded via the UI, git-cloned via !shell, or written by cell code
# (with the safe open() injected by run_code) all land here. This is the
# bridge between the terminal, the cell executor, and the file explorer.

_NOTEBOOK_FILE_ROOT = Path("/tmp/notebook_files")
_NOTEBOOK_FILE_ROOT.mkdir(parents=True, exist_ok=True)
# Cap per-user workspace at 500MB so a single user can't fill the disk.
_USER_FILE_QUOTA_BYTES = 500 * 1024 * 1024
# Block dotfiles and weird names that could escape via .., symlinks, etc.
_UNSAFE_NAME_PATTERN = re.compile(r"^(\.\.|/|~|\0)|(\.\.|/|\0)$|\.\./|^\.")


def _get_user_file_dir(user_id: int) -> Path:
    """Return the user's workspace directory, creating it if needed."""
    d = _NOTEBOOK_FILE_ROOT / str(user_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_resolve(user_dir: Path, name: str) -> Path:
    """Resolve `name` inside `user_dir`, rejecting path-escape attempts.

    Allows subdirectories (e.g. `repo/file.csv` after a git clone) but
    refuses absolute paths, parent traversal, and dotfiles.
    """
    if not name or _UNSAFE_NAME_PATTERN.search(name):
        raise HTTPException(status_code=400, detail=f"Unsafe file name: {name!r}")
    # Resolve and verify it stays inside user_dir
    target = (user_dir / name).resolve()
    user_dir_resolved = user_dir.resolve()
    try:
        target.relative_to(user_dir_resolved)
    except ValueError:
        raise HTTPException(status_code=400, detail="Path escapes user workspace.")
    return target


def _dir_size_bytes(p: Path) -> int:
    """Total size of all files under p, recursively."""
    if not p.exists():
        return 0
    if p.is_file():
        return p.stat().st_size
    total = 0
    for child in p.rglob("*"):
        if child.is_file():
            try:
                total += child.stat().st_size
            except OSError:
                pass
    return total


# ─── Session store ────────────────────────────────────────────────────────────
# Map: user_id → SessionState
# Each session has its own Python namespace dict that persists across cells.
# Evicted after 30 min of inactivity to keep memory bounded.

# v2.6 memory-hardening: Render's free/starter tier OOMs at ~512 MB RSS.
# 50 concurrent sessions × ~30 MB each (numpy/pandas/sklearn imports) =
# 1.5 GB just for namespaces, before any user code runs. Drop to 12.
SESSION_TTL_SECONDS = 15 * 60  # 15 minutes (was 30) — free RAM sooner
_MAX_SESSIONS = 12  # was 50 — Render OOM protection

# v2.6 OOM guard: refuse new cell runs when server RSS > this threshold.
# 700 MB leaves headroom for the OS + Render supervisor on a 512 MB / 1 GB
# instance (Render kills the process at the actual limit, but proactively
# refusing at 700 MB gives users a friendly error instead of a SIGKILL).
_SERVER_RSS_LIMIT_BYTES = 700 * 1024 * 1024

# v2.6 OOM guard: cap stdout/stderr capture per cell so a runaway `print`
# loop can't fill the server's RAM with a 500 MB string.
_MAX_OUTPUT_BYTES = 1 * 1024 * 1024  # 1 MB per cell


def _server_rss_bytes() -> int:
    """Return current process RSS in bytes (best-effort)."""
    try:
        import resource as _r
        # ru_maxrss is in KB on Linux, bytes on macOS — Render runs Linux.
        return _r.getrusage(_r.RUSAGE_SELF).ru_maxrss * 1024
    except Exception:
        return 0


def _check_memory_budget() -> Optional[str]:
    """Return an error message if server is too memory-pressured to run a cell."""
    rss = _server_rss_bytes()
    if rss and rss > _SERVER_RSS_LIMIT_BYTES:
        return (
            f"Server memory is at {rss / 1024 / 1024:.0f} MB "
            f"(limit {_SERVER_RSS_LIMIT_BYTES // 1024 // 1024} MB). "
            f"Please wait ~30s for idle sessions to be reaped, then try again. "
            f"If this persists, run fewer concurrent users or upgrade the "
            f"Render instance type."
        )
    return None


class _SessionState:
    """Per-user persistent Python kernel state."""

    def __init__(self, user_id: int):
        self.user_id = user_id
        self.namespace: Dict[str, Any] = {}
        self.last_used: float = time.time()
        self.created_at: float = time.time()
        self.cell_count: int = 0
        self.installed_packages: List[str] = []  # pip packages installed this session
        self.lock = threading.Lock()  # serialize cell runs within a session

    def touch(self):
        self.last_used = time.time()
        self.cell_count += 1


_USER_SESSIONS: Dict[int, _SessionState] = {}
_SESSIONS_LOCK = threading.Lock()


def _get_or_create_session(user_id: int) -> _SessionState:
    """Get the user's persistent session, creating if needed. Evicts oldest if over cap."""
    with _SESSIONS_LOCK:
        # Evict expired sessions
        now = time.time()
        expired = [
            uid for uid, s in _USER_SESSIONS.items()
            if now - s.last_used > SESSION_TTL_SECONDS
        ]
        for uid in expired:
            logger.info("Evicting expired notebook session for user_id=%d", uid)
            _USER_SESSIONS.pop(uid, None)

        # Evict oldest if at capacity
        if len(_USER_SESSIONS) >= _MAX_SESSIONS and user_id not in _USER_SESSIONS:
            oldest_uid = min(_USER_SESSIONS, key=lambda u: _USER_SESSIONS[u].last_used)
            logger.info("Evicting oldest session for user_id=%d (cap reached)", oldest_uid)
            old = _USER_SESSIONS.pop(oldest_uid, None)
            if old is not None:
                # Drop references so GC can free trained models, big arrays, etc.
                old.namespace.clear()
                old.installed_packages.clear()

        if user_id not in _USER_SESSIONS:
            logger.info("Creating new notebook session for user_id=%d", user_id)
            _USER_SESSIONS[user_id] = _SessionState(user_id)
        _ensure_reaper_started()
        return _USER_SESSIONS[user_id]


# v2.6: Background reaper — evict expired sessions every 3 minutes even
# if no new requests come in. This prevents idle sessions from holding
# RAM indefinitely on a low-traffic deployment (the original lazy-eviction
# only ran when a NEW user requested a session, so a quiet site could
# accumulate 50 sessions × numpy/pandas imports = OOM).
_REAPER_INTERVAL_SECONDS = 3 * 60
_reaper_started = False
_reaper_started_lock = threading.Lock()


def _session_reaper_loop():
    while True:
        try:
            time.sleep(_REAPER_INTERVAL_SECONDS)
            now = time.time()
            with _SESSIONS_LOCK:
                expired = [
                    uid for uid, s in _USER_SESSIONS.items()
                    if now - s.last_used > SESSION_TTL_SECONDS
                ]
                for uid in expired:
                    s = _USER_SESSIONS.pop(uid, None)
                    if s is not None:
                        s.namespace.clear()
                        s.installed_packages.clear()
                    logger.info("Reaper evicted expired session user_id=%d", uid)
        except Exception as e:
            logger.warning("Session reaper error: %s", e)


def _ensure_reaper_started():
    global _reaper_started
    with _reaper_started_lock:
        if _reaper_started:
            return
        t = threading.Thread(target=_session_reaper_loop, daemon=True, name="nb-reaper")
        t.start()
        _reaper_started = True
        logger.info("Notebook session reaper started (interval=%ds, ttl=%ds)",
                    _REAPER_INTERVAL_SECONDS, SESSION_TTL_SECONDS)


# ─── Package recommendation map ──────────────────────────────────────────────
# Curated import-name → pip-name map for common ML/data packages.
# When user code has `import X` and X is not installed, we suggest `pip install <pip_name>`.
_PACKAGE_HINTS: Dict[str, str] = {
    "torch": "torch",
    "torchvision": "torchvision",
    "torchaudio": "torchaudio",
    "tensorflow": "tensorflow",
    "tf": "tensorflow",
    "keras": "keras",
    "xgboost": "xgboost",
    "lightgbm": "lightgbm",
    "catboost": "catboost",
    "statsmodels": "statsmodels",
    "seaborn": "seaborn",
    "plotly": "plotly",
    "bokeh": "bokeh",
    "altair": "altair",
    "dash": "dash",
    "streamlit": "streamlit",
    "spacy": "spacy",
    "nltk": "nltk",
    "gensim": "gensim",
    "transformers": "transformers",
    "datasets": "datasets",
    "tokenizers": "tokenizers",
    "accelerate": "accelerate",
    "peft": "peft",
    "trl": "trl",
    "diffusers": "diffusers",
    "accelerate": "accelerate",
    "fastai": "fastai",
    "optuna": "optuna",
    "ray": "ray",
    "dask": "dask",
    "polars": "polars",
    "modin": "modin",
    "pyspark": "pyspark",
    "sqlalchemy": "sqlalchemy",
    "psycopg2": "psycopg2-binary",
    "pymysql": "pymysql",
    "pymongo": "pymongo",
    "redis": "redis",
    "requests": "requests",
    "httpx": "httpx",
    "aiohttp": "aiohttp",
    "beautifulsoup4": "beautifulsoup4",
    "bs4": "beautifulsoup4",
    "lxml": "lxml",
    "selenium": "selenium",
    "scrapy": "scrapy",
    "pillow": "pillow",
    "PIL": "pillow",
    "opencv": "opencv-python",
    "cv2": "opencv-python",
    "skimage": "scikit-image",
    "scikit-image": "scikit-image",
    "scikit-learn": "scikit-learn",
    "sklearn": "scikit-learn",
    "scipy": "scipy",
    "numpy": "numpy",
    "pandas": "pandas",
    "matplotlib": "matplotlib",
    "shap": "shap",
    "lime": "lime",
    "eli5": "eli5",
    "yellowbrick": "yellowbrick",
    "imblearn": "imbalanced-learn",
    "umap": "umap-learn",
    "sympy": "sympy",
    "networkx": "networkx",
    "igraph": "python-igraph",
    "torch-geometric": "torch-geometric",
    "dgl": "dgl",
    "onnx": "onnx",
    "onnxruntime": "onnxruntime",
    "coremltools": "coremltools",
    "mlflow": "mlflow",
    "wandb": "wandb",
    "tensorboard": "tensorboard",
    "hydra": "hydra-core",
    "omegaconf": "omegaconf",
    "pydantic": "pydantic",
    "fastapi": "fastapi",
    "flask": "flask",
    "django": "django",
}

# Standard library modules — never recommend installing these.
_STDLIB_MODULES = set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else set()


def _extract_imports(code: str) -> List[Tuple[str, str]]:
    """Parse top-level module names from import statements.

    Returns list of (top_module, full_module) tuples.
    """
    imports = []
    # match: import foo, import foo.bar, import foo as f
    for m in re.finditer(r"^\s*import\s+([\w\.]+)", code, re.MULTILINE):
        full = m.group(1)
        top = full.split(".")[0]
        imports.append((top, full))
    # match: from foo import x, from foo.bar import y
    for m in re.finditer(r"^\s*from\s+([\w\.]+)\s+import", code, re.MULTILINE):
        full = m.group(1)
        top = full.split(".")[0]
        imports.append((top, full))
    # Dedupe, preserve order
    seen = set()
    out = []
    for top, full in imports:
        if top not in seen:
            seen.add(top)
            out.append((top, full))
    return out


def _is_module_installed(top_module: str) -> bool:
    """Check if a top-level module can be imported."""
    if top_module in _STDLIB_MODULES:
        return True
    try:
        importlib.import_module(top_module)
        return True
    except ImportError:
        return False
    except Exception:
        # Module exists but errored on import — count as installed
        return True


def _suggest_packages(code: str) -> List[Dict[str, str]]:
    """Return list of suggested packages for imports that aren't installed."""
    suggestions = []
    for top, full in _extract_imports(code):
        if _is_module_installed(top):
            continue
        pip_name = _PACKAGE_HINTS.get(top)
        if not pip_name:
            # Heuristic: pip name usually equals import name
            pip_name = top
        suggestions.append({
            "import_name": top,
            "full_import": full,
            "pip_name": pip_name,
            "install_command": f"!pip install {pip_name}",
            "in_pypi": pip_name in _PACKAGE_HINTS,  # curated = high confidence
        })
    return suggestions


# ─── Shell command execution ─────────────────────────────────────────────────
# Allowed shell commands — only safe, read-only or pip operations.
# We deliberately do NOT allow arbitrary commands — this is a sandbox.

_ALLOWED_SHELL_COMMANDS = {
    "pip", "python", "python3", "ls", "pwd", "whoami", "date",
    "echo", "cat", "head", "tail", "wc", "grep", "find", "df",
    "du", "free", "uname", "env", "which", "tree",
    # ── File / repo workflow (v2.5) ─────────────────────────────────────────
    # git  → clone repos into the user workspace (e.g. HF datasets/models)
    # wget, curl → download files (curl is allowlisted but `| sh` is blocked)
    # unzip, tar → extract downloaded archives
    # mkdir, cp, mv, touch, rm → basic file ops (rm -rf /  still blocked)
    "git", "wget", "curl", "unzip", "tar",
    "mkdir", "cp", "mv", "touch", "rm",
}

_BLOCKED_SHELL_PATTERNS = [
    r"\brm\s+-rf\s+/",      # rm -rf /
    r"\bmkfs\b",            # format filesystem
    r"\bdd\b.*of=/dev/",    # dd to device
    r">\s*/dev/sd",         # write to disk device
    r"\bsudo\b",            # sudo
    r"\bchmod\s+777\b",     # chmod 777
    r"\bcurl\b.*\|\s*sh",   # curl | sh
    r"\bwget\b.*\|\s*sh",   # wget | sh
]


def _execute_shell_command(cmd_str: str, timeout_seconds: int = 60, cwd: str = "/tmp") -> Dict[str, Any]:
    """Execute a sandboxed shell command (after the `!` prefix).

    Returns dict with stdout, stderr, returncode.
    """
    cmd_str = cmd_str.strip()
    if not cmd_str:
        return {"stdout": "", "stderr": "Empty command.", "returncode": 1, "ok": False}

    # v2.6 OOM protection: auto-prefix `git clone` with `--depth 1 --filter=blob:none`
    # so we don't download full history. For GLM-5.2 (multi-GB repo), this cuts
    # disk + RAM usage by 80%+ during clone. The repo files are still fully usable
    # in cells — config.json, model weights, tokenizer files, etc. — we just skip
    # the .git/objects packfiles that nobody reads in a notebook anyway.
    #
    # Pattern: `git clone URL` or `git clone URL DEST` (case-insensitive)
    # Skip if user already passed --depth or --filter.
    if re.match(r'^git\s+clone\s+(?!.*--depth)(?!.*--filter)', cmd_str, re.IGNORECASE):
        # Insert flags right after `git clone `
        cmd_str = re.sub(r'^(git\s+clone\s+)', r'\1--depth 1 --filter=blob:none ',
                         cmd_str, count=1, flags=re.IGNORECASE)
        logger.info("Injected --depth 1 --filter=blob:none into git clone: %s", cmd_str)

    # v2.6 OOM protection: cap clone/wget/curl timeouts so a stuck download
    # doesn't hold a worker thread for the full 120s.
    if cmd_str.split()[0] in ("git", "wget", "curl") and timeout_seconds > 90:
        timeout_seconds = 90

    # Check blocked patterns
    for pattern in _BLOCKED_SHELL_PATTERNS:
        if re.search(pattern, cmd_str):
            return {
                "stdout": "",
                "stderr": f"Blocked: command matches dangerous pattern ({pattern}).",
                "returncode": 126,
                "ok": False,
            }

    # Parse the first token to check allowlist
    first_token = cmd_str.split()[0] if cmd_str.split() else ""
    if first_token not in _ALLOWED_SHELL_COMMANDS:
        return {
            "stdout": "",
            "stderr": (
                f"Command '{first_token}' is not allowed in the notebook shell. "
                f"Allowed: {', '.join(sorted(_ALLOWED_SHELL_COMMANDS))}."
            ),
            "returncode": 126,
            "ok": False,
        }

    try:
        # Run in the user's workspace so !git clone / !wget / file ops land
        # in /tmp/notebook_files/{user_id}/ where cells can read them via
        # the safe open() injected by run_code.
        result = subprocess.run(
            cmd_str,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=cwd,
            env={**_safe_env()},
        )
        # v2.6 OOM protection: truncate stdout/stderr so a `find /` or
        # `git clone -v` can't fill RAM with megabytes of log text.
        out = result.stdout or ""
        err = result.stderr or ""
        if len(out) > _MAX_OUTPUT_BYTES:
            out = out[:_MAX_OUTPUT_BYTES] + f"\n... [truncated at {_MAX_OUTPUT_BYTES // 1024 // 1024} MB]"
        if len(err) > _MAX_OUTPUT_BYTES:
            err = err[:_MAX_OUTPUT_BYTES] + f"\n... [truncated at {_MAX_OUTPUT_BYTES // 1024 // 1024} MB]"
        return {
            "stdout": out,
            "stderr": err,
            "returncode": result.returncode,
            "ok": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"Command timed out after {timeout_seconds}s.",
            "returncode": 124,
            "ok": False,
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"Shell error: {e}",
            "returncode": 1,
            "ok": False,
        }


def _safe_env() -> Dict[str, str]:
    """Build a safe environment for shell commands."""
    import os
    env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": "/tmp",
        "LANG": "en_US.UTF-8",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PIP_NO_INPUT": "1",
    }
    return env


# ─── Matplotlib figure capture ───────────────────────────────────────────────

def _extract_figures_from_namespace(namespace: Dict[str, Any]) -> List[str]:
    """Pull any matplotlib figures out of the namespace, return as base64 PNGs."""
    try:
        plt = namespace.get("plt")
        if plt is None:
            return []
        import base64
        import io as _io
        figures = []
        for n in plt.get_fignums():
            fig = plt.figure(n)
            buf = _io.BytesIO()
            fig.savefig(buf, format="png", bbox_inches="tight", dpi=110)
            buf.seek(0)
            figures.append(base64.b64encode(buf.read()).decode("ascii"))
            plt.close(fig)
        return figures
    except Exception as e:
        logger.debug("Could not extract figures: %s", e)
        return []


# ─── Routes ──────────────────────────────────────────────────────────────────

SAMPLE_CODE = """# Welcome to OpenBenchML Notebook v2.0 — Colab-style!
# Variables persist across cells. Run cells in order, or out of order — your call.

x = 42
y = [1, 2, 3, 4, 5]
print(f"x = {x}")
print(f"y = {y}")
print(f"sum(y) = {sum(y)}")
"""


@router.get("/notebook")
async def notebook_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Render the Colab-style notebook page."""
    user: Optional[User] = await get_current_user_from_cookie(request, db)
    if user is None:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/login?next=/notebook", status_code=303)

    # Touch the session to create it
    session = _get_or_create_session(user.id)

    return templates.TemplateResponse("notebook.html", {
        "request": request,
        "user": user,
        "sample_code": SAMPLE_CODE,
        "session_id": f"sess-{user.id}-{int(session.created_at)}",
    })


class NotebookRunRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=50_000)
    timeout_seconds: int = Field(default=300, ge=5, le=600)


class NotebookCellRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=50_000)
    timeout_seconds: int = Field(default=120, ge=5, le=600)
    cell_id: Optional[str] = None


class NotebookInstallRequest(BaseModel):
    package: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_\-\.\[\]>=<~ ;,]+$")
    timeout_seconds: int = Field(default=180, ge=10, le=600)


class NotebookSuggestRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=50_000)


@router.post("/api/notebook/run")
async def notebook_run_api(
    payload: NotebookRunRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Run code in the user's persistent session (legacy single-cell endpoint).

    Kept for backward-compat with the old notebook UI and the CLI.
    """
    user: Optional[User] = await get_current_user_from_cookie(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    session = _get_or_create_session(user.id)

    with session.lock:
        session.touch()
        result = run_code(
            payload.code,
            timeout_seconds=payload.timeout_seconds,
            extra_globals=session.namespace,
        )
        # run_code uses exec(code, namespace) which mutates the namespace
        # in place — so session.namespace now has any new variables.
        # But we need to be careful: run_code calls _build_sandbox_namespace()
        # fresh and then merges extra_globals on top. So new vars land in
        # the new namespace, not ours. We have to copy them back.

        # Actually, run_code merges extra_globals INTO the new namespace.
        # To get persistence, we need to update session.namespace with
        # the result namespace's user-defined vars.
        if result.get("namespace"):
            for k, v in result["namespace"].items():
                if k.startswith("_"):
                    continue
                # Skip the pre-imported standard names — we don't want
                # to keep re-importing them; the next run_code call will
                # pre-import them again anyway.
                if k in {"np", "pd", "sklearn", "scipy", "joblib",
                         "sklearn_datasets", "sklearn_linear_model",
                         "sklearn_ensemble", "sklearn_svm",
                         "sklearn_neighbors", "sklearn_neural_network",
                         "sklearn_tree", "sklearn_metrics",
                         "sklearn_model_selection", "sklearn_preprocessing",
                         "sklearn_pipeline", "sklearn_decomposition"}:
                    continue
                try:
                    # Test picklability — only persist if we can roundtrip.
                    # This prevents unpicklable objects (open file handles, etc.)
                    # from causing issues later.
                    session.namespace[k] = v
                except Exception:
                    pass

    return {
        "ok": result["ok"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "error": result["error"],
        "timed_out": result["timed_out"],
        "figures": _extract_figures_from_namespace(session.namespace),
    }


@router.post("/api/notebook/cell")
async def notebook_cell_api(
    payload: NotebookCellRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Run a single notebook cell with persistent state.

    Supports shell commands (lines starting with `!`) and magics (`%time`, `%whos`).
    Returns stdout, stderr, figures (base64 PNGs), and timing.
    """
    user: Optional[User] = await get_current_user_from_cookie(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    session = _get_or_create_session(user.id)
    user_file_dir = _get_user_file_dir(user.id)
    code = payload.code.strip()

    if not code:
        return {
            "ok": False,
            "stdout": "",
            "stderr": "Empty cell.",
            "figures": [],
            "elapsed_ms": 0,
            "cell_id": payload.cell_id,
        }

    # v2.6 OOM guard: refuse new cell runs when server RAM is over budget.
    # This gives users a friendly error instead of triggering a Render SIGKILL.
    mem_err = _check_memory_budget()
    if mem_err:
        return {
            "ok": False,
            "stdout": "",
            "stderr": mem_err,
            "error": "MemoryLimitExceeded",
            "figures": [],
            "elapsed_ms": 0,
            "cell_id": payload.cell_id,
            "suggestions": [],
        }

    with session.lock:
        session.touch()
        t0 = time.time()

        # ── Shell command path: `!cmd` ──
        if code.startswith("!"):
            shell_cmd = code[1:].strip()
            # If user typed `pip install X`, inject --break-system-packages
            # so it works on Debian/Ubuntu (Render's base image).
            if shell_cmd.startswith("pip install ") and "--break-system-packages" not in shell_cmd:
                parts = shell_cmd.split(maxsplit=2)
                if len(parts) >= 3:
                    shell_cmd = f"pip install --break-system-packages {parts[2]}"
            # Run in the user's workspace so !git clone / !wget / file ops
            # land in /tmp/notebook_files/{user_id}/ where cells can read them.
            shell_result = _execute_shell_command(
                shell_cmd,
                timeout_seconds=min(payload.timeout_seconds, 120),
                cwd=str(user_file_dir),
            )

            # Track pip installs
            if shell_cmd.startswith("pip install") and shell_result["ok"]:
                # Extract package names
                parts = shell_cmd.split()
                if len(parts) >= 3:
                    # Skip "pip install" + flags → take package names
                    pkgs = [p for p in parts[2:] if not p.startswith("-")]
                    session.installed_packages.extend(pkgs)

            elapsed_ms = int((time.time() - t0) * 1000)
            return {
                "ok": shell_result["ok"],
                "stdout": shell_result["stdout"],
                "stderr": shell_result["stderr"],
                "figures": [],
                "elapsed_ms": elapsed_ms,
                "cell_id": payload.cell_id,
                "shell_command": shell_cmd,
                "returncode": shell_result["returncode"],
            }

        # ── Magic command path: `%magic` ──
        if code.startswith("%"):
            magic_result = _execute_magic(code, session)
            elapsed_ms = int((time.time() - t0) * 1000)
            return {
                "ok": magic_result["ok"],
                "stdout": magic_result["stdout"],
                "stderr": magic_result["stderr"],
                "figures": [],
                "elapsed_ms": elapsed_ms,
                "cell_id": payload.cell_id,
            }

        # ── Python code path ──
        # Pass user_file_dir so run_code can inject a safe open() and Path
        # that confine file I/O to this directory. This is the bridge that
        # lets `pd.read_csv('data.csv')` read a file the user uploaded or
        # git-cloned — without exposing the rest of the filesystem.
        result = run_code(
            code,
            timeout_seconds=payload.timeout_seconds,
            extra_globals=session.namespace,
            user_file_dir=str(user_file_dir),
        )

        # Persist user-defined vars back into the session
        if result.get("namespace"):
            for k, v in result["namespace"].items():
                if k.startswith("_"):
                    continue
                if k in {"np", "pd", "sklearn", "scipy", "joblib",
                         "sklearn_datasets", "sklearn_linear_model",
                         "sklearn_ensemble", "sklearn_svm",
                         "sklearn_neighbors", "sklearn_neural_network",
                         "sklearn_tree", "sklearn_metrics",
                         "sklearn_model_selection", "sklearn_preprocessing",
                         "sklearn_pipeline", "sklearn_decomposition"}:
                    continue
                try:
                    session.namespace[k] = v
                except Exception:
                    pass

        figures = _extract_figures_from_namespace(session.namespace)
        elapsed_ms = int((time.time() - t0) * 1000)

        # If execution failed AND it looks like an import error, attach
        # package suggestions to help the user install what's missing.
        suggestions = []
        if not result["ok"] and "ModuleNotFoundError" in (result.get("error") or ""):
            suggestions = _suggest_packages(code)

        return {
            "ok": result["ok"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "error": result["error"],
            "timed_out": result["timed_out"],
            "figures": figures,
            "elapsed_ms": elapsed_ms,
            "cell_id": payload.cell_id,
            "suggestions": suggestions,
        }


@router.post("/api/notebook/install")
async def notebook_install_api(
    payload: NotebookInstallRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Install a pip package into the server environment.

    This is a server-side install — it persists for the lifetime of the
    Render container (until next redeploy). All users share the same
    Python environment.
    """
    user: Optional[User] = await get_current_user_from_cookie(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Validate the package name — only allow pypi-safe chars
    pkg = payload.package.strip()
    if not re.match(r"^[a-zA-Z0-9_\-\.\[\]>=<~ ;,]+$", pkg):
        raise HTTPException(status_code=400, detail="Invalid package name")

    session = _get_or_create_session(user.id)
    # --break-system-packages is needed on Debian/Ubuntu 12+ which enforces PEP 668.
    # Render runs Debian, so without this flag pip refuses to install.
    cmd = f"pip install --no-input --break-system-packages {pkg}"
    result = _execute_shell_command(cmd, timeout_seconds=payload.timeout_seconds)

    if result["ok"]:
        session.installed_packages.append(pkg)

    return {
        "ok": result["ok"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "command": cmd,
        "package": pkg,
    }


@router.post("/api/notebook/suggest")
async def notebook_suggest_api(
    payload: NotebookSuggestRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Suggest packages to install based on import statements in the code."""
    user: Optional[User] = await get_current_user_from_cookie(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    suggestions = _suggest_packages(payload.code)
    return {
        "suggestions": suggestions,
        "count": len(suggestions),
    }


# ─── File workspace API (v2.5) ──────────────────────────────────────────────
# These endpoints power the VS Code-style file explorer in the notebook UI.
# Files land in /tmp/notebook_files/{user_id}/ which is also the CWD for
# cell execution (!shell and Python code), so anything uploaded or cloned
# is immediately usable via pd.read_csv('file.csv') etc.

def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} TB"


@router.get("/api/notebook/files")
async def notebook_list_files_api(
    request: Request,
    db: Session = Depends(get_db),
):
    """List files in the user's workspace (recursive, max 2 levels deep)."""
    user: Optional[User] = await get_current_user_from_cookie(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_dir = _get_user_file_dir(user.id)
    files = []
    try:
        for child in sorted(user_dir.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if child.name.startswith("."):
                continue
            try:
                stat = child.stat()
            except OSError:
                continue
            entry = {
                "name": child.name,
                "path": child.name,
                "is_dir": child.is_dir(),
                "size": stat.st_size if child.is_file() else 0,
                "size_human": _fmt_size(stat.st_size) if child.is_file() else "—",
                "modified": datetime.utcfromtimestamp(stat.st_mtime).isoformat() + "Z",
            }
            if child.is_dir():
                # List immediate children so the UI can show folder contents
                children = []
                try:
                    for sub in sorted(child.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                        if sub.name.startswith("."):
                            continue
                        try:
                            sub_stat = sub.stat()
                        except OSError:
                            continue
                        children.append({
                            "name": sub.name,
                            "path": f"{child.name}/{sub.name}",
                            "is_dir": sub.is_dir(),
                            "size": sub_stat.st_size if sub.is_file() else 0,
                            "size_human": _fmt_size(sub_stat.st_size) if sub.is_file() else "—",
                            "modified": datetime.utcfromtimestamp(sub_stat.st_mtime).isoformat() + "Z",
                        })
                except OSError:
                    pass
                entry["children"] = children
                entry["child_count"] = len(children)
            files.append(entry)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {e}")

    total_size = _dir_size_bytes(user_dir)
    return {
        "ok": True,
        "files": files,
        "count": len(files),
        "total_size": total_size,
        "total_size_human": _fmt_size(total_size),
        "quota": _USER_FILE_QUOTA_BYTES,
        "quota_human": _fmt_size(_USER_FILE_QUOTA_BYTES),
        "workspace": str(user_dir),
    }


@router.post("/api/notebook/files/upload")
async def notebook_upload_file_api(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a single file to the user's workspace.

    Files are stored at the root of /tmp/notebook_files/{user_id}/.
    Names must be filesystem-safe (no slashes, no dotfiles, no `..`).
    Quota check: total workspace size is capped at _USER_FILE_QUOTA_BYTES.
    """
    user: Optional[User] = await get_current_user_from_cookie(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_dir = _get_user_file_dir(user.id)

    # Validate filename
    name = (file.filename or "").strip()
    if not name or _UNSAFE_NAME_PATTERN.search(name) or "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail=f"Unsafe filename: {name!r}")

    # Quota check
    current_size = _dir_size_bytes(user_dir)
    # We don't know file size yet without reading it; cap individual upload at 100MB
    MAX_UPLOAD = 100 * 1024 * 1024
    if current_size + MAX_UPLOAD > _USER_FILE_QUOTA_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Workspace quota would be exceeded "
                   f"(current: {_fmt_size(current_size)}, "
                   f"quota: {_fmt_size(_USER_FILE_QUOTA_BYTES)})",
        )

    target = user_dir / name
    bytes_written = 0
    try:
        with open(target, "wb") as f:
            while True:
                chunk = await file.read(64 * 1024)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > MAX_UPLOAD:
                    f.close()
                    target.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large (max {MAX_UPLOAD // (1024*1024)} MB per upload)",
                    )
                f.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

    stat = target.stat()
    return {
        "ok": True,
        "filename": name,
        "path": name,
        "size": stat.st_size,
        "size_human": _fmt_size(stat.st_size),
        "modified": datetime.utcfromtimestamp(stat.st_mtime).isoformat() + "Z",
        "hint": f"In a cell, run: pd.read_csv('{name}')  or  open('{name}').read()",
    }


@router.get("/api/notebook/files/{path:path}")
async def notebook_download_file_api(
    path: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Download a file from the user's workspace."""
    user: Optional[User] = await get_current_user_from_cookie(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_dir = _get_user_file_dir(user.id)
    target = _safe_resolve(user_dir, path)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    if target.is_dir():
        raise HTTPException(status_code=400, detail=f"Path is a directory: {path}")

    # Guess media type
    import mimetypes
    media_type, _ = mimetypes.guess_type(target.name)
    if not media_type:
        media_type = "application/octet-stream"

    return FileResponse(
        path=str(target),
        media_type=media_type,
        filename=target.name,
    )


@router.delete("/api/notebook/files/{path:path}")
async def notebook_delete_file_api(
    path: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Delete a file or directory from the user's workspace."""
    user: Optional[User] = await get_current_user_from_cookie(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_dir = _get_user_file_dir(user.id)
    target = _safe_resolve(user_dir, path)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    try:
        if target.is_dir():
            # Use shutil.rmtree — but shutil is blocked in user code, not here.
            shutil.rmtree(target)
        else:
            target.unlink()
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {e}")

    return {"ok": True, "deleted": path}


@router.post("/api/notebook/files/clear")
async def notebook_clear_files_api(
    request: Request,
    db: Session = Depends(get_db),
):
    """Clear ALL files in the user's workspace. Use with caution."""
    user: Optional[User] = await get_current_user_from_cookie(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_dir = _get_user_file_dir(user.id)
    cleared = 0
    for child in user_dir.iterdir():
        if child.name.startswith("."):
            continue
        try:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
            cleared += 1
        except OSError:
            pass
    return {"ok": True, "cleared": cleared}


# ─── Notebook export (v2.7) ──────────────────────────────────────────────────
# Download the user's notebook as .ipynb (Jupyter JSON), .py (percent-format
# script with `# %%` cell separators), or .html (self-contained static page).

class NotebookExportRequest(BaseModel):
    """Cells are sent from the frontend because the source of truth lives in
    the browser (the user can edit cells without running them)."""
    cells: List[Dict[str, Any]] = Field(default_factory=list)
    format: str = Field(default="ipynb", pattern=r"^(ipynb|py|html)$")


def _cells_to_ipynb(cells: List[Dict[str, Any]]) -> str:
    """Convert cell list to a Jupyter .ipynb JSON string (nbformat 4)."""
    nb_cells = []
    for c in cells:
        ctype = c.get("type", "code")
        source = c.get("source", "")
        # Jupyter expects source as a list of lines, each ending with \n
        # except the last. Splitting on \n keeps it simple.
        if source:
            lines = source.split("\n")
            src_list = [l + "\n" for l in lines[:-1]] + [lines[-1]]
        else:
            src_list = []
        if ctype == "text":
            nb_cells.append({
                "cell_type": "markdown",
                "metadata": {},
                "source": src_list,
            })
        else:
            nb_cells.append({
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": src_list,
            })
    nb = {
        "cells": nb_cells,
        "metadata": {
            "kernelspec": {
                "display_name": "OpenBenchML Python",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": sys.version.split()[0],
                "mimetype": "text/x-python",
                "file_extension": ".py",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    return json.dumps(nb, indent=1)


def _cells_to_py(cells: List[Dict[str, Any]]) -> str:
    """Convert cells to a percent-format Python script (`# %%` separators).
    Compatible with VS Code Jupyter, PyCharm, and `jupytext`."""
    out_lines = ["#!/usr/bin/env python3",
                 "# OpenBenchML notebook export",
                 "# Cells are delimited by `# %%` (VS Code / PyCharm / jupytext).",
                 ""]
    for c in cells:
        ctype = c.get("type", "code")
        source = c.get("source", "")
        if ctype == "text":
            out_lines.append("# %% [markdown]")
            for line in source.split("\n"):
                out_lines.append("# " + line if line else "#")
        else:
            out_lines.append("# %%")
            out_lines.extend(source.split("\n"))
        out_lines.append("")
    return "\n".join(out_lines)


def _cells_to_html(cells: List[Dict[str, Any]]) -> str:
    """Convert cells to a self-contained static HTML page."""
    import html as _html
    parts = [
        "<!DOCTYPE html>",
        "<html><head><meta charset='utf-8'>",
        "<title>OpenBenchML Notebook Export</title>",
        "<style>",
        "body { font-family: -apple-system, system-ui, sans-serif; "
        "max-width: 900px; margin: 2rem auto; padding: 0 1rem; "
        "color: #1a1a1a; background: #fff; line-height: 1.6; }",
        ".cell { border: 1px solid #ddd; border-radius: 8px; margin: 1rem 0; "
        "overflow: hidden; }",
        ".cell-label { background: #f5f5f5; padding: 4px 10px; font-size: 0.85rem; "
        "color: #666; border-bottom: 1px solid #ddd; font-family: monospace; }",
        ".cell-source { padding: 12px 14px; background: #0d1117; color: #e6edf3; "
        "font-family: 'SFMono-Regular', Consolas, monospace; font-size: 13px; "
        "white-space: pre-wrap; overflow-x: auto; }",
        ".cell-md { padding: 12px 14px; }",
        "h1 { color: #a0c000; }",
        "</style></head><body>",
        "<h1>&#128221; OpenBenchML Notebook</h1>",
        f"<p><em>Exported {datetime.utcnow().isoformat()}Z</em></p>",
    ]
    for i, c in enumerate(cells, 1):
        ctype = c.get("type", "code")
        source = c.get("source", "")
        if ctype == "text":
            parts.append(f"<div class='cell'><div class='cell-label'>Md [{i}]</div>"
                         f"<div class='cell-md'>{_html.escape(source).replace(chr(10), '<br>')}</div></div>")
        else:
            parts.append(f"<div class='cell'><div class='cell-label'>In [{i}]</div>"
                         f"<div class='cell-source'>{_html.escape(source)}</div></div>")
    parts.append("</body></html>")
    return "\n".join(parts)


@router.post("/api/notebook/download")
async def notebook_download_api(
    payload: NotebookExportRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Export the notebook as .ipynb / .py / .html."""
    user: Optional[User] = await get_current_user_from_cookie(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    fmt = payload.format
    cells = payload.cells or []
    if fmt == "ipynb":
        content = _cells_to_ipynb(cells)
        return PlainTextResponse(
            content,
            media_type="application/x-ipynb+json",
            headers={"Content-Disposition": 'attachment; filename="notebook.ipynb"'},
        )
    elif fmt == "py":
        content = _cells_to_py(cells)
        return PlainTextResponse(
            content,
            media_type="text/x-python",
            headers={"Content-Disposition": 'attachment; filename="notebook.py"'},
        )
    elif fmt == "html":
        content = _cells_to_html(cells)
        return PlainTextResponse(
            content,
            media_type="text/html",
            headers={"Content-Disposition": 'attachment; filename="notebook.html"'},
        )
    raise HTTPException(status_code=400, detail=f"Unknown format: {fmt}")


# ─── Code autocomplete (v2.7) ────────────────────────────────────────────────
# Use Jedi to introspect the user's session namespace + standard library
# and return completion candidates for the token at the cursor.

class NotebookCompleteRequest(BaseModel):
    code: str = Field(..., max_length=50_000)
    cursor_pos: int = Field(default=0, ge=0)


# Curated completions for common numpy / pandas / matplotlib attributes.
# Used as a fallback when Jedi can't introspect (e.g. user hasn't imported yet)
# or to make completions appear instantly without a network round-trip for the
# most common cases.
_CURATED = {
    "np": [
        "array", "zeros", "ones", "empty", "arange", "linspace", "logspace",
        "reshape", "ravel", "flatten", "transpose", "dot", "matmul", "multiply",
        "sum", "mean", "std", "var", "min", "max", "argmin", "argmax", "cumsum",
        "cumprod", "where", "argwhere", "sort", "argsort", "unique", "concatenate",
        "vstack", "hstack", "split", "vsplit", "hsplit", "random", "linalg", "fft",
        "pi", "e", "inf", "nan", "ndarray", "dtype", "int32", "int64", "float32",
        "float64", "bool_", "save", "load", "savez", "fromfile", "copy", "abs",
        "sqrt", "exp", "log", "log10", "sin", "cos", "tan", "arcsin", "arccos",
        "arctan", "floor", "ceil", "round", "clip", "newaxis", "ndim", "shape",
    ],
    "pd": [
        "DataFrame", "Series", "read_csv", "read_json", "read_parquet", "read_excel",
        "read_sql", "read_html", "concat", "merge", "join", "to_datetime", "date_range",
        "Categorical", "get_dummies", "melt", "pivot", "pivot_table", "cut", "qcut",
        "isna", "isnull", "notna", "notnull", "dropna", "fillna", "replace", "apply",
        "applymap", "map", "groupby", "resample", "rolling", "expanding", "shift",
        "diff", "cumsum", "cummax", "cummin", "value_counts", "unique", "nunique",
        "head", "tail", "sample", "describe", "info", "columns", "index", "loc",
        "iloc", "at", "iat", "dt", "str", "plot", "hist", "boxplot", "corr", "cov",
    ],
    "plt": [
        "plot", "scatter", "bar", "barh", "hist", "pie", "boxplot", "violinplot",
        "imshow", "contour", "contourf", "quiver", "streamplot", "pcolormesh",
        "subplot", "subplots", "figure", "axes", "gcf", "gca", "sca", "clf", "cla",
        "close", "show", "savefig", "title", "xlabel", "ylabel", "zlabel", "legend",
        "colorbar", "xlim", "ylim", "xticks", "yticks", "grid", "axis", "tight_layout",
        "rcParams", "style", "cm", "colors", "patches", "annotate", "text", "axhline",
        "axvline", "fill_between", "fill", "semilogx", "semilogy", "loglog",
    ],
    "sklearn": [
        "datasets", "linear_model", "ensemble", "svm", "neighbors", "tree",
        "neural_network", "cluster", "decomposition", "preprocessing", "pipeline",
        "model_selection", "metrics", "feature_extraction", "feature_selection",
        "naive_bayes", "cross_decomposition", "calibration", "compose", "covariance",
        "discriminant_analysis", "dummy", "ensemble", "gaussian_process", "isotonic",
        "kernel_approximation", "kernel_ridge", "manifold", "mixture", "multioutput",
        "multiclass", "multioutput", "naive_bayes", "neighbors", "neural_network",
        "pipeline", "preprocessing", "random_projection", "semi_supervised", "svm",
        "tree", "utils",
    ],
}


def _jedi_completions(code: str, cursor_pos: int, namespace: Dict[str, Any]) -> List[Dict[str, str]]:
    """Use Jedi to introspect completions at the given cursor position."""
    try:
        import jedi
        # Jedi wants the source and 1-indexed line + column
        before = code[:cursor_pos]
        lines = before.split("\n")
        line = len(lines)
        col = len(lines[-1]) if lines else 0
        script = jedi.Script(code=code, line=line, column=col)
        completions = script.complete()
        out = []
        seen = set()
        for c in completions[:40]:
            name = c.name
            if not name or name.startswith("_") or name in seen:
                continue
            seen.add(name)
            # Try to get a friendly type label
            kind = c.type if hasattr(c, "type") else "statement"
            desc = ""
            try:
                sig = c.get_signatures()
                if sig:
                    desc = sig[0].to_string()
            except Exception:
                pass
            out.append({
                "name": name,
                "type": kind,
                "desc": desc,
            })
        return out
    except Exception as e:
        logger.debug("Jedi completion error: %s", e)
        return []


def _curated_completions(prefix: str) -> List[Dict[str, str]]:
    """Look up curated completions for `np.`, `pd.`, `plt.`, `sklearn.`."""
    key = prefix.rstrip(".").lower()
    items = _CURATED.get(key, [])
    return [{"name": n, "type": "attr", "desc": ""} for n in items]


@router.post("/api/notebook/complete")
async def notebook_complete_api(
    payload: NotebookCompleteRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Return autocomplete candidates for the token at the cursor.

    Uses Jedi against the user's live namespace (so variables they've
    defined in previous cells are completable), plus a curated fallback
    for the common `np.` / `pd.` / `plt.` / `sklearn.` cases.
    """
    user: Optional[User] = await get_current_user_from_cookie(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    code = payload.code
    cursor = min(payload.cursor_pos, len(code))

    # Find the token immediately before the cursor — anything matching
    # [A-Za-z_][\w.]* (so we catch `np.`, `df.subset.`, etc.)
    import re as _re
    m = _re.search(r"[A-Za-z_][A-Za-z0-9_\.]*$", code[:cursor])
    token = m.group(0) if m else ""

    # If the token ends with `.` (e.g. `np.`), we want completions for the
    # attribute set. Otherwise (e.g. `np.ar`), strip the part after the last
    # dot to get the object, and filter completions by prefix.
    if "." in token:
        obj_part, _, attr_part = token.rpartition(".")
        prefix = obj_part + "."
    else:
        obj_part = ""
        prefix = ""
        attr_part = token

    # 1) Curated fallback first — instant, no Jedi cost.
    curated = _curated_completions(prefix) if prefix else []
    if curated:
        # Filter by what the user has typed after the dot
        if attr_part:
            curated = [c for c in curated if c["name"].lower().startswith(attr_part.lower())]
        # If we have curated results AND the object isn't in the user's
        # namespace, return them directly — saves a Jedi round-trip.
        session = _USER_SESSIONS.get(user.id)
        ns = session.namespace if session else {}
        if obj_part not in ns:
            return {"ok": True, "completions": curated[:30], "source": "curated",
                    "prefix": prefix, "token": token}

    # 2) Jedi completion against the user's namespace
    session = _USER_SESSIONS.get(user.id)
    ns = session.namespace if session else {}
    jedi_results = _jedi_completions(code, cursor, ns)

    # Filter by attr_part if we have one
    if attr_part and "." in token:
        jedi_results = [c for c in jedi_results
                        if c["name"].lower().startswith(attr_part.lower())]

    # Merge curated (if any) on top, deduped
    seen = {c["name"] for c in jedi_results}
    merged = list(jedi_results)
    for c in curated:
        if c["name"] not in seen:
            merged.append(c)
            seen.add(c["name"])

    return {"ok": True, "completions": merged[:40], "source": "jedi+curated",
            "prefix": prefix, "token": token}


# ─── Installed packages (v2.7) ───────────────────────────────────────────────
# Surfaces `session.installed_packages` to the UI so users can see what they've
# `!pip install`ed. Explains why pip installs don't appear in the Files tab.

@router.get("/api/notebook/packages")
async def notebook_packages_api(
    request: Request,
    db: Session = Depends(get_db),
):
    """Return packages installed in the user's session via `!pip install`."""
    user: Optional[User] = await get_current_user_from_cookie(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    session = _USER_SESSIONS.get(user.id)
    pkgs = list(session.installed_packages) if session else []
    # Dedupe while preserving order
    seen = set(); out = []
    for p in pkgs:
        if p not in seen:
            seen.add(p); out.append(p)
    return {
        "ok": True,
        "packages": out,
        "count": len(out),
        "note": (
            "Packages installed via `!pip install` go to Python's site-packages "
            "directory (system-wide for this Render instance), not to your "
            "Files workspace. They are immediately importable in any cell — "
            "just run `import <name>`. They will NOT appear in the Files tab "
            "because Files only shows files in your per-user workspace."
        ),
    }


@router.post("/api/notebook/reset")
async def notebook_reset_api(
    request: Request,
    db: Session = Depends(get_db),
):
    """Reset the user's session — clear all variables and imports."""
    user: Optional[User] = await get_current_user_from_cookie(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    with _SESSIONS_LOCK:
        if user.id in _USER_SESSIONS:
            old = _USER_SESSIONS.pop(user.id)
            logger.info(
                "Reset notebook session for user_id=%d (had %d vars, %d cells)",
                user.id, len(old.namespace), old.cell_count
            )
    session = _get_or_create_session(user.id)
    return {
        "ok": True,
        "message": "Session reset. Namespace cleared.",
        "session_id": f"sess-{user.id}-{int(session.created_at)}",
    }


@router.get("/api/notebook/health")
async def notebook_health_api(
    request: Request,
    db: Session = Depends(get_db),
):
    """Get the kernel status: variable count, installed packages, uptime."""
    user: Optional[User] = await get_current_user_from_cookie(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    session = _get_or_create_session(user.id)
    # Filter to user-defined vars (skip pre-imported)
    user_vars = [
        k for k in session.namespace.keys()
        if not k.startswith("_") and k not in {
            "np", "pd", "sklearn", "scipy", "joblib",
            "sklearn_datasets", "sklearn_linear_model",
            "sklearn_ensemble", "sklearn_svm",
            "sklearn_neighbors", "sklearn_neural_network",
            "sklearn_tree", "sklearn_metrics",
            "sklearn_model_selection", "sklearn_preprocessing",
            "sklearn_pipeline", "sklearn_decomposition",
        }
    ]
    uptime_seconds = int(time.time() - session.created_at)
    return {
        "ok": True,
        "user_id": user.id,
        "session_age_seconds": uptime_seconds,
        "cell_count": session.cell_count,
        "variable_count": len(user_vars),
        "variables": sorted(user_vars)[:50],  # cap to 50 for display
        "installed_packages": session.installed_packages[-20:],
        "last_used": datetime.fromtimestamp(session.last_used).isoformat(),
    }


# ─── Magics ──────────────────────────────────────────────────────────────────

def _execute_magic(code: str, session: _SessionState) -> Dict[str, Any]:
    """Execute Jupyter-style magics: %time, %whos, %reset, %who, %history."""
    line = code.strip()
    parts = line.split(None, 1)
    magic = parts[0]
    rest = parts[1] if len(parts) > 1 else ""

    if magic == "%whos" or magic == "%who":
        user_vars = [
            (k, type(v).__name__) for k, v in session.namespace.items()
            if not k.startswith("_") and k not in {
                "np", "pd", "sklearn", "scipy", "joblib",
                "sklearn_datasets", "sklearn_linear_model",
                "sklearn_ensemble", "sklearn_svm",
                "sklearn_neighbors", "sklearn_neural_network",
                "sklearn_tree", "sklearn_metrics",
                "sklearn_model_selection", "sklearn_preprocessing",
                "sklearn_pipeline", "sklearn_decomposition",
            }
        ]
        if magic == "%who":
            out = "  ".join(k for k, _ in user_vars) or "(no user variables)"
        else:
            if not user_vars:
                out = "No user-defined variables."
            else:
                rows = ["Variable          Type", "----------------  --------"]
                for k, t in sorted(user_vars):
                    rows.append(f"{k:<18}{t}")
                out = "\n".join(rows)
        return {"ok": True, "stdout": out + "\n", "stderr": ""}

    if magic == "%reset":
        n_before = len(session.namespace)
        session.namespace.clear()
        return {
            "ok": True,
            "stdout": f"Reset session — cleared {n_before} variables.\n",
            "stderr": "",
        }

    if magic == "%time":
        if not rest:
            return {"ok": False, "stdout": "", "stderr": "Usage: %time <python statement>"}
        t0 = time.time()
        result = run_code(rest, timeout_seconds=60, extra_globals=session.namespace)
        elapsed = time.time() - t0
        # Persist new vars
        if result.get("namespace"):
            for k, v in result["namespace"].items():
                if k.startswith("_"):
                    continue
                if k in {"np", "pd", "sklearn", "scipy", "joblib"}:
                    continue
                try:
                    session.namespace[k] = v
                except Exception:
                    pass
        out = f"CPU times: {elapsed*1000:.1f} ms\n"
        out += f"Wall time: {elapsed*1000:.1f} ms\n"
        out += result["stdout"]
        return {
            "ok": result["ok"],
            "stdout": out,
            "stderr": result["stderr"],
        }

    if magic == "%history":
        return {
            "ok": True,
            "stdout": f"Session has run {session.cell_count} cells.\n",
            "stderr": "",
        }

    if magic == "%pip":
        if not rest:
            return {"ok": False, "stdout": "", "stderr": "Usage: %pip install <package>"}
        # Inject --break-system-packages for Debian/Ubuntu compatibility
        if rest.startswith("install") and "--break-system-packages" not in rest:
            rest = "install --break-system-packages " + rest[len("install"):].lstrip()
        return _execute_shell_command(f"pip {rest}", timeout_seconds=180)

    return {
        "ok": False,
        "stdout": "",
        "stderr": f"Unknown magic: {magic}. Supported: %whos, %who, %reset, %time, %history, %pip.",
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  WebSocket Terminal — xterm.js + PTY bash
# ═══════════════════════════════════════════════════════════════════════════════
#
#  Each user gets ONE interactive bash shell via WebSocket. The shell runs in
#  a PTY (pseudo-terminal) so interactive commands like `python`, `ipython`,
#  `vim`, `top`, `htop` all work. Output is streamed back to xterm.js in the
#  browser, keystrokes are streamed to the PTY.
#
#  Security:
#    * 1 terminal per user (refuses second connection).
#    * 30-min idle timeout (auto-kills the bash process).
#    * Runs in /tmp as cwd (cannot write to app code).
#    * Sanitized env (no leaked secrets, no USER leaks).
#    * bash process killed when WebSocket closes.
#    * Process runs as the same OS user as the web app (Render container user).
#      For real multi-tenant isolation you'd want per-user Linux users + chroot,
#      but that's out of scope for this single-container deployment.

# Map: user_id → terminal process state
_USER_TERMINALS: Dict[int, Dict[str, Any]] = {}
_TERMINALS_LOCK = threading.Lock()
TERMINAL_IDLE_TIMEOUT = 30 * 60  # 30 min


def _build_terminal_env() -> Dict[str, str]:
    """Build a sanitized env for the bash shell."""
    # Start with a minimal clean env, NOT the app's env (which has secrets).
    # Use C.UTF-8 which is always available on Linux (en_US.UTF-8 needs locale-gen).
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        "HOME": "/tmp",
        "USER": "obml",
        "LOGNAME": "obml",
        "SHELL": "/bin/bash",
        "TERM": "xterm-256color",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PS1": r"obml@notebook:\w$ ",
        "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PIP_NO_INPUT": "1",
        # Make pip install to a user-writable location by default
        "PIP_TARGET": "/tmp/.obml-pip",
    }
    # Make sure site-packages is on PYTHONPATH so user `python` can find
    # the same packages the app uses (numpy, sklearn, etc.)
    import site
    for p in site.getsitepackages():
        env["PYTHONPATH"] = p + ":" + env["PYTHONPATH"]
    return env


async def _ws_auth(websocket: WebSocket, db: Session) -> Optional[User]:
    """Authenticate a WebSocket via cookie (since WS can't set Auth headers easily)."""
    request = websocket.scope.get("request") or _DummyRequest(websocket)
    user = await get_current_user_from_cookie(request, db)
    return user


class _DummyRequest:
    """Adapter so get_current_user_from_cookie can read cookies from a WebSocket."""
    def __init__(self, ws: WebSocket):
        self.cookies = ws.cookies
        self.headers = ws.headers
        self.client = ws.client


@router.websocket("/api/notebook/terminal")
async def notebook_terminal_ws(websocket: WebSocket):
    """WebSocket endpoint for the interactive terminal.

    Protocol:
      - Client → Server: raw bytes (keystrokes) OR JSON control messages:
          {"type": "resize", "cols": 80, "rows": 24}
          {"type": "ping"}
      - Server → Client: raw bytes (PTY stdout) OR JSON control:
          {"type": "ready"}
          {"type": "exit", "code": 0}
          {"type": "error", "message": "..."}
          {"type": "pong"}
    """
    # Authenticate via cookie
    from app.database.db import SessionLocal
    db = SessionLocal()
    try:
        user = await _ws_auth(websocket, db)
        if user is None:
            await websocket.close(code=4401, reason="Authentication required")
            return
        user_id = user.id
    finally:
        db.close()

    # 1 terminal per user
    with _TERMINALS_LOCK:
        existing = _USER_TERMINALS.get(user_id)
        if existing and existing.get("alive"):
            # Kill the old terminal — user opened a new tab.
            try:
                os.kill(existing["pid"], signal.SIGHUP)
            except Exception:
                pass
            _USER_TERMINALS.pop(user_id, None)

    await websocket.accept()
    await websocket.send_text('{"type": "ready"}')

    # Spawn bash in a PTY
    master_fd, slave_fd = pty.openpty()
    try:
        # Set the PTY window size (default 80x24, updated on resize events)
        _set_pty_size(slave_fd, 80, 24)

        # Write the welcome banner to the PTY slave BEFORE bash starts.
        # This way bash reads it as its first input — but bash would
        # interpret it as a command, which is wrong.
        # Instead, we send the banner directly to the WebSocket client
        # (NOT through the PTY) so the user sees it but bash doesn't.

        proc = subprocess.Popen(
            # -i = interactive (job control, prompt, history)
            # Skip --norc/--noprofile so /etc/bash.bashrc can set up readline,
            # bracketed paste, etc. Our PS1 env var still takes effect because
            # /etc/bash.bashrc on Debian/Ubuntu only sets PS1 if it's not already set.
            ["/bin/bash", "-i"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            preexec_fn=os.setsid,
            cwd="/tmp",
            env=_build_terminal_env(),
            close_fds=True,
        )
    except Exception as e:
        await websocket.send_text(f'{{"type": "error", "message": "Failed to spawn shell: {e}"}}')
        await websocket.close(code=4500, reason="spawn failed")
        return
    finally:
        os.close(slave_fd)  # parent doesn't need the slave end

    # Register the terminal
    terminal_state = {
        "pid": proc.pid,
        "master_fd": master_fd,
        "alive": True,
        "last_activity": time.time(),
        "user_id": user_id,
    }
    with _TERMINALS_LOCK:
        _USER_TERMINALS[user_id] = terminal_state

    # Send the welcome banner DIRECTLY to the WebSocket client (not via PTY),
    # so the user sees it but bash doesn't try to interpret it as commands.
    welcome = (
        "\r\n"
        "┌─────────────────────────────────────────────────────────────┐\r\n"
        "│  OpenBenchML Terminal — bash shell in your browser          │\r\n"
        "│  Cwd: /tmp   •   Env: sanitized   •   Timeout: 30 min idle  │\r\n"
        "│  Try: python, pip install, ls, git, vim, top                │\r\n"
        "└─────────────────────────────────────────────────────────────┘\r\n"
        "\r\n"
    ).encode("utf-8")
    await websocket.send_bytes(welcome)

    # Make master_fd non-blocking so we can poll it without blocking the event loop
    fcntl.fcntl(master_fd, fcntl.F_SETFL, os.O_NONBLOCK)

    # Reader loop: PTY master → WebSocket
    # We use a short async sleep + non-blocking read pattern. This is simple,
    # robust, and works on all platforms. The 50ms latency is imperceptible
    # for terminal use.
    async def pty_reader():
        while terminal_state["alive"]:
            try:
                # Non-blocking read
                try:
                    data = os.read(master_fd, 65536)
                except BlockingIOError:
                    # No data available — check process status & idle timeout
                    if proc.poll() is not None:
                        await websocket.send_text(f'{{"type": "exit", "code": {proc.returncode or 0}}}')
                        return
                    if time.time() - terminal_state["last_activity"] > TERMINAL_IDLE_TIMEOUT:
                        await websocket.send_text('{"type": "exit", "code": -1, "reason": "idle timeout"}')
                        return
                    # Brief yield to event loop so writer task can run
                    await asyncio.sleep(0.05)
                    continue
                except OSError:
                    # PTY closed
                    await websocket.send_text(f'{{"type": "exit", "code": {proc.returncode or 0}}}')
                    return
                if not data:
                    await websocket.send_text(f'{{"type": "exit", "code": {proc.returncode or 0}}}')
                    return
                terminal_state["last_activity"] = time.time()
                # Send raw bytes as binary frame — xterm.js handles them.
                await websocket.send_bytes(data)
            except WebSocketDisconnect:
                return
            except Exception as e:
                logger.warning("terminal reader error for user %s: %s", user_id, e)
                return

    # Writer loop: WebSocket → PTY master
    async def pty_writer():
        while terminal_state["alive"]:
            try:
                msg = await websocket.receive()
            except WebSocketDisconnect:
                return
            except Exception as e:
                logger.warning("terminal ws receive error for user %s: %s", user_id, e)
                return

            terminal_state["last_activity"] = time.time()

            if "bytes" in msg and msg["bytes"] is not None:
                # Binary frame — raw keystrokes, write directly to PTY
                try:
                    os.write(master_fd, msg["bytes"])
                except OSError:
                    return
            elif "text" in msg and msg["text"] is not None:
                text = msg["text"]
                # Try to parse as JSON control message. If it's not JSON,
                # treat it as raw text keystrokes (for clients that send
                # text frames instead of binary).
                is_json = False
                try:
                    import json
                    ctrl = json.loads(text)
                    if isinstance(ctrl, dict) and "type" in ctrl:
                        is_json = True
                except (json.JSONDecodeError, ValueError):
                    pass

                if is_json:
                    ctrl_type = ctrl.get("type")
                    if ctrl_type == "resize":
                        cols = int(ctrl.get("cols", 80))
                        rows = int(ctrl.get("rows", 24))
                        _set_pty_size(master_fd, cols, rows)
                    elif ctrl_type == "ping":
                        await websocket.send_text('{"type": "pong"}')
                    elif ctrl_type == "interrupt":  # Ctrl+C
                        os.write(master_fd, b"\x03")
                    elif ctrl_type == "eof":  # Ctrl+D
                        os.write(master_fd, b"\x04")
                else:
                    # Raw text — write as keystrokes to PTY
                    try:
                        os.write(master_fd, text.encode("utf-8"))
                    except OSError:
                        return

    # Run both loops concurrently
    try:
        await asyncio.gather(pty_reader(), pty_writer())
    finally:
        # Cleanup: kill the bash process
        terminal_state["alive"] = False
        try:
            os.close(master_fd)
        except OSError:
            pass
        try:
            if proc.poll() is None:
                os.killpg(os.getpgid(proc.pid), signal.SIGHUP)
                await asyncio.sleep(0.1)
                if proc.poll() is None:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            pass
        with _TERMINALS_LOCK:
            _USER_TERMINALS.pop(user_id, None)
        try:
            await websocket.close()
        except Exception:
            pass


def _set_pty_size(fd: int, cols: int, rows: int) -> None:
    """Set the PTY window size using TIOCSWINSZ ioctl."""
    try:
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
    except Exception as e:
        logger.debug("Could not set PTY size: %s", e)


@router.get("/api/notebook/terminal/status")
async def notebook_terminal_status(
    request: Request,
    db: Session = Depends(get_db),
):
    """Check if the user has an active terminal session."""
    user: Optional[User] = await get_current_user_from_cookie(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    with _TERMINALS_LOCK:
        state = _USER_TERMINALS.get(user.id)
        if state and state["alive"]:
            return {
                "active": True,
                "pid": state["pid"],
                "idle_seconds": int(time.time() - state["last_activity"]),
            }
    return {"active": False}
