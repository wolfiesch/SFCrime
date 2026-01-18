"""Database setup with SQLAlchemy async and PostGIS support."""

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables and extensions."""
    async with engine.begin() as conn:
        # Enable PostGIS extension
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        except Exception:
            pass  # May already exist

        # Create tables
        await conn.run_sync(Base.metadata.create_all)


async def check_db_ready() -> None:
    """
    Verify database connectivity and expected schema.

    Checks that PostGIS is enabled and required tables exist.
    """
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))

        # PostGIS is required for spatial queries.
        postgis = await conn.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'postgis' LIMIT 1")
        )
        if postgis.first() is None:
            raise RuntimeError("PostGIS extension is not installed.")

        # Tables should exist.
        tables = await conn.execute(
            text(
                "SELECT "
                "to_regclass('public.dispatch_calls') AS dispatch_calls, "
                "to_regclass('public.incident_reports') AS incident_reports, "
                "to_regclass('public.sync_checkpoints') AS sync_checkpoints"
            )
        )
        row = tables.first()
        if row is None or any(value is None for value in row):
            missing = []
            if row is None or row.dispatch_calls is None:
                missing.append("dispatch_calls")
            if row is None or row.incident_reports is None:
                missing.append("incident_reports")
            if row is None or row.sync_checkpoints is None:
                missing.append("sync_checkpoints")

            raise RuntimeError(
                f"Database schema is missing tables: {', '.join(missing)} "
                "(run database init or check migrations)."
            )
