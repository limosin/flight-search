"""
Ingest routes data from routes_summary.json
"""

import sys
import os
import json
from pathlib import Path
from typing import Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.config import SessionLocal
from database.models import Route, Airport


def ingest_routes(routes_summary_path: str):
    """
    Ingest routes from routes_summary.json
    
    Args:
        routes_summary_path: Path to routes_summary.json file
    """
    db = SessionLocal()
    
    try:
        print(f"Loading routes data from {routes_summary_path}...")
        
        # Load routes summary JSON
        with open(routes_summary_path, 'r') as f:
            data = json.load(f)
        
        routes_data = data.get('routes', {})
        
        if not routes_data:
            print("No routes data found")
            return
        
        print(f"Found {len(routes_data)} routes")
        print("Ingesting routes...")
        
        count_new = 0
        count_updated = 0
        
        for route_key, route_info in routes_data.items():
            origin = route_info.get('origin')
            destination = route_info.get('destination')
            
            if not origin or not destination:
                print(f"Skipping route {route_key}: missing origin or destination")
                continue
            
            # Check if airports exist
            origin_airport = db.query(Airport).filter_by(code=origin).first()
            destination_airport = db.query(Airport).filter_by(code=destination).first()
            
            if not origin_airport or not destination_airport:
                print(f"Skipping route {route_key}: airport not found (origin: {origin}, dest: {destination})")
                continue
            
            # Check if route already exists (using new schema with source_code and destination_code)
            existing_route = db.query(Route).filter_by(
                source_code=origin,
                destination_code=destination
            ).first()
            
            if existing_route:
                route = existing_route
                count_updated += 1
            else:
                # Create new route (direct link only, no statistics)
                route = Route(
                    source_code=origin,
                    destination_code=destination
                )
                db.add(route)
                count_new += 1
            
            # Commit to get route ID
            db.flush()
        
        db.commit()
        print(f"✓ Routes ingested: {count_new} new, {count_updated} updated")
        
    except Exception as e:
        db.rollback()
        print(f"✗ Error ingesting routes: {e}")
        raise
    finally:
        db.close()


def main():
    """
    Main function to ingest routes data
    """
    print("=" * 60)
    print("Ingesting Routes Data")
    print("=" * 60)
    
    # Get the path to routes_summary.json
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    routes_file = project_root / 'flights-data' / 'routes_summary.json'
    
    if not routes_file.exists():
        print(f"Error: Routes summary file not found at {routes_file}")
        return
    
    ingest_routes(str(routes_file))
    
    print("\n" + "=" * 60)
    print("Routes data ingestion completed")
    print("=" * 60)


if __name__ == "__main__":
    main()
