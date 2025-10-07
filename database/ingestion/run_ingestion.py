"""
Master ingestion script for Memgraph - Run all ingestion steps in order
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.memgraph_config import init_db, reset_db, get_database_stats
from database.ingestion.ingest_reference_data import ingest_airports, ingest_carriers
from database.ingestion.ingest_routes import ingest_routes
from database.ingestion.ingest_flights import ingest_all_flights
from database.ingestion.ingest_fares import ingest_all_fares


def main():
    """
    Run complete ingestion pipeline for Memgraph
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Run complete data ingestion pipeline for Memgraph')
    parser.add_argument('--reset', action='store_true', help='Reset database before ingestion')
    parser.add_argument('--limit', type=int, help='Limit number of flight files to process (for testing)')
    parser.add_argument('--skip-flights', action='store_true', help='Skip flight data ingestion')
    parser.add_argument('--skip-fares', action='store_true', help='Skip fare data ingestion')
    args = parser.parse_args()
    
    print("\n" + "=" * 70)
    print(" " * 15 + "FLIGHT SEARCH DATA INGESTION - MEMGRAPH")
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
    
    # Step 2: Ingest routes (as CONNECTS_TO relationships)
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
    if not args.skip_flights:
        print("\nSTEP 3: Ingesting Flight Data")
        print("-" * 70)
        flights_data_dir = project_root / 'flights-data'
        
        if flights_data_dir.exists():
            ingest_all_flights(str(flights_data_dir), limit=args.limit)
        else:
            print(f"⚠️  Flight data directory not found at {flights_data_dir}")
    else:
        print("\nSTEP 3: Skipping Flight Data Ingestion")
        print("-" * 70)
    
    print("\n" + "-" * 70)
    
    # Step 4: Ingest fare data
    if not args.skip_fares:
        print("\nSTEP 4: Ingesting Fare Data")
        print("-" * 70)
        flights_data_dir = project_root / 'flights-data'
        
        if flights_data_dir.exists():
            ingest_all_fares(str(flights_data_dir), limit=args.limit)
        else:
            print(f"⚠️  Flight data directory not found at {flights_data_dir}")
    else:
        print("\nSTEP 4: Skipping Fare Data Ingestion")
        print("-" * 70)
    
    print("\n" + "=" * 70)
    print(" " * 20 + "INGESTION COMPLETED SUCCESSFULLY")
    print("=" * 70 + "\n")
    
    # Print summary
    print("Database Summary:")
    stats = get_database_stats()
    
    # Print node counts
    print(f"\nNodes:")
    print(f"  Airports:         {stats.get('Airport', 0)}")
    print(f"  Carriers:         {stats.get('Carrier', 0)}")
    print(f"  Flight Instances: {stats.get('FlightInstance', 0)}")
    print(f"  Fares:            {stats.get('Fare', 0)}")
    
    # Print relationship counts
    print(f"\nRelationships:")
    print(f"  CONNECTS_TO:      {stats.get('CONNECTS_TO', 0)}")
    print(f"  DEPARTS_FROM:     {stats.get('DEPARTS_FROM', 0)}")
    print(f"  ARRIVES_AT:       {stats.get('ARRIVES_AT', 0)}")
    print(f"  OPERATES:         {stats.get('OPERATES', 0)}")
    print(f"  HAS_FARE:         {stats.get('HAS_FARE', 0)}")
    
    print("\n" + "=" * 70)
    print("\nMemgraph Lab UI: http://localhost:3000")
    print("Bolt connection: bolt://localhost:7687")
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()
