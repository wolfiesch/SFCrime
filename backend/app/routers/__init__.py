"""API routers."""

from app.routers.calls import router as calls_router
from app.routers.health import router as health_router
from app.routers.incidents import router as incidents_router

__all__ = ["calls_router", "incidents_router", "health_router"]
