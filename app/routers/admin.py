"""
Admin router — user management and platform statistics.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_active_admin
from app.database import get_db

router = APIRouter(prefix="/admin", tags=["Admin"])


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

@router.get(
    "/users",
    response_model=List[schemas.UserResponse],
    summary="List all registered users (admin only)",
)
def list_users(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_active_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    return (
        db.query(models.User)
        .order_by(models.User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )


@router.get(
    "/users/{user_id}",
    response_model=schemas.UserResponse,
    summary="Get a specific user (admin only)",
)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_active_admin),
):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user


@router.patch(
    "/users/{user_id}/deactivate",
    response_model=schemas.MessageResponse,
    summary="Deactivate a user account (admin only)",
)
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_active_admin),
):
    if user_id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate your own account.")
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    user.is_active = False
    db.commit()
    return schemas.MessageResponse(message=f"User {user.email} deactivated.")


@router.patch(
    "/users/{user_id}/activate",
    response_model=schemas.MessageResponse,
    summary="Re-activate a user account (admin only)",
)
def activate_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_active_admin),
):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    user.is_active = True
    db.commit()
    return schemas.MessageResponse(message=f"User {user.email} activated.")


@router.patch(
    "/users/{user_id}/promote",
    response_model=schemas.MessageResponse,
    summary="Grant admin role to a user (admin only)",
)
def promote_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_active_admin),
):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    user.role = models.UserRole.ADMIN
    db.commit()
    return schemas.MessageResponse(message=f"User {user.email} is now an admin.")


# ---------------------------------------------------------------------------
# Dashboard statistics
# ---------------------------------------------------------------------------

@router.get(
    "/stats",
    summary="Get platform-wide statistics (admin only)",
)
def get_stats(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_active_admin),
):
    """Returns aggregate counts for the admin dashboard."""
    total_users = db.query(models.User).count()
    total_lost = db.query(models.LostItem).count()
    total_found = db.query(models.FoundItem).count()
    total_claims = db.query(models.Claim).count()
    pending_claims = (
        db.query(models.Claim)
        .filter(models.Claim.status == models.ClaimStatus.PENDING)
        .count()
    )
    resolved_lost = (
        db.query(models.LostItem)
        .filter(models.LostItem.status == models.ItemStatus.RESOLVED)
        .count()
    )

    return {
        "users": {"total": total_users},
        "lost_items": {
            "total": total_lost,
            "resolved": resolved_lost,
            "open": db.query(models.LostItem)
                .filter(models.LostItem.status == models.ItemStatus.OPEN).count(),
        },
        "found_items": {
            "total": total_found,
            "resolved": db.query(models.FoundItem)
                .filter(models.FoundItem.status == models.ItemStatus.RESOLVED).count(),
            "open": db.query(models.FoundItem)
                .filter(models.FoundItem.status == models.ItemStatus.OPEN).count(),
        },
        "claims": {
            "total": total_claims,
            "pending": pending_claims,
            "approved": db.query(models.Claim)
                .filter(models.Claim.status == models.ClaimStatus.APPROVED).count(),
            "rejected": db.query(models.Claim)
                .filter(models.Claim.status == models.ClaimStatus.REJECTED).count(),
        },
    }
