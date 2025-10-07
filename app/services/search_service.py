import sys
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session, joinedload
import uuid
import random

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.models import FlightInstance, Flight, Airport, Route, Carrier, Fare
from app.models import FlightLeg, Itinerary, Price
from app.core.config import settings


class FlightSearchService:
    
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
        results = []
        
        if max_hops >= 0:
            direct_flights = self._search_direct(origin, destination, search_date)
            results.extend(direct_flights)
            
            if len(results) >= max_results:
                return results[:max_results]
        
        if max_hops >= 1:
            one_stop_flights = self._search_one_stop(origin, destination, search_date)
            results.extend(one_stop_flights)
            
            if len(results) >= max_results:
                return results[:max_results]
        
        if max_hops >= 2:
            two_stop_flights = self._search_two_stop(origin, destination, search_date)
            results.extend(two_stop_flights)
        
        if preferred_time_start and preferred_time_end:
            results = self._filter_by_time_window(
                results, preferred_time_start, preferred_time_end
            )
        
        results = results[:max_results]
        
        return results
    
    def _search_direct(
        self, origin: str, destination: str, search_date: date
    ) -> List[Itinerary]:
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
        
        itineraries = []
        for instance in instances:
            leg = self._create_flight_leg_from_instance(instance)
            itinerary = self._create_itinerary([leg])
            itineraries.append(itinerary)
        
        return itineraries
    
    def _search_one_stop(
        self, origin: str, destination: str, search_date: date
    ) -> List[Itinerary]:
        from collections import defaultdict
        from sqlalchemy.orm import aliased
        
        itineraries = []
        
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
        
        for route1, route2 in route_pairs:
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
        from sqlalchemy.orm import aliased
        
        itineraries = []
        
        Route1 = aliased(Route)
        Route2 = aliased(Route)
        Route3 = aliased(Route)
        
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
            .limit(50)
            .all()
        )
        
        for route1, route2, route3 in route_triplets:
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
        connection_time = (
            departing_flight.departure_time_utc - arriving_flight.arrival_time_utc
        ).total_seconds() / 60
        
        mct = self.mct_domestic
        
        if connection_time < mct:
            return False
        
        if connection_time > self.max_layover:
            return False
        
        return True
    
    def _create_flight_leg_from_instance(
        self, instance: FlightInstance, route: Optional[Route] = None
    ) -> FlightLeg:
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
        first_departure = legs[0].departure_time_utc
        last_arrival = legs[-1].arrival_time_utc
        total_duration = int((last_arrival - first_departure).total_seconds() / 60)
        
        # Try to get real fare from database
        total_price = self._get_fare_for_itinerary(legs)
        
        # Fallback to random price if no fare found
        if total_price is None:
            base_price = random.uniform(3000, 15000)
            num_legs = len(legs)
            price_multiplier = 1.0 + (num_legs - 1) * 0.3
            total_price = round(base_price * price_multiplier, 2)
        
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
    
    def _get_fare_for_itinerary(self, legs: List[FlightLeg]) -> Optional[float]:
        """
        Attempt to get real fare from database for the itinerary
        For direct flights, looks up fare by flight instance
        For multi-leg, estimates based on individual leg fares
        """
        try:
            if len(legs) == 1:
                # Direct flight - look up exact fare
                leg = legs[0]
                fare = (
                    self.db.query(Fare)
                    .join(FlightInstance, Fare.flight_instance_id == FlightInstance.id)
                    .join(Flight, FlightInstance.flight_id == Flight.id)
                    .join(Route, Flight.route_id == Route.id)
                    .filter(
                        Route.source_code == leg.origin,
                        Route.destination_code == leg.destination,
                        Flight.carrier_code == leg.carrier,
                        Flight.flight_number == leg.flight_number,
                        FlightInstance.departure_time_utc == leg.departure_time_utc
                    )
                    .order_by(Fare.total_price.asc())
                    .first()
                )
                
                if fare:
                    return float(fare.total_price)
            else:
                # Multi-leg - sum individual leg fares if available
                total = 0
                all_fares_found = True
                
                for leg in legs:
                    fare = (
                        self.db.query(Fare)
                        .join(FlightInstance, Fare.flight_instance_id == FlightInstance.id)
                        .join(Flight, FlightInstance.flight_id == Flight.id)
                        .join(Route, Flight.route_id == Route.id)
                        .filter(
                            Route.source_code == leg.origin,
                            Route.destination_code == leg.destination,
                            Flight.carrier_code == leg.carrier,
                            Flight.flight_number == leg.flight_number,
                            FlightInstance.departure_time_utc == leg.departure_time_utc
                        )
                        .order_by(Fare.total_price.asc())
                        .first()
                    )
                    
                    if fare:
                        total += float(fare.total_price)
                    else:
                        all_fares_found = False
                        break
                
                if all_fares_found:
                    return total
        
        except Exception as e:
            print(f"Error fetching fare: {e}")
        
        return None
    
    def _filter_by_time_window(
        self,
        itineraries: List[Itinerary],
        start_time: str,
        end_time: str
    ) -> List[Itinerary]:
        start_hour, start_min = map(int, start_time.split(':'))
        end_hour, end_min = map(int, end_time.split(':'))
        
        filtered = []
        for itin in itineraries:
            dep_time = itin.legs[0].departure_time_utc
            dep_hour = dep_time.hour
            dep_min = dep_time.minute
            
            dep_minutes = dep_hour * 60 + dep_min
            start_minutes = start_hour * 60 + start_min
            end_minutes = end_hour * 60 + end_min
            
            if start_minutes <= dep_minutes <= end_minutes:
                filtered.append(itin)
        
        return filtered
