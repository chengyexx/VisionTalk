"""WebSocket handler for real-time vision conversation."""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Main WebSocket endpoint for Vision Talk communication."""
    await ws.accept()
    logger.info("WebSocket client connected")

    try:
        while True:
            # Receive JSON message from client
            data = await ws.receive_text()
            message = json.loads(data)

            msg_type = message.get("type", "unknown")
            logger.info(f"Received message type: {msg_type}")

            # Echo back for now - will be replaced with LangGraph pipeline
            await ws.send_json({
                "type": "ack",
                "received": msg_type,
            })

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await ws.close()
        except Exception:
            pass
