"""
One-stop flight (1-stop) search implementation
"""
from typing import List
from datetime import date

from sqlalchemy.orm import Session, aliased

from database.models import Route
from app.models import Itinerary
from .helpers import (
    fetch_flight_instances_bulk,
    is_valid_connection,
    create_flight_leg_from_instance,
    index_instances_by_route
)


class OneStopFlightSearch:
    """
    Handles search for one-stop flights (1 intermediate stop)
    """
    
    def __init__(
        self,
        db: Session,
        itinerary_builder,
        mct_domestic: int,
        max_layover: int
    ):
        self.db = db
        self.itinerary_builder = itinerary_builder
        self.mct_domestic = mct_domestic
        self.max_layover = max_layover
    
    def search(
        self,
        origin: str,
        destination: str,
        search_date: date,
        max_results: int = 50
    ) -> List[Itinerary]:
        """
        Search for one-stop flights between origin and destination.
        
        Args:
            origin: Origin airport code
            destination: Destination airport code
            search_date: Date to search for flights
            max_results: Maximum number of results to return
            
        Returns:
            List of itineraries with 1 stop
        """
        # Get all possible route pairs (origin -> via -> destination)
        route_pairs = self._fetch_route_pairs(origin, destination)
        
        if not route_pairs:
            return []
        
        # Extract route IDs
        first_leg_route_ids = {route1.id for route1, _ in route_pairs}
        second_leg_route_ids = {route2.id for _, route2 in route_pairs}
        
        # Fetch all flight instances in bulk
        first_leg_instances = fetch_flight_instances_bulk(
            self.db, first_leg_route_ids, search_date
        )
        
        if not first_leg_instances:
            return []
        
        # Optimize second leg query by filtering on minimum departure time
        minimum_arrival_time = min(
            (inst.arrival_time_utc for inst, _ in first_leg_instances),
            default=None
        )
        
        second_leg_instances = fetch_flight_instances_bulk(
            self.db,
            second_leg_route_ids,
            search_date,
            min_departure_time=minimum_arrival_time
        )
        
        # Index instances by route for faster lookup
        instances_by_route1 = index_instances_by_route(first_leg_instances)
        instances_by_route2 = index_instances_by_route(second_leg_instances)
        
        # Build itineraries with early termination
        return self._build_itineraries(
            route_pairs,
            instances_by_route1,
            instances_by_route2,
            max_results
        )
    
    def _fetch_route_pairs(self, origin: str, destination: str):
        """
        Fetch all valid route pairs for one-stop connections.
        """
        Route1 = aliased(Route)
        Route2 = aliased(Route)
        
        route_pairs = (
            self.db.query(Route1, Route2)
            .filter(
                Route1.source_code == origin,
                Route2.destination_code == destination,
                Route1.destination_code == Route2.source_code,
                Route1.destination_code != origin,
                Route1.destination_code != destination
            )
            .limit(100)
            .all()
        )
        
        return route_pairs
    
    def _build_itineraries(
        self,
        route_pairs,
        instances_by_route1: dict,
        instances_by_route2: dict,
        max_results: int
    ) -> List[Itinerary]:
        """
        Build itineraries from route pairs and flight instances.
        Implements early termination when max_results is reached.
        """
        itineraries = []
        
        for route1, route2 in route_pairs:
            if len(itineraries) >= max_results:
                break
            
            instances1 = instances_by_route1.get(route1.id, [])
            instances2 = instances_by_route2.get(route2.id, [])
            
            for inst1 in instances1:
                if len(itineraries) >= max_results:
                    break
                
                for inst2 in instances2:
                    if is_valid_connection(
                        inst1, inst2,
                        self.mct_domestic,
                        self.max_layover
                    ):
                        leg1 = create_flight_leg_from_instance(inst1, route1)
                        leg2 = create_flight_leg_from_instance(inst2, route2)
                        itinerary = self.itinerary_builder.build([leg1, leg2])
                        itineraries.append(itinerary)
                        
                        if len(itineraries) >= max_results:
                            break
        
        return itineraries
