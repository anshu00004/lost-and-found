"""
Database engine and session management.
Uses SQLAlchemy with a connection pool suited for MySQL.
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import get_settings


settings = get_settings()

# MySQL Database Connection Engine
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,       # Stale connections check karega
    pool_recycle=3600,        # Har 1 ghante me connection refresh karega
    pool_size=10,
    max_overflow=20,
    echo=settings.debug,
)




SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


def get_db():
    """
    FastAPI dependency that yields a database session
    and ensures it is closed after each request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all_tables():
    """Create all tables defined in models (used on startup)."""
    # Import models so their metadata is registered before create_all
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
