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
            data = await ws.receive_text()
            message = json.loads(data)

            msg_type = message.get("type", "unknown")

            if msg_type == "frame":
                frame_data = message.get("data", "")
                frame_size = len(frame_data)
                logger.info(f"[Frame] Received: {frame_size:,} bytes")

                await ws.send_json({
                    "type": "frame_ack",
                    "size": frame_size,
                    "message": f"Frame received ({frame_size:,} bytes)",
                })
            else:
                logger.info(f"[WS] Unknown message type: {msg_type}")
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
