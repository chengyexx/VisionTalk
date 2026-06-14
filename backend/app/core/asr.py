"""
Vision Talk — ASR 语音识别
用户语音 → 文字。纯 I/O 边界层，不参与状态组装。

职责边界:
- 仅接收 Base64 音频，输出识别文本
- 不触碰全局 messages 历史 (由 VLM 节点负责多模态组装)
- 静音/空数据防御性返回 ""
"""
import base64
import io
import logging
import os

from openai import AsyncOpenAI
from app.core.llm import get_active_asr_model

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
    语音转文字 — 通过 OpenAI 兼容端点 (Whisper / SenseVoice)。

    Args:
        audio_b64: Base64 编码音频 (WebM/Opus, 来自浏览器 MediaRecorder)

    Returns:
        识别文本。失败/静音返回 ""
    """
    # ── 防御: 静音或空数据 ──
    if not audio_b64 or len(audio_b64) < 20:
        logger.warning("音频数据过短 (len=%d)，跳过识别", len(audio_b64 or ""))
        return ""

    try:
        # 解码 Base64 → 内存文件 (前端已转码为 WAV/PCM 16kHz)
        audio_bytes = base64.b64decode(audio_b64)
        audio_io = io.BytesIO(audio_bytes)
        audio_io.name = "audio.wav"

        model = get_active_asr_model() or "sensevoice-v1"
        logger.info("ASR 识别中... model=%s size=%d", model, len(audio_bytes))

        client = _get_client()
        response = await client.audio.transcriptions.create(
            model=model,
            file=audio_io,
        )

        text = response.text.strip()
        logger.info("ASR 识别完成 → '%s'", text)
        return text

    except Exception as e:
        logger.exception("ASR 识别失败: %s", e)
        return ""
