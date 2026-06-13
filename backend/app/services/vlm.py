"""
VLM (Visual Language Model) node.
Combines key frame + ASR text for multimodal reasoning and response generation.
"""

import logging
import os

from app.services.llm_client import chat, chat_sync

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是 Vision Talk，一个能通过摄像头看到用户的 AI 视觉对话助手。"
    "你的回复应该：\n"
    "1. 准确描述你看到的画面内容\n"
    "2. 直接回答用户的问题\n"
    "3. 保持自然、友好的语气\n"
    "4. 如果看不清或不确定，诚实说明\n"
    "5. 使用中文回复"
)


async def summarize_visual(vlm_response: str) -> str:
    """
    Generate a short text summary of the current visual context.
    Uses a cheap text-only model to keep costs minimal.
    This summary replaces the raw image Base64 in conversation history,
    preventing token explosion across multi-turn conversations.
    """
    if not vlm_response.strip():
        return ""

    try:
        summary = await chat_sync(
            messages=[{
                "role": "user",
                "content": (
                    f"用一句话（不超过30字）概括以下AI回复中描述的画面内容。"
                    f"只描述客观画面，不要包含AI的主观评论：\n\n{vlm_response}"
                ),
            }],
            model="deepseek/deepseek-chat",  # Cheap text-only model
            temperature=0,
            max_tokens=64,
        )
        return summary.strip()
    except Exception as e:
        logger.warning(f"Visual summarization failed: {e}")
        return ""


async def vlm_node(state: dict) -> dict:
    """
    LangGraph node: visual understanding + response generation.
    Reads state["key_frame"] and state["asr_text"],
    writes state["vlm_response"].
    """
    key_frame = state.get("key_frame", "")
    asr_text = state.get("asr_text", "")
    messages = state.get("messages", [])
    visual_summary = state.get("visual_summary", "")

    if not asr_text:
        logger.warning("VLM: no ASR text to respond to")
        return {"vlm_response": ""}

    # Build user message: image + text
    user_content = []

    # Current key frame as image
    if key_frame:
        user_content.append({
            "type": "image_url",
            "image_url": {"url": key_frame},  # Already includes "data:image/jpeg;base64,..."
        })

    # Previous visual context as text summary (Token compression)
    if visual_summary:
        user_content.append({
            "type": "text",
            "text": f"[之前的画面摘要] {visual_summary}",
        })

    # Current ASR text
    user_content.append({
        "type": "text",
        "text": asr_text,
    })

    # Build full conversation
    api_messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Add history (text-only, no images — token compression)
    for msg in messages:
        api_messages.append(msg)

    # Add current user message with vision
    api_messages.append({"role": "user", "content": user_content})

    model = os.getenv("DEFAULT_VLM_MODEL", "deepseek/deepseek-chat")

    logger.info(f"VLM: calling {model} with {len(asr_text)} chars of text")
    if key_frame:
        logger.info(f"VLM: frame included ({len(key_frame):,} chars base64)")

    # Stream response
    full_text = ""
    try:
        stream = await chat(
            messages=api_messages,
            model=model,
            stream=True,
            temperature=0.7,
            max_tokens=1024,
        )

        async for chunk in stream:
            full_text += chunk
            # TODO: PR3-5 — push chunks to TTS in real-time

    except Exception as e:
        logger.error(f"VLM call failed: {e}")
        full_text = "抱歉，我暂时无法处理你的请求。"

    logger.info(f"VLM response: {full_text[:100]}..." if len(full_text) > 100 else f"VLM response: {full_text}")

    # Token compression: generate text summary to replace raw image
    visual_summary = await summarize_visual(full_text) if key_frame else visual_summary

    # Append to conversation history (text only, no images — key compression step)
    user_msg = asr_text
    if visual_summary:
        user_msg = f"[画面：{visual_summary}]\n{asr_text}"
    messages.append({"role": "user", "content": user_msg})
    messages.append({"role": "assistant", "content": full_text})

    logger.info(f"VLM: memory compressed, visual_summary={visual_summary[:50]}..." if len(visual_summary) > 50 else f"VLM: memory compressed, visual_summary={visual_summary}")

    return {
        "vlm_response": full_text,
        "visual_summary": visual_summary,
        "key_frame": "",  # Clear — prevents image accumulation across turns
        "messages": messages,
    }
