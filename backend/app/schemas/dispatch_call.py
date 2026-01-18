"""Pydantic schemas for dispatch calls."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Coordinates(BaseModel):
    """Geographic coordinates."""

    latitude: float
    longitude: float


class DispatchCallOut(BaseModel):
    """Dispatch call response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    cad_number: str
    call_type_code: str | None = None
    call_type_description: str | None = None
    priority: str | None = None

    received_at: datetime
    dispatch_at: datetime | None = None
    on_scene_at: datetime | None = None
    closed_at: datetime | None = None

    coordinates: Coordinates | None = None
    location_text: str | None = None
    district: str | None = None
    disposition: str | None = None


class DispatchCallsResponse(BaseModel):
    """Paginated response for dispatch calls."""

    calls: list[DispatchCallOut]
    next_cursor: str | None = None
    total: int | None = None


class BoundingBox(BaseModel):
    """Bounding box for viewport queries."""

    min_lat: float = Field(..., ge=-90, le=90)
    min_lng: float = Field(..., ge=-180, le=180)
    max_lat: float = Field(..., ge=-90, le=90)
    max_lng: float = Field(..., ge=-180, le=180)
