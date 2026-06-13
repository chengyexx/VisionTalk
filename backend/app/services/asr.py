"""
ASR (Automatic Speech Recognition) node.
Transcribes audio bytes to text via Whisper or DeepSeek Audio API.
"""

import base64
import io
import logging
import os
import tempfile

logger = logging.getLogger(__name__)

DEFAULT_ASR_MODEL = os.getenv("DEFAULT_ASR_MODEL", "whisper-1")


async def transcribe(
    audio_bytes: bytes,
    model: str = DEFAULT_ASR_MODEL,
) -> str:
    """
    Transcribe audio bytes to text.
    Supports Whisper API (OpenAI-compatible) and DeepSeek Audio.
    """
    try:
        # Try DeepSeek Audio model
        if model.startswith("deepseek"):
            return await _transcribe_deepseek(audio_bytes, model)

        # Default: Whisper via OpenAI API
        return await _transcribe_whisper(audio_bytes, model)

    except Exception as e:
        logger.error(f"ASR transcription failed: {e}")
        return ""


async def _transcribe_whisper(audio_bytes: bytes, model: str) -> str:
    """Transcribe via OpenAI Whisper API."""
    from openai import AsyncOpenAI

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    client = AsyncOpenAI(api_key=api_key)

    # Write audio to temp file (Whisper API requires file upload)
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
        f.write(audio_bytes)
        temp_path = f.name

    try:
        with open(temp_path, "rb") as audio_file:
            response = await client.audio.transcriptions.create(
                model=model,
                file=audio_file,
                response_format="text",
            )
        return response.strip()
    finally:
        os.unlink(temp_path)


async def _transcribe_deepseek(audio_bytes: bytes, model: str) -> str:
    """Transcribe via DeepSeek Audio API (OpenAI-compatible endpoint)."""
    from openai import AsyncOpenAI

    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY not set")

    client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    # Encode audio as base64 data URI
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    data_uri = f"data:audio/webm;base64,{audio_b64}"

    # Use chat completion with audio input
    response = await client.chat.completions.create(
        model=model.replace("deepseek/", ""),
        messages=[
            {"role": "system", "content": "You are a speech recognition assistant. Transcribe the audio accurately."},
            {"role": "user", "content": [
                {"type": "text", "text": "请将这段音频转写为文字："},
                {"type": "input_audio", "input_audio": {"data": audio_b64, "format": "webm"}},
            ]},
        ],
        temperature=0,
        max_tokens=1024,
    )
    return response.choices[0].message.content or ""


async def asr_node(state: dict) -> dict:
    """
    LangGraph node: transcribe audio to text.
    Reads state["audio_chunk"], writes state["asr_text"] and appends to messages.
    """
    audio = state.get("audio_chunk", b"")
    if not audio:
        logger.warning("ASR: no audio chunk in state")
        return {"asr_text": ""}

    logger.info(f"ASR: transcribing {len(audio)} bytes")
    text = await transcribe(audio)
    logger.info(f"ASR result: {text[:100]}..." if len(text) > 100 else f"ASR result: {text}")

    messages = state.get("messages", [])
    messages.append({"role": "user", "content": text})

    return {
        "asr_text": text,
        "messages": messages,
    }
