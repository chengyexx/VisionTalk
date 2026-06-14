"""
Vision Talk — VLM 多模态推理
摄像头帧 + 语音文字 + 历史上下文 → 流式文本回复。

职责边界:
- 多模态消息组装 (assemble_multimodal_message)
- 流式推理 (vlm_inference)
- 记忆压缩 (summarize_visual) — Step 6

设计原则:
- 消息结构必须遵循 LiteLLM / OpenAI 多模态规范 (image_url + text content parts)
- Mock 阶段也使用真实数据结构，避免后期返工
"""
import asyncio
import logging
from typing import AsyncIterator
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

# ── Mock 配置 ────────────────────────────────────────────────────
_MOCK_CHUNK_DELAY = 0.05         # 模拟流式 token 间隔 (秒)
_MOCK_TOKENS = [
    "我看到", "画面中", "是一块", "绿色的", "PCB", "开发板，",
    "上面有", "一个", "红色", "LED", "在闪烁。",
    "这通常", "表示", "电源", "正常", "工作。",
]


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
    多模态流式推理。

    [MOCK] 返回预定义 token 序列 + 模拟延迟。
    真实环境替换为 LiteLLM acompletion(stream=True) 逐 chunk yield。

    Args:
        messages: 完整消息列表 (含 system + history + 新组装的多模态 user message)
        model:    指定模型 (None = 当前活跃 VLM)

    Yields:
        单个文本 token
    """
    model = model or get_active_vlm_model()
    logger.info("VLM 推理开始 (model=%s, messages=%d)", model, len(messages))

    # ── [MOCK] 模拟 token 流 ──
    for token in _MOCK_TOKENS:
        await asyncio.sleep(_MOCK_CHUNK_DELAY)
        yield token

    logger.info("VLM 推理完成 (model=%s)", model)


# ── 真实实现 (接入 LiteLLM 时替换上方 vlm_inference) ──────────
#
# async def vlm_inference(
#     messages: list[dict],
#     model: str | None = None,
# ) -> AsyncIterator[str]:
#     model = model or get_active_vlm_model()
#     response = await chat(messages=messages, model=model, stream=True)
#     async for chunk in response:
#         if chunk.choices and chunk.choices[0].delta.content:
#             yield chunk.choices[0].delta.content


async def summarize_visual(asr_text: str, vlm_response: str) -> str:
    """
    视觉记忆压缩: 从对话文本推断画面内容，生成一句话摘要。

    设计意图 (阅后即焚):
    - 不用 key_frame — 廉价纯文本模型从 asr_text + vlm_response
      即可推断出画面内容，零视觉 Token 消耗
    - 摘要存入 visual_summary → 下轮作为 [之前看到的] 上下文
    - 原始图片 Base64 彻底丢弃，不进 messages 历史

    [MOCK] 返回静态摘要。
    真实环境调用 chat() 对纯文本模型做摘要提取。

    Args:
        asr_text:     用户语音文本 (如 "这个红灯是什么意思？")
        vlm_response: VLM 完整回复 (如 "我看到一块开发板，红色LED...")

    Returns:
        中文一句话摘要，如 "一块红色LED闪烁的PCB开发板"
    """
    if not vlm_response:
        return "用户没有展示画面"

    # ── [MOCK] 从 VLM 回复中提取关键词作为摘要 ──
    # 真实环境:
    #   response = await chat(
    #       messages=[{"role": "user", "content": f"用一句话概括画面: {vlm_response}"}],
    #       model=config.SUMMARY_MODEL,
    #       max_tokens=50,
    #   )
    #   return response.choices[0].message.content.strip()
    return "[摘要] 一块红色LED闪烁的PCB开发板"
