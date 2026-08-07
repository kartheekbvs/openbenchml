"""
OpenBenchML Comments & Notifications Routes
=============================================
Threaded discussions for models and competitions, plus a real-time
notification feed.
"""
import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Request, Depends, HTTPException, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session, joinedload

from app.database.db import get_db
from app.database.models import Comment, Competition, MLModel, User, Notification
from app.routes.auth import get_current_user_from_cookie
from app.config import templates

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── Comments ─────────────────────────────────────────────────────────────────


def _serialise_comment(c: Comment, depth: int = 0) -> dict:
    """Recursively serialise a comment and its replies."""
    return {
        "id": c.id,
        "author_id": c.author_id,
        "author_username": c.author.username if c.author else None,
        "author_avatar_url": c.author.avatar_url if c.author else None,
        "body": c.body,
        "is_pinned": c.is_pinned,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        "depth": depth,
        "replies": [_serialise_comment(r, depth + 1) for r in (c.replies or [])],
    }


@router.post("/comments")
async def create_comment(
    request: Request,
    body: str = Form(...),
    model_id: Optional[int] = Form(None),
    competition_id: Optional[int] = Form(None),
    parent_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    """Create a comment attached to a model or competition (or as a reply)."""
    user = await get_current_user_from_cookie(request, db)
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    if not body.strip():
        raise HTTPException(status_code=400, detail="Comment body cannot be empty")
    if not model_id and not competition_id:
        raise HTTPException(status_code=400, detail="Comment must attach to a model or competition")

    # Validate parent if provided
    if parent_id:
        parent = db.query(Comment).filter(Comment.id == parent_id).first()
        if parent is None:
            raise HTTPException(status_code=404, detail="Parent comment not found")

    comment = Comment(
        author_id=user.id,
        parent_id=parent_id,
        model_id=model_id,
        competition_id=competition_id,
        body=body.strip(),
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    logger.info(
        "Comment created: id=%d, author=%s, model_id=%s, competition_id=%s",
        comment.id, user.username, model_id, competition_id,
    )

    # If it's a reply, notify the parent comment's author
    if parent_id:
        parent = db.query(Comment).filter(Comment.id == parent_id).first()
        if parent and parent.author_id != user.id:
            try:
                n = Notification(
                    user_id=parent.author_id,
                    type="comment_reply",
                    title=f"{user.username} replied to your comment",
                    body=body.strip()[:200],
                    link=f"/models/{model_id}" if model_id else f"/competitions/{parent.competition_id}",
                )
                db.add(n)
                db.commit()
            except Exception as exc:
                db.rollback()
                logger.warning("Could not create reply notification: %s", exc)

    # Redirect back to the referring page
    referer = request.headers.get("referer", "/")
    return RedirectResponse(url=referer, status_code=303)


@router.get("/api/comments", response_class=JSONResponse)
async def api_list_comments(
    model_id: Optional[int] = Query(None),
    competition_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """List comments for a model or competition, including threaded replies."""
    if not model_id and not competition_id:
        raise HTTPException(status_code=400,
                            detail="Provide model_id or competition_id")

    query = db.query(Comment).filter(Comment.parent_id.is_(None))
    if model_id:
        query = query.filter(Comment.model_id == model_id)
    else:
        query = query.filter(Comment.competition_id == competition_id)

    comments = (
        query.options(joinedload(Comment.author))
        .order_by(Comment.is_pinned.desc(), Comment.created_at.asc())
        .all()
    )

    return [_serialise_comment(c) for c in comments]


@router.delete("/api/comments/{comment_id}")
async def api_delete_comment(
    comment_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Delete a comment (only the author or an admin can delete)."""
    user = await get_current_user_from_cookie(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")

    if comment.author_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorised to delete this comment")

    db.delete(comment)
    db.commit()
    return {"status": "deleted", "id": comment_id}


# ─── Notifications ────────────────────────────────────────────────────────────


@router.get("/api/notifications", response_class=JSONResponse)
async def api_list_notifications(
    request: Request,
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List the current user's notifications (most recent first)."""
    user = await get_current_user_from_cookie(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    query = db.query(Notification).filter(Notification.user_id == user.id)
    if unread_only:
        query = query.filter(Notification.is_read == False)

    notifs = query.order_by(Notification.created_at.desc()).limit(limit).all()
    return [
        {
            "id": n.id,
            "type": n.type,
            "title": n.title,
            "body": n.body,
            "link": n.link,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in notifs
    ]


@router.post("/api/notifications/{notification_id}/read")
async def api_mark_notification_read(
    notification_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Mark a single notification as read."""
    user = await get_current_user_from_cookie(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    n = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == user.id,
    ).first()
    if n is None:
        raise HTTPException(status_code=404, detail="Notification not found")

    n.is_read = True
    db.commit()
    return {"status": "read", "id": notification_id}


@router.post("/api/notifications/read-all")
async def api_mark_all_read(
    request: Request,
    db: Session = Depends(get_db),
):
    """Mark all the current user's notifications as read."""
    user = await get_current_user_from_cookie(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.is_read == False,
    ).update({Notification.is_read: True})
    db.commit()
    return {"status": "all_read"}


@router.get("/api/notifications/unread-count")
async def api_unread_count(
    request: Request,
    db: Session = Depends(get_db),
):
    """Return the count of unread notifications for the current user."""
    user = await get_current_user_from_cookie(request, db)
    if user is None:
        return {"count": 0}
    count = (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.is_read == False)
        .count()
    )
    return {"count": count}
