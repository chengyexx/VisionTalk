"""
Vision Talk — VLM 多模态推理
摄像头帧 + 语音文字 + 历史上下文 → 流式文本回复。

职责边界:
- 多模态消息组装 (assemble_multimodal_message)
- 流式推理 (vlm_inference)
- 记忆压缩 (summarize_visual)

设计原则:
- 消息结构必须遵循 LiteLLM / OpenAI 多模态规范 (image_url + text content parts)
- 使用 litellm.acompletion 统一调用 DeepSeek / OpenAI / Qwen 等
"""
import logging
from typing import AsyncIterator

from app.config import config
from app.core.llm import chat, get_active_vlm_model

logger = logging.getLogger("vision_talk.vlm")

SYSTEM_PROMPT = """你是 Vision Talk 助手，一个能够看到用户摄像头画面的 AI 对话伙伴。

你的能力:
- 看到用户摄像头拍摄的实时画面，识别其中的物体、场景、人物
- 听到用户的语音问题，结合画面内容做出自然、有帮助的回答

对话规则:
1. 用自然、友好的中文口语风格回答
2. 回答简洁明了，控制在 2-4 句话
3. 如果画面内容不清晰或有疑问，主动询问用户

当你收到"[之前看到的]"信息时，这是对你之前看到的画面的文字总结，并非当前画面。
当前画面永远是最新的帧数据。"""


def assemble_multimodal_message(
    asr_text: str = "",
    key_frame: str | None = None,
    visual_summary: str | None = None,
) -> dict:
    """
    按 LiteLLM / OpenAI 多模态规范组装单条 user message。

    结构:
        {
            "role": "user",
            "content": [
                {"type": "text",     "text": "[之前看到的]: ..."},   # 可选
                {"type": "image_url", "image_url": {"url": "data:..."}}, # 可选
                {"type": "text",     "text": "用户说的话"},            # 可选
            ]
        }

    Args:
        asr_text:       用户语音识别文本
        key_frame:      当前摄像头帧 Base64 JPEG
        visual_summary: 历史画面文字摘要 (记忆压缩产物)

    Returns:
        OpenAI-format 消息字典，content 为 multimodal list
    """
    content: list[dict] = []

    # 1. 视觉记忆摘要 (如果有) — 放在最前，给 VLM 上下文
    if visual_summary:
        content.append({
            "type": "text",
            "text": f"[之前看到的]: {visual_summary}",
        })

    # 2. 当前关键帧 (如果有)
    if key_frame:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{key_frame}"},
        })

    # 3. 用户语音文本 (如果有)
    if asr_text:
        content.append({"type": "text", "text": asr_text})

    return {"role": "user", "content": content}


async def vlm_inference(
    messages: list[dict],
    model: str | None = None,
) -> AsyncIterator[str]:
    """
    多模态流式推理 — 通过 LiteLLM acompletion(stream=True)。

    Args:
        messages: 完整消息列表 (含 system + history + 新组装的多模态 user message)
        model:    指定模型 (None = 当前活跃 VLM)

    Yields:
        单个文本 token 字符串
    """
    model = model or get_active_vlm_model()
    logger.info("VLM 推理开始 (model=%s, messages=%d)", model, len(messages))

    try:
        response = await chat(messages=messages, model=model, stream=True)
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        logger.exception("VLM 推理失败: %s", e)
        # 异常时返回空，pipeline 层会捕获 err 并写入 state.error
        return

    logger.info("VLM 推理完成 (model=%s)", model)


async def summarize_visual(asr_text: str, vlm_response: str) -> str:
    """
    视觉记忆压缩 — 从对话文本推断画面内容，生成一句话摘要。

    设计意图 (阅后即焚):
    - 零图片 Token 消耗 — 纯文本模型从 asr_text + vlm_response
      推断画面内容
    - 摘要存入 visual_summary → 下轮作为 [之前看到的] 上下文
    - 原始图片 Base64 彻底丢弃，不进 messages 历史

    Args:
        asr_text:     用户语音文本 (如 "这个红灯是什么意思？")
        vlm_response: VLM 完整回复 (如 "我看到一块开发板，红色LED...")

    Returns:
        中文一句话摘要，如 "一块红色LED闪烁的PCB开发板"
    """
    if not vlm_response:
        return "用户没有展示画面"

    prompt = (
        "根据以下对话，用一句话概括用户摄像头画面里有什么对象。"
        "只回答画面内容，不要引入对话本身。\n\n"
        f"用户: {asr_text}\nAI: {vlm_response}"
    )

    try:
        response = await chat(
            messages=[{"role": "user", "content": prompt}],
            model=config.SUMMARY_MODEL,
            max_tokens=50,
        )
        summary = response.choices[0].message.content.strip()
        logger.info("视觉摘要: %s", summary)
        return summary
    except Exception as e:
        logger.exception("摘要生成失败: %s", e)
        return "用户展示了某个画面"
