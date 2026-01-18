"""SyncCheckpoint model to track incremental ingestion progress."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SyncCheckpoint(Base):
    """
    Tracks the last successful sync timestamp for each data source.

    Used for incremental ingestion to avoid re-fetching all data.
    """

    __tablename__ = "sync_checkpoints"

    # 'dispatch_calls' or 'incident_reports'
    source: Mapped[str] = mapped_column(String(50), primary_key=True)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_sync_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    record_count: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)

    def __repr__(self) -> str:
        return f"<SyncCheckpoint {self.source}: {self.last_updated_at}>"
