"""
Claims router — submit and manage ownership claims.

Flow:
  1. A user submits a Claim linking a LostItem they own to a FoundItem.
  2. An admin reviews and either APPROVES or REJECTS the claim.
  3. On approval, both linked items are automatically marked as RESOLVED.
"""
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_active_admin, get_current_user
from app.database import get_db

router = APIRouter(prefix="/claims", tags=["Claims"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_claim_or_404(claim_id: int, db: Session) -> models.Claim:
    claim = db.get(models.Claim, claim_id)
    if not claim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found.")
    return claim


# ---------------------------------------------------------------------------
# Submit a claim (authenticated user)
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=schemas.ClaimResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a claim to retrieve your lost item",
)
def submit_claim(
    payload: schemas.ClaimCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Claim that a found item belongs to you.

    Rules:
    - The lost item must be OPEN or MATCHED.
    - The found item must be OPEN or MATCHED.
    - You must be the reporter of the lost item (proving ownership).
    - Duplicate claims by the same user for the same pair are rejected.
    """
    lost_item = db.get(models.LostItem, payload.lost_item_id)
    if not lost_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lost item not found.")

    found_item = db.get(models.FoundItem, payload.found_item_id)
    if not found_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Found item not found.")

    # Ownership check: claimant must have reported the lost item
    if lost_item.reporter_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only claim items that you reported as lost.",
        )

    # Status checks
    if lost_item.status not in (models.ItemStatus.OPEN, models.ItemStatus.MATCHED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Lost item status '{lost_item.status}' does not allow new claims.",
        )
    if found_item.status not in (models.ItemStatus.OPEN, models.ItemStatus.MATCHED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Found item status '{found_item.status}' does not allow new claims.",
        )

    # Duplicate check
    existing = (
        db.query(models.Claim)
        .filter(
            models.Claim.lost_item_id == payload.lost_item_id,
            models.Claim.found_item_id == payload.found_item_id,
            models.Claim.claimant_id == current_user.id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already submitted a claim for this pair of items.",
        )

    claim = models.Claim(
        user_id=current_user.id,
        lost_item_id=payload.lost_item_id,
        found_item_id=payload.found_item_id,
        claimant_id=current_user.id,
        proof_description=payload.proof_description,
        proof_image_url=payload.proof_image_url,
    )
    db.add(claim)

    # Mark both items as MATCHED so others know a potential match exists
    lost_item.status = models.ItemStatus.MATCHED
    found_item.status = models.ItemStatus.MATCHED

    db.commit()
    db.refresh(claim)
    return claim


# ---------------------------------------------------------------------------
# List claims (admin sees all; user sees own)
# ---------------------------------------------------------------------------

@router.get(
    "/",
    response_model=schemas.PaginatedResponse,
    summary="List claims — admin sees all, regular users see only their own",
)
def list_claims(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    claim_status: Optional[models.ClaimStatus] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    query = db.query(models.Claim)

    if current_user.role != models.UserRole.ADMIN:
        query = query.filter(models.Claim.claimant_id == current_user.id)

    if claim_status:
        query = query.filter(models.Claim.status == claim_status)

    total = query.count()
    items = (
        query.order_by(models.Claim.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return schemas.PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[schemas.ClaimResponse.model_validate(i) for i in items],
    )


# ---------------------------------------------------------------------------
# Get single claim
# ---------------------------------------------------------------------------

@router.get(
    "/{claim_id}",
    response_model=schemas.ClaimResponse,
    summary="Get a claim by ID",
)
def get_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    claim = _get_claim_or_404(claim_id, db)
    if claim.claimant_id != current_user.id and current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorised to view this claim.")
    return claim


# ---------------------------------------------------------------------------
# Review claim (admin only)
# ---------------------------------------------------------------------------

@router.patch(
    "/{claim_id}/review",
    response_model=schemas.ClaimResponse,
    summary="Approve or reject a claim (admin only)",
)
def review_claim(
    claim_id: int,
    payload: schemas.ClaimReview,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_active_admin),
):
    """
    Admin-only endpoint to approve or reject a pending claim.

    - **APPROVED**: Both the lost item and found item are marked RESOLVED.
      All other pending claims on those items are automatically REJECTED.
    - **REJECTED**: If no other active claims exist for the linked items,
      their status reverts to OPEN.
    """
    claim = _get_claim_or_404(claim_id, db)

    if claim.status != models.ClaimStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Claim is already '{claim.status}' and cannot be reviewed again.",
        )

    if payload.status not in (models.ClaimStatus.APPROVED, models.ClaimStatus.REJECTED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Review status must be either 'approved' or 'rejected'.",
        )

    claim.status = payload.status
    claim.admin_notes = payload.admin_notes
    claim.reviewed_by_id = admin.id
    claim.reviewed_at = datetime.now(timezone.utc)

    if payload.status == models.ClaimStatus.APPROVED:
        # Resolve both items
        claim.lost_item.status = models.ItemStatus.RESOLVED
        claim.found_item.status = models.ItemStatus.RESOLVED

        # Reject all other pending claims on these items
        (
            db.query(models.Claim)
            .filter(
                models.Claim.id != claim_id,
                models.Claim.status == models.ClaimStatus.PENDING,
                (
                    models.Claim.lost_item_id == claim.lost_item_id
                ) | (
                    models.Claim.found_item_id == claim.found_item_id
                ),
            )
            .update(
                {
                    "status": models.ClaimStatus.REJECTED,
                    "admin_notes": "Auto-rejected: another claim was approved.",
                },
                synchronize_session=False,
            )
        )

    elif payload.status == models.ClaimStatus.REJECTED:
        # If no other active (pending/approved) claims exist, revert items to OPEN
        other_active = (
            db.query(models.Claim)
            .filter(
                models.Claim.id != claim_id,
                models.Claim.status.in_([models.ClaimStatus.PENDING, models.ClaimStatus.APPROVED]),
                models.Claim.lost_item_id == claim.lost_item_id,
            )
            .count()
        )
        if other_active == 0:
            claim.lost_item.status = models.ItemStatus.OPEN

        other_active_found = (
            db.query(models.Claim)
            .filter(
                models.Claim.id != claim_id,
                models.Claim.status.in_([models.ClaimStatus.PENDING, models.ClaimStatus.APPROVED]),
                models.Claim.found_item_id == claim.found_item_id,
            )
            .count()
        )
        if other_active_found == 0:
            claim.found_item.status = models.ItemStatus.OPEN

    db.commit()
    db.refresh(claim)
    return claim


# ---------------------------------------------------------------------------
# Delete / withdraw a claim (claimant only, while PENDING)
# ---------------------------------------------------------------------------

@router.delete(
    "/{claim_id}",
    response_model=schemas.MessageResponse,
    summary="Withdraw a pending claim (claimant only)",
)
def withdraw_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    claim = _get_claim_or_404(claim_id, db)
    if claim.claimant_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorised to withdraw this claim.")
    if claim.status != models.ClaimStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PENDING claims can be withdrawn.",
        )

    db.delete(claim)
    db.commit()
    return schemas.MessageResponse(message="Claim withdrawn successfully.")


# ---------------------------------------------------------------------------
# Claim status endpoint (lightweight — for polling)
# ---------------------------------------------------------------------------

@router.get(
    "/{claim_id}/status",
    response_model=schemas.ClaimSummary,
    summary="Get the current status of a claim (lightweight)",
)
def get_claim_status(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Lightweight endpoint for polling claim status.
    Returns only claim ID, linked item IDs, status, and timestamp.
    """
    claim = _get_claim_or_404(claim_id, db)
    if claim.claimant_id != current_user.id and current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorised.")
    return claim
