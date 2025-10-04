#!/bin/bash

# Flight Search Application Startup Script

echo "🚀 Starting Flight Search Application..."
echo ""

# Check if we're in the correct directory
if [ ! -f "app/main.py" ]; then
    echo "❌ Error: Please run this script from the Flight-Search root directory"
    exit 1
fi

# Start backend in background
echo "📡 Starting backend server on port 8000..."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait a bit for backend to start
sleep 3

# Check if backend started successfully
if ps -p $BACKEND_PID > /dev/null; then
    echo "✅ Backend started successfully (PID: $BACKEND_PID)"
else
    echo "❌ Backend failed to start"
    exit 1
fi

# Start frontend
echo ""
echo "🎨 Starting frontend server on port 3000..."
cd frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    npm install
fi

npm start &
FRONTEND_PID=$!

echo ""
echo "✅ Application started!"
echo ""
echo "Backend API: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo "Frontend: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping servers..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo "✅ Servers stopped"
    exit 0
}

# Register cleanup function
trap cleanup INT TERM

# Wait for processes
wait
