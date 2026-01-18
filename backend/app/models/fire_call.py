"""FireCall model for Fire Department Calls for Service (nuek-vuh3 dataset)."""

from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FireCall(Base):
    """
    Fire Department Call for Service from DataSF nuek-vuh3 dataset.

    Represents 911 calls to the Fire Department including medical emergencies,
    fires, and other incidents. Uses incident_number as unique key to avoid
    duplicate records when multiple units respond to the same incident.
    """

    __tablename__ = "fire_calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    # Call classification
    call_type: Mapped[str | None] = mapped_column(String(100))
    call_type_group: Mapped[str | None] = mapped_column(String(50))  # Life-threatening, Non Life-threatening
    priority: Mapped[str | None] = mapped_column(String(1), index=True)  # 1, 2, 3 (1 is highest)
    number_of_alarms: Mapped[int | None] = mapped_column(Integer)

    # Timestamps
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dispatch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    on_scene_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    transport_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hospital_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Disposition
    disposition: Mapped[str | None] = mapped_column(String(100))

    # Location (PostGIS geometry for efficient viewport queries)
    location: Mapped[str | None] = mapped_column(Geometry("POINT", srid=4326))
    location_text: Mapped[str | None] = mapped_column(String(255))  # Human-readable address
    zipcode: Mapped[str | None] = mapped_column(String(10))

    # Administrative
    neighborhood: Mapped[str | None] = mapped_column(String(100), index=True)
    supervisor_district: Mapped[str | None] = mapped_column(String(10))
    battalion: Mapped[str | None] = mapped_column(String(10))
    station_area: Mapped[str | None] = mapped_column(String(10))

    # Unit info (first responding unit)
    unit_type: Mapped[str | None] = mapped_column(String(20))  # MEDIC, ENGINE, TRUCK, etc.
    is_als_unit: Mapped[bool | None] = mapped_column(Boolean)  # Advanced Life Support

    # Sync tracking
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        # Spatial index for bounding box queries
        Index("idx_fire_calls_location", location, postgresql_using="gist"),
        # Cursor pagination index
        Index("idx_fire_calls_cursor", received_at.desc(), id.desc()),
        # Call type index for filtering
        Index("idx_fire_calls_type", call_type),
    )

    def __repr__(self) -> str:
        return f"<FireCall {self.incident_number}: {self.call_type}>"
