"""
API models package
"""

from .schemas import (
    SearchRequest,
    SearchResponse,
    FlightLeg,
    Itinerary,
    Price,
    SearchMetadata,
    ErrorResponse,
    CabinClass,
    SortOption,
    TimeWindow
)

__all__ = [
    'SearchRequest',
    'SearchResponse',
    'FlightLeg',
    'Itinerary',
    'Price',
    'SearchMetadata',
    'ErrorResponse',
    'CabinClass',
    'SortOption',
    'TimeWindow'
]
