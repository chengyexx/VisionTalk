"""
Vision Talk — ASR 语音识别
用户语音 → 文字。纯 I/O 边界层，不参与状态组装。

职责边界:
- 仅接收 Base64 音频，输出识别文本
- 不触碰全局 messages 历史 (由 VLM 节点负责多模态组装)
- 静音/空数据防御性返回 ""
"""
import asyncio
import logging
from app.core.llm import get_active_asr_model

logger = logging.getLogger("vision_talk.asr")

# ── Mock 配置 ────────────────────────────────────────────────────
_MOCK_SIMULATED_DELAY = 0.5       # 模拟网络延迟 (秒)
_MOCK_RESULT = "请帮我看看这个板子上闪烁的红灯是什么意思？"
_MOCK_MIN_AUDIO_LEN = 10          # 低于此长度视为静音/空数据


async def transcribe(audio_b64: str) -> str:
    """
    语音转文字。

    [MOCK] 当前返回静态文本 + 模拟延迟。
    真实环境替换为 LiteLLM atranscription() 调用 Whisper API。

    Args:
        audio_b64: Base64 编码音频 (WebM/Opus, 来自浏览器 MediaRecorder)

    Returns:
        识别文本。失败/静音返回 ""
    """
    # ── 模拟网络延迟 ──
    await asyncio.sleep(_MOCK_SIMULATED_DELAY)

    # ── 防御: 静音或空数据 ──
    if not audio_b64 or len(audio_b64) < _MOCK_MIN_AUDIO_LEN:
        logger.warning("音频数据过短 (len=%d)，模拟识别为空", len(audio_b64 or ""))
        return ""

    # ── [MOCK] 返回静态文本 ──
    logger.info("ASR 识别完成 → '%s'", _MOCK_RESULT)
    return _MOCK_RESULT


# ── 真实实现 (接入 LiteLLM 时替换上方) ──────────────────────────
#
# async def transcribe(audio_b64: str) -> str:
#     import base64, tempfile, os
#     from litellm import atranscription
#
#     model = get_active_asr_model()
#     try:
#         audio_bytes = base64.b64decode(audio_b64)
#         with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
#             tmp.write(audio_bytes)
#             tmp_path = tmp.name
#         with open(tmp_path, "rb") as f:
#             response = await atranscription(model=model, file=f)
#         return response.text.strip() if hasattr(response, "text") else ""
#     except Exception:
#         return ""
#     finally:
#         try:
#             os.unlink(tmp_path)
#         except Exception:
#             pass
