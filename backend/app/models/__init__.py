"""Database models."""

from app.models.dispatch_call import DispatchCall
from app.models.fire_call import FireCall
from app.models.incident_report import IncidentReport
from app.models.service_request import ServiceRequest
from app.models.sync_checkpoint import SyncCheckpoint
from app.models.traffic_crash import TrafficCrash

__all__ = [
    "DispatchCall",
    "FireCall",
    "IncidentReport",
    "ServiceRequest",
    "SyncCheckpoint",
    "TrafficCrash",
]
