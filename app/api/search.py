"""
Flight Search API endpoints
Implements the API contract from tech spec
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.models import (
    SearchRequest, SearchResponse, SearchMetadata, ErrorResponse
)
from app.core import get_db, settings
from app.services import FlightSearchService

router = APIRouter(prefix="/search", tags=["search"])


@router.post(
    "",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        422: {"model": ErrorResponse, "description": "No itineraries found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Search for flights",
    description="Search for flight itineraries between origin and destination with up to 2 hops"
)
async def search_flights(
    request: SearchRequest,
    db: Session = Depends(get_db)
) -> SearchResponse:
    """
    Search for flights based on criteria
    
    - **origin**: Origin airport IATA code (3 letters)
    - **destination**: Destination airport IATA code (3 letters)
    - **date**: Departure date (ISO 8601 format)
    - **passengers**: Number of passengers (1-9)
    - **cabin**: Cabin class (economy, premium_economy, business, first)
    - **max_hops**: Maximum number of stops (0-2)
    - **max_results**: Maximum results to return (1-100)
    - **preferred_departure_time_window**: Optional time window for departure
    - **sort**: Sort option (price, duration, departure_time)
    
    Returns a list of itineraries matching the search criteria.
    """
    try:
        # Initialize search service
        search_service = FlightSearchService(db)
        
        # Perform search
        itineraries = search_service.search(
            origin=request.origin,
            destination=request.destination,
            search_date=request.date,
            max_hops=request.max_hops,
            max_results=request.max_results
        )
        
        # Sort results
        if request.sort == "price":
            itineraries.sort(key=lambda x: x.price.amount)
        elif request.sort == "duration":
            itineraries.sort(key=lambda x: x.total_duration_minutes)
        elif request.sort == "departure_time":
            itineraries.sort(key=lambda x: x.legs[0].departure_time_utc)
        
        # Check if any results found
        if not itineraries:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "NO_RESULTS",
                    "message": f"No itineraries found for {request.origin} to {request.destination} on {request.date}",
                    "details": {
                        "origin": request.origin,
                        "destination": request.destination,
                        "date": str(request.date)
                    }
                }
            )
        
        # Generate search ID
        search_id = str(uuid.uuid4())
        
        # Build response
        response = SearchResponse(
            search_id=search_id,
            origin=request.origin,
            destination=request.destination,
            itineraries=itineraries,
            meta=SearchMetadata(
                returned=len(itineraries),
                max_results=request.max_results
            )
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_ERROR",
                "message": "An internal error occurred while processing the search",
                "details": {"error": str(e)}
            }
        )


@router.get(
    "/health",
    summary="Health check",
    description="Check if the search API is healthy"
)
async def health_check():
    """Simple health check endpoint"""
    return {
        "status": "healthy",
        "service": "flight-search-api",
        "version": settings.APP_VERSION
    }
