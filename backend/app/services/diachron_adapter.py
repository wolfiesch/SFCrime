# ============================================================================
# CHANGELOG (recent first, max 5 entries)
# 01/18/2026 - Initial implementation for SFCrime ↔ Diachron integration (Claude)
# ============================================================================

"""
Adapter for converting SFCrime records to Diachron location_facts format.

This module bridges SFCrime's real-time crime data with Diachron's temporal
intelligence schema, enabling unified historical queries across all SF civic data.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from app.models import DispatchCall, IncidentReport


@dataclass
class DiachronLocation:
    """
    Represents a location in Diachron's schema.

    Used for creating or matching locations before inserting facts.
    """

    coordinates_lat: float
    coordinates_lng: float
    address: str | None = None
    current_name: str | None = None
    neighborhood_slug: str | None = None

    # External IDs for deduplication
    osm_id: str | None = None
    wikidata_id: str | None = None

    def __post_init__(self) -> None:
        """Validate coordinates are in SF bounding box."""
        if not (37.6 <= self.coordinates_lat <= 37.85):
            raise ValueError(f"Latitude {self.coordinates_lat} outside SF bounds")
        if not (-122.55 <= self.coordinates_lng <= -122.35):
            raise ValueError(f"Longitude {self.coordinates_lng} outside SF bounds")


@dataclass
class DiachronFact:
    """
    Represents a historical fact in Diachron's schema.

    Maps to the `location_facts` table with proper temporal semantics.
    """

    # Required fields
    kind_code: str  # 'dispatch_call', 'police_incident', 'fire_call', '311_case'
    title: str
    description: str
    valid_from: datetime
    coordinates_lat: float
    coordinates_lng: float

    # Optional temporal
    valid_to: datetime | None = None  # None = point-in-time event

    # Identifiers
    external_id: str | None = None  # CAD number, incident ID, etc.
    id: UUID = field(default_factory=uuid4)

    # Classification
    categories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    significance: str = "local"  # local, city, regional, national, global

    # Temporal metadata
    time_granularity: str = "day"  # day, month, year, decade
    time_certainty: str = "exact"  # exact, approx, inferred, unknown
    date_display: str | None = None  # Human-readable: "Jan 18, 2026"

    # Provenance
    sources: list[dict] = field(default_factory=list)
    source_dataset: str = "sfcrime"
    original_text: str | None = None  # Raw data (not served via API)

    # Location context
    neighborhood_slug: str | None = None
    address: str | None = None

    def to_daterange_sql(self) -> str:
        """Convert to PostgreSQL DATERANGE literal."""
        start = self.valid_from.date().isoformat()
        if self.valid_to:
            # [) semantics: inclusive start, exclusive end
            end = (self.valid_to.date() + timedelta(days=1)).isoformat()
            return f"[{start},{end})"
        else:
            # Point-in-time: single-day range
            end = (self.valid_from.date() + timedelta(days=1)).isoformat()
            return f"[{start},{end})"


# ============================================================================
# DISPATCH CALL ADAPTER
# ============================================================================


def dispatch_call_to_diachron(
    call: DispatchCall,
    latitude: float,
    longitude: float,
) -> DiachronFact:
    """
    Convert a SFCrime DispatchCall to Diachron fact format.

    Args:
        call: The dispatch call model instance
        latitude: Extracted latitude from PostGIS point
        longitude: Extracted longitude from PostGIS point

    Returns:
        DiachronFact ready for insertion into Diachron's location_facts table
    """
    # Build descriptive title
    title = call.call_type_description or call.call_type_code or "Police Dispatch"

    # Build description with available details
    desc_parts = []
    if call.call_type_code:
        desc_parts.append(f"Call Type: {call.call_type_code}")
    if call.priority:
        desc_parts.append(f"Priority: {call.priority}")
    if call.disposition:
        desc_parts.append(f"Disposition: {call.disposition}")
    if call.location_text:
        desc_parts.append(f"Location: {call.location_text}")

    description = " | ".join(desc_parts) if desc_parts else "Police dispatch call"

    # Determine time bounds
    valid_from = call.received_at
    valid_to = call.closed_at  # None if still active

    # Build source metadata
    sources = [
        {
            "url": "https://data.sfgov.org/resource/gnap-fj3t.json",
            "title": "DataSF Law Enforcement Dispatched Calls",
            "dataset_id": "gnap-fj3t",
            "license": "Public Domain",
        }
    ]

    # Categorize by priority
    categories = ["law_enforcement", "dispatch"]
    if call.priority:
        if call.priority in ("A", "B"):
            categories.append("high_priority")
        elif call.priority in ("C", "D"):
            categories.append("low_priority")

    # Map district to neighborhood slug
    neighborhood_slug = _district_to_neighborhood(call.district)

    return DiachronFact(
        kind_code="dispatch_call",
        title=title,
        description=description,
        valid_from=valid_from,
        valid_to=valid_to,
        coordinates_lat=latitude,
        coordinates_lng=longitude,
        external_id=call.cad_number,
        categories=categories,
        tags=[call.call_type_code] if call.call_type_code else [],
        significance="local",
        time_granularity="day",
        time_certainty="exact",
        date_display=valid_from.strftime("%b %d, %Y %I:%M %p"),
        sources=sources,
        source_dataset="datasf_dispatch",
        original_text=None,  # No copyright concern with structured data
        neighborhood_slug=neighborhood_slug,
        address=call.location_text,
    )


def dispatch_call_dict_to_diachron(record: dict[str, Any]) -> DiachronFact | None:
    """
    Convert a raw DataSF dispatch call record to Diachron fact format.

    Used during initial ingestion when we have raw API response, not ORM models.

    Args:
        record: Raw dictionary from DataSF SODA API

    Returns:
        DiachronFact or None if record is invalid
    """
    # Extract coordinates
    point = record.get("intersection_point", {})
    if not point or "coordinates" not in point:
        return None

    coords = point["coordinates"]
    longitude, latitude = coords[0], coords[1]

    # Validate SF bounds
    if not (37.6 <= latitude <= 37.85) or not (-122.55 <= longitude <= -122.35):
        return None

    # Parse received datetime
    received_str = record.get("received_datetime")
    if not received_str:
        return None

    try:
        received_at = datetime.fromisoformat(received_str.replace("Z", "+00:00"))
        if received_at.tzinfo is None:
            received_at = received_at.replace(tzinfo=UTC)
    except (ValueError, AttributeError):
        return None

    # Parse closed datetime if present
    closed_at = None
    if closed_str := record.get("close_datetime"):
        try:
            closed_at = datetime.fromisoformat(closed_str.replace("Z", "+00:00"))
            if closed_at.tzinfo is None:
                closed_at = closed_at.replace(tzinfo=UTC)
        except (ValueError, AttributeError):
            pass

    # Build title and description
    call_type_desc = record.get("call_type_original_desc", "")
    call_type_code = record.get("call_type_original", "")
    title = call_type_desc or call_type_code or "Police Dispatch"

    desc_parts = []
    if call_type_code:
        desc_parts.append(f"Call Type: {call_type_code}")
    if priority := record.get("priority_original"):
        desc_parts.append(f"Priority: {priority}")
    if disposition := record.get("disposition"):
        desc_parts.append(f"Disposition: {disposition}")
    if location := record.get("intersection_name"):
        desc_parts.append(f"Location: {location}")

    description = " | ".join(desc_parts) if desc_parts else "Police dispatch call"

    # Build categories
    categories = ["law_enforcement", "dispatch"]
    priority = record.get("priority_original")
    if priority in ("A", "B"):
        categories.append("high_priority")
    elif priority in ("C", "D"):
        categories.append("low_priority")

    return DiachronFact(
        kind_code="dispatch_call",
        title=title,
        description=description,
        valid_from=received_at,
        valid_to=closed_at,
        coordinates_lat=latitude,
        coordinates_lng=longitude,
        external_id=record.get("cad_number"),
        categories=categories,
        tags=[call_type_code] if call_type_code else [],
        significance="local",
        time_granularity="day",
        time_certainty="exact",
        date_display=received_at.strftime("%b %d, %Y %I:%M %p"),
        sources=[
            {
                "url": "https://data.sfgov.org/resource/gnap-fj3t.json",
                "title": "DataSF Law Enforcement Dispatched Calls",
                "dataset_id": "gnap-fj3t",
                "license": "Public Domain",
            }
        ],
        source_dataset="datasf_dispatch",
        neighborhood_slug=_district_to_neighborhood(record.get("police_district")),
        address=record.get("intersection_name"),
    )


# ============================================================================
# INCIDENT REPORT ADAPTER
# ============================================================================


def incident_report_to_diachron(
    incident: IncidentReport,
    latitude: float,
    longitude: float,
) -> DiachronFact:
    """
    Convert a SFCrime IncidentReport to Diachron fact format.

    Args:
        incident: The incident report model instance
        latitude: Extracted latitude from PostGIS point
        longitude: Extracted longitude from PostGIS point

    Returns:
        DiachronFact ready for insertion into Diachron's location_facts table
    """
    # Build title from category and subcategory
    title = incident.incident_category or "Police Incident"
    if incident.incident_subcategory and incident.incident_subcategory != title:
        title = f"{title}: {incident.incident_subcategory}"

    # Build description
    desc_parts = []
    if incident.incident_description:
        desc_parts.append(incident.incident_description)
    if incident.resolution:
        desc_parts.append(f"Resolution: {incident.resolution}")
    if incident.location_text:
        desc_parts.append(f"Location: {incident.location_text}")

    description = " | ".join(desc_parts) if desc_parts else title

    # Determine valid_from from incident_date + incident_time
    if incident.incident_date:
        if incident.incident_time:
            valid_from = datetime.combine(
                incident.incident_date, incident.incident_time, tzinfo=UTC
            )
        else:
            valid_from = datetime.combine(
                incident.incident_date, datetime.min.time(), tzinfo=UTC
            )
    elif incident.report_datetime:
        valid_from = incident.report_datetime
    else:
        # Fallback: should not happen with valid data
        valid_from = datetime.now(UTC)

    # Categories from incident category
    categories = ["law_enforcement", "incident_report"]
    if incident.incident_category:
        cat_lower = incident.incident_category.lower()
        if "assault" in cat_lower or "robbery" in cat_lower:
            categories.append("violent_crime")
        elif "theft" in cat_lower or "burglary" in cat_lower:
            categories.append("property_crime")
        elif "drug" in cat_lower or "narcotic" in cat_lower:
            categories.append("drug_offense")

    return DiachronFact(
        kind_code="police_incident",
        title=title,
        description=description,
        valid_from=valid_from,
        valid_to=None,  # Point-in-time event
        coordinates_lat=latitude,
        coordinates_lng=longitude,
        external_id=incident.incident_id,
        categories=categories,
        tags=[incident.incident_category] if incident.incident_category else [],
        significance="local",
        time_granularity="day",
        time_certainty="exact",
        date_display=valid_from.strftime("%b %d, %Y"),
        sources=[
            {
                "url": "https://data.sfgov.org/resource/wg3w-h783.json",
                "title": "DataSF Police Department Incident Reports",
                "dataset_id": "wg3w-h783",
                "license": "Public Domain",
            }
        ],
        source_dataset="datasf_incidents",
        neighborhood_slug=incident.analysis_neighborhood,
        address=incident.location_text,
    )


def incident_report_dict_to_diachron(record: dict[str, Any]) -> DiachronFact | None:
    """
    Convert a raw DataSF incident report record to Diachron fact format.

    Used during initial ingestion when we have raw API response, not ORM models.

    Args:
        record: Raw dictionary from DataSF SODA API

    Returns:
        DiachronFact or None if record is invalid
    """
    # Extract coordinates
    latitude = record.get("latitude")
    longitude = record.get("longitude")

    # Try point field if lat/lng not available
    if not latitude or not longitude:
        point = record.get("point", {})
        if point and "coordinates" in point:
            coords = point["coordinates"]
            longitude, latitude = coords[0], coords[1]

    if not latitude or not longitude:
        return None

    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (ValueError, TypeError):
        return None

    # Validate SF bounds
    if not (37.6 <= latitude <= 37.85) or not (-122.55 <= longitude <= -122.35):
        return None

    # Parse incident date
    incident_date = None
    incident_time = None

    if date_str := record.get("incident_date"):
        try:
            incident_date = date.fromisoformat(date_str[:10])
        except ValueError:
            pass

    if time_str := record.get("incident_time"):
        try:
            incident_time = datetime.strptime(time_str, "%H:%M").time()
        except ValueError:
            pass

    # Determine valid_from
    if incident_date:
        if incident_time:
            valid_from = datetime.combine(incident_date, incident_time, tzinfo=UTC)
        else:
            valid_from = datetime.combine(
                incident_date, datetime.min.time(), tzinfo=UTC
            )
    elif report_str := record.get("report_datetime"):
        try:
            valid_from = datetime.fromisoformat(report_str.replace("Z", "+00:00"))
            if valid_from.tzinfo is None:
                valid_from = valid_from.replace(tzinfo=UTC)
        except ValueError:
            return None
    else:
        return None

    # Build title
    category = record.get("incident_category", "")
    subcategory = record.get("incident_subcategory", "")
    title = category or "Police Incident"
    if subcategory and subcategory != title:
        title = f"{title}: {subcategory}"

    # Build description
    desc_parts = []
    if description := record.get("incident_description"):
        desc_parts.append(description)
    if resolution := record.get("resolution"):
        desc_parts.append(f"Resolution: {resolution}")
    if location := record.get("intersection"):
        desc_parts.append(f"Location: {location}")

    description = " | ".join(desc_parts) if desc_parts else title

    # Categories
    categories = ["law_enforcement", "incident_report"]
    if category:
        cat_lower = category.lower()
        if "assault" in cat_lower or "robbery" in cat_lower:
            categories.append("violent_crime")
        elif "theft" in cat_lower or "burglary" in cat_lower:
            categories.append("property_crime")
        elif "drug" in cat_lower or "narcotic" in cat_lower:
            categories.append("drug_offense")

    return DiachronFact(
        kind_code="police_incident",
        title=title,
        description=description,
        valid_from=valid_from,
        valid_to=None,
        coordinates_lat=latitude,
        coordinates_lng=longitude,
        external_id=record.get("incident_id"),
        categories=categories,
        tags=[category] if category else [],
        significance="local",
        time_granularity="day",
        time_certainty="exact",
        date_display=valid_from.strftime("%b %d, %Y"),
        sources=[
            {
                "url": "https://data.sfgov.org/resource/wg3w-h783.json",
                "title": "DataSF Police Department Incident Reports",
                "dataset_id": "wg3w-h783",
                "license": "Public Domain",
            }
        ],
        source_dataset="datasf_incidents",
        neighborhood_slug=record.get("analysis_neighborhood"),
        address=record.get("intersection"),
    )


# ============================================================================
# HELPERS
# ============================================================================


def _district_to_neighborhood(district: str | None) -> str | None:
    """
    Map SFPD district to Diachron neighborhood slug.

    SFPD Districts: Bayview, Central, Ingleside, Mission, Northern,
                   Out of SF, Park, Richmond, Southern, Taraval, Tenderloin
    """
    if not district:
        return None

    district_map = {
        "BAYVIEW": "bayview-hunters-point",
        "CENTRAL": "chinatown",  # Central covers Chinatown, North Beach
        "INGLESIDE": "ingleside",
        "MISSION": "mission",
        "NORTHERN": "pacific-heights",  # Northern covers Pacific Heights, Marina
        "PARK": "haight-ashbury",  # Park covers Haight, Cole Valley
        "RICHMOND": "richmond",
        "SOUTHERN": "south-of-market",  # Southern covers SoMa, Rincon Hill
        "TARAVAL": "sunset-district",  # Taraval covers Sunset, Parkside
        "TENDERLOIN": "tenderloin",
    }

    return district_map.get(district.upper())
