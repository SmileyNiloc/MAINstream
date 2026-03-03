# CompAIr

Repository for CompAIr

## Quick Start

To start both backend and frontend services:

```bash
./start.sh
```

To start only the backend:

```bash
./start.sh backend
```

To start only the frontend:

```bash
./start.sh frontend
```

This will:

- Build and start the backend Docker container (API on port 5000)
- Start the frontend Vue.js development server (on port 8080)

To stop all services:

```bash
./stop.sh
```

To stop individual services:

```bash
./stop.sh backend   # Stop only backend
./stop.sh frontend  # Stop only frontend
```

## Manual Start

### Backend

```bash
docker compose up -d --build
```

### Frontend

```bash
cd frontend/compair-fe
npm install
npm run serve
```

## Access

- Backend API: http://localhost:5000
- Frontend: http://localhost:8080
