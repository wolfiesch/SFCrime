"""WebSocket message schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.dispatch_call import DispatchCallOut


class Viewport(BaseModel):
    """Geographic viewport bounds for filtering updates."""

    min_lat: float
    max_lat: float
    min_lng: float
    max_lng: float

    def contains(self, lat: float, lng: float) -> bool:
        """Check if coordinates are within this viewport."""
        return (
            self.min_lat <= lat <= self.max_lat
            and self.min_lng <= lng <= self.max_lng
        )


class SubscribeMessage(BaseModel):
    """Client subscription message to set viewport and priority filters."""

    type: Literal["subscribe"] = "subscribe"
    viewport: Viewport | None = None
    priorities: list[str] | None = None  # ["A", "B", "C"]


class CallUpdateMessage(BaseModel):
    """Server message with updated dispatch calls."""

    type: Literal["call_update"] = "call_update"
    data: list[DispatchCallOut]
    timestamp: datetime


class PingMessage(BaseModel):
    """Ping message for keep-alive."""

    type: Literal["ping"] = "ping"


class PongMessage(BaseModel):
    """Pong response for keep-alive."""

    type: Literal["pong"] = "pong"


class ErrorMessage(BaseModel):
    """Error message from server."""

    type: Literal["error"] = "error"
    message: str
