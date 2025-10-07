#!/bin/bash

# Flight Search - Memgraph Quick Start Script
# This script helps you get the Memgraph-based flight search system up and running

set -e

echo "========================================="
echo "  Flight Search - Memgraph Quick Start"
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    echo "Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker compose &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed${NC}"
    echo "Please install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

echo -e "${GREEN}✓${NC} Docker and Docker Compose are installed"
echo ""

# Ask user if they want to reset existing data
if [ -d "memgraph-data" ]; then
    echo -e "${YELLOW}Warning: Existing Memgraph data found${NC}"
    read -p "Do you want to reset the database? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Removing existing data..."
        docker compose down -v
        sudo rm -rf memgraph-data memgraph-log memgraph-etc
        echo -e "${GREEN}✓${NC} Database reset"
    fi
fi

# Start services
echo ""
echo "Step 1: Starting Docker services..."
echo "-----------------------------------"
docker compose up -d

# Wait for services to be healthy
echo ""
echo "Step 2: Waiting for services to be healthy..."
echo "---------------------------------------------"

# Wait for Memgraph
echo -n "Waiting for Memgraph..."
for i in {1..30}; do
    if docker exec flight-search-memgraph mgconsole --host localhost -e "RETURN 1;" &> /dev/null; then
        echo -e " ${GREEN}✓${NC}"
        break
    fi
    echo -n "."
    sleep 2
done

# Wait for Backend
echo -n "Waiting for Backend..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health &> /dev/null; then
        echo -e " ${GREEN}✓${NC}"
        break
    fi
    echo -n "."
    sleep 2
done

# Ask if user wants to run data ingestion
echo ""
echo "Step 3: Data Ingestion"
echo "----------------------"
read -p "Do you want to run data ingestion now? (Y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    echo "Running data ingestion (this may take a few minutes)..."
    
    # Ask for limit
    read -p "Limit number of flight files to process? (Enter number or press Enter for all): " limit
    
    if [ -z "$limit" ]; then
        docker exec -it flight-search-backend python database/ingestion/run_ingestion.py
    else
        docker exec -it flight-search-backend python database/ingestion/run_ingestion.py --limit "$limit"
    fi
    
    echo -e "${GREEN}✓${NC} Data ingestion completed"
else
    echo "Skipping data ingestion. You can run it later with:"
    echo "  docker exec -it flight-search-backend python database/ingestion/run_ingestion.py"
fi

# Display final status
echo ""
echo "========================================="
echo "  System is ready!"
echo "========================================="
echo ""
echo "Services:"
echo "  • Memgraph Lab:    ${GREEN}http://localhost:3000${NC}"
echo "  • Backend API:     ${GREEN}http://localhost:8000${NC}"
echo "  • API Docs:        ${GREEN}http://localhost:8000/docs${NC}"
echo "  • Frontend:        ${GREEN}http://localhost:3001${NC}"
echo ""
echo "Useful commands:"
echo "  • View logs:       docker compose logs -f"
echo "  • Stop services:   docker compose down"
echo "  • Restart:         docker compose restart"
echo "  • Shell access:    docker exec -it flight-search-backend bash"
echo ""
echo "Database stats:"
docker exec flight-search-backend python -c "
from database.memgraph_config import get_database_stats
stats = get_database_stats()
print('  • Airports:        ', stats.get('Airport', 0))
print('  • Carriers:        ', stats.get('Carrier', 0))
print('  • Flight Instances:', stats.get('FlightInstance', 0))
print('  • Fares:           ', stats.get('Fare', 0))
print('  • Routes:          ', stats.get('CONNECTS_TO', 0))
" 2>/dev/null || echo "  (Run ingestion to populate data)"
echo ""
echo "For more details, see MEMGRAPH_MIGRATION.md"
echo ""
