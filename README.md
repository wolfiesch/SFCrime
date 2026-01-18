# SFCrime

A Citizen-style live crime map for San Francisco. Real-time dispatch calls and historical incident archive powered by DataSF Open Data.

## Overview

SFCrime consists of two components:

1. **iOS App** (`/ios`) - Native SwiftUI app with live map, list view, and historical archive
2. **Backend API** (`/backend`) - FastAPI server that ingests data from DataSF and serves it to the app

## Features

- **Live Crime Map**: Real-time dispatch calls displayed on an interactive map
- **Priority-Based Markers**: Color-coded by priority (A=Emergency, B=Urgent, C=Routine)
- **Historical Archive**: Search incidents from 2018 to present
- **Offline Support**: SwiftData caching for offline access
- **Data Transparency**: "Data as of" timestamps show data freshness

## Architecture

```
┌─────────────────┐      REST API      ┌─────────────────┐
│                 │  ←────────────────  │                 │
│   iOS App       │                     │  FastAPI        │
│   (SwiftUI)     │  ────────────────→  │  Backend        │
│                 │    Poll every 2min  │                 │
└─────────────────┘                     └────────┬────────┘
                                                 │
                                        Poll every 5min
                                                 │
                                                 ▼
                                        ┌─────────────────┐
                                        │     DataSF      │
                                        │   SODA API      │
                                        └─────────────────┘
```

## Quick Start

### Backend

```bash
cd backend
cp .env.example .env  # Configure database URL
uv sync
uv run uvicorn app.main:app --reload
```

API will be available at http://localhost:8000

### iOS App

1. Open Xcode
2. Create new iOS App project named "SFCrime"
3. Copy files from `/ios/SFCrime/` into the project
4. Configure Info.plist with location permission
5. Build and run

See [backend/README.md](backend/README.md) and [ios/README.md](ios/README.md) for detailed instructions.

## Data Sources

| Dataset | ID | Update Frequency | Use Case |
|---------|-----|------------------|----------|
| [Police Dispatch Calls](https://data.sfgov.org/Public-Safety/Police-Department-Calls-for-Service/gnap-fj3t) | `gnap-fj3t` | ~10 minutes | Live map |
| [Incident Reports](https://data.sfgov.org/Public-Safety/Police-Department-Incident-Reports-2018-to-Present/wg3w-h783) | `wg3w-h783` | Daily | Archive |

## Tech Stack

**iOS App**
- SwiftUI (iOS 17+)
- MapKit
- SwiftData
- CoreLocation

**Backend**
- FastAPI
- SQLAlchemy 2.0 (async)
- PostgreSQL + PostGIS
- APScheduler

## Project Structure

```
SFCrime/
├── ios/                    # iOS app source code
│   ├── SFCrime/
│   │   ├── Domain/        # Models, use cases
│   │   ├── Data/          # Network, cache
│   │   ├── Presentation/  # Views, ViewModels
│   │   └── Core/          # Utilities
│   └── README.md
│
├── backend/               # FastAPI backend
│   ├── app/
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── routers/      # API routes
│   │   ├── services/     # Business logic
│   │   └── tasks/        # Background jobs
│   └── README.md
│
└── docs/                  # Additional documentation
```

## API Endpoints

### Live Dispatch Calls
- `GET /api/v1/calls` - List with cursor pagination
- `GET /api/v1/calls/bbox` - Viewport query for map
- `GET /api/v1/calls/{cad_number}` - Single call

### Historical Incidents
- `GET /api/v1/incidents/search` - Search with filters
- `GET /api/v1/incidents/categories` - List categories
- `GET /api/v1/incidents/districts` - List districts

### Health
- `GET /health` - Ingestion status

## Development

### Prerequisites

- Python 3.12+
- PostgreSQL with PostGIS
- Xcode 15+
- uv (Python package manager)

### Environment Variables

```bash
# Backend
DATABASE_URL=postgresql+asyncpg://localhost:5432/sfcrime
SODA_APP_TOKEN=your_token_here  # Optional but recommended
```

### DataSF App Token

Register for a free app token at https://dev.socrata.com to increase API rate limits from 60 to 1000 requests/hour.

## License

MIT

## Acknowledgments

- Data provided by [DataSF](https://datasf.org)
- Inspired by the [Citizen](https://citizen.com) app
