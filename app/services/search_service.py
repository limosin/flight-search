"""
Flight Search Service - Main entry point for flight searches
Orchestrates search across different hop counts with early termination
"""
import sys
from pathlib import Path
from typing import List
from datetime import date
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models import Itinerary
from app.core.config import settings
from app.services.search.itinerary_builder import ItineraryBuilder
from app.services.search.direct_search import DirectFlightSearch
from app.services.search.one_stop_search import OneStopFlightSearch
from app.services.search.two_stop_search import TwoStopFlightSearch


class FlightSearchService:
    """
    Main flight search service.
    
    Orchestrates flight search across different hop counts (direct, 1-stop, 2-stop).
    Implements progressive search with early termination for optimal performance.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.mct_domestic = settings.MINIMUM_CONNECTION_TIME_DOMESTIC
        self.mct_international = settings.MINIMUM_CONNECTION_TIME_INTERNATIONAL
        self.max_layover = settings.MAXIMUM_LAYOVER_TIME
        
        # Initialize itinerary builder
        self.itinerary_builder = ItineraryBuilder(db)
        
        # Initialize search strategies for different hop counts
        self.direct_search = DirectFlightSearch(db, self.itinerary_builder)
        self.one_stop_search = OneStopFlightSearch(
            db, self.itinerary_builder,
            self.mct_domestic, self.max_layover
        )
        self.two_stop_search = TwoStopFlightSearch(
            db, self.itinerary_builder,
            self.mct_domestic, self.max_layover
        )
    
    def search(
        self,
        origin: str,
        destination: str,
        search_date: date,
        max_hops: int = 2,
        max_results: int = 50
    ) -> List[Itinerary]:

        results = []
        
        # Step 1: Search direct flights (0 hops)
        if max_hops >= 0:
            direct_flights = self.direct_search.search(
                origin, destination, search_date
            )
            results.extend(direct_flights)
            
            # Early termination: Direct flights are preferred
            if len(results) >= max_results:
                return results
        
        # Step 2: Search 1-stop flights only if we need more results
        if max_hops >= 1 and len(results) < max_results:
            remaining_slots = max_results - len(results)
            one_stop_flights = self.one_stop_search.search(
                origin, destination, search_date, remaining_slots
            )
            results.extend(one_stop_flights)
            
            # Early termination after 1-stop if we have enough
            if len(results) >= max_results:
                return results
        
        # Step 3: Search 2-stop flights only if we still need more results
        if max_hops >= 2 and len(results) < max_results:
            remaining_slots = max_results - len(results)
            two_stop_flights = self.two_stop_search.search(
                origin, destination, search_date, remaining_slots
            )
            results.extend(two_stop_flights)
        
        return results


