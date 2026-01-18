"""WebSocket router for real-time dispatch call updates."""

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.websocket.manager import manager
from app.websocket.schemas import (
    ErrorMessage,
    PingMessage,
    PongMessage,
    SubscribeMessage,
    Viewport,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/calls")
async def websocket_calls(websocket: WebSocket):
    """
    WebSocket endpoint for real-time dispatch call updates.

    Protocol:
    - Client connects
    - Client sends subscribe message with viewport and priority filters
    - Server broadcasts call updates matching filters
    - Client can update subscription at any time
    - Server sends pong in response to ping for keep-alive

    Message formats:
    Client -> Server:
        {"type": "subscribe", "viewport": {"min_lat": 37.7, "max_lat": 37.8, "min_lng": -122.5, "max_lng": -122.4}, "priorities": ["A", "B"]}
        {"type": "ping"}

    Server -> Client:
        {"type": "call_update", "data": [...], "timestamp": "2026-01-18T10:30:00Z"}
        {"type": "pong"}
        {"type": "error", "message": "..."}
    """
    await manager.connect(websocket)

    try:
        while True:
            # Receive message from client
            raw_message = await websocket.receive_text()

            try:
                data = json.loads(raw_message)
                msg_type = data.get("type")

                if msg_type == "subscribe":
                    # Parse and apply subscription
                    msg = SubscribeMessage.model_validate(data)
                    await manager.update_subscription(
                        websocket,
                        viewport=msg.viewport,
                        priorities=msg.priorities,
                    )
                    logger.info(
                        f"Subscription updated: viewport={msg.viewport}, priorities={msg.priorities}"
                    )

                elif msg_type == "ping":
                    # Respond with pong for keep-alive
                    await websocket.send_json(PongMessage().model_dump())

                else:
                    # Unknown message type
                    error = ErrorMessage(message=f"Unknown message type: {msg_type}")
                    await websocket.send_json(error.model_dump())

            except json.JSONDecodeError:
                error = ErrorMessage(message="Invalid JSON")
                await websocket.send_json(error.model_dump())
            except Exception as e:
                logger.exception(f"Error processing message: {e}")
                error = ErrorMessage(message=str(e))
                await websocket.send_json(error.model_dump())

    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.exception(f"WebSocket error: {e}")
        await manager.disconnect(websocket)
