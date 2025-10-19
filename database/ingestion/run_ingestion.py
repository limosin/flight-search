"""
Master ingestion script - Run all ingestion steps in order
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.config import init_db, reset_db
from database.ingestion.ingest_reference_data import ingest_airports, ingest_carriers
from database.ingestion.ingest_routes import ingest_routes
from database.ingestion.ingest_flights import ingest_all_flights
from database.ingestion.ingest_fares import ingest_all_fares
from database.config import SessionLocal
from database.models import Airport, Carrier, Route, Flight, FlightInstance, Fare
from database.update_route_durations import compute_and_update as update_route_durations


def main():
    """
    Run complete ingestion pipeline
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Run complete data ingestion pipeline')
    parser.add_argument('--reset', action='store_true', help='Reset database before ingestion')
    args = parser.parse_args()
    
    print("\n" + "=" * 70)
    print(" " * 20 + "FLIGHT SEARCH DATA INGESTION")
    print("=" * 70 + "\n")
    
    # Step 0: Initialize or reset database
    if args.reset:
        print("⚠️  Resetting database (all existing data will be deleted)...")
        response = input("Are you sure? (yes/no): ")
        if response.lower() == 'yes':
            reset_db()
        else:
            print("Aborting reset")
            return
    else:
        print("Initializing database...")
        init_db()
    
    print("\n" + "-" * 70)
    
    # Step 1: Ingest reference data (airports and carriers)
    print("\nSTEP 1: Ingesting Reference Data")
    print("-" * 70)
    ingest_airports()
    ingest_carriers()
    
    print("\n" + "-" * 70)
    
    # Step 2: Ingest routes
    print("\nSTEP 2: Ingesting Routes")
    print("-" * 70)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    routes_file = project_root / 'flights-data' / 'routes_summary.json'
    
    if routes_file.exists():
        ingest_routes(str(routes_file))
    else:
        print(f"⚠️  Routes file not found at {routes_file}")
    
    print("\n" + "-" * 70)
    
    # Step 3: Ingest flight data
    print("\nSTEP 3: Ingesting Flight Data")
    print("-" * 70)
    flights_data_dir = project_root / 'flights-data'
    
    if flights_data_dir.exists():
        ingest_all_flights(str(flights_data_dir))
    else:
        print(f"⚠️  Flight data directory not found at {flights_data_dir}")
    
    print("\n" + "-" * 70)
    
    # Step 4: Ingest fare data
    print("\nSTEP 4: Ingesting Fare Data")
    print("-" * 70)
    flights_data_dir = project_root / 'flights-data'
    
    if flights_data_dir.exists():
        ingest_all_fares(str(flights_data_dir))
    else:
        print(f"⚠️  Flight data directory not found at {flights_data_dir}")

    print("\nSTEP 5: Computing and updating average route durations for routes")
    print("-" * 70)
    update_route_durations()
    
    print("\n" + "=" * 70)
    print(" " * 20 + "INGESTION COMPLETED SUCCESSFULLY")
    print("=" * 70 + "\n")

    
    db = SessionLocal()
    try:
        print("Database Summary:")
        print(f"  Airports:         {db.query(Airport).count()}")
        print(f"  Carriers:         {db.query(Carrier).count()}")
        print(f"  Routes:           {db.query(Route).count()}")
        print(f"  Flights:          {db.query(Flight).count()}")
        print(f"  Flight Instances: {db.query(FlightInstance).count()}")
        print(f"  Fares:            {db.query(Fare).count()}")
    finally:
        db.close()
    
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()
