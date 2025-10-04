# Database Models - Visual Reference

## Entity Relationship Diagram

```
┌─────────────────┐
│    Airport      │
│─────────────────│
│ id (PK)         │
│ code (IATA)     │◄──────┐
│ name            │       │
│ city            │       │
│ country         │       │
│ timezone        │       │
└─────────────────┘       │
         ▲                │
         │                │
         │ FK             │ FK
         │                │
┌─────────────────────────┴────────────┐
│            Route                      │
│───────────────────────────────────────│
│ id (PK)                               │
│ origin_code (FK → Airport)            │
│ destination_code (FK → Airport)       │
│ total_flights                         │
│ direct_flights                        │
└───────────────────────────────────────┘
         ▲
         │ FK
         │
┌────────┴──────────┐
│     Flight        │
│───────────────────│           ┌─────────────────┐
│ id (PK)           │           │    Carrier      │
│ carrier_code ─────┼───────────┤─────────────────│
│ flight_number     │     FK    │ id (PK)         │
│ route_id (FK)     │           │ code (IATA)     │
└───────────────────┘           │ name            │
         ▲                      └─────────────────┘
         │ FK
         │
┌────────┴──────────────────────────────┐
│       FlightInstance                   │
│────────────────────────────────────────│
│ id (PK)                                │
│ flight_id (FK → Flight)                │
│ origin_code (denormalized)             │
│ destination_code (denormalized)        │
│ carrier_code (denormalized)            │
│ flight_number (denormalized)           │
│ departure_time_utc ⏰                  │
│ arrival_time_utc ⏰                    │
│ service_date 📅                        │
│ duration_minutes                       │
│ stops (0, 1, or 2)                    │
│ departure_terminal                     │
│ arrival_terminal                       │
└────────────────────────────────────────┘
         ▲
         │ FK
         │
┌────────┴──────────────────────────────┐
│          Fare                          │
│────────────────────────────────────────│
│ id (PK)                                │
│ flight_instance_id (FK)                │
│ fare_key (unique)                      │
│ fare_class (ECONOMY, BUSINESS)         │
│ fare_brand (REGULAR, SAVER)            │
│ total_price 💰                         │
│ base_fare                              │
│ total_tax                              │
│ checkin_baggage_kg                     │
│ cabin_baggage_kg                       │
│ is_refundable                          │
└────────────────────────────────────────┘

┌────────────────────────────────────────┐
│      LayoverAirport                    │
│────────────────────────────────────────│
│ id (PK)                                │
│ route_id (FK → Route)                  │
│ layover_airport_code (FK → Airport)    │
│ frequency                              │
└────────────────────────────────────────┘

┌────────────────────────────────────────┐
│       FlightLeg                        │
│────────────────────────────────────────│
│ id (PK)                                │
│ itinerary_id (groups legs)             │
│ leg_sequence (1, 2, 3)                 │
│ flight_instance_id (FK)                │
│ origin_code, destination_code          │
│ departure_time_utc, arrival_time_utc   │
│ connection_time_minutes                │
└────────────────────────────────────────┘
```

## Data Flow for Search

```
Search Request:
  - Origin: DEL
  - Destination: BOM  
  - Date: 2025-10-10
  - Max Hops: 2

         │
         ▼
┌────────────────────┐
│ Query FlightInstance│
│  WHERE:              │
│   origin_code = DEL  │
│   service_date = ... │
│                      │
│ INDEX USED:          │
│  origin_date_dep     │
└────────────────────┘
         │
         ▼
    ┌────────┐
    │Direct? │ (stops = 0)
    └────┬───┘
         │
    ┌────┴────┐
    │  YES    │  NO
    │         │
    ▼         ▼
  Return   Find connecting
  results  flights via
           layover airports
```

## Index Usage Patterns

### Primary Search Indexes

1. **Direct Flight Search**
   ```
   idx_flight_instance_origin_date_dep
   ├── origin_code
   ├── service_date  
   └── departure_time_utc
   ```

2. **Destination-based Search**
   ```
   idx_flight_instance_dest_date_arr
   ├── destination_code
   ├── service_date
   └── arrival_time_utc
   ```

3. **Route Search**
   ```
   idx_flight_instance_route_date
   ├── origin_code
   ├── destination_code
   └── service_date
   ```

## Sample Data Relationships

```
Airport: DEL (New Delhi, Asia/Kolkata)
    │
    ├── Route: DEL → BOM
    │     │
    │     ├── Flight: 6E 123 (IndiGo)
    │     │     │
    │     │     └── FlightInstance: 2025-10-10 06:00 UTC
    │     │           │
    │     │           └── Fare: ₹5,564 (REGULAR)
    │     │
    │     └── Flight: AI 456 (Air India)
    │           │
    │           └── FlightInstance: 2025-10-10 08:30 UTC
    │                 │
    │                 └── Fare: ₹11,794 (ECO VALUE)
    │
    └── Route: DEL → BLR
          │
          └── LayoverAirports: BOM, HYD, MAA
```

## Field Denormalization Strategy

**Why Denormalize?**
- FlightInstance duplicates carrier_code, origin_code, destination_code
- Avoids JOINs in time-critical search queries
- Trade-off: Slight data redundancy for major performance gain

```
WITHOUT Denormalization:
  SELECT fi.*, f.carrier_code, r.origin_code, r.destination_code
  FROM flight_instances fi
  JOIN flights f ON fi.flight_id = f.id
  JOIN routes r ON f.route_id = r.id
  WHERE r.origin_code = 'DEL' ...
  (3 table joins per query)

WITH Denormalization:
  SELECT *
  FROM flight_instances
  WHERE origin_code = 'DEL' ...
  (Single table, uses index)
```

## Time Zone Handling

```
API Data (ISO with timezone):
  "2025-10-10T23:00:00.000+05:30"
         │
         ▼
  Parse & Convert to UTC
         │
         ▼
  Store: 2025-10-10 17:30:00 (UTC)
         │
         ├──► service_date: 2025-10-10
         │    (local date at origin)
         │
         └──► departure_time_utc: 17:30:00
              (for calculations)
```

## Query Optimization Examples

### Fast Direct Flight Query
```sql
-- Uses: idx_flight_instance_origin_date_dep
SELECT * FROM flight_instances
WHERE origin_code = 'DEL'
  AND destination_code = 'BOM'
  AND service_date = '2025-10-10'
  AND stops = 0
ORDER BY departure_time_utc;
```

### Connection Flight Discovery
```sql
-- Step 1: Get layover airports
SELECT layover_airport_code 
FROM layover_airports la
JOIN routes r ON la.route_id = r.id
WHERE r.origin_code = 'DEL' 
  AND r.destination_code = 'BLR';

-- Step 2: Find first leg to layover
SELECT * FROM flight_instances
WHERE origin_code = 'DEL'
  AND destination_code IN ('BOM', 'HYD')
  AND service_date = '2025-10-10';

-- Step 3: Find second leg from layover
SELECT * FROM flight_instances
WHERE origin_code IN ('BOM', 'HYD')
  AND destination_code = 'BLR'
  AND departure_time_utc >= [first_leg_arrival + MCT];
```

## Storage Size Estimates

Based on 100 routes, ~9,200 flight instances:

| Table | Records | Size (SQLite) |
|-------|---------|---------------|
| airports | ~40 | < 1 KB |
| carriers | 6 | < 1 KB |
| routes | 100 | ~10 KB |
| flights | ~300 | ~20 KB |
| flight_instances | 9,200 | ~500 KB |
| fares | 0-18,400 | 0-2 MB |
| layover_airports | ~500 | ~30 KB |

**Total Database**: ~3-5 MB (without fares), ~7-10 MB (with fares)

## Scalability Considerations

### Current (SQLite)
- ✅ Perfect for development
- ✅ Handles 10K-100K flight instances
- ✅ No server setup needed

### Production (PostgreSQL)
- 🚀 Millions of flight instances
- 🚀 Concurrent searches
- 🚀 Table partitioning by date
- 🚀 Connection pooling
- 🚀 Better index types (GiST, BRIN)

---

**Legend:**
- PK = Primary Key
- FK = Foreign Key
- ⏰ = Timestamp field
- 📅 = Date field
- 💰 = Price field
