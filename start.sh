#!/bin/bash

# CompAIr Start Script
# This script starts the backend and/or frontend services

# Usage function
usage() {
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  all        Start both backend and frontend (default)"
    echo "  backend    Start only the backend"
    echo "  frontend   Start only the frontend"
    echo "  -h, --help Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0              # Start both services"
    echo "  $0 backend      # Start only backend"
    echo "  $0 frontend     # Start only frontend"
    exit 0
}

# Parse arguments
SERVICE="${1:-all}"

# Show help
if [[ "$SERVICE" == "-h" || "$SERVICE" == "--help" ]]; then
    usage
fi

# Validate argument
if [[ "$SERVICE" != "all" && "$SERVICE" != "backend" && "$SERVICE" != "frontend" ]]; then
    echo "❌ Invalid option: $SERVICE"
    echo ""
    usage
fi

echo "🚀 Starting CompAIr..."
echo ""

# Start backend
if [[ "$SERVICE" == "all" || "$SERVICE" == "backend" ]]; then
    echo "📦 Building and starting backend container..."
    docker compose up -d --build

    if [ $? -ne 0 ]; then
        echo "❌ Failed to start backend"
        exit 1
    fi

    echo "✅ Backend started successfully"
    echo ""
fi

# Start frontend
if [[ "$SERVICE" == "all" || "$SERVICE" == "frontend" ]]; then
    echo "🎨 Starting frontend development server..."
    cd frontend/compair-fe

    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        echo "📥 Installing frontend dependencies..."
        npm install
    fi

    # Start the frontend server
    npm run serve &
    FRONTEND_PID=$!

    cd ../..
fi

echo ""
echo "✅ CompAIr is running!"
echo ""

# Show relevant URLs
if [[ "$SERVICE" == "all" || "$SERVICE" == "backend" ]]; then
    echo "Backend API: http://localhost:5000"
fi

if [[ "$SERVICE" == "all" || "$SERVICE" == "frontend" ]]; then
    echo "Frontend: http://localhost:8080"
fi

echo ""

if [[ "$SERVICE" == "backend" ]]; then
    echo "To view logs: docker logs -f compair-backend-1"
    echo "To stop: docker compose down"
elif [[ "$SERVICE" == "frontend" ]]; then
    echo "Press Ctrl+C to stop the frontend server"
else
    echo "To view backend logs: docker logs -f compair-backend-1"
    echo "To stop everything: ./stop.sh [all|backend|frontend]"
    echo ""
    echo "Press Ctrl+C to stop the frontend server"
fi

echo ""

# Wait for the frontend process if it was started
if [[ "$SERVICE" == "all" || "$SERVICE" == "frontend" ]]; then
    wait $FRONTEND_PID
fi
