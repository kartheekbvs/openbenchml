"""
OpenBenchML Model Management Routes
======================================
Handles model upload, listing, detail views, deletion, and JSON API access.
All HTML routes require cookie-based authentication; API routes accept either
cookie or OAuth2 bearer tokens.
"""

import logging
from typing import Optional, List

from fastapi import APIRouter, Request, Depends, HTTPException, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session, joinedload

from app.database.db import get_db
from app.database.models import MLModel, User, BenchmarkJob, BenchmarkResult
from app.services.auth_service import oauth2_scheme
from app.services.upload_service import validate_model_file, save_uploaded_model, delete_model_file
from app.routes.auth import get_current_user_from_cookie
from app.config import templates, FRAMEWORKS

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── HTML Page Routes ─────────────────────────────────────────────────────────


@router.get("/models/upload", response_class=HTMLResponse)
async def model_upload_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Render the model upload form with framework choices.

    If the visitor is not authenticated they are redirected to the login
    page so that the upload form is only accessible to logged-in users.
    """
    user: Optional[User] = await get_current_user_from_cookie(request, db)
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse("upload.html", {
        "request": request,
        "user": user,
        "frameworks": FRAMEWORKS,
    })


@router.post("/models/upload", response_class=HTMLResponse)
async def model_upload_submit(
    request: Request,
    model_name: str = Form(...),
    description: str = Form(""),
    framework: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Handle model upload form submission.

    Validates the file extension, persists the file to disk via
    ``save_uploaded_model``, and creates a corresponding ``MLModel``
    database record.  On failure the upload form is re-rendered with
    an error message.
    """
    user: Optional[User] = await get_current_user_from_cookie(request, db)
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    # ── Validate framework selection ──────────────────────────────────────
    if framework not in FRAMEWORKS:
        return templates.TemplateResponse("upload.html", {
            "request": request,
            "user": user,
            "frameworks": FRAMEWORKS,
            "error": f"Invalid framework '{framework}'. Please select a valid option.",
        })

    # ── Validate file extension ───────────────────────────────────────────
    if not file.filename or not validate_model_file(file.filename):
        return templates.TemplateResponse("upload.html", {
            "request": request,
            "user": user,
            "frameworks": FRAMEWORKS,
            "error": "Invalid file type. Allowed: " + ", ".join(sorted(FRAMEWORKS)),
        })

    # ── Persist file and create DB record ─────────────────────────────────
    try:
        file_info = await save_uploaded_model(file, user.id)
        new_model = MLModel(
            user_id=user.id,
            model_name=model_name.strip(),
            description=description.strip() or None,
            framework=framework,
            file_path=file_info["file_path"],
            size_kb=file_info["size_kb"],
        )
        db.add(new_model)
        db.commit()
        logger.info(
            "Model uploaded: '%s' (id=%d) by user=%s",
            model_name, new_model.id, user.username,
        )
    except ValueError as exc:
        logger.warning("Upload validation error: %s", exc)
        return templates.TemplateResponse("upload.html", {
            "request": request,
            "user": user,
            "frameworks": FRAMEWORKS,
            "error": str(exc),
        })
    except Exception as exc:
        db.rollback()
        logger.error("Model upload failed for user=%s: %s", user.username, exc)
        return templates.TemplateResponse("upload.html", {
            "request": request,
            "user": user,
            "frameworks": FRAMEWORKS,
            "error": "Upload failed. Please try again.",
        })

    return RedirectResponse(url="/my-models", status_code=303)


@router.get("/my-models", response_class=HTMLResponse)
async def my_models_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Render a list of the current user's uploaded models.

    Each model row includes id, name, framework, size, creation date,
    and version.  Action buttons allow the user to delete a model or
    launch a new benchmark run.
    """
    user: Optional[User] = await get_current_user_from_cookie(request, db)
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    models: List[MLModel] = (
        db.query(MLModel)
        .filter(MLModel.user_id == user.id)
        .order_by(MLModel.created_at.desc())
        .all()
    )

    logger.debug("Fetched %d models for user=%s", len(models), user.username)

    return templates.TemplateResponse("my_models.html", {
        "request": request,
        "user": user,
        "models": models,
    })


@router.get("/models/{model_id}", response_class=HTMLResponse)
async def model_detail_page(
    request: Request,
    model_id: int,
    db: Session = Depends(get_db),
):
    """Render a detailed view for a single model.

    Displays full model metadata together with the model's benchmark
    history (jobs with their results).  Access is restricted to the
    model owner or anyone if the model is marked public.
    """
    user: Optional[User] = await get_current_user_from_cookie(request, db)
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    model: Optional[MLModel] = (
        db.query(MLModel)
        .options(joinedload(MLModel.owner))
        .filter(MLModel.id == model_id)
        .first()
    )
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")

    # Enforce access control: only owner can view private models
    if not model.is_public and model.user_id != user.id:
        raise HTTPException(status_code=403, detail="You do not have access to this model")

    # ── Benchmark history ─────────────────────────────────────────────────
    jobs: List[BenchmarkJob] = (
        db.query(BenchmarkJob)
        .options(joinedload(BenchmarkJob.result), joinedload(BenchmarkJob.dataset))
        .filter(BenchmarkJob.model_id == model_id)
        .order_by(BenchmarkJob.submitted_at.desc())
        .all()
    )

    logger.debug(
        "Model detail: id=%d, name='%s', jobs=%d",
        model_id, model.model_name, len(jobs),
    )

    return templates.TemplateResponse("model_detail.html", {
        "request": request,
        "user": user,
        "model": model,
        "jobs": jobs,
    })


@router.post("/models/{model_id}/delete")
async def model_delete(
    request: Request,
    model_id: int,
    db: Session = Depends(get_db),
):
    """Delete a model file and its database record.

    Only the model owner may delete a model.  The physical file is
    removed first; if that fails the database record is still deleted
    (a dangling file is preferable to an orphaned DB row the user
    cannot remove).
    """
    user: Optional[User] = await get_current_user_from_cookie(request, db)
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    model: Optional[MLModel] = (
        db.query(MLModel).filter(MLModel.id == model_id).first()
    )
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    if model.user_id != user.id:
        raise HTTPException(status_code=403, detail="You can only delete your own models")

    # ── Remove file from disk (best-effort) ───────────────────────────────
    try:
        delete_model_file(model.file_path)
    except ValueError as exc:
        logger.warning("Security issue deleting model file: %s", exc)
    except Exception as exc:
        logger.warning("Failed to delete model file for id=%d: %s", model_id, exc)

    # ── Remove database record (cascade handles jobs & leaderboard) ───────
    try:
        db.delete(model)
        db.commit()
        logger.info("Model deleted: id=%d by user=%s", model_id, user.username)
    except Exception as exc:
        db.rollback()
        logger.error("Failed to delete model id=%d: %s", model_id, exc)
        raise HTTPException(status_code=500, detail="Failed to delete model")

    return RedirectResponse(url="/my-models", status_code=303)


# ─── JSON API Routes ──────────────────────────────────────────────────────────


@router.get("/api/models", response_class=JSONResponse)
async def api_list_models(
    framework: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Return a JSON list of all public models.

    Accepts an optional ``framework`` query parameter to filter results
    to a single framework (e.g. ``?framework=pytorch``).
    """
    query = db.query(MLModel).filter(MLModel.is_public == True)

    if framework:
        if framework not in FRAMEWORKS:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown framework '{framework}'. Valid: {', '.join(FRAMEWORKS)}",
            )
        query = query.filter(MLModel.framework == framework)

    models: List[MLModel] = query.order_by(MLModel.created_at.desc()).all()

    return [
        {
            "id": m.id,
            "model_name": m.model_name,
            "framework": m.framework,
            "size_kb": m.size_kb,
            "version": m.version,
            "is_public": m.is_public,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in models
    ]


@router.get("/api/models/{model_id}", response_class=JSONResponse)
async def api_get_model(
    model_id: int,
    db: Session = Depends(get_db),
):
    """Return JSON details for a single model.

    Includes owner username and a summary of benchmark job statuses.
    Returns 404 if the model does not exist or is private.
    """
    model: Optional[MLModel] = (
        db.query(MLModel)
        .options(joinedload(MLModel.owner))
        .filter(MLModel.id == model_id, MLModel.is_public == True)
        .first()
    )
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")

    # ── Aggregate benchmark statistics ────────────────────────────────────
    job_stats = (
        db.query(BenchmarkJob.status)
        .filter(BenchmarkJob.model_id == model_id)
        .all()
    )
    status_counts = {}
    for (status_value,) in job_stats:
        status_counts[status_value] = status_counts.get(status_value, 0) + 1

    return {
        "id": model.id,
        "model_name": model.model_name,
        "description": model.description,
        "framework": model.framework,
        "size_kb": model.size_kb,
        "version": model.version,
        "is_public": model.is_public,
        "owner": model.owner.username if model.owner else None,
        "created_at": model.created_at.isoformat() if model.created_at else None,
        "updated_at": model.updated_at.isoformat() if model.updated_at else None,
        "benchmark_summary": status_counts,
    }
