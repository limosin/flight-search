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
    
    Args:
        card: Flight card data from API
        db: Database session
        stats: Statistics dictionary to update
    """
    try:
        # Extract basic information
        travel_option_id = card.get('travelOptionId')
        summary = card.get('summary', {})
        
        # Get flight details from subTravelOptionIds (use first one for direct flights)
        sub_travel_options = card.get('subTravelOptionIds', [])
        if not sub_travel_options:
            stats['skipped_no_travel_options'] += 1
            return
        
        # Parse the travel option ID to get flight details
        # Format: "CARRIER-FLIGHT_NUMBER-ORIGIN-DEST-TIMESTAMP" or multi-leg with "__"
        legs = sub_travel_options[0].split('__')
        
        # For now, we'll focus on direct flights and simple connecting flights
        # Multi-leg complex itineraries will be handled separately
        
        # Get origin and destination from summary
        first_departure = summary.get('firstDeparture', {})
        last_arrival = summary.get('lastArrival', {})
        
        origin_code = safe_get(first_departure, 'airport', 'code')
        dest_code = safe_get(last_arrival, 'airport', 'code')
        
        if not origin_code or not dest_code:
            stats['skipped_missing_airports'] += 1
            return
        
        # Get airline from first flight
        flights_list = summary.get('flights', [])
        if not flights_list:
            stats['skipped_no_flights'] += 1
            return
        
        carrier_code = flights_list[0].get('airlineCode')
        flight_number = flights_list[0].get('flightNumber')
        
        if not carrier_code or not flight_number:
            stats['skipped_missing_carrier'] += 1
            return
        
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
        
        # Calculate duration
        duration_obj = summary.get('totalDuration', {})
        duration_minutes = duration_obj.get('hh', 0) * 60 + duration_obj.get('mm', 0)
        
        # Get number of stops
        stops = summary.get('stops', 0)
        
        # Get terminal information
        dep_terminal = safe_get(first_departure, 'airport', 'terminal', 'name')
        arr_terminal = safe_get(last_arrival, 'airport', 'terminal', 'name')
        
        # Check if route exists
        route = db.query(Route).filter_by(
            origin_code=origin_code,
            destination_code=dest_code
        ).first()
        
        if not route:
            # Create route if it doesn't exist
            route = Route(
                origin_code=origin_code,
                destination_code=dest_code,
                total_flights=0,
                direct_flights=0
            )
            db.add(route)
            db.flush()
            stats['routes_created'] += 1
        
        # Check if flight exists (carrier + flight_number + route)
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
        
        # Check if flight instance already exists
        existing_instance = db.query(FlightInstance).filter_by(
            flight_id=flight.id,
            departure_time_utc=dep_time_utc,
            arrival_time_utc=arr_time_utc
        ).first()
        
        if existing_instance:
            stats['instances_duplicates'] += 1
            return
        
        # Create flight instance
        flight_instance = FlightInstance(
            flight_id=flight.id,
            origin_code=origin_code,
            destination_code=dest_code,
            carrier_code=carrier_code,
            flight_number=flight_number,
            departure_time_utc=dep_time_utc,
            arrival_time_utc=arr_time_utc,
            service_date=service_date,
            duration_minutes=duration_minutes,
            stops=stops,
            departure_terminal=dep_terminal,
            arrival_terminal=arr_terminal,
            is_active=True
        )
        db.add(flight_instance)
        db.flush()
        stats['instances_created'] += 1
        
        # Note: Fare information is complex and nested in the API response
        # It would require additional processing from the fareOptions/faresByTravelOptionId
        # For now, we'll skip fare ingestion in this basic version
        
    except Exception as e:
        stats['errors'] += 1
        print(f"Error processing card: {e}")
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
        'skipped_missing_airports': 0,
        'skipped_no_flights': 0,
        'skipped_missing_carrier': 0,
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
        print(f"  - Missing airports:     {stats['skipped_missing_airports']}")
        print(f"  - No flights:           {stats['skipped_no_flights']}")
        print(f"  - Missing carrier:      {stats['skipped_missing_carrier']}")
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
