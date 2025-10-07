"""
Database models for Flight Search System - Reference Data Only
Flight search data is now stored in Memgraph graph database.
This module retains only reference data models (Airport, Carrier) for legacy compatibility.
"""

from sqlalchemy import (
    Column, String, Integer, DateTime
)
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()


class Airport(Base):
    """
    Airport entity with IATA code, name, and timezone information
    Note: This is kept for legacy compatibility. Flight search uses Memgraph.
    """
    __tablename__ = 'airports'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(3), unique=True, nullable=False, index=True)  # IATA code
    name = Column(String(255), nullable=False)
    city = Column(String(100))
    country = Column(String(100))
    country_code = Column(String(2))
    timezone = Column(String(50))  # e.g., "Asia/Kolkata"
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Airport(code='{self.code}', name='{self.name}', city='{self.city}')>"


class Carrier(Base):
    """
    Airline/Carrier entity with IATA code and name
    Note: This is kept for legacy compatibility. Flight search uses Memgraph.
    """
    __tablename__ = 'carriers'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(3), unique=True, nullable=False, index=True)  # IATA code
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Carrier(code='{self.code}', name='{self.name}')>"


# Flight-related models (Route, Flight, FlightInstance, Fare) have been removed.
# All flight search functionality now uses Memgraph graph database.
# See database/memgraph_config.py and app/services/search_service_memgraph.py
