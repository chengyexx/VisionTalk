"""Model switching endpoint for runtime model selection."""

import logging
import os

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/model", tags=["model"])

AVAILABLE_MODELS = {
    "deepseek/deepseek-chat": {"label": "DeepSeek-V3", "description": "默认推荐，性价比最高"},
    "deepseek/deepseek-reasoner": {"label": "DeepSeek-R1", "description": "深度推理，复杂问题"},
    "gpt-4o": {"label": "GPT-4o", "description": "OpenAI 多模态旗舰"},
    "qwen/qwen-vl-max": {"label": "Qwen-VL-Max", "description": "通义千问视觉模型"},
}

_current_model = os.getenv("DEFAULT_VLM_MODEL", "deepseek/deepseek-chat")


@router.get("/models")
async def list_models():
    """List all available models."""
    return {
        "models": [
            {"id": k, **v, "active": k == _current_model}
            for k, v in AVAILABLE_MODELS.items()
        ]
    }


@router.get("/current")
async def get_current():
    """Get the currently selected model."""
    return {"model": _current_model}


@router.post("/switch")
async def switch_model(data: dict):
    """Switch to a different model at runtime."""
    global _current_model
    model = data.get("model", "")
    if model not in AVAILABLE_MODELS:
        return {"error": f"Unknown model: {model}", "available": list(AVAILABLE_MODELS.keys())}, 400

    _current_model = model
    # Update env for downstream services
    os.environ["DEFAULT_VLM_MODEL"] = model
    logger.info(f"Model switched to: {model}")
    return {"model": model, "message": f"Switched to {model}"}
