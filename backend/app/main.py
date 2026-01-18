"""FastAPI application for SFCrime backend."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings
from app.database import check_db_ready
from app.routers import calls_router, health_router, incidents_router
from app.tasks.scheduler import setup_scheduler, shutdown_scheduler
from app.websocket import websocket_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    logger.info("Starting SFCrime backend...")

    # Verify database is ready
    try:
        await check_db_ready()
        logger.info("Database ready")
    except Exception as e:
        logger.error(f"Database not ready: {e}")
        raise

    # Start scheduler (ingestion) once DB is ready.
    setup_scheduler()
    logger.info("Scheduler started")

    yield

    # Shutdown
    shutdown_scheduler()
    logger.info("SFCrime backend shut down")


# Create FastAPI app
app = FastAPI(
    title="SFCrime API",
    description="Live crime map API for San Francisco - powered by DataSF",
    version="0.1.0",
    lifespan=lifespan,
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unhandled exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# Include routers
app.include_router(health_router)
app.include_router(calls_router, prefix=settings.api_v1_prefix)
app.include_router(incidents_router, prefix=settings.api_v1_prefix)
app.include_router(websocket_router)  # WebSocket at /ws/calls


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "SFCrime API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
