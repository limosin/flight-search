#!/bin/bash

# Docker Quick Start Script for Flight Search Application

set -e

echo "🐳 Flight Search Application - Docker Quick Start"
echo "=================================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    echo "   Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    echo "   Visit: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"
echo ""

# Check if database file exists
if [ ! -f "flight_search.db" ]; then
    echo "⚠️  Warning: flight_search.db not found in current directory"
    echo "   The application will start but may not have flight data."
    echo ""
fi

echo ""
echo "🚀 Starting in PRODUCTION mode..."
echo ""

# Build images
echo "📦 Building Docker images..."
docker compose build

# Start containers
echo "🔄 Starting containers..."
docker compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 5

# Check if containers are running
if docker compose ps | grep -q "Up"; then
    echo ""
    echo "✅ Application started successfully!"
    echo ""
    echo "🌐 Access the application:"
    echo "   Frontend:  http://localhost:3000"
    echo "   Backend:   http://localhost:8000"
    echo "   API Docs:  http://localhost:8000/docs"
    echo ""
    echo "📊 View logs:"
    echo "   docker compose logs -f"
    echo ""
    echo "🛑 Stop application:"
    echo "   docker compose down"
else
    echo ""
    echo "❌ Failed to start containers. Check logs:"
    echo "   docker compose logs"
    exit 1
fi
echo "=================================================="