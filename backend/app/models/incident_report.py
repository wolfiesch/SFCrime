"""IncidentReport model for historical incident data (wg3w-h783 dataset)."""

from datetime import date, datetime, time

from geoalchemy2 import Geometry
from sqlalchemy import Date, DateTime, Index, String, Time, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IncidentReport(Base):
    """
    Historical incident report from DataSF wg3w-h783 dataset.

    Represents filed police reports (verified incidents) from 2018-present.
    24-72 hour latency from incident to report availability.
    """

    __tablename__ = "incident_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    incident_number: Mapped[str | None] = mapped_column(String(20))

    # Classification
    incident_category: Mapped[str | None] = mapped_column(String(100), index=True)
    incident_subcategory: Mapped[str | None] = mapped_column(String(100))
    incident_description: Mapped[str | None] = mapped_column(String(500))
    resolution: Mapped[str | None] = mapped_column(String(100))

    # Timestamps
    incident_date: Mapped[date | None] = mapped_column(Date, index=True)
    incident_time: Mapped[time | None] = mapped_column(Time)
    report_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Location (PostGIS geometry for map queries)
    location: Mapped[str | None] = mapped_column(Geometry("POINT", srid=4326))
    location_text: Mapped[str | None] = mapped_column(String(255))  # Human-readable address

    # Administrative
    police_district: Mapped[str | None] = mapped_column(String(50), index=True)
    analysis_neighborhood: Mapped[str | None] = mapped_column(String(100))

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        # Spatial index
        Index("idx_reports_location", location, postgresql_using="gist"),
        # Cursor pagination index
        Index("idx_reports_cursor", report_datetime.desc(), id.desc()),
    )

    def __repr__(self) -> str:
        return f"<IncidentReport {self.incident_id}: {self.incident_category}>"
