"""Application configuration."""

import os


class Settings:
    APP_NAME: str = "Vision Talk"
    VERSION: str = "0.1.0"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # WebSocket
    WS_HEARTBEAT_INTERVAL: int = 30  # seconds


settings = Settings()
