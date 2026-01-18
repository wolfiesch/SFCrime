"""311 Service Request model for non-emergency city service requests."""

from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ServiceRequest(Base):
    """
    311 Service Request from DataSF dataset vw6y-z8j6.

    311 captures non-emergency city service requests like street cleaning,
    graffiti removal, pothole repairs, etc.
    """

    __tablename__ = "service_requests"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Core identifier
    service_request_id: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False
    )

    # Service details
    service_name: Mapped[str | None] = mapped_column(String(100))
    service_subtype: Mapped[str | None] = mapped_column(String(100))
    service_details: Mapped[str | None] = mapped_column(String(255))

    # Status
    status_description: Mapped[str | None] = mapped_column(String(50))
    status_notes: Mapped[str | None] = mapped_column(Text)

    # Agency
    agency_responsible: Mapped[str | None] = mapped_column(String(100))
    source: Mapped[str | None] = mapped_column(String(50))

    # Timestamps
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Location
    location: Mapped[str | None] = mapped_column(Geometry("POINT", srid=4326))
    address: Mapped[str | None] = mapped_column(String(255))
    street: Mapped[str | None] = mapped_column(String(100))

    # Administrative
    neighborhood: Mapped[str | None] = mapped_column(String(100), index=True)
    supervisor_district: Mapped[str | None] = mapped_column(String(10))
    police_district: Mapped[str | None] = mapped_column(String(50))

    # Media
    media_url: Mapped[str | None] = mapped_column(String(512))

    # Sync metadata
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        server_default="now()",
    )

    __table_args__ = (
        Index("ix_service_requests_service_name", "service_name"),
        Index("ix_service_requests_status", "status_description"),
        Index("ix_service_requests_last_updated_at", "last_updated_at"),
        Index("idx_service_requests_location", "location", postgresql_using="gist"),
        Index(
            "idx_service_requests_cursor",
            requested_at.desc(),
            id.desc(),
        ),
    )
