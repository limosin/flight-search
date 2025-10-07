import sys
from pathlib import Path
from typing import List, Optional
from datetime import datetime, date
import uuid

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.memgraph_config import get_memgraph
from app.models import FlightLeg, Itinerary, Price
from app.core.config import settings


class FlightSearchService:
    
    def __init__(self):
        self.db = get_memgraph()
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
        Search for flight itineraries using graph path finding
        
        Args:
            origin: Origin airport code (IATA)
            destination: Destination airport code (IATA)
            search_date: Date of travel
            max_hops: Maximum number of stops (0, 1, or 2)
            max_results: Maximum results to return
            preferred_time_start: Preferred departure time start (HH:MM)
            preferred_time_end: Preferred departure time end (HH:MM)
        
        Returns:
            List of Itinerary objects
        """
        results = []
        service_date_str = search_date.strftime('%Y-%m-%d')
        
        # Use graph pattern matching to find paths with up to max_hops+1 edges
        # Each hop = 1 stop, so 0 hops = 1 edge (direct), 1 hop = 2 edges, 2 hops = 3 edges
        max_edges = max_hops
        
        # Cypher query to find all paths from origin to destination
        # with flight instances on the service date
        query = f"""
        MATCH path = (origin:Airport {{code: $origin}})-[:CONNECTS_TO*1..{max_edges}]->(dest:Airport {{code: $destination}})
        WITH path, [node in nodes(path) | node.code] as airport_codes
        WITH airport_codes, reduce(s = '', code IN airport_codes | s + code + '-') as path_id
        
        // For each path, find matching flight instances for each leg
        UNWIND range(0, size(airport_codes)-2) AS i
        WITH path_id, airport_codes, i, airport_codes[i] as leg_origin, airport_codes[i+1] as leg_dest
        
        MATCH (fi:FlightInstance {{
            service_date: $service_date,
            origin_code: leg_origin,
            dest_code: leg_dest
        }})
        
        RETURN DISTINCT 
            path_id,
            airport_codes,
            fi.id as instance_id,
            fi.carrier_code as carrier,
            fi.flight_number as flight_number,
            fi.origin_code as origin,
            fi.dest_code as destination,
            fi.departure_time_utc as departure_time,
            fi.arrival_time_utc as arrival_time,
            fi.duration_minutes as duration,
            fi.departure_terminal as dep_terminal,
            fi.arrival_terminal as arr_terminal,
            i as leg_index
        ORDER BY path_id, leg_index, fi.departure_time_utc
        LIMIT $limit
        """
        
        try:
            results_data = list(self.db.execute_and_fetch(query, {
                'origin': origin,
                'destination': destination,
                'service_date': service_date_str,
                'limit': max_results * 10  # Get more to allow for filtering
            }))
            
            if not results_data:
                # Try a simpler direct flight query
                results = self._search_direct(origin, destination, search_date, max_results)
            else:
                # Group results by path and create itineraries
                results = self._build_itineraries_from_results(results_data, max_hops)
        
        except Exception as e:
            print(f"Error in graph search: {e}")
            return []

        return results[:max_results]
    
    def _search_direct(
        self, origin: str, destination: str, search_date: date, limit: int = 50
    ) -> List[Itinerary]:
        """
        Search for direct flights using graph query
        """
        service_date_str = search_date.strftime('%Y-%m-%d')
        
        query = """
        MATCH (fi:FlightInstance {
            origin_code: $origin,
            dest_code: $destination,
            service_date: $service_date,
            is_active: true
        })
        MATCH (carrier:Carrier {code: fi.carrier_code})
        
        RETURN 
            fi.id as instance_id,
            fi.carrier_code as carrier,
            fi.flight_number as flight_number,
            fi.origin_code as origin,
            fi.dest_code as destination,
            fi.departure_time_utc as departure_time,
            fi.arrival_time_utc as arrival_time,
            fi.duration_minutes as duration
        ORDER BY fi.departure_time_utc
        LIMIT $limit
        """
        
        results = list(self.db.execute_and_fetch(query, {
            'origin': origin,
            'destination': destination,
            'service_date': service_date_str,
            'limit': limit
        }))
        
        itineraries = []
        for result in results:
            leg = FlightLeg(
                carrier=result['carrier'],
                flight_number=result['flight_number'],
                origin=result['origin'],
                destination=result['destination'],
                departure_time_utc=datetime.fromisoformat(result['departure_time']),
                arrival_time_utc=datetime.fromisoformat(result['arrival_time']),
                duration_minutes=result['duration']
            )
            
            itinerary = self._create_itinerary([leg], result['instance_id'])
            itineraries.append(itinerary)
        
        return itineraries
    
    def _build_itineraries_from_results(
        self, results_data: List[dict], max_hops: int
    ) -> List[Itinerary]:
        """
        Build itineraries from query results
        Groups legs into complete journeys
        """
        # Group by path_id and specific flight combination
        from collections import defaultdict
        paths = defaultdict(lambda: defaultdict(list))
        
        for result in results_data:
            path_id = result.get('path_id', 'unknown')
            leg_index = result.get('leg_index', 0)
            paths[path_id][leg_index].append(result)
        
        itineraries = []
        
        # For each unique path (e.g., BOM->DEL direct, or BOM->AMD->DEL)
        for path_id, legs_by_index in paths.items():
            # Get the expected number of legs for this path
            if not legs_by_index:
                continue
            
            expected_legs = max(legs_by_index.keys()) + 1
            
            # Generate all combinations of flights for this path
            # For direct flights (1 leg), just return each option
            # For multi-leg, we need to generate valid combinations
            if expected_legs == 1:
                # Direct flights - create one itinerary per flight option
                for flight_data in legs_by_index[0]:
                    leg = FlightLeg(
                        carrier=flight_data['carrier'],
                        flight_number=flight_data['flight_number'],
                        origin=flight_data['origin'],
                        destination=flight_data['destination'],
                        departure_time_utc=datetime.fromisoformat(flight_data['departure_time']),
                        arrival_time_utc=datetime.fromisoformat(flight_data['arrival_time']),
                        duration_minutes=flight_data['duration']
                    )
                    
                    itinerary = self._create_itinerary([leg], flight_data['instance_id'])
                    itineraries.append(itinerary)
            else:
                # Multi-leg journey - create combinations
                # This is simplified - in production you'd want to validate connection times
                self._create_multi_leg_itineraries(legs_by_index, expected_legs, itineraries)
        
        return itineraries
    
    def _create_multi_leg_itineraries(
        self, legs_by_index: dict, expected_legs: int, itineraries: List[Itinerary]
    ):
        """
        Create itineraries for multi-leg journeys with connection time validation
        """
        import itertools
        
        # Get all flight options for each leg
        leg_options = []
        for i in range(expected_legs):
            if i in legs_by_index:
                leg_options.append(legs_by_index[i])
            else:
                return  # Missing leg, can't build complete itinerary
        
        # Generate all combinations
        for combination in itertools.product(*leg_options):
            flight_legs = []
            valid = True
            
            for i, leg_data in enumerate(combination):
                leg = FlightLeg(
                    carrier=leg_data['carrier'],
                    flight_number=leg_data['flight_number'],
                    origin=leg_data['origin'],
                    destination=leg_data['destination'],
                    departure_time_utc=datetime.fromisoformat(leg_data['departure_time']),
                    arrival_time_utc=datetime.fromisoformat(leg_data['arrival_time']),
                    duration_minutes=leg_data['duration']
                )
                flight_legs.append(leg)
                
                # Validate connection time for subsequent legs
                if i > 0:
                    prev_leg = flight_legs[i-1]
                    connection_time = (leg.departure_time_utc - prev_leg.arrival_time_utc).total_seconds() / 60
                    
                    # Check minimum and maximum connection time
                    if connection_time < self.mct_domestic or connection_time > self.max_layover:
                        valid = False
                        break
            
            if valid and flight_legs:
                instance_id = combination[0]['instance_id'] if combination else None
                itinerary = self._create_itinerary(flight_legs, instance_id)
                itineraries.append(itinerary)
    
    def _create_itinerary(
        self, legs: List[FlightLeg], primary_instance_id: Optional[str] = None
    ) -> Itinerary:
        """
        Create an Itinerary object from flight legs
        """
        first_departure = legs[0].departure_time_utc
        last_arrival = legs[-1].arrival_time_utc
        total_duration = int((last_arrival - first_departure).total_seconds() / 60)
        
        # Try to get real fare from database
        total_price = self._get_fare_for_legs(legs, primary_instance_id)
        
        # Fallback to estimated price if no fare found
        if total_price is None:
            import random
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
    
    def _get_fare_for_legs(
        self, legs: List[FlightLeg], primary_instance_id: Optional[str] = None
    ) -> Optional[float]:
        """
        Get fare for flight legs from Memgraph
        """
        try:
            if len(legs) == 1 and primary_instance_id:
                # Direct flight - look up exact fare
                query = """
                MATCH (fi:FlightInstance {id: $instance_id})-[:HAS_FARE]->(f:Fare)
                RETURN f.total_price as price
                ORDER BY f.total_price ASC
                LIMIT 1
                """
                
                results = list(self.db.execute_and_fetch(query, {
                    'instance_id': primary_instance_id
                }))
                
                if results:
                    return float(results[0]['price'])
            else:
                # Multi-leg - sum individual leg fares if available
                total = 0
                all_found = True
                
                for leg in legs:
                    query = """
                    MATCH (fi:FlightInstance {
                        carrier_code: $carrier,
                        flight_number: $flight_number,
                        origin_code: $origin,
                        dest_code: $destination,
                        departure_time_utc: $departure_time
                    })-[:HAS_FARE]->(f:Fare)
                    RETURN f.total_price as price
                    ORDER BY f.total_price ASC
                    LIMIT 1
                    """
                    
                    results = list(self.db.execute_and_fetch(query, {
                        'carrier': leg.carrier,
                        'flight_number': leg.flight_number,
                        'origin': leg.origin,
                        'destination': leg.destination,
                        'departure_time': leg.departure_time_utc.isoformat()
                    }))
                    
                    if results:
                        total += float(results[0]['price'])
                    else:
                        all_found = False
                        break
                
                if all_found:
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
        """
        Filter itineraries by departure time window
        """
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
