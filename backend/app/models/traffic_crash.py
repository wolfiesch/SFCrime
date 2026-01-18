"""Traffic Crash model for vehicle collision data."""

from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TrafficCrash(Base):
    """
    Traffic Crash from DataSF dataset ubvf-ztfx.

    Records traffic collisions in San Francisco with details on
    severity, parties involved, and conditions.
    """

    __tablename__ = "traffic_crashes"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Core identifiers
    unique_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    case_id: Mapped[str | None] = mapped_column(String(20))

    # Collision details
    collision_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    collision_severity: Mapped[str | None] = mapped_column(String(100), index=True)
    type_of_collision: Mapped[str | None] = mapped_column(String(100))

    # Casualties
    number_killed: Mapped[int | None] = mapped_column(Integer, default=0)
    number_injured: Mapped[int | None] = mapped_column(Integer, default=0)

    # Location
    location: Mapped[str | None] = mapped_column(Geometry("POINT", srid=4326))
    primary_road: Mapped[str | None] = mapped_column(String(100))
    secondary_road: Mapped[str | None] = mapped_column(String(100))
    distance: Mapped[int | None] = mapped_column(Integer)
    direction: Mapped[str | None] = mapped_column(String(20))

    # Conditions
    weather: Mapped[str | None] = mapped_column(String(50))
    road_surface: Mapped[str | None] = mapped_column(String(50))
    road_condition: Mapped[str | None] = mapped_column(String(100))
    lighting: Mapped[str | None] = mapped_column(String(50))

    # Party information
    party1_type: Mapped[str | None] = mapped_column(String(50))
    party2_type: Mapped[str | None] = mapped_column(String(50))
    pedestrian_action: Mapped[str | None] = mapped_column(String(100))

    # Administrative
    neighborhood: Mapped[str | None] = mapped_column(String(100), index=True)
    supervisor_district: Mapped[str | None] = mapped_column(String(10))
    police_district: Mapped[str | None] = mapped_column(String(50))
    reporting_district: Mapped[str | None] = mapped_column(String(50))
    beat_number: Mapped[str | None] = mapped_column(String(10))

    # Sync metadata
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        server_default="now()",
    )

    __table_args__ = (
        Index("ix_traffic_crashes_type", "type_of_collision"),
        Index("ix_traffic_crashes_last_updated_at", "last_updated_at"),
        Index("idx_traffic_crashes_location", "location", postgresql_using="gist"),
        Index(
            "idx_traffic_crashes_cursor",
            collision_datetime.desc(),
            id.desc(),
        ),
    )
