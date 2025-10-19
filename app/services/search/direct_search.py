"""
Direct flight (0-stop) search implementation
"""
from typing import List
from datetime import date

from sqlalchemy.orm import Session, joinedload

from database.models import FlightInstance, Flight, Route
from app.models import Itinerary
from .helpers import create_flight_leg_from_instance


class DirectFlightSearch:
    """
    Handles search for direct flights (0 stops)
    """
    
    def __init__(self, db: Session, itinerary_builder):
        self.db = db
        self.itinerary_builder = itinerary_builder
    
    def search(
        self,
        origin: str,
        destination: str,
        search_date: date
    ) -> List[Itinerary]:
        """
        Search for direct flights between origin and destination.
        
        Args:
            origin: Origin airport code
            destination: Destination airport code
            search_date: Date to search for flights
            
        Returns:
            List of itineraries with 0 stops
        """
        instances = self._fetch_direct_flight_instances(
            origin, destination, search_date
        )
        
        return self._build_itineraries(instances)
    
    def _fetch_direct_flight_instances(
        self,
        origin: str,
        destination: str,
        search_date: date
    ) -> List[FlightInstance]:
        """
        Fetch all direct flight instances for the given route and date.
        """
        instances = (
            self.db.query(FlightInstance)
            .join(Flight, FlightInstance.flight_id == Flight.id)
            .join(Route, Flight.route_id == Route.id)
            .filter(
                Route.source_code == origin,
                Route.destination_code == destination,
                FlightInstance.service_date == search_date,
                FlightInstance.is_active == True
            )
            .options(
                joinedload(FlightInstance.flight).joinedload(Flight.route),
                joinedload(FlightInstance.flight).joinedload(Flight.carrier)
            )
            .order_by(FlightInstance.departure_time_utc)
            .all()
        )
        
        return instances
    
    def _build_itineraries(
        self,
        instances: List[FlightInstance]
    ) -> List[Itinerary]:
        """
        Convert flight instances to itineraries.
        """
        itineraries = []
        for instance in instances:
            leg = create_flight_leg_from_instance(instance)
            itinerary = self.itinerary_builder.build([leg])
            itineraries.append(itinerary)
        
        return itineraries
