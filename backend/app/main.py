"""
Vision Talk — FastAPI Application Entry Point
AI visual conversation assistant with edge-cloud collaborative architecture.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.websocket import router as ws_router
from app.api.model import router as model_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: startup and shutdown hooks."""
    print("[Vision Talk] Server starting...")
    print("[Vision Talk] WebSocket endpoint: ws://localhost:8000/ws")
    print("[Vision Talk] Model API:       http://localhost:8000/api/model/switch")
    print("[Vision Talk] Available models:", end=" ")
    from app.core.llm import get_model_state
    state = get_model_state()
    print(f"VLM={state['vlm']}, ASR={state['asr']}, TTS={state['tts']}")
    yield
    print("[Vision Talk] Server shutting down.")


app = FastAPI(
    title="Vision Talk",
    description="AI 视觉对话助手 — 实时视频理解 + 语音交互",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: allow React dev server (Vite default port 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "*",  # Allow all origins in development
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
    from app.core.llm import get_model_state
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
