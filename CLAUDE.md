# CLAUDE.md - SFCrime Project

## Project Overview

SFCrime is a Citizen-style live crime map for San Francisco with:
- **iOS App**: SwiftUI native app (iOS 17+)
- **Backend**: FastAPI Python server

## Quick Commands

### Backend

```bash
cd backend

# Install dependencies
uv sync

# Run development server
uv run uvicorn app.main:app --reload

# Run migrations
uv run alembic upgrade head

# Generate migration
uv run alembic revision --autogenerate -m "description"
```

### iOS

```bash
cd ios

# Open in Xcode (once project exists)
open SFCrime.xcodeproj

# Build from command line
xcodebuild -scheme SFCrime -configuration Debug
```

## Architecture

### Backend (`/backend`)

```
app/
├── main.py           # FastAPI app entry
├── config.py         # Pydantic settings
├── database.py       # SQLAlchemy async
├── models/           # DB models (DispatchCall, IncidentReport, SyncCheckpoint)
├── schemas/          # API schemas
├── routers/          # API routes (calls, incidents, health)
├── services/         # Business logic (soda_client, ingestion)
├── tasks/            # Background scheduler
└── websocket/        # Real-time WebSocket support
    ├── manager.py    # ConnectionManager for broadcasts
    ├── schemas.py    # Message types (Subscribe, CallUpdate)
    └── router.py     # WebSocket endpoint /ws/calls
```

### iOS (`/ios/SFCrime`)

```
├── Domain/Models/    # DispatchCall, IncidentReport, Priority
├── Data/Network/     # APIClient, WebSocketClient, WebSocketMessages
├── Data/Cache/       # SwiftData models
├── Presentation/     # Views + ViewModels
│   ├── Map/         # Map view with markers + WebSocket integration
│   ├── List/        # Call list
│   ├── Archive/     # Historical search + incident detail with map
│   └── Settings/    # App settings
└── Core/            # LocationManager, extensions
```

## Key Files

| Purpose | File |
|---------|------|
| Backend entry | `backend/app/main.py` |
| API routes | `backend/app/routers/calls.py`, `incidents.py` |
| Data ingestion | `backend/app/services/ingestion.py` |
| WebSocket manager | `backend/app/websocket/manager.py` |
| iOS map | `ios/SFCrime/Presentation/Map/CrimeMapView.swift` |
| iOS API client | `ios/SFCrime/Data/Network/APIClient.swift` |
| iOS WebSocket | `ios/SFCrime/Data/Network/WebSocketClient.swift` |

## Data Flow

1. **Backend polls DataSF** every 5 minutes (dispatch) / 1 hour (incidents)
2. **Upserts to PostgreSQL** with PostGIS for spatial queries
3. **Broadcasts via WebSocket** to connected clients after each sync
4. **iOS connects via WebSocket** for real-time updates (falls back to REST polling every 5 min)
5. **Caches locally** with SwiftData for offline access

## DataSF Datasets

| Dataset | ID | Polling | Retention |
|---------|-----|---------|-----------|
| Dispatch Calls | `gnap-fj3t` | 5 min | 48 hours |
| Incident Reports | `wg3w-h783` | 1 hour | Multi-year |

## API Endpoints

### Dispatch Calls
- `GET /api/v1/calls` - List with cursor pagination
- `GET /api/v1/calls/bbox?min_lat=&max_lat=&min_lng=&max_lng=` - Viewport query
- `GET /api/v1/calls/{cad_number}` - Single call

### Incidents
- `GET /api/v1/incidents/search?since=&until=&district=&category=` - Search
- `GET /api/v1/incidents/categories` - List categories
- `GET /api/v1/incidents/districts` - List districts

### Health
- `GET /health` - Ingestion status, record counts

### WebSocket
- `WS /ws/calls` - Real-time dispatch call updates
  - Client sends: `{"type": "subscribe", "viewport": {...}, "priorities": ["A","B"]}`
  - Server pushes: `{"type": "call_update", "data": [...], "timestamp": "..."}`

## Environment Variables

```bash
# Required
DATABASE_URL=postgresql+asyncpg://localhost:5432/sfcrime

# Optional (recommended for higher rate limits)
SODA_APP_TOKEN=your_token

# Defaults
DISPATCH_POLL_INTERVAL_MINUTES=5
INCIDENTS_POLL_INTERVAL_MINUTES=60
DISPATCH_RETENTION_HOURS=48
```

## Testing

```bash
# Backend
cd backend && uv run pytest

# iOS (in Xcode)
cmd+U
```

## Common Tasks

### Add new API endpoint
1. Create schema in `backend/app/schemas/`
2. Add route in `backend/app/routers/`
3. Update iOS `APIClient.swift`

### Modify database model
1. Edit model in `backend/app/models/`
2. Generate migration: `uv run alembic revision --autogenerate -m "description"`
3. Apply: `uv run alembic upgrade head`

### Add new iOS view
1. Create view in appropriate `Presentation/` subfolder
2. Create ViewModel if needed
3. Add to navigation in `ContentView.swift`

## Notes

- iOS app requires manual Xcode project creation (Swift files provided)
- PostGIS extension required for spatial queries
- DataSF app token increases rate limit from 60 to 1000 req/hr
