"""
OpenBenchML Convert & Notebook Routes
=======================================
Two student-friendly features powered by the same code-runner service:

* **/convert**     — user pastes Python code that *trains a model* and
                      assigns it to a variable named ``model``.  The
                      platform executes the code, pickles the resulting
                      model, and registers it as an ``MLModel`` ready
                      for benchmarking.  No local Python install needed.

* **/notebook**    — a free-form in-browser Python playground.  Useful
                      for exploring the built-in datasets, prototyping
                      features, or just learning sklearn / numpy.  The
                      output (stdout/stderr/result) is returned to the
                      browser.

Both routes come in two flavours:

  * HTML form flow for the web UI (cookie auth)
  * JSON API flow for the CLI / programmatic clients (Bearer auth)
"""

import logging
from typing import Optional

from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import templates, UPLOAD_DIR, FRAMEWORKS
from app.database.db import get_db
from app.database.models import User, MLModel
from app.routes.auth import get_current_user_from_cookie
from app.services.code_runner_service import (
    run_code,
    code_to_pickled_model,
    save_pickled_model,
    inspect_pickled_bytes,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── /convert ─────────────────────────────────────────────────────────────────

@router.get("/convert", response_class=HTMLResponse)
async def convert_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Render the code-to-model converter page.

    Provides a code editor pre-populated with a working sklearn example
    so first-time users can hit "Convert" immediately and see how it
    works.  No file upload required.
    """
    user: Optional[User] = await get_current_user_from_cookie(request, db)
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    # Pre-populated example code — kept short & beginner-friendly
    sample_code = (
        "from sklearn.datasets import load_iris\n"
        "from sklearn.ensemble import RandomForestClassifier\n"
        "from sklearn.model_selection import train_test_split\n"
        "\n"
        "X, y = load_iris(return_X_y=True)\n"
        "X_train, X_test, y_train, y_test = train_test_split(\n"
        "    X, y, test_size=0.2, random_state=42, stratify=y\n"
        ")\n"
        "\n"
        "model = RandomForestClassifier(n_estimators=50, random_state=42)\n"
        "model.fit(X_train, y_train)\n"
        "\n"
        "acc = model.score(X_test, y_test)\n"
        "print(f'Training complete — test accuracy = {acc:.4f}')\n"
    )

    return templates.TemplateResponse("convert.html", {
        "request": request,
        "user": user,
        "frameworks": FRAMEWORKS,
        "sample_code": sample_code,
    })


@router.post("/convert", response_class=HTMLResponse)
async def convert_submit(
    request: Request,
    model_name: str = Form(...),
    description: str = Form(""),
    framework: str = Form("scikit-learn"),
    code: str = Form(...),
    db: Session = Depends(get_db),
):
    """HTML form handler: convert Python code → pickled MLModel.

    On success redirects to the new model's detail page.  On failure
    re-renders the convert page with the error message + the user's
    code preserved so they don't lose their work.
    """
    user: Optional[User] = await get_current_user_from_cookie(request, db)
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    if framework not in FRAMEWORKS:
        # Auto-detection will run anyway, but if the user explicitly
        # picked an invalid option we tell them.
        return templates.TemplateResponse("convert.html", {
            "request": request, "user": user, "frameworks": FRAMEWORKS,
            "sample_code": code,
            "error": f"Invalid framework '{framework}'. Valid: {', '.join(FRAMEWORKS)}",
        })

    try:
        pickled_bytes, meta = code_to_pickled_model(
            code, expected_var="model", timeout_seconds=300,
        )
    except ValueError as exc:
        logger.warning("Convert failed for user=%s: %s", user.username, exc)
        return templates.TemplateResponse("convert.html", {
            "request": request, "user": user, "frameworks": FRAMEWORKS,
            "sample_code": code,
            "error": str(exc),
        })
    except Exception as exc:
        logger.exception("Unexpected error in /convert for user=%s", user.username)
        return templates.TemplateResponse("convert.html", {
            "request": request, "user": user, "frameworks": FRAMEWORKS,
            "sample_code": code,
            "error": f"Unexpected error: {exc}",
        })

    # ── Persist the pickled model and create the DB row ──────────────────
    file_path, size_kb = save_pickled_model(
        pickled_bytes, user.id, model_name.strip(), UPLOAD_DIR,
    )

    # The auto-detected framework wins unless the user explicitly set
    # something different *and* the auto-detection was inconclusive
    # (i.e. fell back to scikit-learn).
    final_framework = framework if framework else meta["framework"]

    new_model = MLModel(
        user_id=user.id,
        model_name=model_name.strip(),
        description=description.strip() or None,
        framework=final_framework,
        file_path=file_path,
        size_kb=size_kb,
    )
    db.add(new_model)
    db.commit()
    db.refresh(new_model)

    logger.info(
        "Converted code → model '%s' (id=%d, framework=%s, %d KB) for user=%s",
        new_model.model_name, new_model.id, new_model.framework, size_kb, user.username,
    )

    return RedirectResponse(url=f"/models/{new_model.id}", status_code=303)


# NOTE: /notebook (GET) and /api/notebook/run (POST) were moved to
# app/routes/notebook.py in v2.0 — the new module provides a Colab-style
# multi-cell notebook with persistent sessions, shell commands (!pip install),
# package recommendations, and matplotlib figure capture. See notebook.py.


class ConvertApiRequest(BaseModel):
    """JSON schema for the convert API endpoint."""
    model_name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    framework: str = Field(default="scikit-learn")
    code: str = Field(..., min_length=1, max_length=50_000)
    timeout_seconds: int = Field(default=300, ge=10, le=600)


@router.post("/api/convert", response_class=JSONResponse)
async def convert_api(
    payload: ConvertApiRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """JSON API: convert Python code → pickled MLModel.

    Returns the new model's id, name, framework, and size so CLI
    clients can immediately benchmark it.

    The default timeout is 300s (5 min) — bumped from the old 60s so
    that real-world training (RandomForest on California Housing, etc.)
    succeeds on Render's free tier. CLI clients can request up to 600s.
    """
    user: Optional[User] = await get_current_user_from_cookie(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    if payload.framework not in FRAMEWORKS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid framework '{payload.framework}'. Valid: {', '.join(FRAMEWORKS)}",
        )

    try:
        pickled_bytes, meta = code_to_pickled_model(
            payload.code,
            expected_var="model",
            timeout_seconds=payload.timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected error in /api/convert")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}")

    file_path, size_kb = save_pickled_model(
        pickled_bytes, user.id, payload.model_name.strip(), UPLOAD_DIR,
    )

    final_framework = payload.framework or meta["framework"]
    new_model = MLModel(
        user_id=user.id,
        model_name=payload.model_name.strip(),
        description=payload.description.strip() or None,
        framework=final_framework,
        file_path=file_path,
        size_kb=size_kb,
    )
    db.add(new_model)
    db.commit()
    db.refresh(new_model)

    logger.info(
        "API convert → model '%s' (id=%d) for user=%s",
        new_model.model_name, new_model.id, user.username,
    )

    return {
        "id": new_model.id,
        "model_name": new_model.model_name,
        "framework": new_model.framework,
        "size_kb": new_model.size_kb,
        "detected_framework": meta["framework"],
        "model_class": meta["model_class"],
        "task_type": meta.get("task_type", "unknown"),
        "is_fitted": meta.get("is_fitted", True),
        "params": meta.get("params", {}),
        "stdout": meta["stdout"],
        "stderr": meta["stderr"],
        "metrics_in_code": {
            k: v for k, v in {
                "accuracy": meta.get("accuracy"),
                "precision": meta.get("precision"),
                "recall": meta.get("recall"),
                "f1_score": meta.get("f1_score"),
                "auc_roc": meta.get("auc_roc"),
                "log_loss": meta.get("log_loss"),
                "rmse": meta.get("rmse"),
                "mse": meta.get("mse"),
                "r2_score": meta.get("r2_score"),
                "mae": meta.get("mae"),
                "mape": meta.get("mape"),
            }.items() if v is not None
        },
    }


# ─── /api/convert/upload-pickle ──────────────────────────────────────────────
#
# This endpoint powers the Pyodide (in-browser) convert path. The browser:
#   1. Loads Pyodide + numpy/pandas/sklearn via loadPackage.
#   2. Trains the model in-browser (no server timeout — the user's tab
#      can run as long as needed).
#   3. Pickles the trained `model` variable in-browser using joblib.
#   4. Base64-encodes the pickle bytes and POSTs them here.
# The server inspects the pickle (recovers model_class + framework),
# saves the bytes to disk, and creates the MLModel DB row.
#
# This bypasses the 300s server timeout entirely — useful for heavy
# training jobs (RandomForestRegressor on California Housing, XGBoost
# with n_estimators=500, etc.) that the user wants to run on their
# own machine via the browser.


class ConvertUploadPickleRequest(BaseModel):
    """JSON schema for the upload-pickle endpoint."""
    model_name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    framework: str = Field(default="scikit-learn")
    pickle_base64: str = Field(..., min_length=1)
    # Optional metadata from the browser (model_class, framework) — used
    # as a hint but always re-verified server-side via inspect_pickled_bytes.
    model_class_hint: str | None = Field(default=None, max_length=200)
    stdout: str = Field(default="", max_length=20_000)
    stderr: str = Field(default="", max_length=20_000)
    metrics: dict = Field(default_factory=dict)


@router.post("/api/convert/upload-pickle", response_class=JSONResponse)
async def convert_upload_pickle_api(
    payload: ConvertUploadPickleRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """JSON API: save a browser-trained pickled model.

    Used by the Pyodide path on the /convert page. The browser trains
    the model in Pyodide, pickles it, base64-encodes the bytes, and
    uploads them here. The server inspects the pickle to recover the
    framework + model_class, saves the bytes, and creates the MLModel.

    Authentication: Bearer token (cookie or Authorization header).

    Returns the new model's id, name, framework, and size — same
    shape as /api/convert.
    """
    import base64

    user: Optional[User] = await get_current_user_from_cookie(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    if payload.framework not in FRAMEWORKS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid framework '{payload.framework}'. Valid: {', '.join(FRAMEWORKS)}",
        )

    # Decode the base64 pickle into raw bytes.
    try:
        pickled_bytes = base64.b64decode(payload.pickle_base64, validate=True)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid base64 pickle payload: {exc}",
        )

    if len(pickled_bytes) < 16:
        raise HTTPException(
            status_code=400,
            detail=f"Pickle payload is too small ({len(pickled_bytes)} bytes) — "
                   f"did the browser-side code actually train a model?",
        )

    if len(pickled_bytes) > 200 * 1024 * 1024:  # 200 MB cap
        raise HTTPException(
            status_code=413,
            detail=f"Pickle payload too large ({len(pickled_bytes)} bytes > 200 MB).",
        )

    # Inspect the pickle to recover model_class + framework.
    meta = inspect_pickled_bytes(pickled_bytes)

    # Save to disk.
    file_path, size_kb = save_pickled_model(
        pickled_bytes, user.id, payload.model_name.strip(), UPLOAD_DIR,
    )

    # If inspect_pickled_bytes succeeded, use the recovered framework.
    # Otherwise fall back to the user-supplied one.
    final_framework = meta["framework"] if meta["ok"] else payload.framework

    new_model = MLModel(
        user_id=user.id,
        model_name=payload.model_name.strip(),
        description=payload.description.strip() or None,
        framework=final_framework,
        file_path=file_path,
        size_kb=size_kb,
    )
    db.add(new_model)
    db.commit()
    db.refresh(new_model)

    logger.info(
        "API upload-pickle → model '%s' (id=%d, framework=%s, class=%s, %d KB) for user=%s",
        new_model.model_name, new_model.id, final_framework,
        meta.get("model_class"), size_kb, user.username,
    )

    return {
        "id": new_model.id,
        "model_name": new_model.model_name,
        "framework": new_model.framework,
        "size_kb": new_model.size_kb,
        "detected_framework": meta["framework"],
        "model_class": meta.get("model_class") or payload.model_class_hint or "Unknown",
        "task_type": meta.get("task_type", "unknown"),
        "is_fitted": meta.get("is_fitted", True),
        "params": meta.get("params", {}),
        "stdout": payload.stdout,
        "stderr": payload.stderr,
        "metrics_in_code": {
            k: v for k, v in payload.metrics.items() if v is not None
        },
        "engine": "pyodide-browser",
    }

