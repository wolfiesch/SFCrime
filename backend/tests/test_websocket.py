"""Tests for WebSocket connection manager."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.dispatch_call import Coordinates, DispatchCallOut
from app.websocket.manager import ClientSubscription, ConnectionManager
from app.websocket.schemas import Viewport


@pytest.fixture
def sample_call() -> DispatchCallOut:
    """Create sample dispatch call for testing."""
    return DispatchCallOut(
        id=1,
        cad_number="240180001",
        call_type_code="459",
        call_type_description="BURGLARY",
        priority="A",
        received_at=datetime(2024, 1, 18, 10, 30, 0, tzinfo=UTC),
        dispatch_at=datetime(2024, 1, 18, 10, 32, 0, tzinfo=UTC),
        on_scene_at=None,
        closed_at=None,
        coordinates=Coordinates(latitude=37.7749, longitude=-122.4194),
        location_text="MARKET ST / 5TH ST",
        district="SOUTHERN",
        disposition=None,
    )


@pytest.fixture
def sample_call_no_coords() -> DispatchCallOut:
    """Create sample dispatch call without coordinates."""
    return DispatchCallOut(
        id=2,
        cad_number="240180002",
        call_type_code="594",
        call_type_description="VANDALISM",
        priority="B",
        received_at=datetime(2024, 1, 18, 11, 0, 0, tzinfo=UTC),
        dispatch_at=None,
        on_scene_at=None,
        closed_at=None,
        coordinates=None,
        location_text="UNKNOWN",
        district="CENTRAL",
        disposition=None,
    )


class TestClientSubscription:
    """Tests for ClientSubscription."""

    def test_matches_no_filters(self, sample_call):
        """Test that call matches subscription with no filters."""
        sub = ClientSubscription(websocket=MagicMock())

        assert sub.matches(sample_call) is True

    def test_matches_priority_filter_pass(self, sample_call):
        """Test priority filter when call matches."""
        sub = ClientSubscription(websocket=MagicMock(), priorities={"A", "B"})

        assert sub.matches(sample_call) is True  # priority is "A"

    def test_matches_priority_filter_fail(self, sample_call):
        """Test priority filter when call doesn't match."""
        sub = ClientSubscription(websocket=MagicMock(), priorities={"C"})

        assert sub.matches(sample_call) is False  # priority is "A"

    def test_matches_viewport_filter_pass(self, sample_call):
        """Test viewport filter when call is within bounds."""
        viewport = Viewport(
            min_lat=37.0,
            max_lat=38.0,
            min_lng=-123.0,
            max_lng=-122.0,
        )
        sub = ClientSubscription(websocket=MagicMock(), viewport=viewport)

        assert sub.matches(sample_call) is True

    def test_matches_viewport_filter_fail(self, sample_call):
        """Test viewport filter when call is outside bounds."""
        viewport = Viewport(
            min_lat=38.0,  # Call is at 37.7749, outside this viewport
            max_lat=39.0,
            min_lng=-123.0,
            max_lng=-122.0,
        )
        sub = ClientSubscription(websocket=MagicMock(), viewport=viewport)

        assert sub.matches(sample_call) is False

    def test_matches_no_coords_with_viewport(self, sample_call_no_coords):
        """Test that calls without coords pass viewport filter."""
        viewport = Viewport(
            min_lat=37.0,
            max_lat=38.0,
            min_lng=-123.0,
            max_lng=-122.0,
        )
        sub = ClientSubscription(websocket=MagicMock(), viewport=viewport)

        # Calls without coordinates should still match (no viewport to check)
        assert sub.matches(sample_call_no_coords) is True

    def test_matches_combined_filters(self, sample_call):
        """Test combined priority and viewport filters."""
        viewport = Viewport(
            min_lat=37.0,
            max_lat=38.0,
            min_lng=-123.0,
            max_lng=-122.0,
        )
        sub = ClientSubscription(
            websocket=MagicMock(),
            viewport=viewport,
            priorities={"A"},
        )

        assert sub.matches(sample_call) is True

        # Fail on priority
        sub.priorities = {"C"}
        assert sub.matches(sample_call) is False


class TestConnectionManager:
    """Tests for ConnectionManager."""

    @pytest.mark.asyncio
    async def test_connect(self):
        """Test connecting a WebSocket."""
        manager = ConnectionManager()
        ws = AsyncMock()

        await manager.connect(ws)

        assert manager.connection_count == 1
        ws.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnecting a WebSocket."""
        manager = ConnectionManager()
        ws = AsyncMock()

        await manager.connect(ws)
        assert manager.connection_count == 1

        await manager.disconnect(ws)
        assert manager.connection_count == 0

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent(self):
        """Test disconnecting a WebSocket that's not connected."""
        manager = ConnectionManager()
        ws = AsyncMock()

        # Should not raise
        await manager.disconnect(ws)
        assert manager.connection_count == 0

    @pytest.mark.asyncio
    async def test_update_subscription(self):
        """Test updating subscription preferences."""
        manager = ConnectionManager()
        ws = AsyncMock()

        await manager.connect(ws)

        viewport = Viewport(min_lat=37.0, max_lat=38.0, min_lng=-123.0, max_lng=-122.0)
        await manager.update_subscription(
            ws, viewport=viewport, priorities=["A", "B"]
        )

        # Verify subscription was updated
        async with manager._lock:
            sub = manager._connections[ws]
            assert sub.viewport == viewport
            assert sub.priorities == {"A", "B"}

    @pytest.mark.asyncio
    async def test_broadcast_no_connections(self, sample_call):
        """Test broadcast with no connected clients."""
        manager = ConnectionManager()

        # Should not raise
        await manager.broadcast([sample_call])

    @pytest.mark.asyncio
    async def test_broadcast_empty_calls(self):
        """Test broadcast with empty call list."""
        manager = ConnectionManager()
        ws = AsyncMock()
        await manager.connect(ws)

        await manager.broadcast([])

        # Should not send anything
        ws.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_broadcast_to_matching_clients(self, sample_call):
        """Test broadcast sends to clients with matching filters."""
        manager = ConnectionManager()

        ws1 = AsyncMock()
        ws2 = AsyncMock()

        await manager.connect(ws1)
        await manager.connect(ws2)

        # ws1 subscribes to priority A, ws2 subscribes to priority C
        await manager.update_subscription(ws1, priorities=["A"])
        await manager.update_subscription(ws2, priorities=["C"])

        await manager.broadcast([sample_call])  # priority A

        # Only ws1 should receive the message
        ws1.send_json.assert_called_once()
        ws2.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_broadcast_handles_send_error(self, sample_call):
        """Test broadcast handles send errors gracefully."""
        manager = ConnectionManager()

        ws = AsyncMock()
        ws.send_json.side_effect = Exception("Connection closed")

        await manager.connect(ws)

        # Should not raise
        await manager.broadcast([sample_call])

        # Connection should be scheduled for disconnect
        # (The actual disconnect happens in a background task)

    @pytest.mark.asyncio
    async def test_multiple_connections(self, sample_call):
        """Test managing multiple concurrent connections."""
        manager = ConnectionManager()

        connections = [AsyncMock() for _ in range(5)]
        for ws in connections:
            await manager.connect(ws)

        assert manager.connection_count == 5

        await manager.broadcast([sample_call])

        # All connections should receive the message
        for ws in connections:
            ws.send_json.assert_called_once()


class TestViewport:
    """Tests for Viewport model."""

    def test_contains_inside(self):
        """Test point inside viewport."""
        viewport = Viewport(
            min_lat=37.0,
            max_lat=38.0,
            min_lng=-123.0,
            max_lng=-122.0,
        )

        assert viewport.contains(37.5, -122.5) is True

    def test_contains_outside(self):
        """Test point outside viewport."""
        viewport = Viewport(
            min_lat=37.0,
            max_lat=38.0,
            min_lng=-123.0,
            max_lng=-122.0,
        )

        assert viewport.contains(36.0, -122.5) is False  # Below min_lat
        assert viewport.contains(37.5, -124.0) is False  # Left of min_lng

    def test_contains_on_boundary(self):
        """Test point on viewport boundary."""
        viewport = Viewport(
            min_lat=37.0,
            max_lat=38.0,
            min_lng=-123.0,
            max_lng=-122.0,
        )

        # Boundary points should be included
        assert viewport.contains(37.0, -122.5) is True
        assert viewport.contains(38.0, -123.0) is True
