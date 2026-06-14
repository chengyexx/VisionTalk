"""
Vision Talk — FastAPI Application Entry Point
AI visual conversation assistant with edge-cloud collaborative architecture.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.health import router as health_router
from .api.websocket import router as ws_router
from .api.model import router as model_router

logger = logging.getLogger("vision_talk.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: startup and shutdown hooks."""
    from .core.logging_config import setup_logging
    setup_logging(level=logging.INFO)

    logger.info("Server starting...")
    logger.info("WebSocket endpoint: ws://localhost:8000/ws")
    logger.info("Model API:       http://localhost:8000/api/model/switch")
    from .core.llm import get_model_state
    state = get_model_state()
    logger.info("Available models: VLM=%s, ASR=%s, TTS=%s",
                state["vlm"], state["asr"], state["tts"])
    yield
    logger.info("Server shutting down.")


app = FastAPI(
    title="Vision Talk",
    description="AI 视觉对话助手 — 实时视频理解 + 语音交互",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: limit to local dev origins only
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(health_router)
app.include_router(ws_router)
app.include_router(model_router)


@app.get("/")
async def root():
    """Health check endpoint."""
    from .core.llm import get_model_state
    return {
        "service": "Vision Talk",
        "status": "running",
        "models": get_model_state(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
