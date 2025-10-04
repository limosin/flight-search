"""
Flight search service - implements route-based search algorithm
New Schema: Route (direct links) -> Flight (carrier+number) -> FlightInstance (scheduled)
"""

import sys
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session, joinedload
import uuid
import random

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.models import FlightInstance, Flight, Airport, Route, Carrier
from app.models import FlightLeg, Itinerary, Price
from app.core.config import settings


class FlightSearchService:
    """
    Flight search service implementing route-based multi-hop search algorithm
    
    New Schema Architecture:
    - Routes: Direct links between airports (source -> destination)
    - Flights: Carrier + flight_number on a route
    - FlightInstances: Scheduled instances of flights with date/time
    
    Search Strategy:
    1. Find valid route combinations (0, 1, or 2 hops)
    2. For each route combination, fetch flights and instances
    3. Validate connections (MCT, max layover)
    4. Return itineraries
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.mct_domestic = settings.MINIMUM_CONNECTION_TIME_DOMESTIC
        self.mct_international = settings.MINIMUM_CONNECTION_TIME_INTERNATIONAL
        self.max_layover = settings.MAXIMUM_LAYOVER_TIME
    
    def search(
        self,
        origin: str,
        destination: str,
        search_date: date,
        max_hops: int = 2,
        max_results: int = 50,
        preferred_time_start: Optional[str] = None,
        preferred_time_end: Optional[str] = None
    ) -> List[Itinerary]:
        """
        Main search method - finds itineraries with up to max_hops stops
        
        Args:
            origin: Origin airport code
            destination: Destination airport code
            search_date: Travel date
            max_hops: Maximum number of stops (0-2)
            max_results: Maximum results to return
            preferred_time_start: Preferred departure time start (HH:MM)
            preferred_time_end: Preferred departure time end (HH:MM)
            
        Returns:
            List of itineraries
        """
        results = []
        
        # Search for direct flights (0 hops)
        if max_hops >= 0:
            direct_flights = self._search_direct(origin, destination, search_date)
            results.extend(direct_flights)
            
            # Early termination if we have enough results
            if len(results) >= max_results:
                return results[:max_results]
        
        # Search for 1-stop flights (1 hop)
        if max_hops >= 1:
            one_stop_flights = self._search_one_stop(origin, destination, search_date)
            results.extend(one_stop_flights)
            
            # Early termination if we have enough results
            if len(results) >= max_results:
                return results[:max_results]
        
        # Search for 2-stop flights (2 hops)
        if max_hops >= 2:
            two_stop_flights = self._search_two_stop(origin, destination, search_date)
            results.extend(two_stop_flights)
        
        # Filter by time window if specified
        if preferred_time_start and preferred_time_end:
            results = self._filter_by_time_window(
                results, preferred_time_start, preferred_time_end
            )
        
        # Limit results
        results = results[:max_results]
        
        return results
    
    def _search_direct(
        self, origin: str, destination: str, search_date: date
    ) -> List[Itinerary]:
        """
        Search for direct flights (0 hops) using route-based approach
        
        Algorithm:
        1. Find routes where source = origin AND destination = final_destination
        2. For each route, get flights
        3. For each flight, get instances on the search date
        
        Args:
            origin: Origin airport code
            destination: Destination airport code
            search_date: Travel date
            
        Returns:
            List of direct flight itineraries
        """
        # Query: Route -> Flight -> FlightInstance
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
        
        # Convert to itineraries
        itineraries = []
        for instance in instances:
            leg = self._create_flight_leg_from_instance(instance)
            itinerary = self._create_itinerary([leg])
            itineraries.append(itinerary)
        
        return itineraries
    
    def _search_one_stop(
        self, origin: str, destination: str, search_date: date
    ) -> List[Itinerary]:
        """
        Search for 1-stop flights (1 hop) using route-based approach
        
        Algorithm:
        1. Find route pairs: (origin->intermediate, intermediate->destination)
        2. For each route pair, get flight instances
        3. Validate connections (MCT, max layover)
        4. Build itineraries
        
        Args:
            origin: Origin airport code
            destination: Destination airport code
            search_date: Travel date
            
        Returns:
            List of 1-stop itineraries
        """
        from collections import defaultdict
        from sqlalchemy.orm import aliased
        
        itineraries = []
        
        # Use explicit aliases for the two routes
        Route1 = aliased(Route)
        Route2 = aliased(Route)
        
        # Find route pairs: origin -> intermediate -> destination
        route_pairs = (
            self.db.query(Route1, Route2)
            .filter(
                Route1.source_code == origin,
                Route2.destination_code == destination,
                Route1.destination_code == Route2.source_code,  # Connection point
                Route1.destination_code != origin,  # No loops
                Route1.destination_code != destination
            )
            .limit(100)  # Limit route combinations
            .all()
        )
        
        # Step 2: For each route pair, get flight instances
        for route1, route2 in route_pairs:
            # Get instances for first leg
            instances1 = (
                self.db.query(FlightInstance)
                .join(Flight, FlightInstance.flight_id == Flight.id)
                .filter(
                    Flight.route_id == route1.id,
                    FlightInstance.service_date == search_date,
                    FlightInstance.is_active == True
                )
                .options(
                    joinedload(FlightInstance.flight).joinedload(Flight.carrier)
                )
                .order_by(FlightInstance.departure_time_utc)
                .limit(30)
                .all()
            )
            
            # Get instances for second leg
            instances2 = (
                self.db.query(FlightInstance)
                .join(Flight, FlightInstance.flight_id == Flight.id)
                .filter(
                    Flight.route_id == route2.id,
                    FlightInstance.service_date == search_date,
                    FlightInstance.is_active == True
                )
                .options(
                    joinedload(FlightInstance.flight).joinedload(Flight.carrier)
                )
                .order_by(FlightInstance.departure_time_utc)
                .all()
            )
            
            # Step 3: Validate connections and build itineraries
            for inst1 in instances1:
                for inst2 in instances2:
                    if self._is_valid_connection(inst1, inst2):
                        leg1 = self._create_flight_leg_from_instance(inst1, route1)
                        leg2 = self._create_flight_leg_from_instance(inst2, route2)
                        itinerary = self._create_itinerary([leg1, leg2])
                        itineraries.append(itinerary)
        
        return itineraries
    
    def _search_two_stop(
        self, origin: str, destination: str, search_date: date
    ) -> List[Itinerary]:
        """
        Search for 2-stop flights (2 hops) using route-based approach
        
        Algorithm:
        1. Find route triplets: (origin->mid1, mid1->mid2, mid2->destination)
        2. For each route triplet, get flight instances
        3. Validate connections
        4. Build itineraries
        
        Args:
            origin: Origin airport code
            destination: Destination airport code
            search_date: Travel date
            
        Returns:
            List of 2-stop itineraries
        """
        from sqlalchemy.orm import aliased
        
        itineraries = []
        
        # Create aliases for three routes
        Route1 = aliased(Route)
        Route2 = aliased(Route)
        Route3 = aliased(Route)
        
        # Find route triplets
        route_triplets = (
            self.db.query(Route1, Route2, Route3)
            .filter(
                Route1.source_code == origin,
                Route3.destination_code == destination,
                Route1.destination_code == Route2.source_code,  # First connection
                Route2.destination_code == Route3.source_code,  # Second connection
                Route1.destination_code != origin,  # No loops
                Route1.destination_code != destination,
                Route2.destination_code != origin,
                Route2.destination_code != destination,
                Route1.destination_code != Route2.destination_code  # Different intermediates
            )
            .limit(50)  # Limit combinations
            .all()
        )
        
        # For each route triplet, get flight instances
        for route1, route2, route3 in route_triplets:
            # Get instances for each leg (limit to prevent explosion)
            instances1 = (
                self.db.query(FlightInstance)
                .join(Flight, FlightInstance.flight_id == Flight.id)
                .filter(
                    Flight.route_id == route1.id,
                    FlightInstance.service_date == search_date,
                    FlightInstance.is_active == True
                )
                .options(joinedload(FlightInstance.flight).joinedload(Flight.carrier))
                .order_by(FlightInstance.departure_time_utc)
                .limit(10)
                .all()
            )
            
            instances2 = (
                self.db.query(FlightInstance)
                .join(Flight, FlightInstance.flight_id == Flight.id)
                .filter(
                    Flight.route_id == route2.id,
                    FlightInstance.service_date == search_date,
                    FlightInstance.is_active == True
                )
                .options(joinedload(FlightInstance.flight).joinedload(Flight.carrier))
                .order_by(FlightInstance.departure_time_utc)
                .limit(10)
                .all()
            )
            
            instances3 = (
                self.db.query(FlightInstance)
                .join(Flight, FlightInstance.flight_id == Flight.id)
                .filter(
                    Flight.route_id == route3.id,
                    FlightInstance.service_date == search_date,
                    FlightInstance.is_active == True
                )
                .options(joinedload(FlightInstance.flight).joinedload(Flight.carrier))
                .order_by(FlightInstance.departure_time_utc)
                .all()
            )
            
            # Build itineraries with connection validation
            for inst1 in instances1:
                for inst2 in instances2:
                    if not self._is_valid_connection(inst1, inst2):
                        continue
                    
                    for inst3 in instances3:
                        if self._is_valid_connection(inst2, inst3):
                            leg1 = self._create_flight_leg_from_instance(inst1, route1)
                            leg2 = self._create_flight_leg_from_instance(inst2, route2)
                            leg3 = self._create_flight_leg_from_instance(inst3, route3)
                            itinerary = self._create_itinerary([leg1, leg2, leg3])
                            itineraries.append(itinerary)
        
        return itineraries
    
    def _is_valid_connection(
        self, arriving_flight: FlightInstance, departing_flight: FlightInstance
    ) -> bool:
        """
        Check if connection between two flights is valid
        
        Checks:
        - Minimum connection time (MCT)
        - Maximum layover time
        - Time zones handled via UTC
        
        Args:
            arriving_flight: The arriving flight
            departing_flight: The departing flight
            
        Returns:
            True if connection is valid
        """
        # Calculate connection time in minutes
        connection_time = (
            departing_flight.departure_time_utc - arriving_flight.arrival_time_utc
        ).total_seconds() / 60
        
        # Use domestic MCT for simplicity (can be enhanced with international check)
        mct = self.mct_domestic
        
        # Check minimum and maximum connection times
        if connection_time < mct:
            return False
        
        if connection_time > self.max_layover:
            return False
        
        return True
    
    def _create_flight_leg_from_instance(
        self, instance: FlightInstance, route: Optional[Route] = None
    ) -> FlightLeg:
        """
        Convert FlightInstance to FlightLeg API model
        
        Args:
            instance: FlightInstance from database
            route: Optional Route (if not eager loaded)
            
        Returns:
            FlightLeg model
        """
        # Get route info (either from parameter or from instance.flight.route)
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
    
    def _create_itinerary(self, legs: List[FlightLeg]) -> Itinerary:
        """
        Create an itinerary from flight legs
        
        Args:
            legs: List of flight legs
            
        Returns:
            Complete itinerary with price
        """
        # Calculate total duration
        first_departure = legs[0].departure_time_utc
        last_arrival = legs[-1].arrival_time_utc
        total_duration = int((last_arrival - first_departure).total_seconds() / 60)
        
        # Generate price (random for now as per requirement)
        # In production, this would fetch from Fare table or pricing service
        base_price = random.uniform(3000, 15000)
        num_legs = len(legs)
        price_multiplier = 1.0 + (num_legs - 1) * 0.3  # Increase for connections
        total_price = round(base_price * price_multiplier, 2)
        
        # Generate unique IDs and fare key
        itinerary_id = str(uuid.uuid4())
        fare_key = f"fare_{legs[0].origin}_{legs[-1].destination}_{legs[0].departure_time_utc.strftime('%Y%m%d')}_{itinerary_id[:8]}"
        
        return Itinerary(
            id=itinerary_id,
            legs=legs,
            stops=len(legs) - 1,
            total_duration_minutes=total_duration,
            price=Price(currency="INR", amount=total_price),
            fare_key=fare_key
        )
    
    def _filter_by_time_window(
        self,
        itineraries: List[Itinerary],
        start_time: str,
        end_time: str
    ) -> List[Itinerary]:
        """
        Filter itineraries by departure time window
        
        Args:
            itineraries: List of itineraries
            start_time: Start time (HH:MM)
            end_time: End time (HH:MM)
            
        Returns:
            Filtered itineraries
        """
        # Parse time strings
        start_hour, start_min = map(int, start_time.split(':'))
        end_hour, end_min = map(int, end_time.split(':'))
        
        filtered = []
        for itin in itineraries:
            dep_time = itin.legs[0].departure_time_utc
            dep_hour = dep_time.hour
            dep_min = dep_time.minute
            
            # Simple time window check (assumes same day)
            dep_minutes = dep_hour * 60 + dep_min
            start_minutes = start_hour * 60 + start_min
            end_minutes = end_hour * 60 + end_min
            
            if start_minutes <= dep_minutes <= end_minutes:
                filtered.append(itin)
        
        return filtered
