"""API routes for live dispatch calls."""

import base64
import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import DispatchCall
from app.schemas.dispatch_call import Coordinates, DispatchCallOut, DispatchCallsResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/calls", tags=["calls"])


def _encode_cursor(received_at: datetime, id: int) -> str:
    """Encode cursor for keyset pagination."""
    cursor_str = f"{received_at.isoformat()}|{id}"
    return base64.urlsafe_b64encode(cursor_str.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, int]:
    """Decode cursor for keyset pagination."""
    cursor_str = base64.urlsafe_b64decode(cursor.encode()).decode()
    parts = cursor_str.split("|")
    received_at = datetime.fromisoformat(parts[0])
    id = int(parts[1])
    return received_at, id


@router.get("", response_model=DispatchCallsResponse)
async def list_calls(
    db: Annotated[AsyncSession, Depends(get_db)],
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    priority: list[str] | None = Query(None, description="Filter by priority (A, B, C)"),
) -> DispatchCallsResponse:
    """
    List dispatch calls from the last 48 hours with cursor pagination.

    Cursor-based pagination is used for efficient pagination over large datasets.
    The cursor is an opaque string that encodes the position in the result set.
    """
    # Build query
    query = select(
        DispatchCall,
        func.ST_Y(DispatchCall.location).label("lat"),
        func.ST_X(DispatchCall.location).label("lng"),
    ).order_by(
        DispatchCall.received_at.desc(),
        DispatchCall.id.desc(),
    )

    # Apply cursor filter
    if cursor:
        try:
            cursor_time, cursor_id = _decode_cursor(cursor)
            query = query.where(
                (DispatchCall.received_at < cursor_time)
                | ((DispatchCall.received_at == cursor_time) & (DispatchCall.id < cursor_id))
            )
        except Exception:
            logger.warning(f"Invalid cursor: {cursor}")

    # Apply priority filter
    if priority:
        query = query.where(DispatchCall.priority.in_(priority))

    # Fetch records
    query = query.limit(limit + 1)  # Fetch one extra to check for next page
    result = await db.execute(query)
    rows = list(result.all())

    # Determine if there's a next page
    has_next = len(rows) > limit
    if has_next:
        rows = rows[:limit]

    # Build response
    call_schemas = []
    for row in rows:
        call = row[0]
        lat = row[1]
        lng = row[2]
        coords = None
        if lat is not None and lng is not None:
            coords = Coordinates(latitude=float(lat), longitude=float(lng))

        call_schemas.append(
            DispatchCallOut(
                id=call.id,
                cad_number=call.cad_number,
                call_type_code=call.call_type_code,
                call_type_description=call.call_type_description,
                priority=call.priority,
                received_at=call.received_at,
                dispatch_at=call.dispatch_at,
                on_scene_at=call.on_scene_at,
                closed_at=call.closed_at,
                coordinates=coords,
                location_text=call.location_text,
                district=call.district,
                disposition=call.disposition,
            )
        )

    # Generate next cursor
    next_cursor = None
    if has_next and rows:
        last_call = rows[-1][0]
        next_cursor = _encode_cursor(last_call.received_at, last_call.id)

    return DispatchCallsResponse(
        calls=call_schemas,
        next_cursor=next_cursor,
    )


@router.get("/bbox", response_model=list[DispatchCallOut])
async def calls_in_bbox(
    db: Annotated[AsyncSession, Depends(get_db)],
    min_lat: float = Query(..., ge=-90, le=90),
    min_lng: float = Query(..., ge=-180, le=180),
    max_lat: float = Query(..., ge=-90, le=90),
    max_lng: float = Query(..., ge=-180, le=180),
    limit: int = Query(200, ge=1, le=500),
) -> list[DispatchCallOut]:
    """
    Get dispatch calls within a map viewport bounding box.

    Used for efficient map rendering - only fetches visible calls.
    """
    from sqlalchemy import text

    # Use raw SQL for better compatibility with Neon PostgreSQL + PostGIS
    sql = text("""
        SELECT
            id, cad_number, call_type_code, call_type_description, priority,
            received_at, dispatch_at, on_scene_at, closed_at,
            ST_Y(location::geometry) as lat,
            ST_X(location::geometry) as lng,
            location_text, district, disposition
        FROM dispatch_calls
        WHERE location IS NOT NULL
          AND ST_Y(location::geometry) BETWEEN :min_lat AND :max_lat
          AND ST_X(location::geometry) BETWEEN :min_lng AND :max_lng
        ORDER BY received_at DESC
        LIMIT :limit
    """)

    result = await db.execute(
        sql,
        {
            "min_lat": min_lat,
            "max_lat": max_lat,
            "min_lng": min_lng,
            "max_lng": max_lng,
            "limit": limit,
        },
    )
    rows = result.fetchall()

    calls = []
    for row in rows:
        coords = (
            Coordinates(latitude=float(row.lat), longitude=float(row.lng))
            if row.lat is not None and row.lng is not None
            else None
        )

        calls.append(
            DispatchCallOut(
                id=row.id,
                cad_number=row.cad_number,
                call_type_code=row.call_type_code,
                call_type_description=row.call_type_description,
                priority=row.priority,
                received_at=row.received_at,
                dispatch_at=row.dispatch_at,
                on_scene_at=row.on_scene_at,
                closed_at=row.closed_at,
                coordinates=coords,
                location_text=row.location_text,
                district=row.district,
                disposition=row.disposition,
            )
        )

    return calls


@router.get("/{cad_number}", response_model=DispatchCallOut)
async def get_call(
    cad_number: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DispatchCallOut:
    """Get a specific dispatch call by CAD number."""
    query = select(
        DispatchCall,
        func.ST_Y(DispatchCall.location).label("lat"),
        func.ST_X(DispatchCall.location).label("lng"),
    ).where(DispatchCall.cad_number == cad_number)

    result = await db.execute(query)
    row = result.first()

    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Call not found")

    call = row[0]
    lat = row[1]
    lng = row[2]

    coords = (
        Coordinates(latitude=float(lat), longitude=float(lng))
        if lat is not None and lng is not None
        else None
    )

    return DispatchCallOut(
        id=call.id,
        cad_number=call.cad_number,
        call_type_code=call.call_type_code,
        call_type_description=call.call_type_description,
        priority=call.priority,
        received_at=call.received_at,
        dispatch_at=call.dispatch_at,
        on_scene_at=call.on_scene_at,
        closed_at=call.closed_at,
        coordinates=coords,
        location_text=call.location_text,
        district=call.district,
        disposition=call.disposition,
    )
