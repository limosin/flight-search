"""
Memgraph database configuration and connection management
Graph-based flight search system
"""

from gqlalchemy import Memgraph
from typing import Optional, Dict, List, Any
import os
from contextlib import contextmanager


# Memgraph connection settings
MEMGRAPH_HOST = os.getenv('MEMGRAPH_HOST', 'localhost')
MEMGRAPH_PORT = int(os.getenv('MEMGRAPH_PORT', '7687'))
MEMGRAPH_USER = os.getenv('MEMGRAPH_USER', '')
MEMGRAPH_PASSWORD = os.getenv('MEMGRAPH_PASSWORD', '')

# Connection string
MEMGRAPH_URI = f"bolt://{MEMGRAPH_HOST}:{MEMGRAPH_PORT}"


def get_memgraph() -> Memgraph:
    """
    Get Memgraph connection instance
    """
    if MEMGRAPH_USER and MEMGRAPH_PASSWORD:
        return Memgraph(
            host=MEMGRAPH_HOST,
            port=MEMGRAPH_PORT,
            username=MEMGRAPH_USER,
            password=MEMGRAPH_PASSWORD
        )
    else:
        return Memgraph(
            host=MEMGRAPH_HOST,
            port=MEMGRAPH_PORT
        )


@contextmanager
def get_db():
    """
    Context manager for database connection
    Usage:
        with get_db() as db:
            # do something with db
    """
    db = get_memgraph()
    try:
        yield db
    finally:
        # GQLAlchemy manages connections automatically
        pass


def init_db():
    """
    Initialize database - create indexes and constraints for optimal performance
    """
    db = get_memgraph()
    
    print("Initializing Memgraph database...")
    
    # Create indexes for Airport nodes
    try:
        db.execute("CREATE INDEX ON :Airport(code);")
        print("✓ Created index on Airport.code")
    except Exception as e:
        print(f"  Index on Airport.code already exists or error: {e}")
    
    # Create indexes for Carrier nodes
    try:
        db.execute("CREATE INDEX ON :Carrier(code);")
        print("✓ Created index on Carrier.code")
    except Exception as e:
        print(f"  Index on Carrier.code already exists or error: {e}")
    
    # Create indexes for FlightInstance nodes
    try:
        db.execute("CREATE INDEX ON :FlightInstance(service_date);")
        print("✓ Created index on FlightInstance.service_date")
    except Exception as e:
        print(f"  Index on FlightInstance.service_date already exists or error: {e}")
    
    try:
        db.execute("CREATE INDEX ON :FlightInstance(id);")
        print("✓ Created index on FlightInstance.id")
    except Exception as e:
        print(f"  Index on FlightInstance.id already exists or error: {e}")
    
    # Create indexes for Fare nodes
    try:
        db.execute("CREATE INDEX ON :Fare(fare_key);")
        print("✓ Created index on Fare.fare_key")
    except Exception as e:
        print(f"  Index on Fare.fare_key already exists or error: {e}")
    
    # Create constraint for unique airport codes
    try:
        db.execute("CREATE CONSTRAINT ON (a:Airport) ASSERT a.code IS UNIQUE;")
        print("✓ Created unique constraint on Airport.code")
    except Exception as e:
        print(f"  Constraint on Airport.code already exists or error: {e}")
    
    # Create constraint for unique carrier codes
    try:
        db.execute("CREATE CONSTRAINT ON (c:Carrier) ASSERT c.code IS UNIQUE;")
        print("✓ Created unique constraint on Carrier.code")
    except Exception as e:
        print(f"  Constraint on Carrier.code already exists or error: {e}")
    
    print("Database initialization completed")


def drop_db():
    """
    Drop all data - use with caution!
    """
    db = get_memgraph()
    
    print("Dropping all data from Memgraph...")
    
    # Delete all nodes and relationships
    db.execute("MATCH (n) DETACH DELETE n;")
    
    # Drop all indexes
    db.execute("DROP INDEX ON :Airport(code);")
    db.execute("DROP INDEX ON :Carrier(code);")
    db.execute("DROP INDEX ON :FlightInstance(service_date);")
    db.execute("DROP INDEX ON :FlightInstance(id);")
    db.execute("DROP INDEX ON :Fare(fare_key);")
    
    print("All data and indexes dropped")


def reset_db():
    """
    Reset database - drop and recreate all indexes
    """
    drop_db()
    init_db()
    print("Database reset successfully")


def execute_query(query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict]:
    """
    Execute a Cypher query and return results
    
    Args:
        query: Cypher query string
        parameters: Optional parameters for the query
        
    Returns:
        List of result dictionaries
    """
    db = get_memgraph()
    
    if parameters:
        results = db.execute_and_fetch(query, parameters)
    else:
        results = db.execute_and_fetch(query)
    
    return list(results)


def execute_write(query: str, parameters: Optional[Dict[str, Any]] = None):
    """
    Execute a write query (CREATE, MERGE, SET, DELETE)
    
    Args:
        query: Cypher query string
        parameters: Optional parameters for the query
    """
    db = get_memgraph()
    
    if parameters:
        db.execute(query, parameters)
    else:
        db.execute(query)


def get_database_stats() -> Dict[str, int]:
    """
    Get database statistics
    
    Returns:
        Dictionary with node and relationship counts
    """
    db = get_memgraph()
    
    stats = {}
    
    # Count nodes by label
    for label in ['Airport', 'Carrier', 'FlightInstance', 'Fare']:
        result = list(db.execute_and_fetch(f"MATCH (n:{label}) RETURN count(n) as count"))
        stats[label] = result[0]['count'] if result else 0
    
    # Count relationships
    relationships = [
        'DEPARTS_FROM', 
        'ARRIVES_AT', 
        'OPERATES', 
        'HAS_FARE',
        'CONNECTS_TO'
    ]
    
    for rel in relationships:
        result = list(db.execute_and_fetch(f"MATCH ()-[r:{rel}]->() RETURN count(r) as count"))
        stats[rel] = result[0]['count'] if result else 0
    
    return stats
