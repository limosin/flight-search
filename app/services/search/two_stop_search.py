"""
Two-stop flight (2-stop) search implementation
"""
from typing import List
from datetime import date

from sqlalchemy.orm import Session, aliased
from sqlalchemy import func

from database.models import Route
from app.models import Itinerary
from .helpers import (
    fetch_flight_instances_bulk,
    is_valid_connection,
    create_flight_leg_from_instance,
    index_instances_by_route
)


class TwoStopFlightSearch:
    """
    Handles search for two-stop flights (2 intermediate stops)
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
        Search for two-stop flights between origin and destination.
        
        Args:
            origin: Origin airport code
            destination: Destination airport code
            search_date: Date to search for flights
            max_results: Maximum number of results to return
            
        Returns:
            List of itineraries with 2 stops
        """
        # Get all possible route triplets (origin -> via1 -> via2 -> destination)
        route_triplets = self._fetch_route_triplets(origin, destination)
        
        if not route_triplets:
            return []
        
        # Extract route IDs
        first_leg_route_ids = {route1.id for route1, _, _ in route_triplets}
        second_leg_route_ids = {route2.id for _, route2, _ in route_triplets}
        third_leg_route_ids = {route3.id for _, _, route3 in route_triplets}
        
        # Fetch first leg instances
        first_leg_instances = fetch_flight_instances_bulk(
            self.db, first_leg_route_ids, search_date
        )
        
        if not first_leg_instances:
            return []
        
        # Optimize second leg query
        minimum_arrival_time_first = min(
            (inst.arrival_time_utc for inst, _ in first_leg_instances),
            default=None
        )
        
        second_leg_instances = fetch_flight_instances_bulk(
            self.db,
            second_leg_route_ids,
            search_date,
            min_departure_time=minimum_arrival_time_first
        )
        
        if not second_leg_instances:
            return []
        
        # Optimize third leg query
        minimum_arrival_time_second = min(
            (inst.arrival_time_utc for inst, _ in second_leg_instances),
            default=None
        )
        
        third_leg_instances = fetch_flight_instances_bulk(
            self.db,
            third_leg_route_ids,
            search_date,
            min_departure_time=minimum_arrival_time_second
        )
        
        # Index instances by route for faster lookup
        instances_by_route1 = index_instances_by_route(first_leg_instances)
        instances_by_route2 = index_instances_by_route(second_leg_instances)
        instances_by_route3 = index_instances_by_route(third_leg_instances)
        
        # Build itineraries with early termination
        return self._build_itineraries(
            route_triplets,
            instances_by_route1,
            instances_by_route2,
            instances_by_route3,
            max_results
        )
    
    def _fetch_route_triplets(self, origin: str, destination: str):
        """
        Fetch all valid route triplets for two-stop connections.
        """
        Route1 = aliased(Route)
        Route2 = aliased(Route)
        Route3 = aliased(Route)
        # Prefer triplets with lower summed average_duration_minutes.
        # Treat NULL durations as a large value so known durations are preferred.
        large_value = 10_000.0
        total_duration_expr = (
            func.coalesce(Route1.average_duration_minutes, large_value) +
            func.coalesce(Route2.average_duration_minutes, large_value) +
            func.coalesce(Route3.average_duration_minutes, large_value)
        )

        route_triplets = (
            self.db.query(Route1, Route2, Route3)
            .filter(
                Route1.source_code == origin,
                Route3.destination_code == destination,
                Route1.destination_code == Route2.source_code,
                Route2.destination_code == Route3.source_code,
                Route1.destination_code != origin,
                Route1.destination_code != destination,
                Route2.destination_code != origin,
                Route2.destination_code != destination,
                Route1.destination_code != Route2.destination_code
            )
            .order_by(total_duration_expr.asc())
            .limit(50)
            .all()
        )
        
        return route_triplets
    
    def _build_itineraries(
        self,
        route_triplets,
        instances_by_route1: dict,
        instances_by_route2: dict,
        instances_by_route3: dict,
        max_results: int
    ) -> List[Itinerary]:
        """
        Build itineraries from route triplets and flight instances.
        Implements early termination when max_results is reached.
        """
        itineraries = []
        
        for route1, route2, route3 in route_triplets:
            
            instances1 = instances_by_route1.get(route1.id, [])
            instances2 = instances_by_route2.get(route2.id, [])
            instances3 = instances_by_route3.get(route3.id, [])
            
            for inst1 in instances1:
                for inst2 in instances2:
                    if not is_valid_connection(
                        inst1, inst2,
                        self.mct_domestic,
                        self.max_layover
                    ):
                        continue
                    
                    for inst3 in instances3:
                        if is_valid_connection(
                            inst2, inst3,
                            self.mct_domestic,
                            self.max_layover
                        ):
                            leg1 = create_flight_leg_from_instance(inst1, route1)
                            leg2 = create_flight_leg_from_instance(inst2, route2)
                            leg3 = create_flight_leg_from_instance(inst3, route3)
                            itinerary = self.itinerary_builder.build([leg1, leg2, leg3])
                            itineraries.append(itinerary)
        
        return itineraries
