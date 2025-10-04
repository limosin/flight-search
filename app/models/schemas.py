"""
FastAPI Request/Response Models for Flight Search API
Based on tech spec API contract
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from datetime import date as DateType
from enum import Enum


class CabinClass(str, Enum):
    """Cabin class options"""
    ECONOMY = "economy"
    PREMIUM_ECONOMY = "premium_economy"
    BUSINESS = "business"
    FIRST = "first"


class SortOption(str, Enum):
    """Sort options for search results"""
    PRICE = "price"
    DURATION = "duration"
    DEPARTURE_TIME = "departure_time"


class TimeWindow(BaseModel):
    """Preferred departure time window"""
    start: str = Field(..., pattern=r"^([0-1][0-9]|2[0-3]):[0-5][0-9]$", example="00:00")
    end: str = Field(..., pattern=r"^([0-1][0-9]|2[0-3]):[0-5][0-9]$", example="23:59")


class SearchRequest(BaseModel):
    """Flight search request model"""
    origin: str = Field(..., min_length=3, max_length=3, description="Origin airport IATA code")
    destination: str = Field(..., min_length=3, max_length=3, description="Destination airport IATA code")
    date: DateType = Field(..., description="Departure date (ISO 8601 format)")
    passengers: int = Field(default=1, ge=1, le=9, description="Number of passengers")
    cabin: Optional[CabinClass] = Field(default=CabinClass.ECONOMY, description="Cabin class")
    max_hops: int = Field(default=2, ge=0, le=2, description="Maximum number of stops (0-2)")
    max_results: int = Field(default=50, ge=1, le=250, description="Maximum results to return")
    preferred_departure_time_window: Optional[TimeWindow] = Field(
        default=None,
        description="Preferred departure time window"
    )
    sort: SortOption = Field(default=SortOption.PRICE, description="Sort option")

    @validator('origin', 'destination')
    def validate_iata_code(cls, v):
        """Validate IATA codes are uppercase"""
        return v.upper()

    @validator('destination')
    def validate_different_airports(cls, v, values):
        """Ensure origin and destination are different"""
        if 'origin' in values and v == values['origin']:
            raise ValueError('Origin and destination must be different')
        return v


class FlightLeg(BaseModel):
    """Individual flight leg in an itinerary"""
    carrier: str = Field(..., description="Carrier IATA code")
    flight_number: str = Field(..., description="Flight number")
    origin: str = Field(..., description="Origin airport IATA code")
    destination: str = Field(..., description="Destination airport IATA code")
    departure_time_utc: datetime = Field(..., description="Departure time in UTC")
    arrival_time_utc: datetime = Field(..., description="Arrival time in UTC")
    duration_minutes: int = Field(..., description="Flight duration in minutes")


class Price(BaseModel):
    """Price information"""
    currency: str = Field(default="INR", description="Currency code")
    amount: float = Field(..., ge=0, description="Total price amount")


class Itinerary(BaseModel):
    """Complete itinerary with one or more flight legs"""
    id: str = Field(..., description="Unique itinerary ID")
    legs: List[FlightLeg] = Field(..., min_items=1, max_items=3, description="Flight legs (1-3)")
    stops: int = Field(..., ge=0, le=2, description="Number of stops")
    total_duration_minutes: int = Field(..., description="Total journey duration")
    price: Price = Field(..., description="Itinerary price")
    fare_key: str = Field(..., description="Opaque fare key for detailed fare lookup")


class SearchMetadata(BaseModel):
    """Search result metadata"""
    returned: int = Field(..., description="Number of itineraries returned")
    max_results: int = Field(..., description="Maximum results requested")


class SearchResponse(BaseModel):
    """Flight search response model"""
    search_id: str = Field(..., description="Unique search ID")
    origin: str = Field(..., description="Origin airport IATA code")
    destination: str = Field(..., description="Destination airport IATA code")
    itineraries: List[Itinerary] = Field(..., description="List of found itineraries")
    meta: SearchMetadata = Field(..., description="Search metadata")


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[dict] = Field(default=None, description="Additional error details")
