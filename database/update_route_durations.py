import argparse
from collections import defaultdict
from database.config import SessionLocal, engine
from sqlalchemy import text
from database.models.schema import Route, FlightInstance, Flight, Base


def compute_and_update(dry_run: bool = False):
    db = SessionLocal()
    try:
        # Query for average durations grouped by route_id
        sql = text("""
        SELECT f.route_id as route_id, AVG(fi.duration_minutes) as avg_duration
        FROM flight_instances fi
        JOIN flights f ON fi.flight_id = f.id
        WHERE fi.duration_minutes IS NOT NULL
        GROUP BY f.route_id
        """)

        result = db.execute(sql).fetchall()
        updates = {row[0]: int(row[1]) for row in result}

        if not updates:
            print("No duration data found to update routes.")
            return

        print(f"Found average durations for {len(updates)} routes")

        for route_id, avg in updates.items():
            print(f"Route {route_id}: avg duration = {avg:.2f} minutes")
            if not dry_run:
                db.query(Route).filter(Route.id == route_id).update({
                    'average_duration_minutes': float(avg)
                })
        
        if not dry_run:
            db.commit()
            print("Route durations updated successfully")
        else:
            print("Dry run - no changes committed")

    finally:
        db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Update average route durations from flight instances')
    parser.add_argument('--dry-run', action='store_true', help='Print updates without committing')
    args = parser.parse_args()
    compute_and_update(dry_run=args.dry_run)
