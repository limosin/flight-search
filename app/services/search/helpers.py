"""
Helper utilities for flight search operations
"""
from typing import Tuple, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from database.models import FlightInstance, Flight, Route
from app.models import FlightLeg, Itinerary, Price
from sqlalchemy.orm import Session, joinedload


def fetch_flight_instances_bulk(
    db: Session,
    route_ids: set,
    search_date,
    min_departure_time: Optional[datetime] = None
) -> List[Tuple[FlightInstance, str]]:
    """
    Fetch flight instances for multiple routes in a single query.
    
    Args:
        db: Database session
        route_ids: Set of route IDs to fetch instances for
        search_date: The service date to search
        min_departure_time: Optional minimum departure time filter
        
    Returns:
        List of tuples containing (FlightInstance, route_id)
    """
    if not route_ids:
        return []
    
    query = (
        db.query(FlightInstance, Flight.route_id)
        .join(Flight, FlightInstance.flight_id == Flight.id)
        .filter(
            Flight.route_id.in_(route_ids),
            FlightInstance.service_date == search_date,
            FlightInstance.is_active == True
        )
        .options(
            joinedload(FlightInstance.flight).joinedload(Flight.carrier)
        )
        .order_by(FlightInstance.departure_time_utc)
    )
    
    if min_departure_time:
        query = query.filter(FlightInstance.departure_time_utc > min_departure_time)
    
    return query.all()


def is_valid_connection(
    arriving_flight: FlightInstance,
    departing_flight: FlightInstance,
    mct_domestic: int,
    max_layover: int
) -> bool:
    """
    Check if a connection between two flights is valid.
    
    Args:
        arriving_flight: The arriving flight instance
        departing_flight: The departing flight instance
        mct_domestic: Minimum connection time in minutes
        max_layover: Maximum layover time in minutes
        
    Returns:
        True if connection is valid, False otherwise
    """
    connection_time = (
        departing_flight.departure_time_utc - arriving_flight.arrival_time_utc
    ).total_seconds() / 60
    
    if connection_time < mct_domestic:
        return False
    
    if connection_time > max_layover:
        return False
    
    return True


def create_flight_leg_from_instance(
    instance: FlightInstance,
    route: Optional[Route] = None
) -> FlightLeg:
    """
    Create a FlightLeg model from a FlightInstance.
    
    Args:
        instance: FlightInstance from database
        route: Optional Route object (if not provided, uses instance.flight.route)
        
    Returns:
        FlightLeg object
    """
    if route is None:
        route = instance.flight.route
    
    return FlightLeg(
        carrier=instance.flight.carrier_code,
        flight_number=instance.flight.flight_number,
        origin=route.source_code,
        destination=route.destination_code,
        departure_time_utc=instance.departure_time_utc,
        arrival_time_utc=instance.arrival_time_utc,
        duration_minutes=instance.duration_minutes
    )


def index_instances_by_route(
    instances: List[Tuple[FlightInstance, str]]
) -> dict:
    """
    Index flight instances by route ID for faster lookup.
    
    Args:
        instances: List of (FlightInstance, route_id) tuples
        
    Returns:
        Dictionary mapping route_id to list of instances
    """
    instances_by_route = defaultdict(list)
    for instance, route_id in instances:
        instances_by_route[route_id].append(instance)
    return instances_by_route
