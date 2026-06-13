"""WebSocket handler for real-time vision conversation with LangGraph pipeline."""

import base64
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.graph import graph, ConversationState

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


async def run_pipeline(ws: WebSocket, audio_bytes: bytes, frame_base64: str):
    """Run the full ASR → VLM → TTS pipeline and stream results back through WS."""
    config = {"configurable": {"thread_id": "vision-talk-session"}}

    initial_state: ConversationState = {
        "audio_chunk": audio_bytes,
        "key_frame": frame_base64,
        "asr_text": "",
        "vlm_response": "",
        "tts_audio": b"",
        "messages": [],
        "visual_summary": "",
        "interrupted": False,
    }

    try:
        # Stream each node's output as the graph executes
        async for event in graph.astream(initial_state, config):
            for node_name, node_output in event.items():
                if node_name == "asr":
                    text = node_output.get("asr_text", "")
                    if text:
                        await ws.send_json({"type": "asr_text", "text": text})
                        logger.info(f"[Pipeline] ASR: {text[:50]}...")

                elif node_name == "vlm":
                    text = node_output.get("vlm_response", "")
                    if text:
                        await ws.send_json({"type": "vlm_text", "text": text})
                        logger.info(f"[Pipeline] VLM: {text[:50]}...")

                elif node_name == "tts":
                    audio = node_output.get("tts_audio", b"")
                    if audio:
                        # Send audio as base64 for browser playback
                        audio_b64 = base64.b64encode(audio).decode("utf-8")
                        await ws.send_json({
                            "type": "tts_audio",
                            "data": audio_b64,
                            "format": "mp3",
                        })
                        logger.info(f"[Pipeline] TTS: {len(audio)} bytes")

    except Exception as e:
        logger.error(f"[Pipeline] Error: {e}")
        await ws.send_json({"type": "error", "message": str(e)})


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
                # Legacy frame-only message (PR2 compatible)
                frame_data = message.get("data", "")
                frame_size = len(frame_data)
                logger.info(f"[Frame] Received: {frame_size:,} bytes")
                await ws.send_json({
                    "type": "frame_ack",
                    "size": frame_size,
                    "message": f"Frame received ({frame_size:,} bytes)",
                })

            elif msg_type == "pipeline":
                # Full pipeline: frame + audio → ASR → VLM → TTS
                frame_data = message.get("frame", "")
                audio_b64 = message.get("audio", "")

                if not audio_b64:
                    await ws.send_json({"type": "error", "message": "No audio data"})
                    continue

                try:
                    audio_bytes = base64.b64decode(audio_b64)
                except Exception:
                    await ws.send_json({"type": "error", "message": "Invalid audio encoding"})
                    continue

                logger.info(
                    f"[Pipeline] Received — frame: {len(frame_data):,} chars, audio: {len(audio_bytes):,} bytes"
                )
                await ws.send_json({"type": "pipeline_start"})

                # Run pipeline in background, WS stays open for streaming results
                await run_pipeline(ws, audio_bytes, frame_data)

            elif msg_type == "interrupt":
                # Barge-in: stop current pipeline (PR5)
                logger.info("[Interrupt] Received")
                await ws.send_json({"type": "interrupt_ack"})

            else:
                logger.info(f"[WS] Unknown message type: {msg_type}")
                await ws.send_json({"type": "ack", "received": msg_type})

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await ws.close()
        except Exception:
            pass
