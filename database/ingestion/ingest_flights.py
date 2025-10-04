"""
Ingest flight data from API result JSON files
"""

import sys
import os
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.config import SessionLocal
from database.models import (
    Flight, FlightInstance, Fare, Route, Airport, Carrier
)
from database.ingestion.utils import (
    parse_datetime_from_api, get_service_date, calculate_duration_minutes,
    generate_fare_key, safe_get, AIRPORT_DATA
)


def process_flight_card(card: Dict, db, stats: Dict):
    """
    Process a single flight card from API response
    Parse each individual leg as a separate route and create flight instances
    
    For multi-leg journeys, each leg is stored as a separate route/flight/instance.
    The search algorithm will later combine these to find multi-hop itineraries.
    
    Args:
        card: Flight card data from API
        db: Database session
        stats: Statistics dictionary to update
    """
    try:
        summary = card.get('summary', {})
        
        # Get sub travel options which show the leg structure
        sub_travel_options = card.get('subTravelOptionIds', [])
        if not sub_travel_options:
            stats['skipped_no_travel_options'] += 1
            return
        
        # Get flights array which has individual flight details
        flights_list = summary.get('flights', [])
        if not flights_list:
            stats['skipped_no_flights'] += 1
            return
        
        # Parse the first sub_travel_option to extract leg information
        # Format: "CARRIER-FLIGHT_NUM-ORIG-DEST-TIMESTAMP__CARRIER-FLIGHT_NUM-ORIG-DEST-TIMESTAMP"
        leg_strings = sub_travel_options[0].split('__')
        
        # Each leg_string should correspond to a flight in flights_list
        if len(leg_strings) != len(flights_list):
            # For direct flights, there might be 1 flight in the list
            # but the structure is still valid
            pass
        
        # Process each leg
        for i, leg_str in enumerate(leg_strings):
            parts = leg_str.split('-')
            if len(parts) < 5:
                stats['skipped_invalid_format'] += 1
                continue
            
            carrier_code = parts[0]
            flight_number = parts[1]
            origin_code = parts[2]
            dest_code = parts[3]
            # timestamp = parts[4]  # Unix timestamp
            
            # Validate we have the necessary data
            if not all([carrier_code, flight_number, origin_code, dest_code]):
                stats['skipped_missing_data'] += 1
                continue
            
            # For timing, we need to extract from the appropriate part of summary
            # For the first leg, use firstDeparture
            # For the last leg, use lastArrival
            # For middle legs, we'd need more complex parsing
            
            # Simplified approach: for now, create routes and flights
            # but only create instances for flights we can get proper timing for
            
            if len(leg_strings) == 1:
                # Direct flight - use firstDeparture and lastArrival
                first_departure = summary.get('firstDeparture', {})
                last_arrival = summary.get('lastArrival', {})
                
                process_single_leg(
                    carrier_code, flight_number, origin_code, dest_code,
                    first_departure, last_arrival, db, stats
                )
            else:
                # Multi-leg flight
                # We'll create the route and flight but skip instance creation
                # since we don't have individual leg timings in the current data
                create_route_and_flight(
                    carrier_code, flight_number, origin_code, dest_code,
                    db, stats
                )
        
    except Exception as e:
        stats['errors'] += 1
        print(f"Error processing card: {e}")


def create_route_and_flight(carrier_code: str, flight_number: str, 
                            origin_code: str, dest_code: str, db, stats: Dict):
    """
    Create route and flight without instance (for legs we don't have timing for)
    
    Args:
        carrier_code: Airline code
        flight_number: Flight number
        origin_code: Origin airport code
        dest_code: Destination airport code
        db: Database session
        stats: Statistics dictionary
    """
    try:
        # Step 1: Check/Create Route
        route = db.query(Route).filter_by(
            source_code=origin_code,
            destination_code=dest_code
        ).first()
        
        if not route:
            route = Route(
                source_code=origin_code,
                destination_code=dest_code
            )
            db.add(route)
            db.flush()
            stats['routes_created'] += 1
        
        # Step 2: Check/Create Flight
        flight = db.query(Flight).filter_by(
            carrier_code=carrier_code,
            flight_number=flight_number,
            route_id=route.id
        ).first()
        
        if not flight:
            flight = Flight(
                carrier_code=carrier_code,
                flight_number=flight_number,
                route_id=route.id
            )
            db.add(flight)
            db.flush()
            stats['flights_created'] += 1
        
    except Exception as e:
        stats['errors'] += 1
        print(f"Error creating route/flight {carrier_code}-{flight_number}: {e}")


def process_single_leg(carrier_code: str, flight_number: str, origin_code: str, 
                      dest_code: str, first_departure: Dict, last_arrival: Dict,
                      db, stats: Dict):
    """
    Process a single flight leg and create route, flight, and flight instance
    
    Args:
        carrier_code: Airline code
        flight_number: Flight number
        origin_code: Origin airport code
        dest_code: Destination airport code
        first_departure: Departure info dict
        last_arrival: Arrival info dict
        db: Database session
        stats: Statistics dictionary
    """
    try:
        # Get timing information
        dep_time_str = safe_get(first_departure, 'airport', 'time')
        arr_time_str = safe_get(last_arrival, 'airport', 'time')
        
        if not dep_time_str or not arr_time_str:
            stats['skipped_missing_times'] += 1
            return
        
        # Get timezone from airport data
        origin_tz = AIRPORT_DATA.get(origin_code, {}).get('timezone', 'Asia/Kolkata')
        
        # Parse times to UTC
        dep_time_utc = parse_datetime_from_api(dep_time_str, origin_tz)
        arr_time_utc = parse_datetime_from_api(arr_time_str, origin_tz)
        
        # Get service date
        service_date = get_service_date(dep_time_utc, origin_tz)
        
        # Calculate duration in minutes
        duration_seconds = (arr_time_utc - dep_time_utc).total_seconds()
        duration_minutes = int(duration_seconds / 60)
        
        # Get terminal information
        dep_terminal = safe_get(first_departure, 'airport', 'terminal', 'name')
        arr_terminal = safe_get(last_arrival, 'airport', 'terminal', 'name')
        
        # Step 1: Check/Create Route (direct link only)
        route = db.query(Route).filter_by(
            source_code=origin_code,
            destination_code=dest_code
        ).first()
        
        if not route:
            route = Route(
                source_code=origin_code,
                destination_code=dest_code
            )
            db.add(route)
            db.flush()
            stats['routes_created'] += 1
        
        # Step 2: Check/Create Flight (links carrier + flight_number to route)
        flight = db.query(Flight).filter_by(
            carrier_code=carrier_code,
            flight_number=flight_number,
            route_id=route.id
        ).first()
        
        if not flight:
            flight = Flight(
                carrier_code=carrier_code,
                flight_number=flight_number,
                route_id=route.id
            )
            db.add(flight)
            db.flush()
            stats['flights_created'] += 1
        
        # Step 3: Check/Create FlightInstance
        existing_instance = db.query(FlightInstance).filter_by(
            flight_id=flight.id,
            departure_time_utc=dep_time_utc,
            arrival_time_utc=arr_time_utc,
            service_date=service_date
        ).first()
        
        if existing_instance:
            stats['instances_duplicates'] += 1
            return
        
        # Create flight instance
        flight_instance = FlightInstance(
            flight_id=flight.id,
            departure_time_utc=dep_time_utc,
            arrival_time_utc=arr_time_utc,
            service_date=service_date,
            duration_minutes=duration_minutes,
            departure_terminal=dep_terminal,
            arrival_terminal=arr_terminal,
            is_active=True
        )
        db.add(flight_instance)
        db.flush()
        stats['instances_created'] += 1
        
    except Exception as e:
        stats['errors'] += 1
        print(f"Error processing leg {carrier_code}-{flight_number}: {e}")


        # Don't raise - continue with next card


def ingest_flight_file(file_path: str, db, stats: Dict):
    """
    Ingest flights from a single JSON file
    
    Args:
        file_path: Path to the flight JSON file
        db: Database session
        stats: Statistics dictionary to update
    """
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        cards = data.get('cards', {})
        journey_cards = cards.get('J1', [])
        
        if not journey_cards:
            stats['files_no_cards'] += 1
            return
        
        stats['files_processed'] += 1
        
        # Process each card
        for card in journey_cards:
            process_flight_card(card, db, stats)
        
        # Commit after each file
        db.commit()
        
    except Exception as e:
        db.rollback()
        stats['files_error'] += 1
        print(f"Error processing file {file_path}: {e}")


def ingest_all_flights(flights_data_dir: str, limit: Optional[int] = None):
    """
    Ingest all flight JSON files from the flights-data/api-results directory
    
    Args:
        flights_data_dir: Path to flights-data directory
        limit: Optional limit on number of files to process (for testing)
    """
    db = SessionLocal()
    
    # Statistics
    stats = {
        'files_processed': 0,
        'files_no_cards': 0,
        'files_error': 0,
        'routes_created': 0,
        'flights_created': 0,
        'instances_created': 0,
        'instances_duplicates': 0,
        'skipped_no_travel_options': 0,
        'skipped_no_flights': 0,
        'skipped_invalid_format': 0,
        'skipped_missing_data': 0,
        'skipped_missing_times': 0,
        'errors': 0
    }
    
    try:
        api_results_dir = Path(flights_data_dir) / 'api-results'
        
        if not api_results_dir.exists():
            print(f"Error: API results directory not found at {api_results_dir}")
            return
        
        # Get all JSON files
        json_files = list(api_results_dir.glob('flights_*.json'))
        
        if not json_files:
            print(f"No flight JSON files found in {api_results_dir}")
            return
        
        total_files = len(json_files)
        if limit:
            json_files = json_files[:limit]
            print(f"Processing {len(json_files)} of {total_files} files (limited)")
        else:
            print(f"Processing all {total_files} files")
        
        # Process each file
        for i, json_file in enumerate(json_files, 1):
            if i % 10 == 0:
                print(f"Progress: {i}/{len(json_files)} files processed...")
            
            ingest_flight_file(str(json_file), db, stats)
        
        print("\n" + "=" * 60)
        print("Ingestion Statistics")
        print("=" * 60)
        print(f"Files processed:          {stats['files_processed']}")
        print(f"Files with no cards:      {stats['files_no_cards']}")
        print(f"Files with errors:        {stats['files_error']}")
        print(f"\nRoutes created:           {stats['routes_created']}")
        print(f"Flights created:          {stats['flights_created']}")
        print(f"Flight instances created: {stats['instances_created']}")
        print(f"Duplicate instances:      {stats['instances_duplicates']}")
        print(f"\nSkipped records:")
        print(f"  - No travel options:    {stats['skipped_no_travel_options']}")
        print(f"  - No flights:           {stats['skipped_no_flights']}")
        print(f"  - Invalid format:       {stats['skipped_invalid_format']}")
        print(f"  - Missing data:         {stats['skipped_missing_data']}")
        print(f"  - Missing times:        {stats['skipped_missing_times']}")
        print(f"\nErrors:                   {stats['errors']}")
        
    except Exception as e:
        print(f"✗ Fatal error during ingestion: {e}")
        raise
    finally:
        db.close()


def main():
    """
    Main function to ingest flight data
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Ingest flight data from JSON files')
    parser.add_argument('--limit', type=int, help='Limit number of files to process (for testing)')
    args = parser.parse_args()
    
    print("=" * 60)
    print("Ingesting Flight Data")
    print("=" * 60)
    
    # Get the path to flights-data directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    flights_data_dir = project_root / 'flights-data'
    
    if not flights_data_dir.exists():
        print(f"Error: Flights data directory not found at {flights_data_dir}")
        return
    
    ingest_all_flights(str(flights_data_dir), limit=args.limit)
    
    print("\n" + "=" * 60)
    print("Flight data ingestion completed")
    print("=" * 60)


if __name__ == "__main__":
    main()
