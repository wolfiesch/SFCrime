"""Background task scheduler for data ingestion."""

import logging
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from app.database import async_session_maker
from app.services.ingestion import IngestionService
from app.services.soda_client import SODAClient
from app.websocket.manager import manager as ws_manager

logger = logging.getLogger(__name__)
settings = get_settings()

# Global scheduler instance
scheduler: AsyncIOScheduler | None = None


async def sync_dispatch_calls_job() -> None:
    """Background job to sync dispatch calls from DataSF and broadcast updates."""
    logger.info("Starting scheduled dispatch calls sync")
    try:
        async with async_session_maker() as db:
            service = IngestionService(db, SODAClient())
            count, cad_numbers = await service.sync_dispatch_calls()
            logger.info(f"Dispatch sync complete: {count} records")

            # Broadcast to WebSocket clients if there are updates and connections
            if cad_numbers and ws_manager.connection_count > 0:
                calls = await service.fetch_calls_by_cad_numbers(cad_numbers)
                if calls:
                    await ws_manager.broadcast(calls)
                    logger.info(f"Broadcast {len(calls)} calls to WebSocket clients")

            # Prune old records
            pruned = await service.prune_old_dispatch_calls()
            if pruned:
                logger.info(f"Pruned {pruned} old dispatch calls")
    except Exception as e:
        logger.error(f"Dispatch sync failed: {e}", exc_info=True)


async def sync_incident_reports_job() -> None:
    """Background job to sync incident reports from DataSF."""
    logger.info("Starting scheduled incident reports sync")
    try:
        async with async_session_maker() as db:
            service = IngestionService(db, SODAClient())
            count = await service.sync_incident_reports()
            logger.info(f"Incident sync complete: {count} records")
    except Exception as e:
        logger.error(f"Incident sync failed: {e}", exc_info=True)


def setup_scheduler() -> AsyncIOScheduler:
    """Set up and start the background task scheduler."""
    global scheduler

    scheduler = AsyncIOScheduler()
    now = datetime.now(UTC)

    # Schedule dispatch calls sync every 5 minutes
    scheduler.add_job(
        sync_dispatch_calls_job,
        trigger=IntervalTrigger(minutes=settings.dispatch_poll_interval_minutes),
        next_run_time=now,
        id="sync_dispatch_calls",
        name="Sync dispatch calls from DataSF",
        replace_existing=True,
    )

    # Schedule incident reports sync every hour
    scheduler.add_job(
        sync_incident_reports_job,
        trigger=IntervalTrigger(minutes=settings.incidents_poll_interval_minutes),
        next_run_time=now + timedelta(seconds=10),
        id="sync_incident_reports",
        name="Sync incident reports from DataSF",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started")

    return scheduler


def shutdown_scheduler() -> None:
    """Shut down the scheduler gracefully."""
    global scheduler

    if scheduler:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down")
        scheduler = None
