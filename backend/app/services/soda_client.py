"""SODA client for DataSF API with retry logic and app token support."""

import asyncio
import logging
from datetime import datetime
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class SODAClientError(Exception):
    """Base exception for SODA client errors."""

    pass


class SODAClient:
    """
    Client for DataSF Socrata Open Data API (SODA).

    Features:
    - App token support for higher rate limits (1000 req/hr vs 60 req/hr)
    - Exponential backoff retry (3 attempts)
    - Incremental sync support via $where clause
    """

    def __init__(
        self,
        base_url: str = settings.soda_base_url,
        app_token: str | None = settings.soda_app_token,
        max_retries: int = 3,
        timeout: float = 30.0,
    ):
        self.base_url = base_url
        self.app_token = app_token
        self.max_retries = max_retries
        self.timeout = timeout

        # Build headers
        self.headers: dict[str, str] = {
            "Accept": "application/json",
        }
        if app_token:
            self.headers["X-App-Token"] = app_token

    async def _request_with_retry(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Make HTTP request with exponential backoff retry."""
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url, headers=self.headers, params=params)
                    response.raise_for_status()
                    return response.json()

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 429:  # Rate limited
                    wait_time = 2**attempt * 10  # 10s, 20s, 40s
                    logger.warning(f"Rate limited, waiting {wait_time}s before retry")
                    await asyncio.sleep(wait_time)
                elif e.response.status_code >= 500:  # Server error
                    wait_time = 2**attempt
                    logger.warning(f"Server error {e.response.status_code}, retry in {wait_time}s")
                    await asyncio.sleep(wait_time)
                else:
                    raise SODAClientError(f"HTTP error: {e}") from e

            except httpx.RequestError as e:
                last_error = e
                wait_time = 2**attempt
                logger.warning(f"Request error: {e}, retry in {wait_time}s")
                await asyncio.sleep(wait_time)

        raise SODAClientError(f"Failed after {self.max_retries} retries: {last_error}")

    async def fetch_dispatch_calls(
        self,
        since: datetime | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Fetch dispatch calls from gnap-fj3t dataset.

        Args:
            since: Only fetch records updated after this timestamp (incremental sync)
            limit: Maximum number of records to fetch
            offset: Pagination offset

        Returns:
            List of dispatch call records
        """
        url = f"{self.base_url}/{settings.dispatch_calls_dataset_id}.json"

        params: dict[str, Any] = {
            "$limit": limit,
            "$offset": offset,
            "$order": "call_last_updated_at DESC",
        }

        # Add incremental sync filter
        if since:
            # SODA uses ISO 8601 format with 'T' separator
            since_str = since.strftime("%Y-%m-%dT%H:%M:%S")
            params["$where"] = f"call_last_updated_at > '{since_str}'"

        logger.info(f"Fetching dispatch calls: limit={limit}, since={since}")
        records = await self._request_with_retry(url, params)
        logger.info(f"Fetched {len(records)} dispatch call records")

        return records

    async def fetch_incident_reports(
        self,
        since: datetime | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Fetch incident reports from wg3w-h783 dataset.

        Args:
            since: Only fetch records after this date (for historical sync)
            limit: Maximum number of records to fetch
            offset: Pagination offset

        Returns:
            List of incident report records
        """
        url = f"{self.base_url}/{settings.incident_reports_dataset_id}.json"

        params: dict[str, Any] = {
            "$limit": limit,
            "$offset": offset,
            "$order": "report_datetime DESC",
        }

        # Add date filter for incremental sync
        if since:
            since_str = since.strftime("%Y-%m-%dT%H:%M:%S")
            params["$where"] = f"report_datetime > '{since_str}'"

        logger.info(f"Fetching incident reports: limit={limit}, since={since}")
        records = await self._request_with_retry(url, params)
        logger.info(f"Fetched {len(records)} incident report records")

        return records

    async def fetch_all_dispatch_calls(
        self,
        since: datetime | None = None,
        batch_size: int = 1000,
    ) -> list[dict[str, Any]]:
        """
        Fetch all dispatch calls with pagination.

        Args:
            since: Only fetch records updated after this timestamp
            batch_size: Number of records per request

        Returns:
            All matching dispatch call records
        """
        all_records: list[dict[str, Any]] = []
        offset = 0

        while True:
            batch = await self.fetch_dispatch_calls(
                since=since,
                limit=batch_size,
                offset=offset,
            )

            if not batch:
                break

            all_records.extend(batch)
            offset += batch_size

            # Safety limit to prevent runaway requests
            if offset >= 50000:
                logger.warning("Reached safety limit of 50000 records")
                break

        return all_records

    async def fetch_all_incident_reports(
        self,
        since: datetime | None = None,
        batch_size: int = 1000,
    ) -> list[dict[str, Any]]:
        """
        Fetch all incident reports with pagination.

        Args:
            since: Only fetch records after this date
            batch_size: Number of records per request

        Returns:
            All matching incident report records
        """
        all_records: list[dict[str, Any]] = []
        offset = 0

        while True:
            batch = await self.fetch_incident_reports(
                since=since,
                limit=batch_size,
                offset=offset,
            )

            if not batch:
                break

            all_records.extend(batch)
            offset += batch_size

            # Safety limit - keep reasonable for memory/timeout
            if offset >= 50000:
                logger.warning("Reached safety limit of 50000 records for incident reports")
                break

        return all_records

    async def fetch_incident_reports_range(
        self,
        start_date: datetime,
        end_date: datetime,
        batch_size: int = 1000,
    ) -> list[dict[str, Any]]:
        """
        Fetch incident reports within a specific date range.

        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            batch_size: Number of records per request

        Returns:
            All matching incident report records
        """
        all_records: list[dict[str, Any]] = []
        offset = 0

        # Format dates for SODA API
        start_str = start_date.strftime("%Y-%m-%dT%H:%M:%S")
        end_str = end_date.strftime("%Y-%m-%dT%H:%M:%S")

        while True:
            url = f"{self.base_url}/resource/{self.incidents_id}.json"
            params = {
                "$limit": batch_size,
                "$offset": offset,
                "$order": "report_datetime DESC",
                "$where": f"report_datetime >= '{start_str}' AND report_datetime <= '{end_str}'",
            }

            logger.info(f"Fetching incident reports range: {start_str} to {end_str}, offset={offset}")
            batch = await self._request_with_retry(url, params)

            if not batch:
                break

            all_records.extend(batch)
            offset += batch_size
            logger.info(f"Fetched {len(all_records)} records so far...")

            # Safety limit
            if offset >= 100000:
                logger.warning("Reached safety limit of 100000 records for range query")
                break

        logger.info(f"Range query complete: {len(all_records)} total records")
        return all_records
