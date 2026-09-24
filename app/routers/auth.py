"""
Authentication router — register, login, refresh, logout, profile management.
"""
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import (
    create_access_token, create_refresh_token, decode_token,
    get_current_user, hash_password, verify_password,
)
from app.config import get_settings
from app.database import get_db

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

@router.post(
    "/register",
    response_model=schemas.UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
def register(payload: schemas.UserRegister, db: Session = Depends(get_db)):
    """Create a new user. Email must be unique."""
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )
    user = models.User(
        full_name=payload.full_name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        phone=payload.phone,
        role=models.UserRole.USER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Swagger form_data.username me email bhejta hai
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    access_token = create_access_token(str(user.id))
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------

@router.post(
    "/refresh",
    response_model=schemas.TokenResponse,
    summary="Refresh the access token using a valid refresh token",
)
def refresh_token(payload: schemas.RefreshTokenRequest, db: Session = Depends(get_db)):
    """Exchange a non-revoked refresh token for a new access token."""
    token_record = (
        db.query(models.RefreshToken)
        .filter(models.RefreshToken.token == payload.refresh_token)
        .first()
    )
    if not token_record or token_record.revoked:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token.")

    if token_record.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has expired.")

    jwt_payload = decode_token(payload.refresh_token)
    if jwt_payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type.")

    user = db.get(models.User, token_record.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive.")

    # Rotate: revoke old, issue new
    token_record.revoked = True
    new_access = create_access_token(user.id, user.role.value)
    new_refresh = create_refresh_token(user.id)
    expires = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    db.add(models.RefreshToken(token=new_refresh, user_id=user.id, expires_at=expires))
    db.commit()

    return schemas.TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        expires_in=settings.access_token_expire_minutes * 60,
    )


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

@router.post(
    "/logout",
    response_model=schemas.MessageResponse,
    summary="Revoke the current refresh token (logout)",
)
def logout(
    payload: schemas.RefreshTokenRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Revoke the provided refresh token, effectively logging out the session."""
    token_record = (
        db.query(models.RefreshToken)
        .filter(
            models.RefreshToken.token == payload.refresh_token,
            models.RefreshToken.user_id == current_user.id,
        )
        .first()
    )
    if token_record and not token_record.revoked:
        token_record.revoked = True
        db.commit()
    return schemas.MessageResponse(message="Logged out successfully.")


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@router.get(
    "/me",
    response_model=schemas.UserResponse,
    summary="Get the authenticated user's profile",
)
def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.patch(
    "/me",
    response_model=schemas.UserResponse,
    summary="Update the authenticated user's profile",
)
def update_me(
    payload: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    update_data = payload.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post(
    "/change-password",
    response_model=schemas.MessageResponse,
    summary="Change the authenticated user's password",
)
def change_password(
    payload: schemas.ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect.")
    current_user.hashed_password = hash_password(payload.new_password)
    # Revoke all refresh tokens to force re-login everywhere
    db.query(models.RefreshToken).filter(
        models.RefreshToken.user_id == current_user.id
    ).update({"revoked": True})
    db.commit()
    return schemas.MessageResponse(message="Password changed successfully. Please log in again.")
