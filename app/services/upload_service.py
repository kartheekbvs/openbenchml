"""
OpenBenchML Upload Service
===========================
Manages model file validation, persistence, and cleanup.
All file I/O is confined to the configured UPLOAD_DIR.
"""

import logging
import os
import shutil
from pathlib import Path
from typing import Dict

from fastapi import UploadFile

from app.config import UPLOAD_DIR, ALLOWED_EXTENSIONS, MAX_MODEL_SIZE_MB

logger = logging.getLogger(__name__)

# Maximum file size in bytes (computed once at import time)
_MAX_SIZE_BYTES = MAX_MODEL_SIZE_MB * 1024 * 1024


def validate_model_file(filename: str) -> bool:
    """Check whether a filename has an allowed model-file extension.

    The check is case-insensitive and compares the filename suffix against
    the ``ALLOWED_EXTENSIONS`` set from the application configuration
    (e.g. ``{".pkl", ".joblib", ".onnx", ".pt", ".h5", ".pb"}``).

    Args:
        filename: The original name of the uploaded file.

    Returns:
        ``True`` if the extension is allowed, ``False`` otherwise.
    """
    if not filename or not filename.strip():
        logger.warning("validate_model_file called with empty filename")
        return False

    # Extract suffix and normalise to lowercase for comparison
    ext = Path(filename).suffix.lower()
    if not ext:
        logger.warning("Filename '%s' has no extension", filename)
        return False

    if ext not in ALLOWED_EXTENSIONS:
        logger.warning(
            "File extension '%s' not in ALLOWED_EXTENSIONS: %s",
            ext,
            ALLOWED_EXTENSIONS,
        )
        return False

    logger.debug("Filename '%s' passed extension validation (%s)", filename, ext)
    return True


async def save_uploaded_model(file: UploadFile, user_id: int) -> Dict[str, object]:
    """Persist an uploaded model file to disk under the user's directory.

    The file is saved to ``UPLOAD_DIR / {user_id} / {filename}``.  Before
    writing the function validates the file extension and enforces the
    maximum file-size limit defined by ``MAX_MODEL_SIZE_MB``.  If the
    target directory does not exist it is created automatically.

    The file is written to a temporary ``*.tmp`` path first and then
    atomically renamed, which prevents leaving corrupt partial files in
    the event of an interruption.

    Args:
        file: The FastAPI ``UploadFile`` object from the request body.
        user_id: The ID of the user who owns the model.

    Returns:
        A dictionary with ``file_path`` (str) and ``size_kb`` (float).

    Raises:
        ValueError: If the file extension is not allowed.
        ValueError: If the file exceeds ``MAX_MODEL_SIZE_MB``.
        IOError: If the file cannot be written to disk.
    """
    original_filename = file.filename or "unknown"

    # ── Validate extension ─────────────────────────────────────────────────
    if not validate_model_file(original_filename):
        raise ValueError(
            f"File extension not allowed for '{original_filename}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # ── Prepare target directory ───────────────────────────────────────────
    user_dir = UPLOAD_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    target_path = user_dir / original_filename

    # ── Stream the file to disk with size enforcement ──────────────────────
    temp_path = target_path.with_suffix(target_path.suffix + ".tmp")
    total_bytes = 0

    try:
        with open(temp_path, "wb") as dest:
            while True:
                chunk = await file.read(1024 * 1024)  # 1 MiB chunks
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > _MAX_SIZE_BYTES:
                    # Clean up the partial file before raising
                    dest.close()
                    temp_path.unlink(missing_ok=True)
                    raise ValueError(
                        f"File exceeds maximum size of {MAX_MODEL_SIZE_MB} MB"
                    )
                dest.write(chunk)

        # Atomic rename from temp to final path
        temp_path.replace(target_path)

    except IOError as exc:
        temp_path.unlink(missing_ok=True)
        logger.error("Failed to write uploaded file to %s: %s", target_path, exc)
        raise IOError(f"Could not save file to disk: {exc}") from exc

    size_kb = round(total_bytes / 1024, 2)
    logger.info(
        "Saved model file '%s' for user_id=%d (%.2f KB)",
        original_filename,
        user_id,
        size_kb,
    )

    return {
        "file_path": str(target_path),
        "size_kb": size_kb,
    }


def delete_model_file(file_path: str) -> bool:
    """Remove a model file from disk.

    The function performs a safety check to ensure the resolved path is
    still inside ``UPLOAD_DIR`` before deletion, preventing path-traversal
    attacks.  If the file does not exist the function returns ``False``
    rather than raising.

    Args:
        file_path: Absolute or relative path to the model file.

    Returns:
        ``True`` if the file was removed, ``False`` if it did not exist
        or could not be removed.

    Raises:
        ValueError: If *file_path* resolves outside ``UPLOAD_DIR``.
    """
    if not file_path or not file_path.strip():
        logger.warning("delete_model_file called with empty path")
        return False

    resolved = Path(file_path).resolve()
    upload_root = UPLOAD_DIR.resolve()

    # ── Security: prevent path traversal ───────────────────────────────────
    try:
        resolved.relative_to(upload_root)
    except ValueError:
        logger.error(
            "Attempted to delete file outside UPLOAD_DIR: %s", resolved
        )
        raise ValueError("File path is outside the allowed upload directory")

    if not resolved.exists():
        logger.warning("File not found for deletion: %s", resolved)
        return False

    try:
        resolved.unlink()
        logger.info("Deleted model file: %s", resolved)
    except OSError as exc:
        logger.error("Failed to delete file %s: %s", resolved, exc)
        return False

    # ── Clean up empty parent directories ──────────────────────────────────
    parent = resolved.parent
    try:
        if parent != upload_root and not any(parent.iterdir()):
            parent.rmdir()
            logger.debug("Removed empty directory: %s", parent)
    except OSError:
        pass  # Non-critical; leave the empty directory

    return True
