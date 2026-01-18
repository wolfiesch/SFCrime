"""Pydantic schemas for incident reports."""

from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict

from app.schemas.dispatch_call import Coordinates


class IncidentReportOut(BaseModel):
    """Incident report response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: str
    incident_number: str | None = None

    incident_category: str | None = None
    incident_subcategory: str | None = None
    incident_description: str | None = None
    resolution: str | None = None

    incident_date: date | None = None
    incident_time: time | None = None
    report_datetime: datetime | None = None

    coordinates: Coordinates | None = None
    location_text: str | None = None
    police_district: str | None = None
    analysis_neighborhood: str | None = None


class IncidentReportsResponse(BaseModel):
    """Paginated response for incident reports."""

    incidents: list[IncidentReportOut]
    next_cursor: str | None = None
    total: int | None = None


class IncidentSearchParams(BaseModel):
    """Parameters for searching incident reports."""

    cursor: str | None = None
    limit: int = 50
    since: datetime | None = None
    until: datetime | None = None
    district: str | None = None
    category: str | None = None
