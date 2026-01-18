"""WebSocket connection manager for broadcasting dispatch call updates."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Callable

from fastapi import WebSocket

from app.schemas.dispatch_call import DispatchCallOut
from app.websocket.schemas import CallUpdateMessage, Viewport

logger = logging.getLogger(__name__)


@dataclass
class ClientSubscription:
    """Tracks a client's subscription preferences."""

    websocket: WebSocket
    viewport: Viewport | None = None
    priorities: set[str] = field(default_factory=set)
    connected_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def matches(self, call: DispatchCallOut) -> bool:
        """Check if a call matches this subscription's filters."""
        # Check priority filter
        if self.priorities and call.priority not in self.priorities:
            return False

        # Check viewport filter
        if self.viewport and call.coordinates:
            if not self.viewport.contains(
                call.coordinates.latitude, call.coordinates.longitude
            ):
                return False

        return True


class ConnectionManager:
    """
    Manages WebSocket connections and broadcasts updates.

    Thread-safe for use with APScheduler background tasks.
    Designed for single-instance deployment; can be extended with Redis pub/sub
    for multi-instance horizontal scaling.
    """

    def __init__(self):
        self._connections: dict[WebSocket, ClientSubscription] = {}
        self._lock = asyncio.Lock()
        self._broadcast_callback: Callable[[list[DispatchCallOut]], None] | None = None

    @property
    def connection_count(self) -> int:
        """Number of active connections."""
        return len(self._connections)

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self._connections[websocket] = ClientSubscription(websocket=websocket)
        logger.info(f"WebSocket connected. Total connections: {self.connection_count}")

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a disconnected WebSocket."""
        async with self._lock:
            if websocket in self._connections:
                del self._connections[websocket]
        logger.info(f"WebSocket disconnected. Total connections: {self.connection_count}")

    async def update_subscription(
        self,
        websocket: WebSocket,
        viewport: Viewport | None = None,
        priorities: list[str] | None = None,
    ) -> None:
        """Update a client's subscription preferences."""
        async with self._lock:
            if websocket in self._connections:
                sub = self._connections[websocket]
                if viewport is not None:
                    sub.viewport = viewport
                if priorities is not None:
                    sub.priorities = set(priorities)
                logger.debug(
                    f"Updated subscription: viewport={viewport}, priorities={priorities}"
                )

    async def broadcast(self, calls: list[DispatchCallOut]) -> None:
        """
        Broadcast updated calls to all matching subscribers.

        Filters calls per-client based on viewport and priority preferences.
        """
        if not calls:
            return

        async with self._lock:
            if not self._connections:
                return

            timestamp = datetime.now(UTC)

            # Group calls by matching subscriptions
            tasks = []
            for websocket, subscription in list(self._connections.items()):
                # Filter calls for this subscriber
                matching_calls = [c for c in calls if subscription.matches(c)]

                if matching_calls:
                    message = CallUpdateMessage(
                        data=matching_calls,
                        timestamp=timestamp,
                    )
                    tasks.append(self._send_safe(websocket, message))

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                logger.info(
                    f"Broadcast {len(calls)} calls to {len(tasks)} subscribers"
                )

    async def _send_safe(
        self, websocket: WebSocket, message: CallUpdateMessage
    ) -> None:
        """Send message to websocket, handling errors gracefully."""
        try:
            await websocket.send_json(message.model_dump(mode="json"))
        except Exception as e:
            logger.warning(f"Failed to send to websocket: {e}")
            # Schedule disconnect (don't do it here to avoid deadlock)
            asyncio.create_task(self.disconnect(websocket))

    async def broadcast_sync(self, calls: list[DispatchCallOut]) -> None:
        """
        Synchronous-friendly broadcast wrapper for use in scheduler callbacks.

        Creates a new event loop task if called from a sync context.
        """
        await self.broadcast(calls)


# Global singleton instance
manager = ConnectionManager()
