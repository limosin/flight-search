Tech Spec: Flight Booking — Low-Level Design (Search-focused)


Overview
--------
This document is a concise low-level design (LLD) for a flight search subsystem that finds itineraries between a source and a destination allowing up to 2 hops (i.e., up to 2 intermediate stops; maximum 3 flight legs). The intent is a practical engineering design sketch — not a complete specification. User management, booking/holders, payments and downstream ticketing processes are intentionally out of scope.

Assumptions
-----------
- "Hops" means intermediate stops between origin and destination. "Up to 2 hops" = 0, 1, or 2 stops allowed (0..2), i.e., 1..3 legs.
- We operate on a daily search basis (searches are anchored to date/time ranges). Time zones are considered when computing connection feasibility.
- Flight schedule and inventory (seat availability, fares) are available from upstream providers and are represented as regularly-updated domain records.
- Pricing composition, taxes and fare rules are simplified for search: we return an aggregated price for an itinerary and a fareKey to fetch full fare details later.

Goals
-----
- Provide a RESTful search interface that returns viable itineraries between origin and destination for a requested date, constrained to <= 2 hops.
- Produce an efficient search algorithm and data layout suitable for medium-to-large scale use (millions of flights per day, thousands of concurrent searches).

Non-Goals / Out of Scope
------------------------
- User authentication, session management, and bookings.
- Detailed fare rule evaluation, refunds, or ticketing workflows.
- Carrier-specific business logic beyond connection time rules.

High-level architecture
-----------------------
- API Layer (stateless): Receives search requests, validates inputs, enforces rate limits, and orchestrates search.
- Search Service (stateful/ephemeral compute): Executes itinerary search algorithms. May call local caches, indexes, or persistent storage.
- Flight Catalog DB (primary store): Relational DB (Postgres) that stores flight schedules, flight segments, airports, carriers and fares. Append-only schedule load process keeps it updated.
- Adjacency / Connections Cache: Precomputed adjacency lists and popular O-D caches in Redis for fast candidate generation (especially for 1-stop and 2-stop combos).
- Inventory Cache / Seats: Redis or dedicated inventory service for available seat counts (strong consistency required for booking, but for search we can use slightly stale data with a freshness bound).
- Background Workers & Message Queue: Consume updates from provider feeds and regenerate precomputed connections, invalidate caches, update fares.

Data model (core entities)
--------------------------
All times are stored in UTC internally; local time display is done by clients.

Airport
- id: UUID (or IATA code as canonical string)
- code: string (IATA, e.g., "JFK")
- name: string
- timezone: string (tz database name)

Carrier
- id: UUID
- code: string (IATA)
- name: string

Route
- source : Airport
- destiantion : Airport

Flight
- Route
- Carrier
- Aircraft

FlightInstance (a scheduled operating flight instance)
- id: UUID
- Carrier
- Flight
- departure_time_utc: timestamp
- arrival_time_utc: timestamp
- service_date: date (the calendar date of departure in origin local)


Indexes and storage layout
-------------------------
- Postgres tables:
	- airports(airport_code PK) with timezone metadata
	- Carrier - pk on id and index on code
	- Route (1 to 1 mapping between airports ids)
	- flights(id PK), indexes on source and destination airports

- DB Indexes:
	- flights: (origin, service_date, dep_utc)  -- primary index for candidate lookup
	- flights: (destination, service_date, dep_utc) -- support reverse lookups if needed
	- fares: (schedule_id) and (fare_key)

- Partitioning Strategies? Only fight instances would

- Redis caches:
	- adjacency:<origin>:<date> => sorted set by dep_utc containing schedule_ids
	- od_cache:<origin>:<destination>:<date> => precomputed/aggregated itineraries for hot O-D pairs (0..2 hops)
	- fare_snapshot:<fare_key> => serialized FareSnapshot

Caching strategy
----------------
- Keep recent popular O-D pairs precomputed (daily recompute jobs). This serves the majority of queries efficiently.
- Use a TTL on per-search caches (e.g., 5–30 minutes) depending on expected fare volatility.
- Invalidate or update caches when upstream fare updates are received. Use a message queue and worker to recompute affected adjacency entries.


API contract — Search
---------------------
POST /v1/search
Request JSON
{
	"origin": "JFK",
	"destination": "LHR",
	"date": "2026-03-15",           // outbound date (ISO 8601)
	"passengers": 1,                  // simple integer for search pricing
	"cabin": "economy",             // optional
	"max_hops": 2,                    // 0..2 (default 2)
	"max_results": 50,                // cap to control response size
	"preferred_departure_time_window": { "start": "00:00", "end": "23:59" },
	"sort": "price"                  // price | duration | departure_time
}

Response JSON (200)
{
	"search_id": "uuid",
	"origin": "JFK",
	"destination": "LHR",
	"itineraries": [
		{
			"id": "uuid",
			"legs": [
				{
					"carrier": "AA",
					"flight_number": "AA100",
					"origin": "JFK",
					"destination": "LHR",
					"departure_time_utc": "2026-03-15T08:00:00Z",
					"arrival_time_utc": "2026-03-15T20:00:00Z",
					"duration_minutes": 720
				}
			],
			"stops": 0,
			"total_duration_minutes": 720,
			"price": { "currency": "USD", "amount": 55000 },
			"fare_key": "opaque-fare-key"
		}
	],
	"meta": { "returned": 1, "max_results": 50 }
}

Errors
- 400: invalid request
- 422: no itineraries found
- 429: rate limited
- 500: internal error

Search algorithm (LLD sketch)
-----------------------------
The search domain is a directed time-aware multi-graph where nodes are airport+time events (or simply airports when working with schedule buckets) and edges are flight legs that depart at a given time and arrive at a given time.

Constraints to enforce when building itineraries:
- max_hops (0..2)
- minimum connection time (MCT) — per-airport or per-carrier, e.g., 45 minutes
- maximum connection time / max_layover (e.g., 12 or 24 hours); configurable
- arrival must be before the next leg's departure, taking into account time zones and MCT
- avoid loops (same airport repeated in the same itinerary sequence) unless explicitly allowed

Candidate generation approach (practical and performant):
1) Candidate leg lookup: index FlightSchedule by origin + departure date/time range. Retrieve flights departing origin on the requested day (or time window). Use a time-sorted adjacency list: Redis sorted sets or DB index (origin, departure_time). Limit per-origin fetch to a sensible fanout (e.g., top N by frequency or earliest N).
2) For 0-hop (direct): filter candidate legs whose destination == requested destination.
3) For 1-hop: for each candidate first-leg (origin -> mid), fetch second-leg candidates where mid -> destination with departure_time >= first.arrival_time + MCT and within max_layover.
4) For 2-hop: extend the above: for each first-leg consider second-legs (mid1 -> mid2) and then third-leg (mid2 -> destination) using the same connection rules.

Pseudocode (simplified):

**** Figure out the pseudocode

Notes on complexity & pruning
- Naive expansion can explode combinatorially. Use the following to keep work bounded:
	- Limit firstLegs to flights departing in a reasonable time window and/or limit by carrier/popularity.
	- Early prune candidate chains whose accumulated minimum possible arrival time is worse than a covered threshold.
	- Apply route blacklists (e.g., disallow circling through far-away hubs) and deduplicate by airport sequences.
	- Use heuristics to prioritize cheaper/shorter carriers first during expansion.

Connection rules and timezones
-----------------------------
- All time arithmetic is done in UTC. To determine connection feasibility:
	connection_feasible = (next_dep_utc - prev_arr_utc) >= MCT(prev_airport)
- Use airport-specific MCTs when available; otherwise, fall back to a global default (e.g., 45 minutes for domestic, 90 minutes for international).

Pricing and availability in search
---------------------------------
- For search speed, use cached FareSnapshot if available and fresh. If no fresh snapshot, either return itinerary without price (and a fare_key to get price later) or perform a fast fare lookup.
- The search surfaces a price estimate and a fare_key; final price lock/booking must revalidate availability.

Concurrency & consistency
------------------------
- Flight schedules are read-mostly; updates come via batch feeds. Use eventual consistency for schedule updates; index rebuilds and Redis invalidation are managed by background workers.
- Fare and seat inventory are volatile. For search we allow slight staleness but include a freshness timestamp. For booking, a separate flow must re-check seat counts using strong consistency (not covered here).

Scaling considerations
----------------------
- Partitioning: shard FlightSchedule and fares by departure_date and origin region to localize queries.
- Precompute connections for common hubs and popular O-D pairs (especially 1-stop combos) to avoid on-the-fly combinatorial expansion.
- Horizontal scale of search nodes: stateless API + scaled search workers that read from shared caches and databases.
- Monitoring: track search latency P50/P95/P99, cache hit ratio for od_cache, per-search expansion counts, and queries per second.

Test cases and edge cases
-------------------------
- Happy path: direct flight available.
- 1-stop: good connection with MCT satisfied.
- 2-stop: two valid connections.
- No-route: return 422 (or empty list) with useful diagnostic.
- Tight MCT: connection within minimum allowed time should be rejected.
- Overnight layover: respect max_layover config.
- Circular routes: detect and disallow loops like A -> B -> A -> C.
- Timezone shifts: ensure correct ordering of times across zones.


Expectations
------------

1. Use the data dump to popoulate the DB.
2. Implement the search logic for n maximum hops.
3. Write test cases to evaluate the same.
4. 