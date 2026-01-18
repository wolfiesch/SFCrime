"""WebSocket module for real-time dispatch call updates."""

from app.websocket.manager import ConnectionManager
from app.websocket.router import router as websocket_router

__all__ = ["ConnectionManager", "websocket_router"]
