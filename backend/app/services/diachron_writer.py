# ============================================================================
# CHANGELOG (recent first, max 5 entries)
# 01/18/2026 - Initial implementation for Diachron dual-write (Claude)
# ============================================================================

"""
Writer service for persisting SFCrime data to Diachron's location_facts table.

This service handles the dual-write pattern: data is written to both SFCrime's
real-time tables (with 48hr retention) AND Diachron's historical tables
(permanent storage).

Architecture:
- Uses asyncpg directly (not SQLAlchemy) to match Diachron's async patterns
- Handles location deduplication via coordinates
- Maps SFCrime fact_kinds to Diachron's semantic schema
- Tracks import sessions for provenance
"""

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import AsyncGenerator
from uuid import UUID, uuid4

import asyncpg

from app.config import get_settings
from app.services.diachron_adapter import DiachronFact

logger = logging.getLogger(__name__)
settings = get_settings()


class DiachronWriter:
    """
    Writes SFCrime events to Diachron's location_facts table.

    Uses a separate database connection pool to Diachron's Neon instance.
    Designed for concurrent writes during ingestion.
    """

    def __init__(self, database_url: str | None = None):
        """
        Initialize the Diachron writer.

        Args:
            database_url: Diachron database URL. If None, uses settings.
        """
        self.database_url = database_url or settings.diachron_database_url
        self._pool: asyncpg.Pool | None = None
        self._fact_kinds_cache: dict[str, UUID] = {}

    async def connect(self) -> None:
        """Create connection pool to Diachron database."""
        if not self.database_url:
            raise ValueError("Diachron database URL not configured")

        # Convert SQLAlchemy URL to asyncpg format if needed
        db_url = self.database_url
        if db_url.startswith("postgresql+asyncpg://"):
            db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

        self._pool = await asyncpg.create_pool(
            db_url,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
        logger.info("Connected to Diachron database")

        # Preload fact_kinds cache
        await self._load_fact_kinds()

    async def disconnect(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("Disconnected from Diachron database")

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Get a connection from the pool."""
        if not self._pool:
            await self.connect()

        async with self._pool.acquire() as conn:  # type: ignore[union-attr]
            yield conn

    async def _load_fact_kinds(self) -> None:
        """Load fact_kinds into cache for efficient lookups."""
        async with self.connection() as conn:
            rows = await conn.fetch("SELECT id, code FROM fact_kinds")
            self._fact_kinds_cache = {row["code"]: row["id"] for row in rows}
            logger.info(f"Loaded {len(self._fact_kinds_cache)} fact_kinds")

    async def _get_fact_kind_id(self, code: str) -> UUID | None:
        """Get fact_kind UUID by code."""
        if not self._fact_kinds_cache:
            await self._load_fact_kinds()
        return self._fact_kinds_cache.get(code)

    async def _find_or_create_location(
        self,
        conn: asyncpg.Connection,
        lat: float,
        lng: float,
        address: str | None = None,
        neighborhood_slug: str | None = None,
    ) -> UUID:
        """
        Find existing location by coordinates or create new one.

        Uses ST_DWithin with 10m threshold for deduplication.
        """
        # Try to find existing location within 10 meters
        row = await conn.fetchrow(
            """
            SELECT id FROM locations
            WHERE ST_DWithin(
                coordinates::geography,
                ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography,
                10  -- 10 meters threshold
            )
            LIMIT 1
            """,
            lng,
            lat,
        )

        if row:
            return row["id"]

        # Look up neighborhood_id if slug provided
        neighborhood_id = None
        if neighborhood_slug:
            nbhd_row = await conn.fetchrow(
                "SELECT id FROM neighborhoods WHERE slug = $1",
                neighborhood_slug,
            )
            if nbhd_row:
                neighborhood_id = nbhd_row["id"]

        # Create new location
        location_id = uuid4()
        await conn.execute(
            """
            INSERT INTO locations (id, coordinates, address, neighborhood_id)
            VALUES ($1, ST_SetSRID(ST_MakePoint($2, $3), 4326), $4, $5)
            """,
            location_id,
            lng,
            lat,
            address,
            neighborhood_id,
        )

        return location_id

    async def write_fact(self, fact: DiachronFact) -> UUID | None:
        """
        Write a single fact to Diachron's location_facts table.

        Returns:
            UUID of the inserted fact, or None if fact_kind is unknown.
        """
        kind_id = await self._get_fact_kind_id(fact.kind_code)
        if not kind_id:
            logger.warning(f"Unknown fact_kind: {fact.kind_code}")
            return None

        async with self.connection() as conn:
            # Find or create location
            location_id = await self._find_or_create_location(
                conn,
                lat=fact.coordinates_lat,
                lng=fact.coordinates_lng,
                address=fact.address,
                neighborhood_slug=fact.neighborhood_slug,
            )

            # Check for existing fact by external_id to avoid duplicates
            if fact.external_id:
                existing = await conn.fetchrow(
                    """
                    SELECT id FROM location_facts
                    WHERE external_id = $1 AND kind_id = $2
                    """,
                    fact.external_id,
                    kind_id,
                )
                if existing:
                    # Update existing fact if needed
                    await self._update_fact(conn, existing["id"], fact, kind_id)
                    return existing["id"]

            # Insert new fact
            fact_id = fact.id
            daterange = fact.to_daterange_sql()

            await conn.execute(
                """
                INSERT INTO location_facts (
                    id, location_id, kind_id, title, description,
                    valid_during, time_granularity, time_certainty, date_display,
                    categories, tags, significance, sources, source_dataset,
                    external_id, created_at
                ) VALUES (
                    $1, $2, $3, $4, $5,
                    $6::daterange, $7::time_granularity, $8::time_certainty, $9,
                    $10, $11, $12::significance_level, $13, $14,
                    $15, $16
                )
                """,
                fact_id,
                location_id,
                kind_id,
                fact.title,
                fact.description,
                daterange,
                fact.time_granularity,
                fact.time_certainty,
                fact.date_display,
                fact.categories,
                fact.tags,
                fact.significance,
                str(fact.sources),  # JSONB stored as text
                fact.source_dataset,
                fact.external_id,
                datetime.now(UTC),
            )

            return fact_id

    async def _update_fact(
        self,
        conn: asyncpg.Connection,
        fact_id: UUID,
        fact: DiachronFact,
        kind_id: UUID,
    ) -> None:
        """Update an existing fact with new data."""
        daterange = fact.to_daterange_sql()

        await conn.execute(
            """
            UPDATE location_facts SET
                title = $2,
                description = $3,
                valid_during = $4::daterange,
                date_display = $5,
                categories = $6,
                tags = $7,
                sources = $8,
                updated_at = $9
            WHERE id = $1
            """,
            fact_id,
            fact.title,
            fact.description,
            daterange,
            fact.date_display,
            fact.categories,
            fact.tags,
            str(fact.sources),
            datetime.now(UTC),
        )

    async def write_facts_batch(
        self,
        facts: list[DiachronFact],
        source_name: str = "sfcrime_ingestion",
    ) -> tuple[int, int]:
        """
        Write multiple facts in a batch.

        Uses a single transaction for efficiency.

        Args:
            facts: List of DiachronFact instances
            source_name: Name for import session tracking

        Returns:
            Tuple of (inserted_count, updated_count)
        """
        if not facts:
            return 0, 0

        inserted = 0
        updated = 0

        async with self.connection() as conn:
            async with conn.transaction():
                for fact in facts:
                    kind_id = await self._get_fact_kind_id(fact.kind_code)
                    if not kind_id:
                        logger.warning(f"Skipping unknown fact_kind: {fact.kind_code}")
                        continue

                    # Find or create location
                    location_id = await self._find_or_create_location(
                        conn,
                        lat=fact.coordinates_lat,
                        lng=fact.coordinates_lng,
                        address=fact.address,
                        neighborhood_slug=fact.neighborhood_slug,
                    )

                    # Check for existing
                    existing = None
                    if fact.external_id:
                        existing = await conn.fetchrow(
                            """
                            SELECT id FROM location_facts
                            WHERE external_id = $1 AND kind_id = $2
                            """,
                            fact.external_id,
                            kind_id,
                        )

                    if existing:
                        await self._update_fact(conn, existing["id"], fact, kind_id)
                        updated += 1
                    else:
                        # Insert new
                        daterange = fact.to_daterange_sql()

                        await conn.execute(
                            """
                            INSERT INTO location_facts (
                                id, location_id, kind_id, title, description,
                                valid_during, time_granularity, time_certainty,
                                date_display, categories, tags, significance,
                                sources, source_dataset, external_id, created_at
                            ) VALUES (
                                $1, $2, $3, $4, $5,
                                $6::daterange, $7::time_granularity, $8::time_certainty,
                                $9, $10, $11, $12::significance_level,
                                $13, $14, $15, $16
                            )
                            """,
                            fact.id,
                            location_id,
                            kind_id,
                            fact.title,
                            fact.description,
                            daterange,
                            fact.time_granularity,
                            fact.time_certainty,
                            fact.date_display,
                            fact.categories,
                            fact.tags,
                            fact.significance,
                            str(fact.sources),
                            fact.source_dataset,
                            fact.external_id,
                            datetime.now(UTC),
                        )
                        inserted += 1

        logger.info(
            f"Diachron batch write complete: {inserted} inserted, {updated} updated"
        )
        return inserted, updated


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

_writer_instance: DiachronWriter | None = None


async def get_diachron_writer() -> DiachronWriter | None:
    """
    Get the global Diachron writer instance.

    Returns None if Diachron integration is disabled.
    """
    global _writer_instance

    if not settings.diachron_enabled:
        return None

    if _writer_instance is None:
        _writer_instance = DiachronWriter()
        await _writer_instance.connect()

    return _writer_instance


async def close_diachron_writer() -> None:
    """Close the global Diachron writer instance."""
    global _writer_instance

    if _writer_instance:
        await _writer_instance.disconnect()
        _writer_instance = None
