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
    max_results: int = Field(default=50, ge=1, le=100, description="Maximum results to return")
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

    class Config:
        json_schema_extra = {
            "example": {
                "origin": "DEL",
                "destination": "BOM",
                "date": "2025-10-10",
                "passengers": 1,
                "cabin": "economy",
                "max_hops": 2,
                "max_results": 50,
                "preferred_departure_time_window": {
                    "start": "00:00",
                    "end": "23:59"
                },
                "sort": "price"
            }
        }


class FlightLeg(BaseModel):
    """Individual flight leg in an itinerary"""
    carrier: str = Field(..., description="Carrier IATA code")
    flight_number: str = Field(..., description="Flight number")
    origin: str = Field(..., description="Origin airport IATA code")
    destination: str = Field(..., description="Destination airport IATA code")
    departure_time_utc: datetime = Field(..., description="Departure time in UTC")
    arrival_time_utc: datetime = Field(..., description="Arrival time in UTC")
    duration_minutes: int = Field(..., description="Flight duration in minutes")

    class Config:
        json_schema_extra = {
            "example": {
                "carrier": "6E",
                "flight_number": "6422",
                "origin": "DEL",
                "destination": "BOM",
                "departure_time_utc": "2025-10-10T08:00:00Z",
                "arrival_time_utc": "2025-10-10T10:15:00Z",
                "duration_minutes": 135
            }
        }


class Price(BaseModel):
    """Price information"""
    currency: str = Field(default="INR", description="Currency code")
    amount: float = Field(..., ge=0, description="Total price amount")

    class Config:
        json_schema_extra = {
            "example": {
                "currency": "INR",
                "amount": 5564.0
            }
        }


class Itinerary(BaseModel):
    """Complete itinerary with one or more flight legs"""
    id: str = Field(..., description="Unique itinerary ID")
    legs: List[FlightLeg] = Field(..., min_items=1, max_items=3, description="Flight legs (1-3)")
    stops: int = Field(..., ge=0, le=2, description="Number of stops")
    total_duration_minutes: int = Field(..., description="Total journey duration")
    price: Price = Field(..., description="Itinerary price")
    fare_key: str = Field(..., description="Opaque fare key for detailed fare lookup")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "legs": [
                    {
                        "carrier": "6E",
                        "flight_number": "6422",
                        "origin": "DEL",
                        "destination": "BOM",
                        "departure_time_utc": "2025-10-10T08:00:00Z",
                        "arrival_time_utc": "2025-10-10T10:15:00Z",
                        "duration_minutes": 135
                    }
                ],
                "stops": 0,
                "total_duration_minutes": 135,
                "price": {
                    "currency": "INR",
                    "amount": 5564.0
                },
                "fare_key": "fare_DEL_BOM_20251010_6E6422"
            }
        }


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

    class Config:
        json_schema_extra = {
            "example": {
                "search_id": "650e8400-e29b-41d4-a716-446655440001",
                "origin": "DEL",
                "destination": "BOM",
                "itineraries": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "legs": [
                            {
                                "carrier": "6E",
                                "flight_number": "6422",
                                "origin": "DEL",
                                "destination": "BOM",
                                "departure_time_utc": "2025-10-10T08:00:00Z",
                                "arrival_time_utc": "2025-10-10T10:15:00Z",
                                "duration_minutes": 135
                            }
                        ],
                        "stops": 0,
                        "total_duration_minutes": 135,
                        "price": {
                            "currency": "INR",
                            "amount": 5564.0
                        },
                        "fare_key": "fare_DEL_BOM_20251010_6E6422"
                    }
                ],
                "meta": {
                    "returned": 1,
                    "max_results": 50
                }
            }
        }


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[dict] = Field(default=None, description="Additional error details")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "VALIDATION_ERROR",
                "message": "Invalid airport code",
                "details": {
                    "field": "origin",
                    "value": "XYZ"
                }
            }
        }
