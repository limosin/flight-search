"""
Flight search service - implements the search algorithm from tech spec
"""

import sys
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
import uuid
import random

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.models import FlightInstance, Airport, Route
from app.models import FlightLeg, Itinerary, Price
from app.core.config import settings


class FlightSearchService:
    """
    Flight search service implementing multi-hop search algorithm
    Supports 0, 1, or 2 hops (direct, 1-stop, 2-stop flights)
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
        
        # Search for 1-stop flights (1 hop)
        if max_hops >= 1:
            one_stop_flights = self._search_one_stop(origin, destination, search_date)
            results.extend(one_stop_flights)
        
        # # Search for 2-stop flights (2 hops)
        # if max_hops >= 2:
        #     two_stop_flights = self._search_two_stop(origin, destination, search_date)
        #     results.extend(two_stop_flights)
        
        # # Filter by time window if specified
        # if preferred_time_start and preferred_time_end:
        #     results = self._filter_by_time_window(
        #         results, preferred_time_start, preferred_time_end
        #     )
        
        # Limit results
        results = results[:max_results]
        
        return results
    
    def _search_direct(
        self, origin: str, destination: str, search_date: date
    ) -> List[Itinerary]:
        """
        Search for direct flights (0 hops)
        
        Args:
            origin: Origin airport code
            destination: Destination airport code
            search_date: Travel date
            
        Returns:
            List of direct flight itineraries
        """
        # Query direct flights
        flights = self.db.query(FlightInstance).filter(
            FlightInstance.origin_code == origin,
            FlightInstance.destination_code == destination,
            FlightInstance.service_date == search_date,
            FlightInstance.stops == 0,
            FlightInstance.is_active == True
        ).order_by(FlightInstance.departure_time_utc).all()
        
        # Convert to itineraries
        itineraries = []
        for flight in flights:
            leg = self._create_flight_leg(flight)
            itinerary = self._create_itinerary([leg])
            itineraries.append(itinerary)
        
        return itineraries
    
    def _search_one_stop(
        self, origin: str, destination: str, search_date: date
    ) -> List[Itinerary]:
        """
        Search for 1-stop flights (1 hop)
        
        Algorithm:
        1. Find all flights from origin on the date
        2. For each flight, find connecting flights from its destination
        3. Validate connection time (MCT and max layover)
        
        Args:
            origin: Origin airport code
            destination: Destination airport code
            search_date: Travel date
            
        Returns:
            List of 1-stop itineraries
        """
        itineraries = []
        
        # Get first leg candidates (origin -> intermediate)
        first_legs = self.db.query(FlightInstance).filter(
            FlightInstance.origin_code == origin,
            FlightInstance.service_date == search_date,
            FlightInstance.destination_code != destination,  # Not direct
            FlightInstance.is_active == True
        ).all()
        
        for first_leg in first_legs:
            intermediate = first_leg.destination_code
            
            # Avoid loops
            if intermediate == origin:
                continue
            
            # Get second leg candidates (intermediate -> destination)
            second_legs = self.db.query(FlightInstance).filter(
                FlightInstance.origin_code == intermediate,
                FlightInstance.destination_code == destination,
                FlightInstance.service_date == search_date,
                FlightInstance.is_active == True
            ).all()
            
            for second_leg in second_legs:
                # Check connection feasibility
                if self._is_valid_connection(first_leg, second_leg):
                    leg1 = self._create_flight_leg(first_leg)
                    leg2 = self._create_flight_leg(second_leg)
                    itinerary = self._create_itinerary([leg1, leg2])
                    itineraries.append(itinerary)
        
        return itineraries
    
    def _search_two_stop(
        self, origin: str, destination: str, search_date: date
    ) -> List[Itinerary]:
        """
        Search for 2-stop flights (2 hops)
        
        Algorithm:
        1. Find first leg from origin
        2. Find second leg from first intermediate
        3. Find third leg to destination
        4. Validate all connections
        
        Args:
            origin: Origin airport code
            destination: Destination airport code
            search_date: Travel date
            
        Returns:
            List of 2-stop itineraries
        """
        itineraries = []
        
        # Get first leg candidates
        first_legs = self.db.query(FlightInstance).filter(
            FlightInstance.origin_code == origin,
            FlightInstance.service_date == search_date,
            FlightInstance.destination_code != destination,
            FlightInstance.is_active == True
        ).all()
        
        for first_leg in first_legs:
            intermediate1 = first_leg.destination_code
            
            if intermediate1 == origin:
                continue
            
            # Get second leg candidates
            second_legs = self.db.query(FlightInstance).filter(
                FlightInstance.origin_code == intermediate1,
                FlightInstance.destination_code != destination,
                FlightInstance.destination_code != origin,
                FlightInstance.service_date == search_date,
                FlightInstance.is_active == True
            ).all()
            
            for second_leg in second_legs:
                if not self._is_valid_connection(first_leg, second_leg):
                    continue
                
                intermediate2 = second_leg.destination_code
                
                # Avoid loops
                if intermediate2 in [origin, intermediate1]:
                    continue
                
                # Get third leg candidates
                third_legs = self.db.query(FlightInstance).filter(
                    FlightInstance.origin_code == intermediate2,
                    FlightInstance.destination_code == destination,
                    FlightInstance.service_date == search_date,
                    FlightInstance.is_active == True
                ).all()
                
                for third_leg in third_legs:
                    if self._is_valid_connection(second_leg, third_leg):
                        leg1 = self._create_flight_leg(first_leg)
                        leg2 = self._create_flight_leg(second_leg)
                        leg3 = self._create_flight_leg(third_leg)
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
    
    def _create_flight_leg(self, flight: FlightInstance) -> FlightLeg:
        """
        Convert FlightInstance to FlightLeg API model
        
        Args:
            flight: FlightInstance from database
            
        Returns:
            FlightLeg model
        """
        return FlightLeg(
            carrier=flight.carrier_code,
            flight_number=flight.flight_number,
            origin=flight.origin_code,
            destination=flight.destination_code,
            departure_time_utc=flight.departure_time_utc,
            arrival_time_utc=flight.arrival_time_utc,
            duration_minutes=flight.duration_minutes
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
