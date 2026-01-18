"""API routes for historical incident reports."""

import base64
import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import IncidentReport
from app.schemas.dispatch_call import Coordinates
from app.schemas.incident_report import IncidentReportOut, IncidentReportsResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/incidents", tags=["incidents"])


def _encode_cursor(report_datetime: datetime, id: int) -> str:
    """Encode cursor for keyset pagination."""
    cursor_str = f"{report_datetime.isoformat()}|{id}"
    return base64.urlsafe_b64encode(cursor_str.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, int]:
    """Decode cursor for keyset pagination."""
    cursor_str = base64.urlsafe_b64decode(cursor.encode()).decode()
    parts = cursor_str.split("|")
    report_datetime = datetime.fromisoformat(parts[0])
    id = int(parts[1])
    return report_datetime, id


@router.get("/search", response_model=IncidentReportsResponse)
async def search_incidents(
    db: Annotated[AsyncSession, Depends(get_db)],
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    q: str | None = Query(None, description="Search term (category, description, location, etc.)"),
    since: datetime | None = Query(None, description="Only incidents after this date"),
    until: datetime | None = Query(None, description="Only incidents before this date"),
    district: str | None = Query(None, description="Filter by police district"),
    category: str | None = Query(None, description="Filter by incident category"),
) -> IncidentReportsResponse:
    """
    Search historical incident reports with cursor pagination.

    Supports filtering by date range, district, and category.
    Uses cursor-based pagination for efficient traversal of large datasets.
    """
    from sqlalchemy import text

    # Build dynamic WHERE clauses
    where_clauses = ["1=1"]  # Always true base
    params: dict = {"limit": limit + 1}

    # Apply cursor filter
    if cursor:
        try:
            cursor_time, cursor_id = _decode_cursor(cursor)
            where_clauses.append(
                "(report_datetime < :cursor_time OR (report_datetime = :cursor_time AND id < :cursor_id))"
            )
            params["cursor_time"] = cursor_time
            params["cursor_id"] = cursor_id
        except Exception:
            logger.warning(f"Invalid cursor: {cursor}")

    # Apply search filter
    q_stripped = q.strip() if q else None
    if q_stripped:
        where_clauses.append("""(
            incident_category ILIKE :search_term OR
            incident_subcategory ILIKE :search_term OR
            incident_description ILIKE :search_term OR
            location_text ILIKE :search_term OR
            analysis_neighborhood ILIKE :search_term
        )""")
        params["search_term"] = f"%{q_stripped}%"

    if since:
        where_clauses.append("report_datetime >= :since")
        params["since"] = since
    if until:
        where_clauses.append("report_datetime <= :until")
        params["until"] = until
    if district:
        where_clauses.append("police_district = :district")
        params["district"] = district
    if category:
        where_clauses.append("incident_category = :category")
        params["category"] = category

    where_sql = " AND ".join(where_clauses)

    # Use raw SQL for Neon PostgreSQL compatibility
    sql = text(f"""
        SELECT
            id, incident_id, incident_number,
            incident_category, incident_subcategory, incident_description,
            resolution, incident_date, incident_time, report_datetime,
            ST_Y(location::geometry) as lat,
            ST_X(location::geometry) as lng,
            location_text, police_district, analysis_neighborhood
        FROM incident_reports
        WHERE {where_sql}
        ORDER BY report_datetime DESC NULLS LAST, id DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    # Determine if there's a next page
    has_next = len(rows) > limit
    if has_next:
        rows = rows[:limit]

    # Build response
    incidents = []
    for row in rows:
        lat = row[10]
        lng = row[11]

        coords = (
            Coordinates(latitude=float(lat), longitude=float(lng))
            if lat is not None and lng is not None
            else None
        )

        incidents.append(
            IncidentReportOut(
                id=row[0],
                incident_id=row[1],
                incident_number=row[2],
                incident_category=row[3],
                incident_subcategory=row[4],
                incident_description=row[5],
                resolution=row[6],
                incident_date=row[7],
                incident_time=row[8],
                report_datetime=row[9],
                coordinates=coords,
                location_text=row[12],
                police_district=row[13],
                analysis_neighborhood=row[14],
            )
        )

    # Generate next cursor
    next_cursor = None
    if has_next and rows:
        last_row = rows[-1]
        last_report_datetime = last_row[9]
        last_id = last_row[0]
        if last_report_datetime:
            next_cursor = _encode_cursor(last_report_datetime, last_id)

    return IncidentReportsResponse(
        incidents=incidents,
        next_cursor=next_cursor,
    )


@router.get("/categories", response_model=list[str])
async def list_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[str]:
    """Get list of all incident categories."""
    query = (
        select(IncidentReport.incident_category)
        .where(IncidentReport.incident_category.isnot(None))
        .distinct()
        .order_by(IncidentReport.incident_category)
    )
    result = await db.execute(query)
    categories = [row[0] for row in result.all()]
    return categories


@router.get("/districts", response_model=list[str])
async def list_districts(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[str]:
    """Get list of all police districts."""
    query = (
        select(IncidentReport.police_district)
        .where(IncidentReport.police_district.isnot(None))
        .distinct()
        .order_by(IncidentReport.police_district)
    )
    result = await db.execute(query)
    districts = [row[0] for row in result.all()]
    return districts


@router.get("/{incident_id}", response_model=IncidentReportOut)
async def get_incident(
    incident_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> IncidentReportOut:
    """Get a specific incident report by ID."""
    from sqlalchemy import text

    sql = text("""
        SELECT
            id, incident_id, incident_number,
            incident_category, incident_subcategory, incident_description,
            resolution, incident_date, incident_time, report_datetime,
            ST_Y(location::geometry) as lat,
            ST_X(location::geometry) as lng,
            location_text, police_district, analysis_neighborhood
        FROM incident_reports
        WHERE incident_id = :incident_id
    """)

    result = await db.execute(sql, {"incident_id": incident_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Incident not found")

    lat = row[10]
    lng = row[11]

    coords = (
        Coordinates(latitude=float(lat), longitude=float(lng))
        if lat is not None and lng is not None
        else None
    )

    return IncidentReportOut(
        id=row[0],
        incident_id=row[1],
        incident_number=row[2],
        incident_category=row[3],
        incident_subcategory=row[4],
        incident_description=row[5],
        resolution=row[6],
        incident_date=row[7],
        incident_time=row[8],
        report_datetime=row[9],
        coordinates=coords,
        location_text=row[12],
        police_district=row[13],
        analysis_neighborhood=row[14],
    )
