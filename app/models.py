"""
SQLAlchemy ORM models for the Lost & Found Portal.

Tables:
  - users           : Registered users / admins
  - lost_items      : Items reported as lost
  - found_items     : Items reported as found
  - claims          : Claims linking a lost item to a found item
  - refresh_tokens  : Active refresh tokens (for JWT revocation)
"""
import enum
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey,
    Integer, String, Text, func,
)
from sqlalchemy.orm import relationship

from app.database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ItemStatus(str, enum.Enum):
    OPEN = "open"           # Still missing / available
    MATCHED = "matched"     # Potential match found
    RESOLVED = "resolved"   # Returned / closed
    EXPIRED = "expired"     # Past deadline with no resolution


class ClaimStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class Category(str, enum.Enum):
    ELECTRONICS = "electronics"
    CLOTHING = "clothing"
    ACCESSORIES = "accessories"
    DOCUMENTS = "documents"
    BAGS = "bags"
    KEYS = "keys"
    WALLET = "wallet"
    JEWELRY = "jewelry"
    PET = "pet"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    # Columns Definition
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships (Doosri Tables Ke Sath Connection)
    lost_items = relationship("LostItem", back_populates="reporter", cascade="all, delete-orphan")
    found_items = relationship("FoundItem", back_populates="reporter", cascade="all, delete-orphan")
    claims = relationship("Claim", back_populates="claimant", foreign_keys="Claim.claimant_id")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"


class LostItem(Base):
    __tablename__ = "lost_items"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(Enum(Category), nullable=False)
    date_lost = Column(DateTime, nullable=False)
    location_lost = Column(String(300), nullable=False)
    reward_offered = Column(Boolean, default=False)
    reward_amount = Column(String(50), nullable=True)
    image_url = Column(String(500), nullable=True)
    status = Column(Enum(ItemStatus), default=ItemStatus.OPEN, nullable=False)
    reporter_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    reporter = relationship("User", back_populates="lost_items")
    claims = relationship("Claim", back_populates="lost_item", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<LostItem id={self.id} title={self.title!r}>"


class FoundItem(Base):
    __tablename__ = "found_items"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(Enum(Category), nullable=False)
    date_found = Column(DateTime, nullable=False)
    location_found = Column(String(300), nullable=False)
    storage_location = Column(String(300), nullable=True)
    image_url = Column(String(500), nullable=True)
    status = Column(Enum(ItemStatus), default=ItemStatus.OPEN, nullable=False)
    reporter_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    reporter = relationship("User", back_populates="found_items")
    claims = relationship("Claim", back_populates="found_item", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<FoundItem id={self.id} title={self.title!r}>"


class Claim(Base):
    __tablename__ = "claims"

    id = Column(Integer, primary_key=True, index=True) # Ensure primary key exists
    user_id = Column(Integer, ForeignKey("users.id"))
    lost_item_id = Column(Integer, ForeignKey("lost_items.id", ondelete="CASCADE"), nullable=False)
    found_item_id = Column(Integer, ForeignKey("found_items.id", ondelete="CASCADE"), nullable=False)
    claimant_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    proof_description = Column(Text, nullable=False)
    proof_image_url = Column(String(500), nullable=True)
    status = Column(Enum(ClaimStatus), default=ClaimStatus.PENDING, nullable=False)
    admin_notes = Column(Text, nullable=True)
    reviewed_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    lost_item = relationship("LostItem", back_populates="claims")
    found_item = relationship("FoundItem", back_populates="claims")
    claimant = relationship("User", back_populates="claims", foreign_keys=[claimant_id])
    
    # FIX HERE: reviewed_by ki jagah reviewed_by_id kar diya hai
    reviewer = relationship("User", foreign_keys=[reviewed_by_id])

    def __repr__(self) -> str:
        return f"<Claim id={self.id} status={self.status}>"


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(512), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="refresh_tokens")

    def __repr__(self) -> str:
        return f"<RefreshToken id={self.id} user_id={self.user_id}>"
