"""
Ingest airports and carriers reference data
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.config import SessionLocal, init_db
from database.models import Airport, Carrier
from database.ingestion.utils import AIRPORT_DATA, CARRIER_DATA
from sqlalchemy.exc import IntegrityError


def ingest_airports():
    """
    Ingest airport reference data
    """
    db = SessionLocal()
    
    try:
        print("Ingesting airports...")
        count_new = 0
        count_updated = 0
        
        for code, data in AIRPORT_DATA.items():
            # Check if airport already exists
            existing = db.query(Airport).filter_by(code=code).first()
            
            if existing:
                # Update existing record
                existing.name = data['name']
                existing.city = data['city']
                existing.country = data['country']
                existing.country_code = data['country_code']
                existing.timezone = data['timezone']
                count_updated += 1
            else:
                # Create new record
                airport = Airport(
                    code=code,
                    name=data['name'],
                    city=data['city'],
                    country=data['country'],
                    country_code=data['country_code'],
                    timezone=data['timezone']
                )
                db.add(airport)
                count_new += 1
        
        db.commit()
        print(f"✓ Airports ingested: {count_new} new, {count_updated} updated")
        
    except Exception as e:
        db.rollback()
        print(f"✗ Error ingesting airports: {e}")
        raise
    finally:
        db.close()


def ingest_carriers():
    """
    Ingest carrier/airline reference data
    """
    db = SessionLocal()
    
    try:
        print("Ingesting carriers...")
        count_new = 0
        count_updated = 0
        
        for code, data in CARRIER_DATA.items():
            # Check if carrier already exists
            existing = db.query(Carrier).filter_by(code=code).first()
            
            if existing:
                # Update existing record
                existing.name = data['name']
                count_updated += 1
            else:
                # Create new record
                carrier = Carrier(
                    code=code,
                    name=data['name']
                )
                db.add(carrier)
                count_new += 1
        
        db.commit()
        print(f"✓ Carriers ingested: {count_new} new, {count_updated} updated")
        
    except Exception as e:
        db.rollback()
        print(f"✗ Error ingesting carriers: {e}")
        raise
    finally:
        db.close()


def main():
    """
    Main function to ingest reference data
    """
    print("=" * 60)
    print("Ingesting Reference Data")
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
