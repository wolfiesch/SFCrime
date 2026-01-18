"""Tests for SODA client."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.soda_client import SODAClient, SODAClientError


class TestSODAClient:
    """Tests for SODAClient."""

    def test_init_with_token(self):
        """Test client initialization with app token."""
        client = SODAClient(app_token="test_token")
        assert client.app_token == "test_token"
        assert "X-App-Token" in client.headers
        assert client.headers["X-App-Token"] == "test_token"

    def test_init_without_token(self):
        """Test client initialization without app token."""
        client = SODAClient(app_token=None)
        assert client.app_token is None
        assert "X-App-Token" not in client.headers

    @pytest.mark.asyncio
    async def test_fetch_dispatch_calls_success(self, sample_dispatch_records):
        """Test successful dispatch call fetch."""
        client = SODAClient(app_token="test")
        client._request_with_retry = AsyncMock(return_value=sample_dispatch_records)

        records = await client.fetch_dispatch_calls(limit=100)

        assert len(records) == 3
        assert records[0]["cad_number"] == "240180001"
        client._request_with_retry.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_dispatch_calls_with_since(self, sample_dispatch_records):
        """Test dispatch call fetch with incremental sync."""
        client = SODAClient(app_token="test")
        client._request_with_retry = AsyncMock(return_value=sample_dispatch_records)

        since = datetime(2024, 1, 18, 10, 0, 0, tzinfo=UTC)
        await client.fetch_dispatch_calls(since=since)

        # Verify $where clause was included
        call_args = client._request_with_retry.call_args
        params = call_args[1]["params"] if "params" in call_args[1] else call_args[0][1]
        assert "$where" in params
        assert "call_last_updated_at" in params["$where"]

    @pytest.mark.asyncio
    async def test_fetch_incident_reports_success(self, sample_incident_records):
        """Test successful incident report fetch."""
        client = SODAClient(app_token="test")
        client._request_with_retry = AsyncMock(return_value=sample_incident_records)

        records = await client.fetch_incident_reports(limit=100)

        assert len(records) == 2
        assert records[0]["incident_id"] == "1000001"

    @pytest.mark.asyncio
    async def test_fetch_all_dispatch_calls_pagination(self, sample_dispatch_records):
        """Test paginated fetch with multiple batches."""
        client = SODAClient(app_token="test")

        # First call returns records, second call returns empty (end of data)
        client._request_with_retry = AsyncMock(
            side_effect=[sample_dispatch_records, []]
        )

        records = await client.fetch_all_dispatch_calls(batch_size=10)

        assert len(records) == 3
        assert client._request_with_retry.call_count == 2

    @pytest.mark.asyncio
    async def test_fetch_all_dispatch_calls_safety_limit(self):
        """Test safety limit prevents runaway requests."""
        client = SODAClient(app_token="test")

        # Always return data to trigger safety limit
        client._request_with_retry = AsyncMock(
            return_value=[{"cad_number": f"CAD{i}"} for i in range(1000)]
        )

        records = await client.fetch_all_dispatch_calls(batch_size=1000)

        # Should stop at 50000 records (50 batches)
        assert client._request_with_retry.call_count == 50

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(self):
        """Test exponential backoff on rate limit."""
        client = SODAClient(app_token="test", max_retries=2)

        # Create a proper HTTPStatusError
        mock_response = httpx.Response(429, request=httpx.Request("GET", "http://test"))

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.side_effect = httpx.HTTPStatusError(
                "Rate limited", request=mock_response.request, response=mock_response
            )

            with pytest.raises(SODAClientError) as exc_info:
                await client._request_with_retry("http://test/resource")

            assert "Failed after" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_retry_on_server_error(self):
        """Test retry on 500 server errors."""
        client = SODAClient(app_token="test", max_retries=2)

        mock_response = httpx.Response(500, request=httpx.Request("GET", "http://test"))

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.side_effect = httpx.HTTPStatusError(
                "Server error", request=mock_response.request, response=mock_response
            )

            with pytest.raises(SODAClientError):
                await client._request_with_retry("http://test/resource")

    @pytest.mark.asyncio
    async def test_no_retry_on_client_error(self):
        """Test no retry on 4xx client errors (except 429)."""
        client = SODAClient(app_token="test", max_retries=3)

        mock_response = httpx.Response(
            400,
            request=httpx.Request("GET", "http://test"),
            content=b"Bad request",
        )

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.side_effect = httpx.HTTPStatusError(
                "Bad request", request=mock_response.request, response=mock_response
            )

            with pytest.raises(SODAClientError):
                await client._request_with_retry("http://test/resource")

            # Should only try once for client errors
            assert mock_get.call_count == 1
