"""
Vision Talk — WebSocket 路由
全双工通信 + 管线执行 + 打断机制。

协议规范 (Protocol Contract):
═══════════════════════════════════════════════════════

Client → Server:
  {"type": "start_turn", "audio_b64": "<base64>", "image_b64": "<base64>"}
    发起一轮对话。image_b64 可为空字符串。

  {"type": "interrupt"}
    打断信号。取消当前管线，重置状态，回到 idle。

Server → Client:
  {"type": "state_change", "state": "thinking|speaking|idle"}
    通知前端切换 UI 状态。

  {"type": "turn_end", "payload": {"asr_text": "...", "vlm_response": "...", "tts_audio_b64": "..."}}
    本轮完成，携带完整结果。

  [未来 Phase 5 流式]
  {"type": "vlm_token", "text": "..."}     流式推送 VLM token
  {"type": "tts_chunk", "audio_b64": "..."} 流式推送 TTS 音频块

  {"type": "error", "message": "..."}
    管线执行出错。
"""
import asyncio
import base64
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.pipeline import PipelineExecutor

logger = logging.getLogger("vision_talk.ws")
router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """
    Vision Talk 主 WebSocket 端点。

    每个连接持有独立的 PipelineExecutor + Task 引用，
    确保多连接隔离、打断机制精准可控。
    """
    await ws.accept()
    logger.info("WebSocket 连接已建立")

    executor = PipelineExecutor()
    current_task: asyncio.Task | None = None

    # ── 管线执行协程 ────────────────────────────────────────
    async def _run_pipeline(audio_b64: str, image_b64: str) -> None:
        """在独立 Task 中执行管线，完成后推送结果。"""
        nonlocal current_task

        try:
            await ws.send_json({"type": "state_change", "state": "thinking"})

            result = await executor.execute(
                audio_b64=audio_b64,
                frame_b64=image_b64,
            )

            # 检查是否被取消
            if current_task and current_task.cancelled():
                return

            if result.error:
                await ws.send_json({
                    "type": "turn_end",
                    "payload": {"error": result.error},
                })
                return

            # 编码 TTS 音频为 Base64
            tts_b64 = ""
            if result.tts_audio:
                tts_b64 = base64.b64encode(result.tts_audio).decode("utf-8")

            await ws.send_json({
                "type": "turn_end",
                "payload": {
                    "asr_text": result.asr_text,
                    "vlm_response": result.vlm_response,
                    "tts_audio_b64": tts_b64,
                },
            })

            await ws.send_json({"type": "state_change", "state": "idle"})

        except asyncio.CancelledError:
            logger.info("管线任务被取消 (interrupt)")
            # 不推送任何消息 — interrupt 处理器已经发了 idle
            raise

        except Exception as e:
            logger.exception("管线执行异常")
            await ws.send_json({"type": "error", "message": str(e)})
            await ws.send_json({"type": "state_change", "state": "idle"})

    # ── 消息循环 ────────────────────────────────────────────
    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type", "")

            # ── start_turn: 发起新一轮对话 ──
            if msg_type == "start_turn":
                # 强杀上一轮 (如果还在跑)
                if current_task and not current_task.done():
                    current_task.cancel()
                    try:
                        await current_task
                    except asyncio.CancelledError:
                        pass

                # 重置管线状态，开启新一轮
                executor.reset()

                current_task = asyncio.create_task(
                    _run_pipeline(
                        audio_b64=data.get("audio_b64", ""),
                        image_b64=data.get("image_b64", ""),
                    )
                )

            # ── interrupt: 打断 ──
            elif msg_type == "interrupt":
                logger.info("收到打断信号")
                if current_task and not current_task.done():
                    current_task.cancel()
                    try:
                        await current_task
                    except asyncio.CancelledError:
                        pass

                executor.reset()
                await ws.send_json({"type": "state_change", "state": "idle"})

            # ── 未知消息 ──
            else:
                logger.warning("未知消息类型: %s", msg_type)

    except WebSocketDisconnect:
        logger.info("WebSocket 连接断开")
    except Exception as e:
        logger.exception("WebSocket 异常")
    finally:
        # 清理: 取消正在执行的任务
        if current_task and not current_task.done():
            current_task.cancel()
            try:
                await current_task
            except asyncio.CancelledError:
                pass
