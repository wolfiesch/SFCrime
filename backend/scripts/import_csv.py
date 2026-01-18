#!/usr/bin/env python3
"""
Direct CSV import script for SFCrime incident reports.

Uses asyncpg copy_records_to_table for fast bulk imports to Neon PostgreSQL.
"""

import asyncio
import csv
import os
import sys
from datetime import datetime, time, timezone
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "").replace("+asyncpg", "").replace("postgresql://", "postgres://")

BATCH_SIZE = 10000
REPORT_INTERVAL = 50000


def log(msg):
    """Print with flush for immediate output."""
    print(msg, flush=True)


def parse_datetime(value: str | None) -> datetime | None:
    """Parse datetime string from CSV (returns timezone-aware UTC)."""
    if not value:
        return None
    try:
        for fmt in [
            "%Y/%m/%d %I:%M:%S %p",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
        ]:
            try:
                dt = datetime.strptime(value, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None
    except Exception:
        return None


def parse_date(value: str | None):
    """Parse date string from CSV."""
    if not value:
        return None
    try:
        for fmt in ["%Y/%m/%d", "%Y-%m-%d"]:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        return None
    except Exception:
        return None


def parse_time(value: str | None):
    """Parse time string from CSV to datetime.time."""
    if not value:
        return None
    try:
        parts = value.split(":")
        if len(parts) >= 2:
            hour = int(parts[0])
            minute = int(parts[1])
            second = int(parts[2]) if len(parts) > 2 else 0
            return time(hour, minute, second)
        return None
    except (ValueError, IndexError):
        return None


def parse_float(value: str | None) -> float | None:
    """Parse float from CSV."""
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def transform_row(row: dict) -> dict | None:
    """Transform a CSV row into database dict (for direct insert)."""
    incident_id = row.get("Incident ID")
    if not incident_id:
        return None

    lat = parse_float(row.get("Latitude"))
    lng = parse_float(row.get("Longitude"))

    return {
        "incident_id": incident_id,
        "incident_number": row.get("Incident Number") or None,
        "incident_category": row.get("Incident Category") or None,
        "incident_subcategory": row.get("Incident Subcategory") or None,
        "incident_description": row.get("Incident Description") or None,
        "resolution": row.get("Resolution") or None,
        "incident_date": parse_date(row.get("Incident Date")),
        "incident_time": parse_time(row.get("Incident Time")),
        "report_datetime": parse_datetime(row.get("Report Datetime")),
        "latitude": lat,
        "longitude": lng,
        "location_text": row.get("Intersection") or None,
        "police_district": row.get("Police District") or None,
        "analysis_neighborhood": row.get("Analysis Neighborhood") or None,
    }


async def import_csv(csv_path: str):
    """Import CSV directly to Neon PostgreSQL using batch inserts."""
    log("Connecting to database...")
    conn = await asyncpg.connect(DATABASE_URL)

    log(f"Reading CSV: {csv_path}")

    # Count total rows
    with open(csv_path, "r", encoding="utf-8") as f:
        total_rows = sum(1 for _ in f) - 1
    log(f"Total rows to import: {total_rows:,}")

    # Get initial count
    initial_count = await conn.fetchval("SELECT COUNT(*) FROM incident_reports")
    log(f"Current records in DB: {initial_count:,}")

    imported = 0
    skipped = 0
    batch = []

    # Prepare the upsert statement
    upsert_sql = """
        INSERT INTO incident_reports (
            incident_id, incident_number, incident_category, incident_subcategory,
            incident_description, resolution, incident_date, incident_time,
            report_datetime, location, location_text, police_district, analysis_neighborhood
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9,
            CASE WHEN $10::double precision IS NOT NULL AND $11::double precision IS NOT NULL
                 THEN ST_SetSRID(ST_MakePoint($11, $10), 4326)
                 ELSE NULL END,
            $12, $13, $14
        )
        ON CONFLICT (incident_id) DO UPDATE SET
            incident_number = EXCLUDED.incident_number,
            incident_category = EXCLUDED.incident_category,
            incident_subcategory = EXCLUDED.incident_subcategory,
            incident_description = EXCLUDED.incident_description,
            resolution = EXCLUDED.resolution,
            incident_date = EXCLUDED.incident_date,
            incident_time = EXCLUDED.incident_time,
            report_datetime = EXCLUDED.report_datetime,
            location = EXCLUDED.location,
            location_text = EXCLUDED.location_text,
            police_district = EXCLUDED.police_district,
            analysis_neighborhood = EXCLUDED.analysis_neighborhood
    """

    log("Starting import...")
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            transformed = transform_row(row)
            if not transformed:
                skipped += 1
                continue

            # Convert dict to tuple for executemany
            batch.append((
                transformed["incident_id"],
                transformed["incident_number"],
                transformed["incident_category"],
                transformed["incident_subcategory"],
                transformed["incident_description"],
                transformed["resolution"],
                transformed["incident_date"],
                transformed["incident_time"],
                transformed["report_datetime"],
                transformed["latitude"],
                transformed["longitude"],
                transformed["location_text"],
                transformed["police_district"],
                transformed["analysis_neighborhood"],
            ))

            if len(batch) >= BATCH_SIZE:
                await conn.executemany(upsert_sql, batch)
                imported += len(batch)
                batch = []

                if imported % REPORT_INTERVAL == 0:
                    pct = (imported / total_rows) * 100
                    log(f"Progress: {imported:,} / {total_rows:,} ({pct:.1f}%)")

        # Final batch
        if batch:
            await conn.executemany(upsert_sql, batch)
            imported += len(batch)

    log(f"\nImport complete!")
    log(f"  Processed: {imported:,}")
    log(f"  Skipped (no ID): {skipped:,}")

    # Get final count
    final_count = await conn.fetchval("SELECT COUNT(*) FROM incident_reports")
    log(f"  Total in DB: {final_count:,}")
    log(f"  Net new records: {final_count - initial_count:,}")

    await conn.close()


if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/sfcrime_incidents.csv"

    if not Path(csv_path).exists():
        log(f"Error: CSV file not found: {csv_path}")
        log("Download it first: curl -o /tmp/sfcrime_incidents.csv 'https://data.sfgov.org/api/views/wg3w-h783/rows.csv?accessType=DOWNLOAD'")
        sys.exit(1)

    asyncio.run(import_csv(csv_path))
