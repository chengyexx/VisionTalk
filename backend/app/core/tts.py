"""
Vision Talk — TTS 语音合成
VLM 文本 → 语音 (Edge TTS 免费优先 / OpenAI TTS 备选)。

职责边界:
- 纯 I/O 转换层 — 接收文本，输出音频字节
- 不触碰 messages、不操作 State
- 分句逻辑为未来全双工流式做准备 (Phase 5)

节点串行陷阱 (LangGraph):
- 默认 tts_node 等待 vlm_node 完全执行完毕才启动
- 未来 Phase 5: 通过 asyncio.Queue 边收 VLM 句子边并发合成
"""
import asyncio
import base64
import re
import logging
from typing import AsyncIterator
from app.config import config
from app.core.llm import get_active_tts_model

logger = logging.getLogger("vision_talk.tts")


def split_sentences(text: str) -> list[str]:
    """
    按中文标点拆分为句子列表。

    规则: 以 。！？.!? 为分界，标点归属于前一句。
    为空字符串时返回空列表。

    例: "我看到一块板子。上面有红灯。" → ["我看到一块板子。", "上面有红灯。"]
    """
    if not text:
        return []
    parts = re.split(r"([。！？.!?])", text)
    parts.append("")
    sentences = ["".join(i) for i in zip(parts[0::2], parts[1::2])]
    return [s.strip() for s in sentences if s.strip()]


async def synthesize(text: str) -> bytes:
    """
    单段文本 → 音频字节。

    [MOCK] 返回固定字节 + 模拟延迟。
    真实环境: Edge TTS (免费) 优先，失败降级 OpenAI TTS。

    Args:
        text: 待合成的文本片段 (单句)

    Returns:
        音频字节 (MP3)。失败返回 b""
    """
    if not text.strip():
        return b""

    logger.info("TTS 合成: '%s'", text[:30])
    await asyncio.sleep(0.2)  # 模拟 API 延迟
    return b"MOCK_AUDIO_PAYLOAD"


async def synthesize_stream(
    text: str,
    audio_queue: asyncio.Queue | None = None,
) -> AsyncIterator[str]:
    """
    流式 TTS: 逐句合成，即时推送。

    [STUB] Phase 5 (全双工) 实现。
    真实环境: 每句话单独调 synthesize()，结果 encode 为 Base64 推送。

    Args:
        text:        VLM 回复全文
        audio_queue: WebSocket 音频推送队列

    Yields:
        每句对应一个 Base64 编码的音频块
    """
    sentences = split_sentences(text)
    for sentence in sentences:
        audio_bytes = await synthesize(sentence)
        if audio_bytes:
            chunk_b64 = base64.b64encode(audio_bytes).decode("utf-8")
            if audio_queue is not None:
                await audio_queue.put({"type": "tts_audio", "chunk": chunk_b64})
            yield chunk_b64


# ── 真实实现 (接入时替换 synthesize) ──────────────────────────
#
# async def synthesize_with_edge_tts(text: str) -> bytes:
#     import edge_tts
#     voice = config.EDGE_TTS_VOICE
#     communicate = edge_tts.Communicate(text, voice)
#     chunks: list[bytes] = []
#     async for chunk in communicate.stream():
#         if chunk["type"] == "audio":
#             chunks.append(chunk["data"])
#     return b"".join(chunks)
#
# async def synthesize_with_openai_tts(text: str) -> bytes:
#     from litellm import atext_to_speech
#     response = await atext_to_speech(
#         model=get_active_tts_model(),
#         text=text,
#         voice=config.TTS_VOICE,
#         speed=config.TTS_SPEED,
#     )
#     return response.content
#
# async def synthesize(text: str) -> bytes:
#     try:
#         return await synthesize_with_edge_tts(text)
#     except Exception:
#         try:
#             return await synthesize_with_openai_tts(text)
#         except Exception:
#             return b""
