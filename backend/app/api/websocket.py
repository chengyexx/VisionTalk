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
import hashlib
import json
import logging
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..core.pipeline import PipelineExecutor

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
    _task_started_at: float = 0
    # 最短任务存活时间（秒）：新任务在此时长内不会被后续 start_turn 取消
    _MIN_TASK_AGE = 1.0

    # ── 旁路推流回调 ────────────────────────────────────────
    # vlm_node 通过此回调将 token/audio 直接推送到 WebSocket。
    # 需要包装 try/except 防止 WS 断开时崩溃。
    async def _ws_sender(msg: dict) -> None:
        try:
            await ws.send_json(msg)
        except Exception:
            pass  # WS 已断开，静默丢弃

    # ── 管线执行协程 ────────────────────────────────────────
    async def _run_pipeline(audio_b64: str, image_b64: str) -> None:
        """在独立 Task 中执行管线，完成后推送结果。"""
        nonlocal current_task

        try:
            await ws.send_json({"type": "state_change", "state": "thinking"})

            result = await executor.execute(
                audio_b64=audio_b64,
                frame_b64=image_b64,
                ws_sender=_ws_sender,   # 注入旁路推流回调
            )

            if current_task and current_task.cancelled():
                return

            if result.error:
                await ws.send_json({
                    "type": "turn_end",
                    "payload": {"error": result.error},
                })
                return

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
            # 不推送 idle — interrupt handler 已处理

        except Exception as e:
            logger.exception("管线执行异常")
            try:
                await ws.send_json({"type": "error", "message": str(e)})
                await ws.send_json({"type": "state_change", "state": "idle"})
            except Exception:
                pass

    # ── 消息循环 ────────────────────────────────────────────
    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type", "")

            # ── start_turn: 发起新一轮对话 ──
            if msg_type == "start_turn":
                audio_b64_in = data.get("audio_b64", "")
                image_b64_in = data.get("image_b64", "")

                # 防御: 空音频 / 超短碎片直接丢弃，不给前端错误回显
                if not audio_b64_in or len(audio_b64_in) < 100:
                    logger.debug("丢弃过短音频 (len=%d)", len(audio_b64_in or ""))
                    continue

                # 音频指纹 — 对比前后端指纹确认传输一致性
                audio_hash = hashlib.sha256(audio_b64_in.encode()).hexdigest()[:16]
                logger.info(
                    "WS start_turn — audio_len=%d audio_hash=%s audio_fp=%s... "
                    "frame_len=%d",
                    len(audio_b64_in),
                    audio_hash,
                    audio_b64_in[:30],
                    len(image_b64_in),
                )

                # 强杀上一轮 — 但保护刚创建的任务（防止 VAD 高频触发连锁取消）
                if current_task and not current_task.done():
                    age = time.monotonic() - _task_started_at
                    if age < _MIN_TASK_AGE:
                        logger.debug("上一轮任务仅运行 %.1fs，跳过取消", age)
                        continue
                    current_task.cancel()
                    try:
                        await current_task
                    except asyncio.CancelledError:
                        pass

                # 重置管线状态，开启新一轮
                executor.reset()

                current_task = asyncio.create_task(
                    _run_pipeline(
                        audio_b64=audio_b64_in,
                        image_b64=data.get("image_b64", ""),
                    )
                )
                _task_started_at = time.monotonic()

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
