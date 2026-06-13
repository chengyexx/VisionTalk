"""
Unified LLM client via LiteLLM.
Supports DeepSeek, OpenAI, Qwen and 100+ models through a single interface.
"""

import os
from typing import AsyncIterator

from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = os.getenv("DEFAULT_VLM_MODEL", "deepseek/deepseek-chat")


async def chat(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    stream: bool = False,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> str | AsyncIterator[str]:
    """
    Unified chat completion.
    Returns full response string if stream=False, async iterator of chunks if stream=True.
    """
    try:
        from litellm import acompletion

        response = await acompletion(
            model=model,
            messages=messages,
            stream=stream,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        if stream:

            async def stream_chunks():
                async for chunk in response:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield delta.content

            return stream_chunks()

        return response.choices[0].message.content or ""

    except ImportError:
        # Fallback: direct OpenAI-compatible API (works with DeepSeek)
        from openai import AsyncOpenAI

        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        model_name = model.replace("deepseek/", "")

        client = AsyncOpenAI(base_url=base_url, api_key=api_key)

        response = await client.chat.completions.create(
            model=model_name,
            messages=messages,
            stream=stream,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        if stream:

            async def stream_chunks():
                async for chunk in response:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield delta.content

            return stream_chunks()

        return response.choices[0].message.content or ""


async def chat_sync(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> str:
    """Convenience: non-streaming chat, returns full text."""
    result = await chat(
        messages=messages,
        model=model,
        stream=False,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    assert isinstance(result, str)
    return result
