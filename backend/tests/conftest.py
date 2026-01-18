"""Pytest fixtures for SFCrime backend tests."""

import asyncio
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.database import Base, get_db
from app.main import app
from app.services.soda_client import SODAClient


# Test database URL - uses SQLite for isolation (no PostGIS features tested)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings() -> Settings:
    """Test settings with safe defaults."""
    return Settings(
        database_url=TEST_DATABASE_URL,
        soda_app_token="test_token",
        debug=True,
    )


@pytest_asyncio.fixture
async def async_engine():
    """Create async engine for testing."""
    # Use PostgreSQL for tests that need PostGIS
    # Falls back to mocking for unit tests
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    # Create tables (simplified - no PostGIS in SQLite)
    async with async_engine.begin() as conn:
        # Create simplified tables for testing
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS dispatch_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cad_number TEXT UNIQUE NOT NULL,
                call_type_code TEXT,
                call_type_description TEXT,
                priority TEXT,
                received_at TIMESTAMP NOT NULL,
                dispatch_at TIMESTAMP,
                on_scene_at TIMESTAMP,
                closed_at TIMESTAMP,
                location TEXT,
                location_text TEXT,
                district TEXT,
                disposition TEXT,
                last_updated_at TIMESTAMP
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS sync_checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT UNIQUE NOT NULL,
                last_updated_at TIMESTAMP NOT NULL,
                last_sync_at TIMESTAMP NOT NULL,
                record_count INTEGER DEFAULT 0
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS incident_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT UNIQUE NOT NULL,
                incident_number TEXT,
                incident_category TEXT,
                incident_subcategory TEXT,
                incident_description TEXT,
                resolution TEXT,
                incident_date DATE,
                incident_time TIME,
                report_datetime TIMESTAMP,
                location TEXT,
                location_text TEXT,
                police_district TEXT,
                analysis_neighborhood TEXT
            )
        """))

    async_session = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client with database override."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def mock_soda_client() -> SODAClient:
    """Create mocked SODA client."""
    client = SODAClient(app_token="test_token")
    client._request_with_retry = AsyncMock()
    return client


@pytest.fixture
def sample_dispatch_records() -> list[dict[str, Any]]:
    """Sample dispatch call records from DataSF API."""
    return [
        {
            "cad_number": "240180001",
            "call_type_original": "459",
            "call_type_original_desc": "BURGLARY",
            "priority_original": "A",
            "received_datetime": "2024-01-18T10:30:00.000",
            "dispatch_datetime": "2024-01-18T10:32:00.000",
            "onscene_datetime": "2024-01-18T10:45:00.000",
            "close_datetime": None,
            "call_last_updated_at": "2024-01-18T10:45:00.000",
            "intersection_point": {
                "type": "Point",
                "coordinates": [-122.4194, 37.7749],
            },
            "intersection_name": "MARKET ST / 5TH ST",
            "police_district": "SOUTHERN",
            "disposition": "REP",
        },
        {
            "cad_number": "240180002",
            "call_type_original": "594",
            "call_type_original_desc": "VANDALISM",
            "priority_original": "B",
            "received_datetime": "2024-01-18T11:00:00.000",
            "dispatch_datetime": "2024-01-18T11:05:00.000",
            "onscene_datetime": None,
            "close_datetime": None,
            "call_last_updated_at": "2024-01-18T11:05:00.000",
            "intersection_point": {
                "type": "Point",
                "coordinates": [-122.4089, 37.7851],
            },
            "intersection_name": "POWELL ST / GEARY ST",
            "police_district": "CENTRAL",
            "disposition": None,
        },
        {
            "cad_number": "240180003",
            "call_type_original": "211",
            "call_type_original_desc": "ROBBERY",
            "priority_original": "A",
            "received_datetime": "2024-01-18T12:00:00.000",
            "dispatch_datetime": None,
            "onscene_datetime": None,
            "close_datetime": None,
            "call_last_updated_at": "2024-01-18T12:00:00.000",
            "intersection_point": None,  # No coordinates
            "intersection_name": "UNKNOWN",
            "police_district": "MISSION",
            "disposition": None,
        },
    ]


@pytest.fixture
def sample_incident_records() -> list[dict[str, Any]]:
    """Sample incident report records from DataSF API."""
    return [
        {
            "incident_id": "1000001",
            "incident_number": "240100001",
            "incident_category": "Larceny Theft",
            "incident_subcategory": "Larceny - From Vehicle",
            "incident_description": "Theft from locked vehicle",
            "resolution": "Open or Active",
            "incident_date": "2024-01-15",
            "incident_time": "14:30",
            "report_datetime": "2024-01-15T15:00:00.000",
            "latitude": "37.7749",
            "longitude": "-122.4194",
            "intersection": "MARKET ST / 5TH ST",
            "police_district": "Southern",
            "analysis_neighborhood": "South of Market",
        },
        {
            "incident_id": "1000002",
            "incident_number": "240100002",
            "incident_category": "Assault",
            "incident_subcategory": "Aggravated Assault",
            "incident_description": "Assault with deadly weapon",
            "resolution": "Cite or Arrest Adult",
            "incident_date": "2024-01-16",
            "incident_time": "22:15",
            "report_datetime": "2024-01-16T23:00:00.000",
            "latitude": "37.7851",
            "longitude": "-122.4089",
            "intersection": "POWELL ST / GEARY ST",
            "police_district": "Central",
            "analysis_neighborhood": "Downtown/Civic Center",
        },
    ]


@pytest.fixture
def sample_datetime() -> datetime:
    """Sample datetime for testing."""
    return datetime(2024, 1, 18, 10, 0, 0, tzinfo=UTC)
