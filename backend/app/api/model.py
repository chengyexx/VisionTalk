"""
Vision Talk — 模型管理 API
运行时模型切换 / 查询 / 重置。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.llm import set_model, get_model_state, reset_models
from app.config import config

router = APIRouter(prefix="/api")


class ModelSwitchRequest(BaseModel):
    type: str    # "vlm" | "asr" | "tts"
    model: str   # e.g. "dashscope/qwen-vl-max"


class ModelStateResponse(BaseModel):
    vlm: str
    asr: str
    tts: str


class AvailableModelsResponse(BaseModel):
    vlm: list[str]
    asr: list[str]
    tts: list[str]


VALID_TYPES = {"vlm", "asr", "tts"}
MODEL_LISTS = {
    "vlm": config.VLM_MODELS,
    "asr": config.ASR_MODELS,
    "tts": config.TTS_MODELS,
}


@router.get("/model/available", response_model=AvailableModelsResponse)
async def get_available_models():
    """可选模型列表"""
    return AvailableModelsResponse(
        vlm=config.VLM_MODELS,
        asr=config.ASR_MODELS,
        tts=config.TTS_MODELS,
    )


@router.get("/model/state", response_model=ModelStateResponse)
async def get_current_model_state():
    """当前活跃模型"""
    state = get_model_state()
    return ModelStateResponse(vlm=state["vlm"], asr=state["asr"], tts=state["tts"])


@router.post("/model/switch", response_model=ModelStateResponse)
async def switch_model(req: ModelSwitchRequest):
    """运行时切换模型"""
    if req.type not in VALID_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"无效模型类型 '{req.type}'，可选: {', '.join(VALID_TYPES)}",
        )
    if req.model not in MODEL_LISTS.get(req.type, []):
        raise HTTPException(
            status_code=400,
            detail=f"模型 '{req.model}' 不在 {req.type} 可用列表中",
        )
    await set_model(req.type, req.model)
    state = get_model_state()
    return ModelStateResponse(vlm=state["vlm"], asr=state["asr"], tts=state["tts"])


@router.post("/model/reset", response_model=ModelStateResponse)
async def reset_model():
    """重置为 .env 默认模型"""
    await reset_models()
    state = get_model_state()
    return ModelStateResponse(vlm=state["vlm"], asr=state["asr"], tts=state["tts"])
