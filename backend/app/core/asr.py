"""
Vision Talk — ASR 语音识别
用户语音 → 文字。纯 I/O 边界层，不参与状态组装。

职责边界:
- 仅接收 Base64 音频，输出识别文本
- 不触碰全局 messages 历史 (由 VLM 节点负责多模态组装)
- 静音/空数据防御性返回 ""
"""
import base64
import hashlib
import io
import logging
import os
import struct

from openai import AsyncOpenAI
from .llm import get_active_asr_model

logger = logging.getLogger("vision_talk.asr")

# ── 客户端 (延迟初始化，避免无凭证时报错) ──────────────────────
_asr_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _asr_client
    if _asr_client is None:
        _asr_client = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            base_url=os.getenv("OPENAI_BASE_URL") or None,
        )
    return _asr_client


async def transcribe(audio_b64: str) -> str:
    """
    语音转文字 — 通过 OpenAI 兼容端点 (DashScope compatible-mode/v1)。

    Args:
        audio_b64: Base64 编码 WAV/PCM 16kHz 音频

    Returns:
        识别文本。失败/静音返回 ""
    """
    if not audio_b64 or len(audio_b64) < 20:
        return ""

    fingerprint = audio_b64[:30]
    audio_hash = hashlib.sha256(audio_b64.encode()).hexdigest()[:16]
    logger.info(
        "ASR 识别中... model=%s raw_b64_len=%d fingerprint=%s... hash=%s",
        get_active_asr_model() or "sensevoice-v1",
        len(audio_b64),
        fingerprint,
        audio_hash,
    )

    try:
        audio_bytes = base64.b64decode(audio_b64)

        # ── WAV 头校验 ──
        if len(audio_bytes) >= 44 and audio_bytes[:4] == b"RIFF":
            channels = struct.unpack_from("<H", audio_bytes, 22)[0]
            sample_rate = struct.unpack_from("<I", audio_bytes, 24)[0]
            bits_per_sample = struct.unpack_from("<H", audio_bytes, 34)[0]
            data_size = struct.unpack_from("<I", audio_bytes, 40)[0]
            duration_ms = (data_size / (sample_rate * channels * bits_per_sample / 8)) * 1000
            logger.info(
                "ASR: WAV 校验 — sample_rate=%d Hz, channels=%d, bits=%d, "
                "data_size=%d, duration=%.0f ms",
                sample_rate, channels, bits_per_sample, data_size, duration_ms,
            )

        audio_io = io.BytesIO(audio_bytes)
        audio_io.name = "audio.wav"

        model = get_active_asr_model() or "sensevoice-v1"
        client = _get_client()

        response = await client.audio.transcriptions.create(
            model=model,
            file=audio_io,
            response_format="text",
        )

        text = response if isinstance(response, str) else response.text
        logger.info("ASR 识别完成 → '%s'", text.strip())
        return text.strip()

    except Exception as e:
        logger.exception("ASR 识别失败 (raw_bytes=%d): %s", len(audio_b64), e)
        return ""
