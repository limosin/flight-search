"""
Ingest routes data from routes_summary.json into Memgraph
Creates CONNECTS_TO relationships between Airport nodes
"""

import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.memgraph_config import get_memgraph


def ingest_routes(routes_summary_path: str):
    """
    Ingest routes from routes_summary.json
    Creates CONNECTS_TO relationships between Airport nodes
    
    Args:
        routes_summary_path: Path to routes_summary.json file
    """
    db = get_memgraph()
    
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
        print("Ingesting routes as CONNECTS_TO relationships...")
        
        count = 0
        
        for route_key, route_info in routes_data.items():
            origin = route_info.get('origin')
            destination = route_info.get('destination')
            
            if not origin or not destination:
                print(f"Skipping route {route_key}: missing origin or destination")
                continue
            
            # Create CONNECTS_TO relationship between airports
            # Use MERGE to avoid duplicates
            query = """
            MATCH (a1:Airport {code: $origin})
            MATCH (a2:Airport {code: $destination})
            MERGE (a1)-[r:CONNECTS_TO]->(a2)
            SET r.route_key = $route_key,
                r.updated_at = timestamp()
            """
            
            try:
                db.execute(query, {
                    'origin': origin,
                    'destination': destination,
                    'route_key': route_key
                })
                count += 1
            except Exception as e:
                print(f"Error creating route {route_key}: {e}")
                continue
        
        print(f"✓ Routes ingested: {count} CONNECTS_TO relationships created")
        
    except Exception as e:
        print(f"✗ Error ingesting routes: {e}")
        raise


def main():
    """
    Main function to ingest routes data
    """
    print("=" * 60)
    print("Ingesting Routes Data to Memgraph")
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
