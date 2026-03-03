#!/bin/bash

# CompAIr Stop Script
# This script stops the backend and/or frontend services

# Usage function
usage() {
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  all        Stop both backend and frontend (default)"
    echo "  backend    Stop only the backend"
    echo "  frontend   Stop only the frontend"
    echo "  -h, --help Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0              # Stop both services"
    echo "  $0 backend      # Stop only backend"
    echo "  $0 frontend     # Stop only frontend"
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

echo "🛑 Stopping CompAIr..."
echo ""

# Stop backend Docker containers
if [[ "$SERVICE" == "all" || "$SERVICE" == "backend" ]]; then
    echo "📦 Stopping backend container..."
    docker compose down
    echo "✅ Backend stopped"
    echo ""
fi

# Stop frontend (find and kill npm process)
if [[ "$SERVICE" == "all" || "$SERVICE" == "frontend" ]]; then
    echo "🎨 Stopping frontend development server..."
    pkill -f "vue-cli-service serve"
    echo "✅ Frontend stopped"
    echo ""
fi

echo "Services stopped successfully!"
