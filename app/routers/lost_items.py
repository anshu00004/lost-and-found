"""
Lost Items router — CRUD for items reported as lost.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_active_admin, get_current_user
from app.database import get_db

router = APIRouter(prefix="/lost-items", tags=["Lost Items"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_lost_item_or_404(item_id: int, db: Session) -> models.LostItem:
    item = db.get(models.LostItem, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lost item not found.")
    return item


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=schemas.LostItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Report a lost item",
)
def report_lost_item(
    payload: schemas.LostItemCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Report an item that you have lost. The item will be visible to all
    authenticated users so that someone who found it may file a claim.
    """
    item = models.LostItem(**payload.model_dump(), reporter_id=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


# ---------------------------------------------------------------------------
# List / Search
# ---------------------------------------------------------------------------

@router.get(
    "/",
    response_model=schemas.PaginatedResponse,
    summary="List / search lost items with pagination and filters",
)
def list_lost_items(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
    # Filters
    category: Optional[models.Category] = Query(None),
    status: Optional[models.ItemStatus] = Query(None),
    keyword: Optional[str] = Query(None, max_length=100),
    # Pagination
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    Return a paginated list of lost items.
    Supports filtering by category, status, and a full-text keyword search
    on title + description + location.
    """
    query = db.query(models.LostItem)

    if category:
        query = query.filter(models.LostItem.category == category)
    if status:
        query = query.filter(models.LostItem.status == status)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            or_(
                models.LostItem.title.ilike(like),
                models.LostItem.description.ilike(like),
                models.LostItem.location_lost.ilike(like),
            )
        )

    total = query.count()
    items = (
        query.order_by(models.LostItem.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return schemas.PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[schemas.LostItemSummary.model_validate(i) for i in items],
    )


# ---------------------------------------------------------------------------
# Read (single)
# ---------------------------------------------------------------------------

@router.get(
    "/{item_id}",
    response_model=schemas.LostItemResponse,
    summary="Get a lost item by ID",
)
def get_lost_item(
    item_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    return _get_lost_item_or_404(item_id, db)


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

@router.patch(
    "/{item_id}",
    response_model=schemas.LostItemResponse,
    summary="Update a lost item (owner or admin)",
)
def update_lost_item(
    item_id: int,
    payload: schemas.LostItemUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Update the details of a lost item. Only the original reporter or an admin
    may make changes.
    """
    item = _get_lost_item_or_404(item_id, db)
    if item.reporter_id != current_user.id and current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorised to modify this item.")

    update_data = payload.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(item, field, value)

    db.commit()
    db.refresh(item)
    return item


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@router.delete(
    "/{item_id}",
    response_model=schemas.MessageResponse,
    summary="Delete a lost item (owner or admin)",
)
def delete_lost_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    item = _get_lost_item_or_404(item_id, db)
    if item.reporter_id != current_user.id and current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorised to delete this item.")

    db.delete(item)
    db.commit()
    return schemas.MessageResponse(message="Lost item deleted successfully.")


# ---------------------------------------------------------------------------
# My lost items
# ---------------------------------------------------------------------------

@router.get(
    "/my/reports",
    response_model=List[schemas.LostItemSummary],
    summary="Get all lost items reported by the current user",
)
def my_lost_items(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.LostItem)
        .filter(models.LostItem.reporter_id == current_user.id)
        .order_by(models.LostItem.created_at.desc())
        .all()
    )
