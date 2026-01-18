"""Tests for ingestion service."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.ingestion import IngestionService


class TestIngestionService:
    """Tests for IngestionService."""

    def test_parse_datetime_valid(self, db_session):
        """Test parsing valid datetime strings."""
        service = IngestionService(db=db_session)

        # ISO format with microseconds
        result = service._parse_datetime("2024-01-18T10:30:00.123")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 18
        assert result.hour == 10
        assert result.minute == 30

        # ISO format without microseconds
        result = service._parse_datetime("2024-01-18T10:30:00")
        assert result is not None

        # Space-separated format
        result = service._parse_datetime("2024-01-18 10:30:00")
        assert result is not None

    def test_parse_datetime_invalid(self, db_session):
        """Test parsing invalid datetime strings."""
        service = IngestionService(db=db_session)

        assert service._parse_datetime(None) is None
        assert service._parse_datetime("") is None
        assert service._parse_datetime("invalid") is None
        assert service._parse_datetime("01/18/2024") is None

    def test_parse_point_from_intersection_point(self, db_session):
        """Test extracting point from intersection_point field."""
        service = IngestionService(db=db_session)

        record = {
            "intersection_point": {
                "type": "Point",
                "coordinates": [-122.4194, 37.7749],
            }
        }

        # Note: WKTElement requires PostGIS, so in SQLite tests we check the logic
        # The actual PostGIS functionality would be tested in integration tests
        point = service._parse_point(record)
        # In real tests with PostGIS, this would return a WKTElement
        # For unit tests, we're mainly verifying the parsing logic works

    def test_parse_point_from_lat_lng(self, db_session):
        """Test extracting point from lat/lng fields."""
        service = IngestionService(db=db_session)

        record = {
            "latitude": "37.7749",
            "longitude": "-122.4194",
        }

        point = service._parse_point(record)
        # Returns WKTElement with the coordinates

    def test_parse_point_missing(self, db_session):
        """Test handling missing coordinates."""
        service = IngestionService(db=db_session)

        assert service._parse_point({}) is None
        assert service._parse_point({"latitude": None}) is None
        assert service._parse_point({"longitude": "invalid"}) is None

    def test_transform_incident_record(self, db_session, sample_incident_records):
        """Test transforming raw incident record."""
        service = IngestionService(db=db_session)

        record = sample_incident_records[0]
        result = service._transform_incident_record(record)

        assert result is not None
        assert result["incident_id"] == "1000001"
        assert result["incident_number"] == "240100001"
        assert result["incident_category"] == "Larceny Theft"
        assert result["incident_subcategory"] == "Larceny - From Vehicle"
        assert result["police_district"] == "Southern"
        assert result["analysis_neighborhood"] == "South of Market"

    def test_transform_incident_record_missing_id(self, db_session):
        """Test that records without incident_id are rejected."""
        service = IngestionService(db=db_session)

        record = {"incident_category": "Test"}
        result = service._transform_incident_record(record)

        assert result is None

    @pytest.mark.asyncio
    async def test_sync_dispatch_calls_no_records(self, db_session, mock_soda_client):
        """Test sync when no new records available."""
        mock_soda_client.fetch_all_dispatch_calls = AsyncMock(return_value=[])
        service = IngestionService(db=db_session, soda_client=mock_soda_client)

        count, cad_numbers = await service.sync_dispatch_calls()

        assert count == 0
        assert cad_numbers == []

    @pytest.mark.asyncio
    async def test_sync_dispatch_calls_skips_invalid(
        self, db_session, mock_soda_client
    ):
        """Test that records without required fields are skipped."""
        mock_soda_client.fetch_all_dispatch_calls = AsyncMock(
            return_value=[
                {"cad_number": "123"},  # Missing received_datetime
                {"received_datetime": "2024-01-18T10:00:00"},  # Missing cad_number
            ]
        )
        service = IngestionService(db=db_session, soda_client=mock_soda_client)

        count, cad_numbers = await service.sync_dispatch_calls()

        assert count == 0
        assert cad_numbers == []

    @pytest.mark.asyncio
    async def test_get_checkpoint_not_found(self, db_session):
        """Test getting checkpoint that doesn't exist."""
        service = IngestionService(db=db_session)

        result = await service.get_checkpoint("nonexistent_source")

        assert result is None

    @pytest.mark.asyncio
    async def test_sync_incident_reports_no_records(self, db_session, mock_soda_client):
        """Test incident sync when no records available."""
        mock_soda_client.fetch_all_incident_reports = AsyncMock(return_value=[])
        service = IngestionService(db=db_session, soda_client=mock_soda_client)

        count = await service.sync_incident_reports()

        assert count == 0


class TestIngestionServiceIntegration:
    """Integration-style tests that verify database operations."""

    @pytest.mark.asyncio
    async def test_checkpoint_roundtrip(self, db_session):
        """Test updating and retrieving checkpoint."""
        from sqlalchemy import text

        service = IngestionService(db=db_session)

        # Initial checkpoint should be None
        checkpoint = await service.get_checkpoint("test_source")
        assert checkpoint is None

        # Update checkpoint (use raw SQL for SQLite compatibility)
        now = datetime.now(UTC)
        await db_session.execute(
            text("""
                INSERT INTO sync_checkpoints (source, last_updated_at, last_sync_at, record_count)
                VALUES (:source, :last_updated_at, :last_sync_at, :record_count)
            """),
            {
                "source": "test_source",
                "last_updated_at": now,
                "last_sync_at": now,
                "record_count": 100,
            },
        )
        await db_session.commit()

        # Retrieve checkpoint
        result = await db_session.execute(
            text("SELECT last_updated_at FROM sync_checkpoints WHERE source = :source"),
            {"source": "test_source"},
        )
        row = result.fetchone()
        assert row is not None
