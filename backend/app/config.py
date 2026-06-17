"""
Vision Talk — Configuration
Loads API keys and model settings from environment variables.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # DeepSeek (纯文本对话 + 摘要)
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

    # ASR (OpenAI 兼容端点，复用 DashScope)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # Qwen / DashScope (多模态主力)
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")

    # Default models
    DEFAULT_VLM_MODEL: str = os.getenv("DEFAULT_VLM_MODEL", "dashscope/qwen-vl-max")
    DEFAULT_ASR_MODEL: str = os.getenv("DEFAULT_ASR_MODEL", "sensevoice-v1")
    DEFAULT_TTS_MODEL: str = os.getenv("DEFAULT_TTS_MODEL", "")

    # Available models for switching
    VLM_MODELS: list[str] = [
        "dashscope/qwen-vl-max",       # Qwen VL Max (多模态，推荐)
        "dashscope/qwen-vl-plus",      # Qwen VL Plus (多模态，轻量)
        "deepseek/deepseek-chat",      # DeepSeek V3 (纯文本！不支持图片)
    ]

    ASR_MODELS: list[str] = [
        "FunAudioLLM/SenseVoiceSmall",  # 硅基流动 SenseVoice (中文原生，免费，国内直连)
        "whisper-large-v3",             # Groq Whisper (备选)
        "whisper-large-v3-turbo",        # Groq Whisper Turbo (备选)
        "whisper-1",                     # OpenAI Whisper
    ]

    TTS_MODELS: list[str] = [
        "edge-tts",                    # Microsoft Edge TTS (免费)
    ]

    # Edge TTS configuration
    EDGE_TTS_VOICE: str = os.getenv("EDGE_TTS_VOICE", "zh-CN-XiaoxiaoNeural")

    # VLM parameters
    VLM_MAX_TOKENS: int = int(os.getenv("VLM_MAX_TOKENS", "1024"))
    VLM_TEMPERATURE: float = float(os.getenv("VLM_TEMPERATURE", "0.7"))

    # TTS parameters
    TTS_VOICE: str = os.getenv("TTS_VOICE", "alloy")
    TTS_SPEED: float = float(os.getenv("TTS_SPEED", "1.0"))

    # Memory compression (纯文本，不需要视觉)
    SUMMARY_MODEL: str = os.getenv("SUMMARY_MODEL", "deepseek/deepseek-chat")

    @classmethod
    def get_litellm_model_list(cls) -> list[str]:
        """All model IDs available via LiteLLM."""
        return [
            "dashscope/qwen-vl-max",
            "dashscope/qwen-vl-plus",
            "deepseek/deepseek-chat",
            "sensevoice-v1",
            "whisper-1",
        ]


config = Config()
