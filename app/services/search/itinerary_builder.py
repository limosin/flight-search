"""
Itinerary builder - handles creation of itinerary objects with pricing
"""
import uuid
import random
from typing import List, Optional

from sqlalchemy.orm import Session

from database.models import Fare, FlightInstance, Flight, Route
from app.models import FlightLeg, Itinerary, Price


class ItineraryBuilder:
    """
    Responsible for building Itinerary objects from FlightLegs
    and fetching fare information
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def build(self, legs: List[FlightLeg]) -> Itinerary:
        """
        Build an itinerary from a list of flight legs.
        
        Args:
            legs: List of FlightLeg objects
            
        Returns:
            Complete Itinerary object with pricing
        """
        first_departure = legs[0].departure_time_utc
        last_arrival = legs[-1].arrival_time_utc
        total_duration = int((last_arrival - first_departure).total_seconds() / 60)

        total_price = self._estimate_price(legs)
        
        itinerary_id = str(uuid.uuid4())
        fare_key = self._generate_fare_key(legs, itinerary_id)
        
        return Itinerary(
            id=itinerary_id,
            legs=legs,
            stops=len(legs) - 1,
            total_duration_minutes=total_duration,
            price=Price(currency="INR", amount=total_price),
            fare_key=fare_key
        )


    def _estimate_price(self, legs: List[FlightLeg]) -> float:
        """
        Generate estimated price when real fare is not available.
        Multi-leg flights are more expensive.
        """
        base_price = random.uniform(3000, 15000)
        num_legs = len(legs)
        price_multiplier = 1.0 + (num_legs - 1) * 0.3
        return round(base_price * price_multiplier, 2)

    def _generate_fare_key(self, legs: List[FlightLeg], itinerary_id: str) -> str:
        """Generate a unique fare key for the itinerary."""
        origin = legs[0].origin
        destination = legs[-1].destination
        date_str = legs[0].departure_time_utc.strftime('%Y%m%d')
        short_id = itinerary_id[:8]

        return f"fare_{origin}_{destination}_{date_str}_{short_id}"
