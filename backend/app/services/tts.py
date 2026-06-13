"""
TTS (Text-to-Speech) node.
Synthesizes speech from VLM text response, supports streaming output.
"""

import logging
import os
from typing import AsyncIterator

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

DEFAULT_TTS_MODEL = os.getenv("DEFAULT_TTS_MODEL", "tts-1")
DEFAULT_TTS_VOICE = os.getenv("DEFAULT_TTS_VOICE", "alloy")


async def synthesize(
    text: str,
    model: str = DEFAULT_TTS_MODEL,
    voice: str = DEFAULT_TTS_VOICE,
) -> bytes:
    """
    Synthesize text to speech (non-streaming).
    Returns complete audio bytes.
    """
    if not text.strip():
        return b""

    try:
        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

        response = await client.audio.speech.create(
            model=model,
            voice=voice,
            input=text,
            response_format="mp3",
            speed=1.0,
        )

        return response.content

    except Exception as e:
        logger.error(f"TTS synthesis failed: {e}")
        # Fallback: silent audio
        return b""


async def synthesize_stream(
    text: str,
    model: str = DEFAULT_TTS_MODEL,
    voice: str = DEFAULT_TTS_VOICE,
) -> AsyncIterator[bytes]:
    """
    Synthesize text to speech with streaming.
    Yields audio chunks as they become available.
    Note: OpenAI TTS doesn't natively stream per-chunk.
    We split long text into sentences for lower perceived latency.
    """
    if not text.strip():
        return

    # Split text into sentences for progressive synthesis
    import re
    sentences = re.split(r"([。！？；\n])", text)
    segments = []
    current = ""
    for i, part in enumerate(sentences):
        current += part
        if i % 2 == 1:  # Odd indices are delimiters
            segments.append(current)
            current = ""
    if current.strip():
        segments.append(current)

    if not segments:
        # Fallback: synthesize whole text
        audio = await synthesize(text, model, voice)
        if audio:
            yield audio
        return

    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue
        logger.info(f"TTS segment: {segment[:50]}...")
        audio = await synthesize(segment, model, voice)
        if audio:
            yield audio


async def tts_node(state: dict) -> dict:
    """
    LangGraph node: text → speech synthesis.
    Reads state["vlm_response"], writes state["tts_audio"].
    """
    text = state.get("vlm_response", "")
    if not text:
        logger.warning("TTS: no VLM response to synthesize")
        return {"tts_audio": b""}

    logger.info(f"TTS: synthesizing {len(text)} chars")
    audio = await synthesize(text)
    logger.info(f"TTS: generated {len(audio)} bytes of audio")

    return {"tts_audio": audio}
