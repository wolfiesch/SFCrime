"""Tests for API endpoints."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import text

# Mark tests that require PostGIS
requires_postgis = pytest.mark.skip(reason="Requires PostgreSQL with PostGIS extension")


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        """Test health endpoint returns status."""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data


class TestRootEndpoint:
    """Tests for root endpoint."""

    @pytest.mark.asyncio
    async def test_root_endpoint(self, client):
        """Test root endpoint returns API info."""
        response = await client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "SFCrime API"
        assert "version" in data
        assert "docs" in data


class TestCallsEndpoints:
    """Tests for dispatch calls endpoints."""

    @requires_postgis
    @pytest.mark.asyncio
    async def test_list_calls_empty(self, client):
        """Test listing calls when database is empty."""
        response = await client.get("/api/v1/calls")

        assert response.status_code == 200
        data = response.json()
        assert "calls" in data
        assert data["calls"] == []
        assert data["next_cursor"] is None

    @requires_postgis
    @pytest.mark.asyncio
    async def test_list_calls_with_data(self, client, db_session):
        """Test listing calls with data in database."""
        # Insert test data
        now = datetime.now(UTC)
        await db_session.execute(
            text("""
                INSERT INTO dispatch_calls (
                    cad_number, call_type_code, call_type_description,
                    priority, received_at, location_text, district
                ) VALUES (
                    :cad_number, :call_type_code, :call_type_description,
                    :priority, :received_at, :location_text, :district
                )
            """),
            {
                "cad_number": "240180001",
                "call_type_code": "459",
                "call_type_description": "BURGLARY",
                "priority": "A",
                "received_at": now,
                "location_text": "MARKET ST",
                "district": "SOUTHERN",
            },
        )
        await db_session.commit()

        response = await client.get("/api/v1/calls")

        assert response.status_code == 200
        data = response.json()
        assert len(data["calls"]) == 1
        assert data["calls"][0]["cad_number"] == "240180001"

    @requires_postgis
    @pytest.mark.asyncio
    async def test_list_calls_priority_filter(self, client, db_session):
        """Test filtering calls by priority."""
        # Insert test data with different priorities
        now = datetime.now(UTC)
        for i, priority in enumerate(["A", "B", "C"]):
            await db_session.execute(
                text("""
                    INSERT INTO dispatch_calls (
                        cad_number, priority, received_at
                    ) VALUES (
                        :cad_number, :priority, :received_at
                    )
                """),
                {
                    "cad_number": f"24018000{i}",
                    "priority": priority,
                    "received_at": now,
                },
            )
        await db_session.commit()

        # Filter by priority A
        response = await client.get("/api/v1/calls?priority=A")

        assert response.status_code == 200
        data = response.json()
        assert len(data["calls"]) == 1
        assert data["calls"][0]["priority"] == "A"

    @requires_postgis
    @pytest.mark.asyncio
    async def test_list_calls_pagination(self, client, db_session):
        """Test cursor-based pagination."""
        # Insert multiple records
        now = datetime.now(UTC)
        for i in range(5):
            await db_session.execute(
                text("""
                    INSERT INTO dispatch_calls (
                        cad_number, priority, received_at
                    ) VALUES (
                        :cad_number, :priority, :received_at
                    )
                """),
                {
                    "cad_number": f"2401800{i:02d}",
                    "priority": "A",
                    "received_at": now,
                },
            )
        await db_session.commit()

        # First page
        response = await client.get("/api/v1/calls?limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["calls"]) == 2
        assert data["next_cursor"] is not None

        # Second page using cursor
        cursor = data["next_cursor"]
        response = await client.get(f"/api/v1/calls?limit=2&cursor={cursor}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["calls"]) == 2

    @requires_postgis
    @pytest.mark.asyncio
    async def test_get_call_by_cad_number(self, client, db_session):
        """Test getting a specific call by CAD number."""
        now = datetime.now(UTC)
        await db_session.execute(
            text("""
                INSERT INTO dispatch_calls (
                    cad_number, call_type_description, priority, received_at
                ) VALUES (
                    :cad_number, :desc, :priority, :received_at
                )
            """),
            {
                "cad_number": "240180001",
                "desc": "TEST CALL",
                "priority": "A",
                "received_at": now,
            },
        )
        await db_session.commit()

        response = await client.get("/api/v1/calls/240180001")

        assert response.status_code == 200
        data = response.json()
        assert data["cad_number"] == "240180001"
        assert data["call_type_description"] == "TEST CALL"

    @requires_postgis
    @pytest.mark.asyncio
    async def test_get_call_not_found(self, client):
        """Test getting a non-existent call."""
        response = await client.get("/api/v1/calls/NONEXISTENT")

        assert response.status_code == 404

    @requires_postgis
    @pytest.mark.asyncio
    async def test_bbox_endpoint_empty(self, client):
        """Test bounding box query with no results."""
        response = await client.get(
            "/api/v1/calls/bbox",
            params={
                "min_lat": 37.0,
                "max_lat": 38.0,
                "min_lng": -123.0,
                "max_lng": -122.0,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data == []

    @pytest.mark.asyncio
    async def test_bbox_endpoint_validation(self, client):
        """Test bounding box parameter validation."""
        # Invalid latitude
        response = await client.get(
            "/api/v1/calls/bbox",
            params={
                "min_lat": 100.0,  # Invalid
                "max_lat": 38.0,
                "min_lng": -123.0,
                "max_lng": -122.0,
            },
        )

        assert response.status_code == 422  # Validation error


class TestIncidentsEndpoints:
    """Tests for incident report endpoints."""

    @requires_postgis
    @pytest.mark.asyncio
    async def test_search_incidents_empty(self, client):
        """Test searching incidents when database is empty."""
        response = await client.get("/api/v1/incidents/search")

        assert response.status_code == 200
        data = response.json()
        assert "incidents" in data
        assert data["incidents"] == []

    @requires_postgis
    @pytest.mark.asyncio
    async def test_search_incidents_with_data(self, client, db_session):
        """Test searching incidents with data."""
        now = datetime.now(UTC)
        await db_session.execute(
            text("""
                INSERT INTO incident_reports (
                    incident_id, incident_number, incident_category,
                    incident_description, report_datetime, police_district
                ) VALUES (
                    :incident_id, :incident_number, :category,
                    :description, :report_datetime, :district
                )
            """),
            {
                "incident_id": "1000001",
                "incident_number": "240100001",
                "category": "Larceny Theft",
                "description": "Theft from vehicle",
                "report_datetime": now,
                "district": "Southern",
            },
        )
        await db_session.commit()

        response = await client.get("/api/v1/incidents/search")

        assert response.status_code == 200
        data = response.json()
        assert len(data["incidents"]) == 1
        assert data["incidents"][0]["incident_id"] == "1000001"

    @requires_postgis
    @pytest.mark.asyncio
    async def test_search_incidents_district_filter(self, client, db_session):
        """Test filtering incidents by district."""
        now = datetime.now(UTC)
        for i, district in enumerate(["Southern", "Central", "Mission"]):
            await db_session.execute(
                text("""
                    INSERT INTO incident_reports (
                        incident_id, incident_category, report_datetime, police_district
                    ) VALUES (
                        :incident_id, :category, :report_datetime, :district
                    )
                """),
                {
                    "incident_id": f"100000{i}",
                    "category": "Test",
                    "report_datetime": now,
                    "district": district,
                },
            )
        await db_session.commit()

        response = await client.get("/api/v1/incidents/search?district=Southern")

        assert response.status_code == 200
        data = response.json()
        assert len(data["incidents"]) == 1
        assert data["incidents"][0]["police_district"] == "Southern"

    @pytest.mark.asyncio
    async def test_categories_endpoint(self, client, db_session):
        """Test getting incident categories."""
        now = datetime.now(UTC)
        categories = ["Larceny Theft", "Assault", "Burglary"]
        for i, category in enumerate(categories):
            await db_session.execute(
                text("""
                    INSERT INTO incident_reports (
                        incident_id, incident_category, report_datetime
                    ) VALUES (
                        :incident_id, :category, :report_datetime
                    )
                """),
                {
                    "incident_id": f"100000{i}",
                    "category": category,
                    "report_datetime": now,
                },
            )
        await db_session.commit()

        response = await client.get("/api/v1/incidents/categories")

        assert response.status_code == 200
        data = response.json()
        assert set(data) == set(categories)

    @pytest.mark.asyncio
    async def test_districts_endpoint(self, client, db_session):
        """Test getting police districts."""
        now = datetime.now(UTC)
        districts = ["Southern", "Central", "Mission"]
        for i, district in enumerate(districts):
            await db_session.execute(
                text("""
                    INSERT INTO incident_reports (
                        incident_id, incident_category, report_datetime, police_district
                    ) VALUES (
                        :incident_id, :category, :report_datetime, :district
                    )
                """),
                {
                    "incident_id": f"100000{i}",
                    "category": "Test",
                    "report_datetime": now,
                    "district": district,
                },
            )
        await db_session.commit()

        response = await client.get("/api/v1/incidents/districts")

        assert response.status_code == 200
        data = response.json()
        assert set(data) == set(districts)


class TestCursorEncoding:
    """Tests for cursor encoding/decoding utilities."""

    def test_encode_decode_cursor(self):
        """Test cursor roundtrip."""
        from app.routers.calls import _decode_cursor, _encode_cursor

        test_time = datetime(2024, 1, 18, 10, 30, 0)
        test_id = 12345

        encoded = _encode_cursor(test_time, test_id)
        decoded_time, decoded_id = _decode_cursor(encoded)

        assert decoded_time == test_time
        assert decoded_id == test_id

    def test_decode_invalid_cursor(self):
        """Test decoding invalid cursor."""
        from app.routers.calls import _decode_cursor

        with pytest.raises(Exception):
            _decode_cursor("invalid_cursor_string")
