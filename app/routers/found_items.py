"""
Found Items router — CRUD for items reported as found.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user
from app.database import get_db

router = APIRouter(prefix="/found-items", tags=["Found Items"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_found_item_or_404(item_id: int, db: Session) -> models.FoundItem:
    item = db.get(models.FoundItem, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Found item not found.")
    return item


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=schemas.FoundItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Report a found item",
)
def report_found_item(
    payload: schemas.FoundItemCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Report an item that you have found. The owner may see this listing and
    submit a claim to retrieve their belonging.
    """
    item = models.FoundItem(**payload.model_dump(), reporter_id=current_user.id)
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
    summary="List / search found items with pagination and filters",
)
def list_found_items(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
    category: Optional[models.Category] = Query(None),
    status: Optional[models.ItemStatus] = Query(None),
    keyword: Optional[str] = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    query = db.query(models.FoundItem)

    if category:
        query = query.filter(models.FoundItem.category == category)
    if status:
        query = query.filter(models.FoundItem.status == status)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            or_(
                models.FoundItem.title.ilike(like),
                models.FoundItem.description.ilike(like),
                models.FoundItem.location_found.ilike(like),
            )
        )

    total = query.count()
    items = (
        query.order_by(models.FoundItem.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return schemas.PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[schemas.FoundItemSummary.model_validate(i) for i in items],
    )


# ---------------------------------------------------------------------------
# Read (single)
# ---------------------------------------------------------------------------

@router.get(
    "/{item_id}",
    response_model=schemas.FoundItemResponse,
    summary="Get a found item by ID",
)
def get_found_item(
    item_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    return _get_found_item_or_404(item_id, db)


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

@router.patch(
    "/{item_id}",
    response_model=schemas.FoundItemResponse,
    summary="Update a found item (reporter or admin)",
)
def update_found_item(
    item_id: int,
    payload: schemas.FoundItemUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    item = _get_found_item_or_404(item_id, db)
    if item.reporter_id != current_user.id and current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorised to modify this item.")

    for field, value in payload.model_dump(exclude_none=True).items():
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
    summary="Delete a found item (reporter or admin)",
)
def delete_found_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    item = _get_found_item_or_404(item_id, db)
    if item.reporter_id != current_user.id and current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorised to delete this item.")

    db.delete(item)
    db.commit()
    return schemas.MessageResponse(message="Found item deleted successfully.")


# ---------------------------------------------------------------------------
# My found items
# ---------------------------------------------------------------------------

@router.get(
    "/my/reports",
    response_model=List[schemas.FoundItemSummary],
    summary="Get all found items reported by the current user",
)
def my_found_items(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.FoundItem)
        .filter(models.FoundItem.reporter_id == current_user.id)
        .order_by(models.FoundItem.created_at.desc())
        .all()
    )
