"""Health and metrics endpoints."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import DispatchCall, IncidentReport, SyncCheckpoint

router = APIRouter(tags=["health"])


class DataSourceStatus(BaseModel):
    """Status of a data source."""

    last_sync: datetime | None
    record_count: int
    oldest_record: datetime | None = None
    newest_record: datetime | None = None
    date_range: list[str] | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    timestamp: datetime
    dispatch_calls: DataSourceStatus
    incident_reports: DataSourceStatus


@router.get("/health", response_model=HealthResponse)
async def health_check(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HealthResponse:
    """
    Health check endpoint with ingestion status.

    Returns sync timestamps and record counts for each data source.
    """
    # Get dispatch calls status
    dispatch_checkpoint = await db.execute(
        select(SyncCheckpoint).where(SyncCheckpoint.source == "dispatch_calls")
    )
    dispatch_cp = dispatch_checkpoint.scalar_one_or_none()

    dispatch_count_result = await db.execute(select(func.count(DispatchCall.id)))
    dispatch_count = dispatch_count_result.scalar() or 0

    dispatch_oldest_result = await db.execute(
        select(func.min(DispatchCall.received_at))
    )
    dispatch_oldest = dispatch_oldest_result.scalar()

    dispatch_newest_result = await db.execute(
        select(func.max(DispatchCall.received_at))
    )
    dispatch_newest = dispatch_newest_result.scalar()

    dispatch_status = DataSourceStatus(
        last_sync=dispatch_cp.last_sync_at if dispatch_cp else None,
        record_count=dispatch_count,
        oldest_record=dispatch_oldest,
        newest_record=dispatch_newest,
    )

    # Get incident reports status
    incidents_checkpoint = await db.execute(
        select(SyncCheckpoint).where(SyncCheckpoint.source == "incident_reports")
    )
    incidents_cp = incidents_checkpoint.scalar_one_or_none()

    incidents_count_result = await db.execute(select(func.count(IncidentReport.id)))
    incidents_count = incidents_count_result.scalar() or 0

    incidents_oldest_result = await db.execute(
        select(func.min(IncidentReport.incident_date))
    )
    incidents_oldest = incidents_oldest_result.scalar()

    incidents_newest_result = await db.execute(
        select(func.max(IncidentReport.incident_date))
    )
    incidents_newest = incidents_newest_result.scalar()

    date_range = None
    if incidents_oldest and incidents_newest:
        date_range = [str(incidents_oldest), str(incidents_newest)]

    incidents_status = DataSourceStatus(
        last_sync=incidents_cp.last_sync_at if incidents_cp else None,
        record_count=incidents_count,
        date_range=date_range,
    )

    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(UTC),
        dispatch_calls=dispatch_status,
        incident_reports=incidents_status,
    )


class SyncResult(BaseModel):
    """Result of a manual sync operation."""

    source: str
    records_synced: int
    message: str


@router.post("/sync/incidents", response_model=SyncResult)
async def trigger_incident_sync(
    db: Annotated[AsyncSession, Depends(get_db)],
    days_back: int = Query(3, ge=1, le=365, description="Days to look back for initial sync"),
) -> SyncResult:
    """
    Manually trigger incident reports sync.

    Useful for initial data seeding or debugging.
    Set days_back to control how far back to fetch (only applies when no checkpoint).
    """
    from app.services.ingestion import IngestionService
    from app.services.soda_client import SODAClient

    service = IngestionService(db, SODAClient())
    count = await service.sync_incident_reports(initial_days_back=days_back)

    return SyncResult(
        source="incident_reports",
        records_synced=count,
        message=f"Successfully synced {count} incident reports",
    )


@router.delete("/sync/incidents/checkpoint")
async def clear_incident_checkpoint(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """
    Clear the incident reports checkpoint to allow re-syncing historical data.

    WARNING: Next sync will fetch from scratch based on days_back parameter.
    """
    from sqlalchemy import delete
    from app.models import SyncCheckpoint

    result = await db.execute(
        delete(SyncCheckpoint).where(SyncCheckpoint.source == "incident_reports")
    )
    await db.commit()

    return {
        "message": "Incident reports checkpoint cleared",
        "deleted": result.rowcount > 0,
    }


@router.post("/sync/incidents/chunked", response_model=SyncResult)
async def chunked_incident_sync(
    db: Annotated[AsyncSession, Depends(get_db)],
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
) -> SyncResult:
    """
    Sync incident reports for a specific date range (chunked backfill).

    Use this for historical backfill by calling multiple times with different ranges.
    Does NOT update checkpoint - use for one-time backfill operations.
    """
    from datetime import datetime
    from app.services.ingestion import IngestionService
    from app.services.soda_client import SODAClient

    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=UTC)
        end = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError:
        return SyncResult(
            source="incident_reports",
            records_synced=0,
            message="Invalid date format. Use YYYY-MM-DD",
        )

    service = IngestionService(db, SODAClient())
    count = await service.sync_incident_reports_range(start, end)

    return SyncResult(
        source="incident_reports",
        records_synced=count,
        message=f"Synced {count} incident reports from {start_date} to {end_date}",
    )


@router.get("/ready")
async def readiness_check() -> dict:
    """Simple readiness probe for container orchestration."""
    return {"status": "ready"}


@router.get("/live")
async def liveness_check() -> dict:
    """Simple liveness probe for container orchestration."""
    return {"status": "alive"}
