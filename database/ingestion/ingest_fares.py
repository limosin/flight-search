"""
Ingest fares from flight API JSON files into Memgraph
Creates Fare nodes and HAS_FARE relationships to FlightInstance nodes
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, date
import uuid

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.memgraph_config import get_memgraph


def parse_fare_key_for_route(fare_key: str) -> Optional[Dict[str, Any]]:
    """
    Parse fare key to extract route and flight information
    
    Example fare_key:
    REGULAR__AMD|BLR|1760034600000|1|0|0|ECONOMY|IN||||REGULAR|production_IN_search_amadeus_dom_india_raw_pwd~AMD^DEL^AI^2686:DEL^BLR^AI^2815__AMADEUS__...
    """
    try:
        parts = fare_key.split('__')
        if len(parts) < 3:
            return None
        
        # Parse route info from second part (AMD|BLR|timestamp|...)
        route_parts = parts[1].split('|')
        if len(route_parts) < 3:
            return None
        
        origin = route_parts[0]
        destination = route_parts[1]
        timestamp_ms = int(route_parts[2])
        
        # Parse flight legs from the provider-specific part
        flight_info = None
        for part in parts:
            if '~' in part and '^' in part:
                flight_info = part.split('~')[-1]
                break
        
        if not flight_info:
            return None
        
        # Parse legs (AMD^DEL^AI^2686:DEL^BLR^AI^2815)
        legs = flight_info.split(':')
        parsed_legs = []
        
        for leg in legs:
            leg_parts = leg.split('^')
            if len(leg_parts) >= 4:
                parsed_legs.append({
                    'origin': leg_parts[0],
                    'destination': leg_parts[1],
                    'carrier': leg_parts[2],
                    'flight_number': leg_parts[3]
                })
        
        return {
            'origin': origin,
            'destination': destination,
            'timestamp_ms': timestamp_ms,
            'service_date': datetime.fromtimestamp(timestamp_ms / 1000).date(),
            'legs': parsed_legs
        }
    except Exception as e:
        print(f"Error parsing fare key: {e}")
        return None


def extract_fare_from_json(fare_id: str, fare_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract fare information from JSON fare object
    """
    try:
        pricing = fare_info.get('pricing', {})
        total_pricing = pricing.get('totalPricing', {})
        
        # Determine refundability and amenities
        is_refundable = False
        is_partial_refundable = False
        has_free_meal = False
        has_free_seat = False
        
        for tag in fare_info.get('benefitTags', []):
            benefit_type = tag.get('benefitType', '').upper()
            if 'FULLY_REFUNDABLE' in benefit_type or benefit_type == 'REFUNDABLE':
                is_refundable = True
            elif 'PARTIAL_REFUNDABLE' in benefit_type:
                is_partial_refundable = True
            elif 'MEAL' in benefit_type:
                has_free_meal = True
            elif 'SEAT' in benefit_type:
                has_free_seat = True
        
        fare_record = {
            'id': str(uuid.uuid4()),
            'fare_key': fare_id,
            'fare_brand': fare_info.get('brand', ''),
            'fare_category': fare_info.get('fareCategory', ''),
            
            # Pricing
            'currency': 'INR',
            'total_price': float(total_pricing.get('totalPrice', 0)),
            'base_fare': float(total_pricing.get('totalBaseFare', 0)),
            'total_tax': float(total_pricing.get('totalTax', 0)),
            
            # Baggage
            'checkin_baggage_kg': 15 if fare_info.get('checkInBaggageAllowed', False) else 0,
            'cabin_baggage_kg': 7,
            
            # Refundability
            'is_refundable': is_refundable,
            'is_partial_refundable': is_partial_refundable,
            
            # Amenities
            'has_free_meal': has_free_meal,
            'has_free_seat': has_free_seat,
        }
        
        return fare_record
    except Exception as e:
        print(f"Error extracting fare: {e}")
        return None


def ingest_fares_from_file(json_file_path: str, db) -> int:
    """
    Ingest fares from a single JSON file into Memgraph
    
    Returns:
        Number of fares inserted
    """
    print(f"Processing: {json_file_path}")
    
    with open(json_file_path, 'r') as f:
        data = json.load(f)
    
    fares_data = data.get('fares', {})
    inserted_count = 0
    skipped_count = 0
    
    for fare_id, fare_info in fares_data.items():
        try:
            # Extract fare record
            fare_record = extract_fare_from_json(fare_id, fare_info)
            if not fare_record:
                skipped_count += 1
                continue
            
            # Parse fare key to get route info
            route_info = parse_fare_key_for_route(fare_id)
            
            # Create Fare node
            if route_info and len(route_info['legs']) == 1:
                # Try to link to FlightInstance for direct flights
                leg = route_info['legs'][0]
                service_date_str = route_info['service_date'].strftime('%Y-%m-%d')
                
                query = """
                // Check if fare already exists
                OPTIONAL MATCH (existing:Fare {fare_key: $fare_key})
                WITH existing
                WHERE existing IS NULL
                
                // Find matching flight instance
                OPTIONAL MATCH (fi:FlightInstance {
                    carrier_code: $carrier_code,
                    flight_number: $flight_number,
                    origin_code: $origin_code,
                    dest_code: $dest_code,
                    service_date: $service_date
                })
                
                // Create Fare node
                CREATE (f:Fare {
                    id: $id,
                    fare_key: $fare_key,
                    fare_brand: $fare_brand,
                    fare_category: $fare_category,
                    currency: $currency,
                    total_price: $total_price,
                    base_fare: $base_fare,
                    total_tax: $total_tax,
                    checkin_baggage_kg: $checkin_baggage_kg,
                    cabin_baggage_kg: $cabin_baggage_kg,
                    is_refundable: $is_refundable,
                    is_partial_refundable: $is_partial_refundable,
                    has_free_meal: $has_free_meal,
                    has_free_seat: $has_free_seat,
                    created_at: timestamp()
                })
                
                // Create relationship if flight instance found
                FOREACH (instance IN CASE WHEN fi IS NOT NULL THEN [fi] ELSE [] END |
                    MERGE (instance)-[:HAS_FARE]->(f)
                )
                
                RETURN f.id as id
                """
                
                results = list(db.execute_and_fetch(query, {
                    **fare_record,
                    'carrier_code': leg['carrier'],
                    'flight_number': leg['flight_number'],
                    'origin_code': leg['origin'],
                    'dest_code': leg['destination'],
                    'service_date': service_date_str
                }))
                
                if results:
                    inserted_count += 1
                else:
                    skipped_count += 1
            else:
                # Create fare without flight instance link (multi-leg or unparseable)
                query = """
                // Check if fare already exists
                OPTIONAL MATCH (existing:Fare {fare_key: $fare_key})
                WITH existing
                WHERE existing IS NULL
                
                CREATE (f:Fare {
                    id: $id,
                    fare_key: $fare_key,
                    fare_brand: $fare_brand,
                    fare_category: $fare_category,
                    currency: $currency,
                    total_price: $total_price,
                    base_fare: $base_fare,
                    total_tax: $total_tax,
                    checkin_baggage_kg: $checkin_baggage_kg,
                    cabin_baggage_kg: $cabin_baggage_kg,
                    is_refundable: $is_refundable,
                    is_partial_refundable: $is_partial_refundable,
                    has_free_meal: $has_free_meal,
                    has_free_seat: $has_free_seat,
                    created_at: timestamp()
                })
                
                RETURN f.id as id
                """
                
                results = list(db.execute_and_fetch(query, fare_record))
                
                if results:
                    inserted_count += 1
                else:
                    skipped_count += 1
            
        except Exception as e:
            print(f"Error processing fare {fare_id[:50]}...: {e}")
            skipped_count += 1
            continue
    
    print(f"  Inserted: {inserted_count}, Skipped: {skipped_count}")
    
    return inserted_count


def ingest_all_fares(flights_data_dir: str, limit: Optional[int] = None):
    """
    Ingest fares from all JSON files in the flights-data directory
    
    Args:
        flights_data_dir: Path to flights-data directory
        limit: Optional limit on number of files to process
    """
    api_results_dir = Path(flights_data_dir) / 'api-results'
    
    if not api_results_dir.exists():
        print(f"API results directory not found: {api_results_dir}")
        return
    
    json_files = sorted(api_results_dir.glob('flights_*.json'))
    
    if limit:
        json_files = json_files[:limit]
    
    print(f"\nFound {len(json_files)} JSON files to process")
    print("-" * 70)
    
    db = get_memgraph()
    total_inserted = 0
    
    try:
        for json_file in json_files:
            inserted = ingest_fares_from_file(str(json_file), db)
            total_inserted += inserted
    except Exception as e:
        print(f"Error during fare ingestion: {e}")
        raise
    
    print("-" * 70)
    print(f"Total fares inserted: {total_inserted}")


def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Ingest fares from flight JSON files into Memgraph')
    parser.add_argument('--data-dir', default='flights-data', 
                       help='Path to flights-data directory')
    parser.add_argument('--limit', type=int, 
                       help='Limit number of files to process (for testing)')
    parser.add_argument('--file', help='Process a single JSON file')
    
    args = parser.parse_args()
    
    db = get_memgraph()
    
    try:
        if args.file:
            # Process single file
            inserted = ingest_fares_from_file(args.file, db)
            print(f"\nTotal fares inserted: {inserted}")
        else:
            # Process all files
            script_dir = Path(__file__).parent
            project_root = script_dir.parent.parent
            data_dir = project_root / args.data_dir
            
            ingest_all_fares(str(data_dir), limit=args.limit)
    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
