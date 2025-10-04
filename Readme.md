# Flight Search Application

A multi-hop flight search system that finds viable flight itineraries between origin and destination airports, supporting up to 2 intermediate stops.


## Steps to Run

### Prerequisites

- Docker
- Docker Compose

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Flight-Search
   ```

2. **Execute the docker-start script**
   ```bash
   ./docker-start.sh
   ```

   This script will:
   - Build the Docker containers
   - Start the backend API server
   - Start the frontend application
   - Initialize the database with flight data

Head over to `localhost:3000` to interact with the search UI.

The application will be accessible at the configured ports once the containers are running.


## Code Structure

1. `app` - backend api code, implementing the search functionality
2. `database` - has the data parsing and migration code
3. `frontend` - small ui to interact with the API.


## Caveats
1. The UI does not support any other date and will crash if changed.
2. Almost 90% of the code has been AI written.