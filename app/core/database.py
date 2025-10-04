"""
Database dependency for FastAPI
"""

import sys
from pathlib import Path

# Add parent directory to path to import database module
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.config import SessionLocal, engine
from sqlalchemy.orm import Session


def get_db():
    """
    Database dependency for FastAPI routes
    Yields a database session and ensures it's closed after use
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
