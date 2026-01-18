# Diachron + SFCrime Merger Architecture

## Executive Summary

This plan merges **SFCrime** (real-time crime mapping) with **Diachron** (temporal intelligence platform) to create a unified SF civic data system.

**Result**: Diachron becomes the "temporal intelligence layer" that powers SFCrime's historical context, while SFCrime contributes its real-time ingestion capabilities.

---

## Current State

### SFCrime (This Project)
| Component | Status | Notes |
|-----------|--------|-------|
| Backend | ✅ FastAPI + WebSocket | PostgreSQL + PostGIS (Neon) |
| iOS App | ✅ SwiftUI | Real-time map, archive search |
| Data Sources | ✅ 2 datasets | Dispatch (5min), Incidents (1hr) |
| Schema | Dispatch + Incidents | 48hr dispatch retention |

### Diachron (~/projects/HistoryAPI)
| Component | Status | Notes |
|-----------|--------|-------|
| API | ✅ FastAPI | 9 endpoints, production on Fly.io |
| MCP Server | ✅ 6 tools | search_nearby, search_semantic, etc. |
| Database | ✅ Neon | PostGIS + pgvector (708 locations, 961 facts) |
| Data Sources | ✅ OSM + NRHP | Partially: FoundSF.org |

---

## Target Architecture

```
                    ┌─────────────────────────────────────────┐
                    │           SF Open Data Portal           │
                    │   (dispatch, incidents, fire, 311...)   │
                    └──────────────────┬──────────────────────┘
                                       │
                    ┌──────────────────▼──────────────────────┐
                    │         Unified Ingestion Layer         │
                    │   (SFCrime ingestion + Diachron pipes)  │
                    └──────────────────┬──────────────────────┘
                                       │
          ┌────────────────────────────┼────────────────────────────┐
          │                            │                            │
          ▼                            ▼                            ▼
┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
│  SFCrime Database   │   │ Diachron Database   │   │    Shared Neon      │
│  (real-time calls)  │◄──│  (location_facts)   │──►│   (single instance) │
│  48hr retention     │   │  Multi-year hist.   │   │                     │
└─────────────────────┘   └─────────────────────┘   └─────────────────────┘
          │                            │
          │                            │
          ▼                            ▼
┌─────────────────────┐   ┌─────────────────────┐
│   SFCrime iOS App   │   │  Diachron MCP Srvr  │
│  (user-facing map)  │   │  (Claude context)   │
└─────────────────────┘   └─────────────────────┘
```

---

## Phase 1: Schema Unification (Day 1)

### 1.1 Add Crime-Specific Fact Kinds to Diachron

```sql
-- Add to Diachron's fact_kinds table
INSERT INTO fact_kinds (code, display_name, temporal_semantics, snapshot_dimension) VALUES
  ('dispatch_call', 'Police Dispatch Call', 'event', 'point'),
  ('police_incident', 'Police Incident Report', 'event', 'point'),
  ('fire_call', 'Fire Department Call', 'event', 'point'),
  ('ems_call', 'EMS Emergency Call', 'event', 'point'),
  ('311_case', '311 Service Request', 'event', 'point'),
  ('traffic_crash', 'Traffic Collision', 'event', 'point');
```

### 1.2 Map SFCrime Records → Diachron location_facts

| SFCrime Field | Diachron Field | Notes |
|---------------|----------------|-------|
| `cad_number` | `external_id` | Unique reference |
| `call_type_description` | `title` | Event title |
| `call_type_code + priority` | `description` | Event details |
| `received_at` | `valid_during` | DATERANGE for event time |
| `location` | `coordinates` | PostGIS POINT |
| `district` | `neighborhood_id` | Mapped via lookup |
| `disposition` | `sources` (JSONB) | Resolution info |

### 1.3 Create Adapter Interface

```python
# backend/app/services/diachron_adapter.py
from dataclasses import dataclass
from datetime import datetime

@dataclass
class DiachronFact:
    """Adapter for SFCrime records → Diachron location_facts"""
    kind_code: str  # 'dispatch_call', 'police_incident', etc.
    title: str
    description: str
    valid_from: datetime
    valid_to: datetime | None
    latitude: float
    longitude: float
    external_id: str
    sources: dict  # Original record metadata
```

---

## Phase 2: Dual-Write Pipeline (Day 1-2)

### 2.1 Modify Ingestion Service

```python
# backend/app/services/ingestion.py (modified)

async def sync_dispatch_calls(self) -> tuple[int, list[str]]:
    """Sync to both SFCrime (real-time) and Diachron (historical)."""

    # Existing SFCrime upsert logic (keep for 48hr retention)
    upserted, cad_numbers = await self._upsert_dispatch_calls(records)

    # NEW: Also write to Diachron location_facts (permanent history)
    await self._write_to_diachron(records, kind='dispatch_call')

    return upserted, cad_numbers
```

### 2.2 Diachron Writer Service

```python
# backend/app/services/diachron_writer.py

class DiachronWriter:
    """Writes SFCrime events to Diachron's location_facts table."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def write_facts(
        self,
        facts: list[DiachronFact],
        source_name: str = "sfcrime_ingestion"
    ) -> int:
        """
        Write facts to Diachron's location_facts table.

        Uses Diachron's schema:
        - location_id (UUID) - found/created by coordinates
        - kind_id (FK) - from fact_kinds table
        - valid_during (DATERANGE)
        - sources (JSONB)
        """
        ...
```

---

## Phase 3: Extend Diachron MCP Server (Day 2)

### 3.1 New Crime-Focused Tools

```python
# ~/projects/HistoryAPI/mcp-server/server.py (additions)

@mcp.tool()
async def search_crimes_nearby(
    latitude: float,
    longitude: float,
    radius_meters: int = 500,
    hours_back: int = 24,
    categories: list[str] | None = None
) -> str:
    """Search for recent crime activity near a location."""
    ...

@mcp.tool()
async def get_crime_hotspots(
    neighborhood: str | None = None,
    time_window: str = "week"  # hour, day, week, month
) -> str:
    """Get crime density hotspots for a neighborhood or city-wide."""
    ...

@mcp.tool()
async def compare_crime_patterns(
    latitude: float,
    longitude: float,
    period1: str,  # e.g., "2024-Q1"
    period2: str   # e.g., "2025-Q1"
) -> str:
    """Compare crime patterns between two time periods."""
    ...
```

### 3.2 Enhanced Context for LLMs

```python
@mcp.tool()
async def get_location_safety_context(
    latitude: float,
    longitude: float,
    include_historical: bool = True
) -> str:
    """
    Get comprehensive safety context for a location.

    Combines:
    - Recent dispatch calls (24-48 hours)
    - Historical incidents (multi-year patterns)
    - Neighborhood trends
    - Nearby infrastructure (police stations, fire stations)
    """
    ...
```

---

## Phase 4: iOS App Integration (Day 3)

### 4.1 Add Historical Context View

```swift
// ios/SFCrime/Presentation/Map/HistoricalContextView.swift

struct HistoricalContextView: View {
    let location: CLLocationCoordinate2D
    @State private var historicalFacts: [HistoricalFact] = []

    var body: some View {
        // Show historical crime patterns for selected location
        // Query Diachron API for temporal context
    }
}
```

### 4.2 Diachron API Client

```swift
// ios/SFCrime/Data/Network/DiachronClient.swift

class DiachronClient {
    let baseURL = URL(string: "https://diachron-api.fly.dev")!

    func searchNearby(
        latitude: Double,
        longitude: Double,
        radius: Int = 500,
        yearFrom: Int? = nil,
        yearTo: Int? = nil
    ) async throws -> [LocationFact] {
        // Query Diachron's /v1/events endpoint
    }
}
```

---

## Phase 5: Add New Data Sources (Day 3-4)

### 5.1 Fire Incidents

```python
# backend/app/services/soda_client.py (additions)

async def fetch_fire_incidents(
    self,
    since: datetime | None = None
) -> list[dict]:
    """Fetch fire department calls from DataSF."""
    dataset_id = "wr8u-xric"  # Fire Department Calls for Service
    ...
```

### 5.2 311 Cases

```python
async def fetch_311_cases(
    self,
    since: datetime | None = None
) -> list[dict]:
    """Fetch 311 service requests from DataSF."""
    dataset_id = "vw6y-z8j6"  # 311 Cases
    ...
```

---

## File Changes Summary

### SFCrime Project (This Repo)

| File | Change Type | Description |
|------|-------------|-------------|
| `backend/app/services/diachron_adapter.py` | **NEW** | Adapter for SFCrime → Diachron |
| `backend/app/services/diachron_writer.py` | **NEW** | Writer to Diachron's location_facts |
| `backend/app/services/ingestion.py` | **MODIFY** | Add dual-write to Diachron |
| `backend/app/services/soda_client.py` | **MODIFY** | Add fire, 311, traffic datasets |
| `backend/app/config.py` | **MODIFY** | Add Diachron connection settings |
| `ios/SFCrime/Data/Network/DiachronClient.swift` | **NEW** | Diachron API client |
| `ios/SFCrime/Presentation/Map/HistoricalContextView.swift` | **NEW** | Historical context UI |

### HistoryAPI Project (~/projects/HistoryAPI)

| File | Change Type | Description |
|------|-------------|-------------|
| `migrations/004_crime_fact_kinds.sql` | **NEW** | Add crime-specific fact_kinds |
| `mcp-server/server.py` | **MODIFY** | Add crime-focused tools |
| `api/routers/facts.py` | **MODIFY** | Add crime-specific endpoints |

---

## Database Strategy

### Option A: Shared Neon Instance (Recommended)
- Both projects use same Neon database
- SFCrime tables: `dispatch_calls`, `incident_reports`, `sync_checkpoints`
- Diachron tables: `locations`, `location_facts`, `fact_kinds`, etc.
- Pros: Single source of truth, simpler operations
- Cons: Schema coupling, migration coordination

### Option B: Separate Databases with Sync
- SFCrime has its own Neon DB (current state)
- Diachron has its own Neon DB (current state)
- Background job syncs SFCrime → Diachron
- Pros: Independence, isolation
- Cons: Data lag, complexity

**Recommendation**: Option A - shared database. SFCrime's real-time tables are small (48hr retention), and Diachron benefits from direct access.

---

## Implementation Order

1. **Schema Unification** (2 hours)
   - Create `004_crime_fact_kinds.sql` migration
   - Apply to Diachron's Neon database

2. **Adapter + Writer** (3 hours)
   - Implement `diachron_adapter.py`
   - Implement `diachron_writer.py`
   - Unit tests for adapter

3. **Dual-Write Integration** (2 hours)
   - Modify `ingestion.py` to write to both tables
   - Integration test with real data

4. **MCP Server Extension** (3 hours)
   - Add crime-focused tools
   - Test with Claude

5. **iOS Integration** (4 hours)
   - Add Diachron client
   - Historical context view
   - UI polish

6. **New Data Sources** (4 hours)
   - Fire incidents ingestion
   - 311 cases ingestion
   - Traffic crashes

---

## Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Data latency | < 5 min | Time from DataSF → Diachron |
| Query performance | < 200ms | P95 API response time |
| MCP tool accuracy | > 90% | Manual spot checks |
| iOS context load | < 1s | Time to load historical context |
| Data coverage | 3+ sources | Dispatch + Incidents + Fire + 311 |

---

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 01/18/2026 | Initial architecture plan | Claude |

---

## Implementation Changelog

| Date | Task | Status |
|------|------|--------|
| 01/18/2026 | Created architecture plan | ✅ Complete |
| 01/18/2026 | Created `004_crime_fact_kinds.sql` migration | ✅ Complete |
| 01/18/2026 | Created `diachron_adapter.py` | ✅ Complete |
| 01/18/2026 | Created `diachron_writer.py` | ✅ Complete |
| 01/18/2026 | Updated `ingestion.py` with dual-write | ✅ Complete |
| 01/18/2026 | Added crime tools to MCP server | ✅ Complete |
| 01/18/2026 | Updated `config.py` with Diachron settings | ✅ Complete |

## Status: IN PROGRESS

**Completed**:
- Migration for crime-specific fact_kinds
- Data adapter (dispatch calls + incidents)
- Diachron writer service
- Dual-write integration in ingestion
- Crime-focused MCP tools (search_crimes_nearby, get_crime_hotspots, get_location_safety_context)

**Next Steps**:
1. Apply migration to Diachron's Neon database
2. Set `DIACHRON_DATABASE_URL` and `DIACHRON_ENABLED=true` in .env
3. Run tests to verify integration
4. Deploy updates to production
