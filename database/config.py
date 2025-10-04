"""
Database configuration and connection management
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import os

# Database URL - can be configured via environment variable
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///flight_search.db')

# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL query logging
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=3600,  # Recycle connections after 1 hour
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Get database session
    Usage:
        with get_db() as db:
            # do something with db
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database - create all tables
    """
    from .models.schema import Base
    Base.metadata.create_all(bind=engine)
    print("Database initialized successfully")


def drop_db():
    """
    Drop all tables - use with caution!
    """
    from .models.schema import Base
    Base.metadata.drop_all(bind=engine)
    print("All tables dropped")


def reset_db():
    """
    Reset database - drop and recreate all tables
    """
    drop_db()
    init_db()
    print("Database reset successfully")
