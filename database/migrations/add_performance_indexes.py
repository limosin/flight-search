"""
Add performance indexes for optimized flight search queries

This migration adds composite indexes to optimize:
1. Bulk queries with IN clause on origin_code
2. Direct flight searches
3. Connection searches

Based on SEARCH_PERFORMANCE_ANALYSIS.md recommendations
"""

from sqlalchemy import create_engine, text
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.config import DATABASE_URL


def upgrade():
    """Add performance indexes"""
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        print("Adding performance indexes...")
        
        # Index 1: Optimized for origin + destination + date queries (direct flights)
        print("Creating idx_origin_dest_date_dep...")
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_origin_dest_date_dep 
            ON flight_instances(origin_code, destination_code, service_date, departure_time_utc)
        """))
        conn.commit()
        
        # Index 2: Optimized for origin + date queries (first legs)
        print("Creating idx_origin_date_dep...")
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_origin_date_dep 
            ON flight_instances(origin_code, service_date, departure_time_utc)
        """))
        conn.commit()
        
        # Index 3: Optimized for destination + date queries (for reverse lookups)
        print("Creating idx_dest_date_arr...")
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_dest_date_arr 
            ON flight_instances(destination_code, service_date, arrival_time_utc)
        """))
        conn.commit()
        
        # Index 4: Covering index for active flights (frequently filtered)
        print("Creating idx_active_origin_date...")
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_active_origin_date 
            ON flight_instances(is_active, origin_code, service_date) 
            WHERE is_active = 1
        """))
        conn.commit()
        
        print("✅ All performance indexes created successfully!")
        

def downgrade():
    """Remove performance indexes"""
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        print("Removing performance indexes...")
        
        conn.execute(text("DROP INDEX IF EXISTS idx_origin_dest_date_dep"))
        conn.execute(text("DROP INDEX IF EXISTS idx_origin_date_dep"))
        conn.execute(text("DROP INDEX IF EXISTS idx_dest_date_arr"))
        conn.execute(text("DROP INDEX IF EXISTS idx_active_origin_date"))
        conn.commit()
        
        print("✅ All performance indexes removed!")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Add performance indexes")
    parser.add_argument(
        "--downgrade",
        action="store_true",
        help="Remove the indexes instead of adding them"
    )
    
    args = parser.parse_args()
    
    if args.downgrade:
        downgrade()
    else:
        upgrade()
