"""
Vision Talk — TTS 语音合成
VLM 文本 → 语音 (Edge TTS 免费优先)。

职责边界:
- 纯 I/O 转换层 — 接收文本，输出音频字节
- 不触碰 messages、不操作 State
- 分句逻辑为全双工流式做准备
"""
import asyncio
import base64
import logging
import re
from typing import AsyncIterator

import edge_tts

from ..config import config

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
    单段文本 → 音频字节 — 通过 Microsoft Edge TTS (免费)。

    Args:
        text: 待合成的文本片段 (单句)

    Returns:
        音频字节 (MP3)。失败返回 b""
    """
    if not text.strip():
        return b""

    try:
        voice = config.EDGE_TTS_VOICE or "zh-CN-XiaoxiaoNeural"

        chunks: list[bytes] = []
        communicate = edge_tts.Communicate(text, voice)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])

        audio_bytes = b"".join(chunks)
        logger.info("TTS 合成: '%s' → %d bytes", text[:30], len(audio_bytes))
        return audio_bytes

    except Exception as e:
        logger.exception("TTS 合成失败: %s", e)
        return b""


async def synthesize_stream(
    text: str,
    audio_queue: asyncio.Queue | None = None,
) -> AsyncIterator[str]:
    """
    流式 TTS: 逐句合成，即时推送。

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
