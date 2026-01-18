# ============================================================================
# CHANGELOG (recent first, max 5 entries)
# 01/18/2026 - Added Diachron dual-write integration (Claude)
# ============================================================================

"""Ingestion service for syncing DataSF data to local database."""

import logging
from datetime import UTC, datetime, timedelta

from geoalchemy2 import WKTElement
from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import (
    DispatchCall,
    FireCall,
    IncidentReport,
    ServiceRequest,
    SyncCheckpoint,
    TrafficCrash,
)
from app.schemas.dispatch_call import Coordinates, DispatchCallOut
from app.services.diachron_adapter import (
    dispatch_call_dict_to_diachron,
    fire_call_dict_to_diachron,
    incident_report_dict_to_diachron,
    service_request_dict_to_diachron,
    traffic_crash_dict_to_diachron,
)
from app.services.diachron_writer import get_diachron_writer
from app.services.soda_client import SODAClient

logger = logging.getLogger(__name__)
settings = get_settings()


class IngestionService:
    """
    Service for ingesting data from DataSF into local database.

    Features:
    - Incremental sync using checkpoints
    - Upsert logic to handle updates
    - Automatic pruning of old dispatch calls (48hr retention)
    """

    def __init__(self, db: AsyncSession, soda_client: SODAClient | None = None):
        self.db = db
        self.soda_client = soda_client or SODAClient()

    def _parse_datetime(self, value: str | None) -> datetime | None:
        """Parse ISO 8601 datetime string."""
        if not value:
            return None
        try:
            # Handle various formats
            for fmt in [
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
            ]:
                try:
                    return datetime.strptime(value, fmt).replace(tzinfo=UTC)
                except ValueError:
                    continue
            return None
        except Exception:
            return None

    def _parse_point(self, record: dict) -> WKTElement | None:
        """Extract PostGIS point from record coordinates."""
        # Try intersection_point first (dispatch calls)
        point = record.get("intersection_point")
        if point and "coordinates" in point:
            coords = point["coordinates"]
            return WKTElement(f"POINT({coords[0]} {coords[1]})", srid=4326)

        # Try case_location (fire calls)
        case_location = record.get("case_location")
        if case_location and "coordinates" in case_location:
            coords = case_location["coordinates"]
            return WKTElement(f"POINT({coords[0]} {coords[1]})", srid=4326)

        # Try point_geom (311 service requests)
        point_geom = record.get("point_geom")
        if point_geom and "coordinates" in point_geom:
            coords = point_geom["coordinates"]
            return WKTElement(f"POINT({coords[0]} {coords[1]})", srid=4326)

        # Try direct lat/lng or lat/long (incident reports, 311, traffic crashes)
        lat = record.get("latitude") or record.get("lat") or record.get("tb_latitude")
        lng = record.get("longitude") or record.get("long") or record.get("tb_longitude")
        if lat and lng:
            try:
                return WKTElement(f"POINT({float(lng)} {float(lat)})", srid=4326)
            except (ValueError, TypeError):
                pass

        # Try point field
        point = record.get("point")
        if point and "coordinates" in point:
            coords = point["coordinates"]
            return WKTElement(f"POINT({coords[0]} {coords[1]})", srid=4326)

        return None

    async def get_checkpoint(self, source: str) -> datetime | None:
        """Get last sync checkpoint for a data source."""
        result = await self.db.execute(
            select(SyncCheckpoint).where(SyncCheckpoint.source == source)
        )
        checkpoint = result.scalar_one_or_none()
        return checkpoint.last_updated_at if checkpoint else None

    async def update_checkpoint(
        self, source: str, last_updated_at: datetime, record_count: int
    ) -> None:
        """Update sync checkpoint after successful ingestion."""
        stmt = insert(SyncCheckpoint).values(
            source=source,
            last_updated_at=last_updated_at,
            last_sync_at=func.now(),
            record_count=record_count,
        ).on_conflict_do_update(
            index_elements=["source"],
            set_={
                "last_updated_at": last_updated_at,
                "last_sync_at": func.now(),
                "record_count": record_count,
            },
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def sync_dispatch_calls(self) -> tuple[int, list[str]]:
        """
        Sync dispatch calls from DataSF.

        Returns:
            Tuple of (number of records upserted, list of upserted CAD numbers)
        """
        logger.info("Starting dispatch call sync")

        # Get last checkpoint
        checkpoint = await self.get_checkpoint("dispatch_calls")
        logger.info(f"Last dispatch checkpoint: {checkpoint}")

        # Fetch new records
        records = await self.soda_client.fetch_all_dispatch_calls(since=checkpoint)

        if not records:
            logger.info("No new dispatch call records")
            return 0, []

        # Transform and upsert
        upserted = 0
        upserted_cad_numbers: list[str] = []
        latest_updated = checkpoint

        for record in records:
            # Parse timestamps
            received_at = self._parse_datetime(record.get("received_datetime"))
            if not received_at:
                continue  # Skip records without received timestamp

            cad_number = record.get("cad_number")
            if not cad_number:
                continue

            last_updated = self._parse_datetime(record.get("call_last_updated_at"))
            if last_updated and (not latest_updated or last_updated > latest_updated):
                latest_updated = last_updated

            # Build upsert statement
            values = {
                "cad_number": cad_number,
                "call_type_code": record.get("call_type_original"),
                "call_type_description": record.get("call_type_original_desc"),
                "priority": record.get("priority_original"),
                "received_at": received_at,
                "dispatch_at": self._parse_datetime(record.get("dispatch_datetime")),
                "on_scene_at": self._parse_datetime(record.get("onscene_datetime")),
                "closed_at": self._parse_datetime(record.get("close_datetime")),
                "location": self._parse_point(record),
                "location_text": record.get("intersection_name"),
                "district": record.get("police_district"),
                "disposition": record.get("disposition"),
                "last_updated_at": last_updated,
            }

            stmt = insert(DispatchCall).values(**values).on_conflict_do_update(
                index_elements=["cad_number"],
                set_={k: v for k, v in values.items() if k != "cad_number"},
            )

            await self.db.execute(stmt)
            upserted += 1
            upserted_cad_numbers.append(cad_number)

        await self.db.commit()

        # Update checkpoint
        if latest_updated:
            # Get current record count
            count_result = await self.db.execute(select(func.count(DispatchCall.id)))
            count = count_result.scalar()
            await self.update_checkpoint("dispatch_calls", latest_updated, count or 0)

        logger.info(f"Synced {upserted} dispatch call records")

        # Dual-write to Diachron (if enabled)
        await self._write_to_diachron(records, kind="dispatch")

        return upserted, upserted_cad_numbers

    async def fetch_calls_by_cad_numbers(
        self, cad_numbers: list[str]
    ) -> list[DispatchCallOut]:
        """
        Fetch dispatch calls by CAD numbers as DispatchCallOut schemas.

        Used for WebSocket broadcasting after sync.
        """
        if not cad_numbers:
            return []

        # Use raw SQL for PostGIS coordinate extraction (Neon compatible)
        placeholders = ", ".join([f":cad_{i}" for i in range(len(cad_numbers))])
        sql = text(f"""
            SELECT
                id, cad_number, call_type_code, call_type_description, priority,
                received_at, dispatch_at, on_scene_at, closed_at,
                ST_Y(location::geometry) as lat,
                ST_X(location::geometry) as lng,
                location_text, district, disposition
            FROM dispatch_calls
            WHERE cad_number IN ({placeholders})
            ORDER BY received_at DESC
        """)

        params = {f"cad_{i}": cad for i, cad in enumerate(cad_numbers)}
        result = await self.db.execute(sql, params)
        rows = result.fetchall()

        calls = []
        for row in rows:
            coords = (
                Coordinates(latitude=float(row.lat), longitude=float(row.lng))
                if row.lat is not None and row.lng is not None
                else None
            )

            calls.append(
                DispatchCallOut(
                    id=row.id,
                    cad_number=row.cad_number,
                    call_type_code=row.call_type_code,
                    call_type_description=row.call_type_description,
                    priority=row.priority,
                    received_at=row.received_at,
                    dispatch_at=row.dispatch_at,
                    on_scene_at=row.on_scene_at,
                    closed_at=row.closed_at,
                    coordinates=coords,
                    location_text=row.location_text,
                    district=row.district,
                    disposition=row.disposition,
                )
            )

        return calls

    def _transform_incident_record(self, record: dict) -> dict | None:
        """Transform a raw incident record into database values."""
        incident_id = record.get("incident_id")
        if not incident_id:
            return None

        report_datetime = self._parse_datetime(record.get("report_datetime"))

        # Parse incident date/time
        incident_date = None
        if date_str := record.get("incident_date"):
            try:
                incident_date = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
            except ValueError:
                pass

        incident_time = None
        if time_str := record.get("incident_time"):
            try:
                incident_time = datetime.strptime(time_str, "%H:%M").time()
            except ValueError:
                pass

        return {
            "incident_id": incident_id,
            "incident_number": record.get("incident_number"),
            "incident_category": record.get("incident_category"),
            "incident_subcategory": record.get("incident_subcategory"),
            "incident_description": record.get("incident_description"),
            "resolution": record.get("resolution"),
            "incident_date": incident_date,
            "incident_time": incident_time,
            "report_datetime": report_datetime,
            "location": self._parse_point(record),
            "location_text": record.get("intersection"),
            "police_district": record.get("police_district"),
            "analysis_neighborhood": record.get("analysis_neighborhood"),
        }

    async def sync_incident_reports(self, initial_days_back: int = 3) -> int:
        """
        Sync incident reports from DataSF.

        Args:
            initial_days_back: Days to look back when no checkpoint exists (default 3)

        Returns:
            Number of records upserted
        """
        logger.info("Starting incident report sync")

        # Get last checkpoint
        checkpoint = await self.get_checkpoint("incident_reports")
        logger.info(f"Last incident checkpoint: {checkpoint}")

        # Fetch new records - use configurable initial window
        since = checkpoint
        if since is None:
            since = datetime.now(UTC) - timedelta(days=initial_days_back)
            logger.info(
                "No incident checkpoint found; seeding with last %d days (since=%s)",
                initial_days_back,
                since,
            )

        records = await self.soda_client.fetch_all_incident_reports(since=since)

        if not records:
            logger.info("No new incident report records")
            return 0

        logger.info(f"Processing {len(records)} incident records...")

        # Transform records
        transformed = []
        latest_updated = checkpoint
        for record in records:
            values = self._transform_incident_record(record)
            if values:
                transformed.append(values)
                report_datetime = values.get("report_datetime")
                if report_datetime and (not latest_updated or report_datetime > latest_updated):
                    latest_updated = report_datetime

        if not transformed:
            logger.info("No valid incident records to upsert")
            return 0

        # Batch upsert for performance (500 at a time)
        batch_size = 500
        upserted = 0

        for i in range(0, len(transformed), batch_size):
            batch = transformed[i:i + batch_size]

            for values in batch:
                stmt = insert(IncidentReport).values(**values).on_conflict_do_update(
                    index_elements=["incident_id"],
                    set_={k: v for k, v in values.items() if k != "incident_id"},
                )
                await self.db.execute(stmt)
                upserted += 1

            # Commit each batch to avoid long transactions
            await self.db.commit()
            logger.info(f"Upserted batch {i // batch_size + 1}: {upserted}/{len(transformed)} records")

        # Update checkpoint
        if latest_updated:
            count_result = await self.db.execute(select(func.count(IncidentReport.id)))
            count = count_result.scalar()
            await self.update_checkpoint("incident_reports", latest_updated, count or 0)

        logger.info(f"Synced {upserted} incident report records")

        # Dual-write to Diachron (if enabled)
        await self._write_to_diachron(records, kind="incident")

        return upserted

    def _transform_fire_call_record(self, record: dict) -> dict | None:
        """Transform a raw fire call record into database values."""
        incident_number = record.get("incident_number")
        if not incident_number:
            return None

        received_at = self._parse_datetime(record.get("received_dttm"))
        if not received_at:
            return None

        # Parse number of alarms
        num_alarms = None
        if alarms_str := record.get("number_of_alarms"):
            try:
                num_alarms = int(alarms_str)
            except ValueError:
                pass

        # Parse ALS unit boolean
        is_als = None
        als_value = record.get("als_unit")
        if als_value is not None:
            is_als = als_value in (True, "true", "True", "1", 1)

        return {
            "incident_number": incident_number,
            "call_type": record.get("call_type"),
            "call_type_group": record.get("call_type_group"),
            "priority": record.get("priority"),
            "number_of_alarms": num_alarms,
            "received_at": received_at,
            "dispatch_at": self._parse_datetime(record.get("dispatch_dttm")),
            "on_scene_at": self._parse_datetime(record.get("on_scene_dttm")),
            "transport_at": self._parse_datetime(record.get("transport_dttm")),
            "hospital_at": self._parse_datetime(record.get("hospital_dttm")),
            "available_at": self._parse_datetime(record.get("available_dttm")),
            "disposition": record.get("call_final_disposition"),
            "location": self._parse_point(record),
            "location_text": record.get("address"),
            "zipcode": record.get("zipcode_of_incident"),
            "neighborhood": record.get("neighborhoods_analysis_boundaries"),
            "supervisor_district": record.get("supervisor_district"),
            "battalion": record.get("battalion"),
            "station_area": record.get("station_area"),
            "unit_type": record.get("unit_type"),
            "is_als_unit": is_als,
            "last_updated_at": self._parse_datetime(record.get("data_as_of")),
        }

    async def sync_fire_calls(self, initial_days_back: int = 1) -> int:
        """
        Sync Fire Department calls from DataSF.

        Args:
            initial_days_back: Days to look back when no checkpoint exists (default 1)

        Returns:
            Number of records upserted
        """
        logger.info("Starting fire call sync")

        # Get last checkpoint
        checkpoint = await self.get_checkpoint("fire_calls")
        logger.info(f"Last fire call checkpoint: {checkpoint}")

        # Fetch new records
        since = checkpoint
        if since is None:
            since = datetime.now(UTC) - timedelta(days=initial_days_back)
            logger.info(
                "No fire call checkpoint found; seeding with last %d days (since=%s)",
                initial_days_back,
                since,
            )

        records = await self.soda_client.fetch_all_fire_calls(since=since)

        if not records:
            logger.info("No new fire call records")
            return 0

        logger.info(f"Processing {len(records)} fire call records...")

        # Deduplicate by incident_number (keep first/most recent)
        seen_incidents: set[str] = set()
        unique_records = []
        for record in records:
            incident_number = record.get("incident_number")
            if incident_number and incident_number not in seen_incidents:
                seen_incidents.add(incident_number)
                unique_records.append(record)

        logger.info(f"Deduplicated to {len(unique_records)} unique incidents")

        # Transform records
        transformed = []
        latest_updated = checkpoint
        for record in unique_records:
            values = self._transform_fire_call_record(record)
            if values:
                transformed.append(values)
                last_updated = values.get("last_updated_at") or values.get("received_at")
                if last_updated and (not latest_updated or last_updated > latest_updated):
                    latest_updated = last_updated

        if not transformed:
            logger.info("No valid fire call records to upsert")
            return 0

        # Batch upsert for performance (500 at a time)
        batch_size = 500
        upserted = 0

        for i in range(0, len(transformed), batch_size):
            batch = transformed[i:i + batch_size]

            for values in batch:
                stmt = insert(FireCall).values(**values).on_conflict_do_update(
                    index_elements=["incident_number"],
                    set_={k: v for k, v in values.items() if k != "incident_number"},
                )
                await self.db.execute(stmt)
                upserted += 1

            # Commit each batch to avoid long transactions
            await self.db.commit()
            logger.info(f"Upserted batch {i // batch_size + 1}: {upserted}/{len(transformed)} records")

        # Update checkpoint
        if latest_updated:
            count_result = await self.db.execute(select(func.count(FireCall.id)))
            count = count_result.scalar()
            await self.update_checkpoint("fire_calls", latest_updated, count or 0)

        logger.info(f"Synced {upserted} fire call records")

        # Dual-write to Diachron (if enabled)
        await self._write_to_diachron(unique_records, kind="fire")

        return upserted

    def _transform_service_request_record(self, record: dict) -> dict | None:
        """Transform a raw 311 service request record into database values."""
        service_request_id = record.get("service_request_id")
        if not service_request_id:
            return None

        requested_at = self._parse_datetime(record.get("requested_datetime"))
        if not requested_at:
            return None

        # Extract media URL if present
        media_url = None
        media_data = record.get("media_url")
        if isinstance(media_data, dict):
            media_url = media_data.get("url")
        elif isinstance(media_data, str):
            media_url = media_data

        # Parse supervisor district (comes as "9.00000" format)
        supervisor_district = None
        if dist := record.get("supervisor_district"):
            try:
                supervisor_district = str(int(float(dist)))
            except (ValueError, TypeError):
                supervisor_district = str(dist)

        return {
            "service_request_id": service_request_id,
            "service_name": record.get("service_name"),
            "service_subtype": record.get("service_subtype"),
            "service_details": record.get("service_details"),
            "status_description": record.get("status_description"),
            "status_notes": record.get("status_notes"),
            "agency_responsible": record.get("agency_responsible"),
            "source": record.get("source"),
            "requested_at": requested_at,
            "closed_at": self._parse_datetime(record.get("closed_date")),
            "updated_at": self._parse_datetime(record.get("updated_datetime")),
            "location": self._parse_point(record),
            "address": record.get("address"),
            "street": record.get("street"),
            "neighborhood": record.get("analysis_neighborhood"),
            "supervisor_district": supervisor_district,
            "police_district": record.get("police_district"),
            "media_url": media_url,
            "last_updated_at": self._parse_datetime(record.get("data_as_of")),
        }

    async def sync_service_requests(self, initial_days_back: int = 1) -> int:
        """
        Sync 311 Service Requests from DataSF.

        Args:
            initial_days_back: Days to look back when no checkpoint exists (default 1)

        Returns:
            Number of records upserted
        """
        logger.info("Starting 311 service request sync")

        # Get last checkpoint
        checkpoint = await self.get_checkpoint("service_requests")
        logger.info(f"Last 311 checkpoint: {checkpoint}")

        # Fetch new records
        since = checkpoint
        if since is None:
            since = datetime.now(UTC) - timedelta(days=initial_days_back)
            logger.info(
                "No 311 checkpoint found; seeding with last %d days (since=%s)",
                initial_days_back,
                since,
            )

        records = await self.soda_client.fetch_all_service_requests(since=since)

        if not records:
            logger.info("No new 311 service request records")
            return 0

        logger.info(f"Processing {len(records)} 311 service request records...")

        # Transform records
        transformed = []
        latest_updated = checkpoint
        for record in records:
            values = self._transform_service_request_record(record)
            if values:
                transformed.append(values)
                last_updated = values.get("last_updated_at") or values.get("requested_at")
                if last_updated and (not latest_updated or last_updated > latest_updated):
                    latest_updated = last_updated

        if not transformed:
            logger.info("No valid 311 records to upsert")
            return 0

        # Batch upsert for performance (500 at a time)
        batch_size = 500
        upserted = 0

        for i in range(0, len(transformed), batch_size):
            batch = transformed[i:i + batch_size]

            for values in batch:
                stmt = insert(ServiceRequest).values(**values).on_conflict_do_update(
                    index_elements=["service_request_id"],
                    set_={k: v for k, v in values.items() if k != "service_request_id"},
                )
                await self.db.execute(stmt)
                upserted += 1

            # Commit each batch to avoid long transactions
            await self.db.commit()
            logger.info(f"Upserted batch {i // batch_size + 1}: {upserted}/{len(transformed)} records")

        # Update checkpoint
        if latest_updated:
            count_result = await self.db.execute(select(func.count(ServiceRequest.id)))
            count = count_result.scalar()
            await self.update_checkpoint("service_requests", latest_updated, count or 0)

        logger.info(f"Synced {upserted} 311 service request records")

        # Dual-write to Diachron (if enabled)
        await self._write_to_diachron(records, kind="311")

        return upserted

    def _transform_traffic_crash_record(self, record: dict) -> dict | None:
        """Transform a raw traffic crash record into database values."""
        unique_id = record.get("unique_id")
        if not unique_id:
            return None

        collision_datetime = self._parse_datetime(record.get("collision_datetime"))
        if not collision_datetime:
            return None

        # Parse integer fields
        number_killed = None
        if killed := record.get("number_killed"):
            try:
                number_killed = int(killed)
            except (ValueError, TypeError):
                pass

        number_injured = None
        if injured := record.get("number_injured"):
            try:
                number_injured = int(injured)
            except (ValueError, TypeError):
                pass

        distance = None
        if dist := record.get("distance"):
            try:
                distance = int(dist)
            except (ValueError, TypeError):
                pass

        # Parse supervisor district
        supervisor_district = None
        if dist := record.get("supervisor_district"):
            try:
                supervisor_district = str(int(float(dist)))
            except (ValueError, TypeError):
                supervisor_district = str(dist)

        return {
            "unique_id": unique_id,
            "case_id": record.get("case_id_pkey"),
            "collision_datetime": collision_datetime,
            "collision_severity": record.get("collision_severity"),
            "type_of_collision": record.get("type_of_collision"),
            "number_killed": number_killed,
            "number_injured": number_injured,
            "location": self._parse_point(record),
            "primary_road": record.get("primary_rd"),
            "secondary_road": record.get("secondary_rd"),
            "distance": distance,
            "direction": record.get("direction"),
            "weather": record.get("weather_1"),
            "road_surface": record.get("road_surface"),
            "road_condition": record.get("road_cond_1"),
            "lighting": record.get("lighting"),
            "party1_type": record.get("party1_type"),
            "party2_type": record.get("party2_type"),
            "pedestrian_action": record.get("ped_action"),
            "neighborhood": record.get("analysis_neighborhood"),
            "supervisor_district": supervisor_district,
            "police_district": record.get("police_district"),
            "reporting_district": record.get("reporting_district"),
            "beat_number": record.get("beat_number"),
            "last_updated_at": self._parse_datetime(record.get("data_as_of")),
        }

    async def sync_traffic_crashes(self, initial_days_back: int = 7) -> int:
        """
        Sync Traffic Crashes from DataSF.

        Args:
            initial_days_back: Days to look back when no checkpoint exists (default 7)

        Returns:
            Number of records upserted
        """
        logger.info("Starting traffic crash sync")

        # Get last checkpoint
        checkpoint = await self.get_checkpoint("traffic_crashes")
        logger.info(f"Last traffic crash checkpoint: {checkpoint}")

        # Fetch new records
        since = checkpoint
        if since is None:
            since = datetime.now(UTC) - timedelta(days=initial_days_back)
            logger.info(
                "No traffic crash checkpoint found; seeding with last %d days (since=%s)",
                initial_days_back,
                since,
            )

        records = await self.soda_client.fetch_all_traffic_crashes(since=since)

        if not records:
            logger.info("No new traffic crash records")
            return 0

        logger.info(f"Processing {len(records)} traffic crash records...")

        # Transform records
        transformed = []
        latest_updated = checkpoint
        for record in records:
            values = self._transform_traffic_crash_record(record)
            if values:
                transformed.append(values)
                last_updated = values.get("last_updated_at") or values.get("collision_datetime")
                if last_updated and (not latest_updated or last_updated > latest_updated):
                    latest_updated = last_updated

        if not transformed:
            logger.info("No valid traffic crash records to upsert")
            return 0

        # Batch upsert for performance (500 at a time)
        batch_size = 500
        upserted = 0

        for i in range(0, len(transformed), batch_size):
            batch = transformed[i:i + batch_size]

            for values in batch:
                stmt = insert(TrafficCrash).values(**values).on_conflict_do_update(
                    index_elements=["unique_id"],
                    set_={k: v for k, v in values.items() if k != "unique_id"},
                )
                await self.db.execute(stmt)
                upserted += 1

            # Commit each batch to avoid long transactions
            await self.db.commit()
            logger.info(f"Upserted batch {i // batch_size + 1}: {upserted}/{len(transformed)} records")

        # Update checkpoint
        if latest_updated:
            count_result = await self.db.execute(select(func.count(TrafficCrash.id)))
            count = count_result.scalar()
            await self.update_checkpoint("traffic_crashes", latest_updated, count or 0)

        logger.info(f"Synced {upserted} traffic crash records")

        # Dual-write to Diachron (if enabled)
        await self._write_to_diachron(records, kind="traffic")

        return upserted

    async def prune_old_dispatch_calls(self) -> int:
        """
        Remove dispatch calls older than retention period (48 hours).

        Returns:
            Number of records deleted
        """
        cutoff = datetime.now(UTC) - timedelta(hours=settings.dispatch_retention_hours)

        result = await self.db.execute(
            delete(DispatchCall).where(DispatchCall.received_at < cutoff)
        )
        await self.db.commit()

        deleted = result.rowcount
        if deleted:
            logger.info(f"Pruned {deleted} old dispatch calls")

        return deleted

    async def _write_to_diachron(
        self,
        records: list[dict],
        kind: str,
    ) -> tuple[int, int]:
        """
        Write records to Diachron's location_facts table (dual-write pattern).

        This enables permanent historical storage while SFCrime maintains
        its 48hr retention for real-time operations.

        Args:
            records: Raw DataSF records
            kind: Record type ('dispatch' or 'incident')

        Returns:
            Tuple of (inserted_count, updated_count)
        """
        writer = await get_diachron_writer()
        if not writer:
            # Diachron integration disabled
            return 0, 0

        # Convert records to Diachron facts
        facts = []
        for record in records:
            if kind == "dispatch":
                fact = dispatch_call_dict_to_diachron(record)
            elif kind == "incident":
                fact = incident_report_dict_to_diachron(record)
            elif kind == "fire":
                fact = fire_call_dict_to_diachron(record)
            elif kind == "311":
                fact = service_request_dict_to_diachron(record)
            elif kind == "traffic":
                fact = traffic_crash_dict_to_diachron(record)
            else:
                logger.warning(f"Unknown record kind: {kind}")
                continue

            if fact:
                facts.append(fact)

        if not facts:
            return 0, 0

        try:
            inserted, updated = await writer.write_facts_batch(
                facts,
                source_name=f"sfcrime_{kind}_ingestion",
            )
            logger.info(
                f"Diachron dual-write ({kind}): {inserted} inserted, {updated} updated"
            )
            return inserted, updated
        except Exception as e:
            logger.error(f"Diachron dual-write failed: {e}")
            # Don't fail the main ingestion if Diachron write fails
            return 0, 0

    async def sync_incident_reports_range(
        self, start_date: datetime, end_date: datetime
    ) -> int:
        """
        Sync incident reports for a specific date range (chunked backfill).

        Does NOT update checkpoint - use for one-time historical imports.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            Number of records upserted
        """
        logger.info(f"Starting chunked incident sync: {start_date} to {end_date}")

        # Fetch records in date range
        records = await self.soda_client.fetch_incident_reports_range(
            start_date=start_date,
            end_date=end_date,
        )

        if not records:
            logger.info("No incident records in date range")
            return 0

        logger.info(f"Processing {len(records)} incident records...")

        # Transform records
        transformed = []
        for record in records:
            values = self._transform_incident_record(record)
            if values:
                transformed.append(values)

        if not transformed:
            logger.info("No valid incident records to upsert")
            return 0

        # Batch upsert for performance (500 at a time)
        batch_size = 500
        upserted = 0

        for i in range(0, len(transformed), batch_size):
            batch = transformed[i:i + batch_size]

            for values in batch:
                stmt = insert(IncidentReport).values(**values).on_conflict_do_update(
                    index_elements=["incident_id"],
                    set_={k: v for k, v in values.items() if k != "incident_id"},
                )
                await self.db.execute(stmt)
                upserted += 1

            await self.db.commit()
            logger.info(f"Upserted batch {i // batch_size + 1}: {upserted}/{len(transformed)} records")

        logger.info(f"Chunked sync complete: {upserted} incident records")
        return upserted
