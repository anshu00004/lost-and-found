"""
Pydantic v2 schemas for request validation and response serialization.
"""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models import Category, ClaimStatus, ItemStatus, UserRole


# ---------------------------------------------------------------------------
# Auth Schemas
# ---------------------------------------------------------------------------

class UserRegister(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100, examples=["Jane Doe"])
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    phone: Optional[str] = Field(None, max_length=20, examples=["+91-9876543210"])

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        return v


# ---------------------------------------------------------------------------
# User Schemas
# ---------------------------------------------------------------------------

class UserBase(BaseModel):
    full_name: str
    email: EmailStr
    phone: Optional[str] = None


class UserResponse(UserBase):
    id: int
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)


# ---------------------------------------------------------------------------
# Lost Item Schemas
# ---------------------------------------------------------------------------

class LostItemCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10)
    category: Category
    date_lost: datetime
    location_lost: str = Field(..., min_length=3, max_length=300)
    reward_offered: bool = False
    reward_amount: Optional[str] = Field(None, max_length=50)
    image_url: Optional[str] = Field(None, max_length=500)

    @field_validator("reward_amount")
    @classmethod
    def reward_required_if_offered(cls, v, info):
        if info.data.get("reward_offered") and not v:
            raise ValueError("reward_amount is required when reward_offered is True.")
        return v


class LostItemUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = Field(None, min_length=10)
    category: Optional[Category] = None
    date_lost: Optional[datetime] = None
    location_lost: Optional[str] = Field(None, min_length=3, max_length=300)
    reward_offered: Optional[bool] = None
    reward_amount: Optional[str] = Field(None, max_length=50)
    image_url: Optional[str] = Field(None, max_length=500)
    status: Optional[ItemStatus] = None


class LostItemResponse(BaseModel):
    id: int
    title: str
    description: str
    category: Category
    date_lost: datetime
    location_lost: str
    reward_offered: bool
    reward_amount: Optional[str] = None
    image_url: Optional[str] = None
    status: ItemStatus
    reporter_id: int
    reporter: UserResponse
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LostItemSummary(BaseModel):
    id: int
    title: str
    category: Category
    location_lost: str
    date_lost: datetime
    status: ItemStatus
    reward_offered: bool
    image_url: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Found Item Schemas
# ---------------------------------------------------------------------------

class FoundItemCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10)
    category: Category
    date_found: datetime
    location_found: str = Field(..., min_length=3, max_length=300)
    storage_location: Optional[str] = Field(None, max_length=300)
    image_url: Optional[str] = Field(None, max_length=500)


class FoundItemUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = Field(None, min_length=10)
    category: Optional[Category] = None
    date_found: Optional[datetime] = None
    location_found: Optional[str] = Field(None, min_length=3, max_length=300)
    storage_location: Optional[str] = Field(None, max_length=300)
    image_url: Optional[str] = Field(None, max_length=500)
    status: Optional[ItemStatus] = None


class FoundItemResponse(BaseModel):
    id: int
    title: str
    description: str
    category: Category
    date_found: datetime
    location_found: str
    storage_location: Optional[str] = None
    image_url: Optional[str] = None
    status: ItemStatus
    reporter_id: int
    reporter: UserResponse
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class FoundItemSummary(BaseModel):
    id: int
    title: str
    category: Category
    location_found: str
    date_found: datetime
    status: ItemStatus
    image_url: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Claim Schemas
# ---------------------------------------------------------------------------

class ClaimCreate(BaseModel):
    lost_item_id: int
    found_item_id: int
    proof_description: str = Field(..., min_length=20)
    proof_image_url: Optional[str] = Field(None, max_length=500)


class ClaimReview(BaseModel):
    status: ClaimStatus
    admin_notes: Optional[str] = Field(None, max_length=1000)


class ClaimResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    lost_item_id: int
    found_item_id: int
    claimant_id: int
    proof_description: str
    proof_image_url: Optional[str] = None
    status: ClaimStatus
    admin_notes: Optional[str] = None
    reviewed_by_id: Optional[int] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Nested
    lost_item: LostItemSummary
    found_item: FoundItemSummary
    claimant: UserResponse

    model_config = {"from_attributes": True}


class ClaimSummary(BaseModel):
    id: int
    lost_item_id: int
    found_item_id: int
    status: ClaimStatus
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list


# ---------------------------------------------------------------------------
# Generic Message
# ---------------------------------------------------------------------------

class MessageResponse(BaseModel):
    message: str
