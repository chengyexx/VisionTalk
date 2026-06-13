"""WebSocket handler for real-time vision conversation with LangGraph pipeline."""

import base64
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.asr import transcribe
from app.services.vlm import vlm_node as run_vlm
from app.services.tts import synthesize_stream

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])

# Global flag for barge-in support
_pipeline_interrupted = False


async def run_pipeline(ws: WebSocket, audio_bytes: bytes, frame_base64: str):
    """Run the full ASR → VLM → TTS pipeline with real-time streaming output."""
    global _pipeline_interrupted
    _pipeline_interrupted = False

    state: dict = {
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
        # === ASR (non-streaming, typically fast) ===
        if _pipeline_interrupted:
            return
        text = await transcribe(audio_bytes)
        state["asr_text"] = text
        await ws.send_json({"type": "asr_text", "text": text})
        logger.info(f"[Pipeline] ASR: {text[:50]}...")

        if not text:
            await ws.send_json({"type": "error", "message": "No speech detected"})
            return

        # === VLM (streaming — push tokens in real time) ===
        if _pipeline_interrupted:
            return

        async def on_token(token: str):
            await ws.send_json({"type": "vlm_token", "text": token})

        state = await run_vlm(state, on_token=on_token)
        vlm_text = state.get("vlm_response", "")

        if not vlm_text:
            await ws.send_json({"type": "error", "message": "No VLM response"})
            return

        # === TTS (streaming — push audio chunks as they're synthesized) ===
        if _pipeline_interrupted:
            return

        async for audio_chunk in synthesize_stream(vlm_text):
            if _pipeline_interrupted:
                break
            audio_b64 = base64.b64encode(audio_chunk).decode("utf-8")
            await ws.send_json({
                "type": "tts_audio",
                "data": audio_b64,
                "format": "mp3",
            })

    except Exception as e:
        if not _pipeline_interrupted:
            logger.error(f"[Pipeline] Error: {e}")
            await ws.send_json({"type": "error", "message": str(e)})


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Main WebSocket endpoint for Vision Talk communication."""
    global _pipeline_interrupted
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

            elif msg_type == "pipeline":
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
                await run_pipeline(ws, audio_bytes, frame_data)

            elif msg_type == "interrupt":
                logger.info("[Interrupt] Received — stopping pipeline")
                _pipeline_interrupted = True
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
