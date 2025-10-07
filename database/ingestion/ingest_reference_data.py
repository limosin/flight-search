"""
Ingest airports and carriers reference data into Memgraph
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.memgraph_config import get_memgraph, init_db
from database.ingestion.utils import AIRPORT_DATA, CARRIER_DATA


def ingest_airports():
    """
    Ingest airport reference data as nodes in Memgraph
    """
    db = get_memgraph()
    
    try:
        print("Ingesting airports...")
        count = 0
        
        for code, data in AIRPORT_DATA.items():
            # Use MERGE to avoid duplicates
            query = """
            MERGE (a:Airport {code: $code})
            SET a.name = $name,
                a.city = $city,
                a.country = $country,
                a.country_code = $country_code,
                a.timezone = $timezone,
                a.updated_at = timestamp()
            """
            
            db.execute(query, {
                'code': code,
                'name': data['name'],
                'city': data['city'],
                'country': data['country'],
                'country_code': data['country_code'],
                'timezone': data['timezone']
            })
            count += 1
        
        print(f"✓ Airports ingested: {count}")
        
    except Exception as e:
        print(f"✗ Error ingesting airports: {e}")
        raise


def ingest_carriers():
    """
    Ingest carrier/airline reference data as nodes in Memgraph
    """
    db = get_memgraph()
    
    try:
        print("Ingesting carriers...")
        count = 0
        
        for code, data in CARRIER_DATA.items():
            # Use MERGE to avoid duplicates
            query = """
            MERGE (c:Carrier {code: $code})
            SET c.name = $name,
                c.updated_at = timestamp()
            """
            
            db.execute(query, {
                'code': code,
                'name': data['name']
            })
            count += 1
        
        print(f"✓ Carriers ingested: {count}")
        
    except Exception as e:
        print(f"✗ Error ingesting carriers: {e}")
        raise


def main():
    """
    Main function to ingest reference data
    """
    print("=" * 60)
    print("Ingesting Reference Data to Memgraph")
    print("=" * 60)
    
    # Initialize database if needed
    init_db()
    
    # Ingest data
    ingest_airports()
    ingest_carriers()
    
    print("\n" + "=" * 60)
    print("Reference data ingestion completed")
    print("=" * 60)


if __name__ == "__main__":
    main()
