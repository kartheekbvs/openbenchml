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
            code, expected_var="model", timeout_seconds=60,
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


# ─── /notebook ────────────────────────────────────────────────────────────────

@router.get("/notebook", response_class=HTMLResponse)
async def notebook_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Render the in-browser Python notebook page.

    The notebook is a single-cell playground: paste code, hit Run,
    see stdout/stderr.  It's intentionally simpler than Jupyter —
    perfect for quick experimentation without leaving the platform.
    """
    user: Optional[User] = await get_current_user_from_cookie(request, db)
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    sample_code = (
        "# Welcome to the OpenBenchML notebook!\n"
        "# np, pd, sklearn, scipy are pre-imported for you.\n"
        "\n"
        "from sklearn.datasets import load_iris\n"
        "\n"
        "X, y = load_iris(return_X_y=True)\n"
        "print(f'Iris: {X.shape[0]} samples, {X.shape[1]} features')\n"
        "print(f'Classes: {sorted(set(y))}')\n"
        "print(f'Feature matrix dtype: {X.dtype}')\n"
        "print()\n"
        "print('First 3 rows:')\n"
        "print(X[:3])\n"
    )

    return templates.TemplateResponse("notebook.html", {
        "request": request,
        "user": user,
        "sample_code": sample_code,
    })


class NotebookRunRequest(BaseModel):
    """JSON schema for the notebook run endpoint."""
    code: str = Field(..., min_length=1, max_length=50_000)
    timeout_seconds: int = Field(default=30, ge=1, le=120)


@router.post("/api/notebook/run", response_class=JSONResponse)
async def notebook_run_api(
    payload: NotebookRunRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """JSON API: execute Python code and return captured output.

    Used by both the in-browser notebook UI and the CLI
    ``openbenchml notebook`` command.  Authentication via Bearer
    token (CLI) or cookie (browser).
    """
    user: Optional[User] = await get_current_user_from_cookie(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    result = run_code(payload.code, timeout_seconds=payload.timeout_seconds)

    # Strip the namespace from the response — it contains unpicklable
    # objects (sklearn estimators, numpy arrays) that JSON can't handle.
    # The notebook UI only needs stdout/stderr/ok anyway.
    return {
        "ok": result["ok"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "error": result["error"],
        "timed_out": result["timed_out"],
    }


class ConvertApiRequest(BaseModel):
    """JSON schema for the convert API endpoint."""
    model_name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    framework: str = Field(default="scikit-learn")
    code: str = Field(..., min_length=1, max_length=50_000)


@router.post("/api/convert", response_class=JSONResponse)
async def convert_api(
    payload: ConvertApiRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """JSON API: convert Python code → pickled MLModel.

    Returns the new model's id, name, framework, and size so CLI
    clients can immediately benchmark it.
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
            payload.code, expected_var="model", timeout_seconds=60,
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
        "stdout": meta["stdout"],
        "stderr": meta["stderr"],
        "metrics_in_code": {
            k: v for k, v in {
                "accuracy": meta.get("accuracy"),
                "f1_score": meta.get("f1_score"),
                "rmse": meta.get("rmse"),
                "r2_score": meta.get("r2_score"),
                "mae": meta.get("mae"),
            }.items() if v is not None
        },
    }
