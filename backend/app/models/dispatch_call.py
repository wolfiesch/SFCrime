"""DispatchCall model for live 911 dispatch data (gnap-fj3t dataset)."""

from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DispatchCall(Base):
    """
    Live dispatch call from DataSF gnap-fj3t dataset.

    Represents 911 calls as they happen with 10-15 minute delay.
    Rolling 48-hour retention window.
    """

    __tablename__ = "dispatch_calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    cad_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    # Call classification
    call_type_code: Mapped[str | None] = mapped_column(String(20))
    call_type_description: Mapped[str | None] = mapped_column(String(255))
    priority: Mapped[str | None] = mapped_column(String(1), index=True)  # A, B, or C

    # Timestamps
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dispatch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    on_scene_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Location (PostGIS geometry for efficient viewport queries)
    location: Mapped[str | None] = mapped_column(Geometry("POINT", srid=4326))
    location_text: Mapped[str | None] = mapped_column(String(255))  # Human-readable intersection

    # Administrative
    district: Mapped[str | None] = mapped_column(String(50), index=True)
    disposition: Mapped[str | None] = mapped_column(String(20))

    # Sync tracking
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        # Spatial index for bounding box queries
        Index("idx_calls_location", location, postgresql_using="gist"),
        # Cursor pagination index
        Index("idx_calls_cursor", received_at.desc(), id.desc()),
    )

    def __repr__(self) -> str:
        return f"<DispatchCall {self.cad_number}: {self.call_type_description}>"
