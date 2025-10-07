"""
Database models for Flight Search System
Based on tech spec: Low-Level Design for flight search with up to 2 hops
"""

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Date, ForeignKey, 
    Boolean, Index, UniqueConstraint, Text
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()


class Airport(Base):
    """
    Airport entity with IATA code, name, and timezone information
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
    """
    __tablename__ = 'carriers'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(3), unique=True, nullable=False, index=True)  # IATA code
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Carrier(code='{self.code}', name='{self.name}')>"


class Route(Base):
    """
    Route represents a DIRECT link between two airports (no connected routes)
    This stores only the direct flight path from source to destination
    """
    __tablename__ = 'routes'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_code = Column(String(3), ForeignKey('airports.code'), nullable=False)
    destination_code = Column(String(3), ForeignKey('airports.code'), nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    source = relationship("Airport", foreign_keys=[source_code])
    destination = relationship("Airport", foreign_keys=[destination_code])
    
    # Unique constraint for source-destination pair
    __table_args__ = (
        UniqueConstraint('source_code', 'destination_code', name='uq_route_source_dest'),
        Index('idx_route_source', 'source_code'),
        Index('idx_route_destination', 'destination_code'),
    )
    
    def __repr__(self):
        return f"<Route(source='{self.source_code}', destination='{self.destination_code}')>"


class Flight(Base):
    """
    Flight links a plane (identified by carrier + flight_number) with a route_id
    This represents a scheduled flight service on a specific route
    """
    __tablename__ = 'flights'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    route_id = Column(String(36), ForeignKey('routes.id'), nullable=False)
    carrier_code = Column(String(3), ForeignKey('carriers.code'), nullable=False)
    flight_number = Column(String(10), nullable=False)
    
    # Optional: Aircraft information
    aircraft_type = Column(String(50))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    route = relationship("Route")
    carrier = relationship("Carrier")
    
    # Unique constraint for carrier + flight_number + route
    __table_args__ = (
        UniqueConstraint('carrier_code', 'flight_number', 'route_id', name='uq_flight_carrier_number_route'),
        Index('idx_flight_carrier', 'carrier_code'),
        Index('idx_flight_route', 'route_id'),
    )
    
    def __repr__(self):
        return f"<Flight(carrier='{self.carrier_code}', number='{self.flight_number}', route_id='{self.route_id}')>"


class FlightInstance(Base):
    """
    FlightInstance represents a scheduled operating flight on a specific date/time
    This is an instance of a Flight (which is linked to a Route)
    Core entity for search operations
    """
    __tablename__ = 'flight_instances'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    flight_id = Column(String(36), ForeignKey('flights.id'), nullable=False)
    
    # Timing information (all in UTC)
    departure_time_utc = Column(DateTime, nullable=False, index=True)
    arrival_time_utc = Column(DateTime, nullable=False, index=True)
    
    # Service date (departure date in origin's local time)
    service_date = Column(Date, nullable=False, index=True)
    
    # Duration in minutes
    duration_minutes = Column(Integer)
    
    # Terminal information
    departure_terminal = Column(String(10))
    arrival_terminal = Column(String(10))
    
    # Operational status
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    flight = relationship("Flight")
    
    # Indexes for search operations
    # Note: We'll join with flight -> route to get source/destination
    __table_args__ = (
        Index('idx_flight_instance_flight_date', 'flight_id', 'service_date', 'departure_time_utc'),
        Index('idx_flight_instance_service_date', 'service_date'),
    )
    
    def __repr__(self):
        return f"<FlightInstance(flight_id='{self.flight_id}', date='{self.service_date}')>"


class Fare(Base):
    """
    Fare represents pricing information for a flight instance
    Simplified for search purposes - detailed fare rules handled separately
    """
    __tablename__ = 'fares'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    flight_instance_id = Column(String(36), ForeignKey('flight_instances.id'), nullable=True)
    
    # Fare identification
    fare_key = Column(String(500), unique=True, nullable=False, index=True)  # Opaque key for detailed fare lookup
    fare_class = Column(String(20))  # e.g., "ECONOMY", "BUSINESS"
    fare_brand = Column(String(50))  # e.g., "REGULAR", "SAVER", "ECO VALUE"
    fare_category = Column(String(20))  # e.g., "RETAIL", "CORPORATE"
    
    # Pricing (in smallest currency unit - paise for INR)
    currency = Column(String(3), default='INR')
    total_price = Column(Float, nullable=False)
    base_fare = Column(Float, nullable=False)
    total_tax = Column(Float, nullable=False)
    
    # Baggage allowance
    checkin_baggage_kg = Column(Integer)
    cabin_baggage_kg = Column(Integer)
    
    # Refundability
    is_refundable = Column(Boolean, default=False)
    is_partial_refundable = Column(Boolean, default=False)
    
    # Amenities
    has_free_meal = Column(Boolean, default=False)
    has_free_seat = Column(Boolean, default=False)
    
    # Availability
    seats_available = Column(Integer)
    
    # Timestamps
    valid_from = Column(DateTime)
    valid_until = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    flight_instance = relationship("FlightInstance")
    
    __table_args__ = (
        Index('idx_fare_flight_instance', 'flight_instance_id'),
        Index('idx_fare_key', 'fare_key'),
    )
    
    def __repr__(self):
        return f"<Fare(key='{self.fare_key[:20]}...', price={self.total_price})>"
