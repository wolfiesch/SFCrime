# SFCrime Backend

FastAPI backend for the SFCrime iOS app - a live crime map for San Francisco.

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL with PostGIS extension
- uv (Python package manager)

### Setup

1. **Install dependencies:**
   ```bash
   cd backend
   uv sync
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials
   ```

3. **Set up PostgreSQL with PostGIS:**
   ```bash
   # Create database
   createdb sfcrime

   # Enable PostGIS extension (also created by migrations)
   psql sfcrime -c "CREATE EXTENSION IF NOT EXISTS postgis;"
   ```

4. **Run migrations:**
   ```bash
   uv run alembic upgrade head
   ```
   Note: The backend does not auto-create tables on startup; migrations are required.

5. **Start the server:**
   ```bash
   uv run uvicorn app.main:app --reload
   ```

6. **View API docs:**
   Open http://localhost:8000/docs

## API Endpoints

### Live Dispatch Calls

- `GET /api/v1/calls` - List calls with cursor pagination
- `GET /api/v1/calls/bbox` - Get calls in map viewport
- `GET /api/v1/calls/{cad_number}` - Get specific call

### Historical Incidents

- `GET /api/v1/incidents/search` - Search with filters
- `GET /api/v1/incidents/categories` - List all categories
- `GET /api/v1/incidents/districts` - List all districts
- `GET /api/v1/incidents/{incident_id}` - Get specific incident

### Health

- `GET /health` - Ingestion status and metrics
- `GET /ready` - Readiness probe
- `GET /live` - Liveness probe

## Data Sources

| Source | Dataset | Update Frequency |
|--------|---------|------------------|
| Dispatch Calls | `gnap-fj3t` | Every 5 minutes |
| Incident Reports | `wg3w-h783` | Every hour |

## Architecture

```
app/
├── main.py           # FastAPI app entry point
├── config.py         # Pydantic settings
├── database.py       # SQLAlchemy async setup
├── models/           # Database models
├── schemas/          # Pydantic schemas
├── routers/          # API routes
├── services/         # Business logic
└── tasks/            # Background jobs
```

## Deployment

### Docker

```bash
docker build -t sfcrime-backend .
docker run -p 8000:8000 --env-file .env sfcrime-backend
```

### Fly.io

```bash
fly launch
fly secrets set DATABASE_URL=...
fly deploy
```

## DataSF App Token

Register for a free app token at https://dev.socrata.com to increase rate limits from 60 to 1000 requests/hour.
