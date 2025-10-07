"""
Ingest flight data from API result JSON files into Memgraph
Creates FlightInstance nodes and relationships to Airport and Carrier nodes
"""

import sys
import json
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
import uuid

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.memgraph_config import get_memgraph
from database.ingestion.utils import (
    parse_datetime_from_api, get_service_date, safe_get, AIRPORT_DATA
)


def process_flight_card(card: Dict, db, stats: Dict):
    """
    Process a single flight card from API response
    Parse each individual leg as a separate flight instance
    
    Args:
        card: Flight card data from API
        db: Memgraph connection
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
        leg_strings = sub_travel_options[0].split('__')
        
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
            
            # Validate we have the necessary data
            if not all([carrier_code, flight_number, origin_code, dest_code]):
                stats['skipped_missing_data'] += 1
                continue
            
            if len(leg_strings) == 1:
                # Direct flight - use firstDeparture and lastArrival
                first_departure = summary.get('firstDeparture', {})
                last_arrival = summary.get('lastArrival', {})
                
                process_single_leg(
                    carrier_code, flight_number, origin_code, dest_code,
                    first_departure, last_arrival, db, stats
                )
        
    except Exception as e:
        stats['errors'] += 1
        print(f"Error processing card: {e}")


def process_single_leg(carrier_code: str, flight_number: str, origin_code: str, 
                      dest_code: str, first_departure: Dict, last_arrival: Dict,
                      db, stats: Dict):
    """
    Process a single flight leg and create FlightInstance node with relationships
    
    Args:
        carrier_code: Airline code
        flight_number: Flight number
        origin_code: Origin airport code
        dest_code: Destination airport code
        first_departure: Departure info dict
        last_arrival: Arrival info dict
        db: Memgraph connection
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
        dep_terminal = safe_get(first_departure, 'airport', 'terminal', 'name') or ''
        arr_terminal = safe_get(last_arrival, 'airport', 'terminal', 'name') or ''
        
        # Generate unique ID for flight instance
        instance_id = str(uuid.uuid4())
        
        # Create FlightInstance node with relationships
        # Using MERGE to avoid duplicates based on key properties
        query = """
        MATCH (origin:Airport {code: $origin_code})
        MATCH (dest:Airport {code: $dest_code})
        MATCH (carrier:Carrier {code: $carrier_code})
        
        MERGE (fi:FlightInstance {
            carrier_code: $carrier_code,
            flight_number: $flight_number,
            origin_code: $origin_code,
            dest_code: $dest_code,
            service_date: $service_date,
            departure_time_utc: $departure_time_utc
        })
        ON CREATE SET
            fi.id = $instance_id,
            fi.arrival_time_utc = $arrival_time_utc,
            fi.duration_minutes = $duration_minutes,
            fi.departure_terminal = $departure_terminal,
            fi.arrival_terminal = $arrival_terminal,
            fi.is_active = true,
            fi.created_at = timestamp()
        ON MATCH SET
            fi.updated_at = timestamp()
        
        MERGE (fi)-[:DEPARTS_FROM]->(origin)
        MERGE (fi)-[:ARRIVES_AT]->(dest)
        MERGE (carrier)-[:OPERATES]->(fi)
        
        RETURN fi.id as id
        """
        
        results = list(db.execute_and_fetch(query, {
            'instance_id': instance_id,
            'carrier_code': carrier_code,
            'flight_number': flight_number,
            'origin_code': origin_code,
            'dest_code': dest_code,
            'service_date': service_date.strftime('%Y-%m-%d'),
            'departure_time_utc': dep_time_utc.isoformat(),
            'arrival_time_utc': arr_time_utc.isoformat(),
            'duration_minutes': duration_minutes,
            'departure_terminal': dep_terminal,
            'arrival_terminal': arr_terminal
        }))
        
        if results:
            stats['instances_created'] += 1
        
    except Exception as e:
        stats['errors'] += 1
        print(f"Error processing leg {carrier_code}-{flight_number}: {e}")


def ingest_flight_file(file_path: str, db, stats: Dict):
    """
    Ingest flights from a single JSON file
    
    Args:
        file_path: Path to the flight JSON file
        db: Memgraph connection
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
        
    except Exception as e:
        stats['files_error'] += 1
        print(f"Error processing file {file_path}: {e}")


def ingest_all_flights(flights_data_dir: str, limit: Optional[int] = None):
    """
    Ingest all flight JSON files from the flights-data/api-results directory
    
    Args:
        flights_data_dir: Path to flights-data directory
        limit: Optional limit on number of files to process (for testing)
    """
    db = get_memgraph()
    
    # Statistics
    stats = {
        'files_processed': 0,
        'files_no_cards': 0,
        'files_error': 0,
        'instances_created': 0,
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
        print(f"\nFlight instances created: {stats['instances_created']}")
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


def main():
    """
    Main function to ingest flight data
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Ingest flight data from JSON files into Memgraph')
    parser.add_argument('--limit', type=int, help='Limit number of files to process (for testing)')
    args = parser.parse_args()
    
    print("=" * 60)
    print("Ingesting Flight Data to Memgraph")
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
