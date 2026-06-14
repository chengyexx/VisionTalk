"""
Vision Talk — Configuration
Loads API keys and model settings from environment variables.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # DeepSeek (primary model)
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

    # OpenAI (optional)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # Qwen / DashScope (optional)
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")

    # Default models
    DEFAULT_VLM_MODEL: str = os.getenv("DEFAULT_VLM_MODEL", "deepseek/deepseek-chat")
    DEFAULT_ASR_MODEL: str = os.getenv("DEFAULT_ASR_MODEL", "whisper-1")
    DEFAULT_TTS_MODEL: str = os.getenv("DEFAULT_TTS_MODEL", "openai/tts-1")

    # Available models for switching
    VLM_MODELS: list[str] = [
        "deepseek/deepseek-chat",
        "openai/gpt-4o",
        "openai/gpt-4o-mini",
        "openai/gpt-4-turbo",
    ]

    ASR_MODELS: list[str] = [
        "whisper-1",
    ]

    TTS_MODELS: list[str] = [
        "openai/tts-1",
        "openai/tts-1-hd",
    ]

    # Edge TTS configuration
    EDGE_TTS_VOICE: str = os.getenv("EDGE_TTS_VOICE", "zh-CN-XiaoxiaoNeural")

    # VLM parameters
    VLM_MAX_TOKENS: int = int(os.getenv("VLM_MAX_TOKENS", "1024"))
    VLM_TEMPERATURE: float = float(os.getenv("VLM_TEMPERATURE", "0.7"))

    # TTS parameters
    TTS_VOICE: str = os.getenv("TTS_VOICE", "alloy")
    TTS_SPEED: float = float(os.getenv("TTS_SPEED", "1.0"))

    # Memory compression
    SUMMARY_MODEL: str = os.getenv("SUMMARY_MODEL", "deepseek/deepseek-chat")

    @classmethod
    def get_litellm_model_list(cls) -> list[str]:
        """All model IDs available via LiteLLM."""
        return [
            "deepseek/deepseek-chat",
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            "openai/gpt-4-turbo",
            "openai/whisper-1",
            "openai/tts-1",
            "openai/tts-1-hd",
        ]


config = Config()
