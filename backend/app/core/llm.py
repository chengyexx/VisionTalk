"""
Vision Talk — LiteLLM 统一客户端
多模型访问: 运行时切换 + 流式对话 + 语音转录/合成。

LiteLLM 以 OpenAI-compatible 格式统一调用 DeepSeek / OpenAI / Qwen 等，
vision message (image_url) 由 LiteLLM 自动转换为各厂商的原生多模态格式。
"""
import asyncio
import logging
from typing import Any
from litellm import acompletion
from ..config import config

# ── 抑制 LiteLLM DEBUG 日志 ──
import litellm
litellm.set_verbose = False
litellm.suppress_debug_info = True
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("litellm").setLevel(logging.WARNING)

# ── 运行时模型覆盖 ─────────────────────────────────────────────────
# 模块级全局变量，允许通过 API 在运行时切换模型。
# 优先级: 运行时覆盖 > config 默认值。
# 写操作受 _model_lock 保护，防止并发切换请求的竞态条件。

_current_vlm: str = ""
_current_asr: str = ""
_current_tts: str = ""

_model_lock = asyncio.Lock()


async def set_model(model_type: str, model_id: str) -> None:
    """运行时切换活跃模型。model_type ∈ {vlm, asr, tts}"""
    global _current_vlm, _current_asr, _current_tts
    async with _model_lock:
        if model_type == "vlm":
            _current_vlm = model_id
        elif model_type == "asr":
            _current_asr = model_id
        elif model_type == "tts":
            _current_tts = model_id


def get_active_vlm_model() -> str:
    """当前 VLM 模型 ID，运行时覆盖优先于 .env 默认值"""
    return _current_vlm or config.DEFAULT_VLM_MODEL


def get_active_asr_model() -> str:
    """当前 ASR 模型 ID"""
    return _current_asr or config.DEFAULT_ASR_MODEL


def get_active_tts_model() -> str:
    """当前 TTS 模型 ID"""
    return _current_tts or config.DEFAULT_TTS_MODEL


async def reset_models() -> None:
    """全部重置为 .env 默认值"""
    global _current_vlm, _current_asr, _current_tts
    async with _model_lock:
        _current_vlm = ""
        _current_asr = ""
        _current_tts = ""


def get_model_state() -> dict[str, str]:
    """当前模型快照"""
    return {
        "vlm": get_active_vlm_model(),
        "asr": get_active_asr_model(),
        "tts": get_active_tts_model(),
    }


# ── 核心能力 ─────────────────────────────────────────────────────

async def chat(
    messages: list[dict[str, Any]],
    model: str | None = None,
    stream: bool = False,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> Any:
    """
    统一异步对话补全入口。

    支持 vision message (image_url) — LiteLLM 自动将
    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
    转换为各厂商的原生多模态格式。

    Args:
        messages:    OpenAI-format 消息列表
        model:       指定模型 (None = 使用当前活跃 VLM)
        stream:      流式返回 AsyncIterator
        max_tokens:  最大输出 token (None = config 默认)
        temperature: 采样温度 (None = config 默认)

    Returns:
        LiteLLM ModelResponse (非流式) 或 AsyncIterator[ModelResponse] (流式)
    """
    model = model or get_active_vlm_model()

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "max_tokens": max_tokens if max_tokens is not None else config.VLM_MAX_TOKENS,
        "temperature": temperature if temperature is not None else config.VLM_TEMPERATURE,
    }

    return await acompletion(**kwargs)
