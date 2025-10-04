# Flight Search Database

Database models and ingestion scripts for the Flight Search system, based on the Low-Level Design specification.

## Overview

This package provides:
- **SQLAlchemy models** for all flight-related entities
- **Ingestion scripts** to populate the database from JSON data files
- **Utilities** for data validation and statistics

## Data Models

Based on the tech spec requirements for a flight search system supporting up to 2 hops (0-2 intermediate stops):

### Core Entities

1. **Airport** - IATA codes, names, cities, timezones
2. **Carrier** - Airline codes and names
3. **Route** - Directional paths between two airports
4. **Flight** - Carrier's flight number on a specific route
5. **FlightInstance** - Scheduled flight on a specific date/time (main search entity)
6. **Fare** - Pricing information for flight instances
7. **FlightLeg** - Individual segments in multi-leg itineraries
8. **LayoverAirport** - Tracking of connection airports for routes

### Key Design Decisions

- **All times stored in UTC** - Conversions to local time handled in application layer
- **Service date** - Departure date in origin's local time (for search queries)
- **Denormalized fields** - Origin/destination codes duplicated in FlightInstance for query performance
- **Indexed fields** - Comprehensive indexes on (origin, date, departure_time) and similar combinations

## Database Schema

```
airports
├── id (PK)
├── code (IATA, unique, indexed)
├── name
├── city
├── country
├── timezone
└── timestamps

carriers
├── id (PK)
├── code (IATA, unique, indexed)
├── name
└── timestamps

routes
├── id (PK)
├── origin_code (FK → airports)
├── destination_code (FK → airports)
├── total_flights
├── direct_flights
└── timestamps
    Unique: (origin_code, destination_code)

flights
├── id (PK)
├── carrier_code (FK → carriers)
├── flight_number
├── route_id (FK → routes)
└── timestamps
    Unique: (carrier_code, flight_number, route_id)

flight_instances
├── id (PK)
├── flight_id (FK → flights)
├── origin_code (denormalized, FK → airports)
├── destination_code (denormalized, FK → airports)
├── carrier_code (denormalized)
├── flight_number (denormalized)
├── departure_time_utc (indexed)
├── arrival_time_utc (indexed)
├── service_date (indexed)
├── duration_minutes
├── stops (0 for direct)
├── terminals
└── timestamps
    Indexes: Multiple composite indexes for search queries

fares
├── id (PK)
├── flight_instance_id (FK → flight_instances)
├── fare_key (unique, indexed)
├── fare_class, brand, category
├── pricing (total, base, tax)
├── baggage allowances
├── amenities
└── timestamps

layover_airports
├── id (PK)
├── route_id (FK → routes)
├── layover_airport_code (FK → airports)
├── frequency
└── timestamps
    Unique: (route_id, layover_airport_code)
```

## Installation

### 1. Install Dependencies

```bash
cd database
pip install -r requirements.txt
```

Required packages:
- `sqlalchemy>=2.0.0` - ORM and database toolkit
- `pytz>=2023.3` - Timezone handling
- `psycopg2-binary>=2.9.0` - PostgreSQL adapter (optional)

### 2. Configure Database

Set the database URL via environment variable:

```bash
# SQLite (default)
export DATABASE_URL="sqlite:///flight_search.db"

# PostgreSQL
export DATABASE_URL="postgresql://user:password@localhost/flight_search"
```

Or create a `.env` file:
```
DATABASE_URL=sqlite:///flight_search.db
```

## Usage

### Quick Start - Complete Ingestion

Run the master ingestion script to populate the entire database:

```bash
python database/ingestion/run_ingestion.py
```

Options:
- `--reset` - Reset database (drops all tables and recreates)
- `--limit N` - Process only first N flight files (for testing)
- `--skip-flights` - Skip flight data ingestion

Example:
```bash
# Full ingestion with database reset
python database/ingestion/run_ingestion.py --reset

# Test with limited data
python database/ingestion/run_ingestion.py --limit 10
```

### Step-by-Step Ingestion

If you prefer to run steps individually:

#### 1. Initialize Database
```python
from database.config import init_db
init_db()
```

Or from command line:
```bash
python -c "from database.config import init_db; init_db()"
```

#### 2. Ingest Reference Data (Airports & Carriers)
```bash
python database/ingestion/ingest_reference_data.py
```

This populates:
- 40+ airports with IATA codes, names, cities, timezones
- 6 carriers (IndiGo, Air India, Air India Express, Akasa Air, SpiceJet, Star Air)

#### 3. Ingest Routes
```bash
python database/ingestion/ingest_routes.py
```

This reads `flights-data/routes_summary.json` and creates:
- Route records for all origin-destination pairs
- Route statistics (total flights, direct flights)
- Layover airport associations

#### 4. Ingest Flight Data
```bash
python database/ingestion/ingest_flights.py
```

Options:
- `--limit N` - Process only first N files

This reads all `flights-data/api-results/flights_*.json` files and creates:
- Flight records (carrier + flight number + route)
- FlightInstance records (scheduled flights with times)

### Database Statistics and Validation

View database statistics:
```bash
python database/ingestion/db_stats.py
```

Run data validation checks:
```bash
python database/ingestion/db_stats.py --validate
```

This shows:
- Record counts for all tables
- Top routes by flight count
- Carrier distribution
- Direct vs connecting flights ratio
- Price statistics (if fares are ingested)
- Data integrity checks

## Data Flow

```
routes_summary.json
      ↓
[ingest_routes.py]
      ↓
   Routes + Layover Airports

flights_data/api-results/*.json
      ↓
[ingest_flights.py]
      ↓
   Flights + FlightInstances
```

## Query Examples

### Get all direct flights from DEL to BOM on a specific date
```python
from database.config import SessionLocal
from database.models import FlightInstance
from datetime import date

db = SessionLocal()

flights = db.query(FlightInstance).filter(
    FlightInstance.origin_code == 'DEL',
    FlightInstance.destination_code == 'BOM',
    FlightInstance.service_date == date(2025, 10, 10),
    FlightInstance.stops == 0
).order_by(FlightInstance.departure_time_utc).all()

for flight in flights:
    print(f"{flight.carrier_code}{flight.flight_number}: "
          f"{flight.departure_time_utc} → {flight.arrival_time_utc} "
          f"({flight.duration_minutes}min)")

db.close()
```

### Find all routes with more than 50 flights
```python
from database.models import Route

db = SessionLocal()

busy_routes = db.query(Route).filter(
    Route.total_flights > 50
).order_by(Route.total_flights.desc()).all()

for route in busy_routes:
    print(f"{route.origin_code} → {route.destination_code}: "
          f"{route.total_flights} flights "
          f"({route.direct_flights} direct)")

db.close()
```

### Get all flights for a specific carrier on a date
```python
from database.models import FlightInstance

db = SessionLocal()

indigo_flights = db.query(FlightInstance).filter(
    FlightInstance.carrier_code == '6E',
    FlightInstance.service_date == date(2025, 10, 10)
).count()

print(f"IndiGo has {indigo_flights} flight instances on 2025-10-10")

db.close()
```

## Limitations & Future Enhancements

### Current Limitations

1. **Fare Data** - Fares are not fully ingested (complex nested structure in API)
2. **Multi-leg Itineraries** - FlightLeg model is defined but not populated
3. **Connection Time Validation** - Minimum connection time (MCT) not enforced during ingestion
4. **Aircraft Details** - Aircraft type field exists but not populated from current data
5. **Seat Availability** - Not tracked in current implementation

### Planned Enhancements

1. **Fare Ingestion** - Parse and store fare options from API responses
2. **Itinerary Builder** - Populate FlightLeg for multi-leg journeys
3. **Search Optimization** - Add Redis caching layer for hot routes
4. **Data Updates** - Incremental update mechanism for schedule changes
5. **Partitioning** - Table partitioning by service_date for large datasets
6. **Time Zone Handling** - Enhanced timezone conversion utilities
7. **Data Quality** - More comprehensive validation rules

## Tech Spec Alignment

This implementation aligns with the technical specification:

✓ All times in UTC internally  
✓ Service date as local departure date  
✓ Airport with timezone information  
✓ Carrier and Flight entities  
✓ FlightInstance as core search entity  
✓ Route modeling for O-D pairs  
✓ Indexes on (origin, service_date, dep_utc)  
✓ Support for 0-2 hops (via stops field)  
✓ Denormalized fields for query performance  

## Troubleshooting

### "No module named 'sqlalchemy'"
```bash
pip install -r database/requirements.txt
```

### "No such table" error
Initialize the database first:
```bash
python -c "from database.config import init_db; init_db()"
```

### "No flight files found"
Ensure you're running from the project root and `flights-data/api-results/` exists with JSON files.

### Performance issues with large datasets
Consider:
- Using PostgreSQL instead of SQLite
- Adding more indexes for your specific query patterns
- Implementing batch commits in ingestion scripts

## Contributing

When adding new models:
1. Define model in `database/models/schema.py`
2. Add to `__all__` in `database/models/__init__.py`
3. Create migration/ingestion script
4. Update this README with schema details

## License

Part of the Flight Search System project.
