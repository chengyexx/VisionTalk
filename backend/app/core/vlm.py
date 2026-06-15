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

from ..config import config
from .llm import chat, get_active_vlm_model

logger = logging.getLogger("vision_talk.vlm")

SYSTEM_PROMPT = """你是 Vision Talk 助手，一个通过摄像头实时观察用户周围环境的 AI 对话伙伴。

核心原则 — 只说你看到的，不编造:

1. 摄像头画面是你对世界的唯一感官。用户说的话是他们的问题，不是你看到的画面。
   两者不是一回事。不要把用户描述的东西当成你"看到"的。
2. 如果用户描述了一个你画面中没有的物体（比如"电路板"、"红灯"），
   直接告诉用户你实际看到了什么（人脸、房间、桌面等），
   然后请用户把那个物体对准摄像头。绝对不要假装你看到了它。
3. 画面中有人的时候，你是对方的对话伙伴，不要机械地描述对方的外貌。

视觉记忆规则:
- 当你收到"[之前看到的画面摘要]"信息时，这是一段历史摘要，可能会过时或与实际画面矛盾。
- 当前摄像头画面永远比摘要更可信。如果摘要与当前画面矛盾，相信当前画面。
- 如果摘要中描述的物体在当前画面中看不到，果断忽略摘要。

对话规则:
1. 用自然、友好的中文口语风格回答
2. 回答简洁明了，控制在 2-4 句话
3. 直接回应用户的问题，不需要每句话都描述画面"""


def assemble_multimodal_message(
    asr_text: str = "",
    key_frame: str | None = None,
    visual_summary: str | None = None,
) -> dict:
    """
    工业级多模态消息组装，严格遵守 OpenAI/LiteLLM Vision 规范。
    """
    content: list[dict] = []

    # ── 1. 视觉层 (图像或记忆) 优先 ──
    if key_frame:
        # Base64 头部防呆处理 (Double-Prefix 防御)
        # 前端 canvas.toDataURL() 吐出的字符串自带 "data:image/jpeg;base64,"，
        # 如果后端再盲目拼接一次，VLM 会解析出花屏或直接忽略图片。
        if key_frame.startswith("data:image"):
            image_url = key_frame
        else:
            image_url = f"data:image/jpeg;base64,{key_frame}"

        content.append({
            "type": "image_url",
            "image_url": {
                "url": image_url,
                "detail": "auto"
            }
        })
    elif visual_summary:
        content.append({
            "type": "text",
            "text": f"[之前看到的画面摘要]: {visual_summary}"
        })

    # ── 2. 文本层 (用户意图) 压底 ──
    # 利用大模型的"近因效应 (Recency Bias)"：把用户真正的诉求放在序列末尾，
    # 让 VLM 不会被长篇大论的图片 Base64 Token 冲散注意力。
    if asr_text:
        content.append({
            "type": "text",
            "text": asr_text
        })
    else:
        # 纯视觉空转防御：VLM 的 content 只有 image 没有 text 会直接报错 400，
        # 兜底提示词确保任何情况下都不会因缺字而崩溃。
        content.append({
            "type": "text",
            "text": "请观察当前画面。"
        })

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
    logger.debug("VLM 推理开始 (model=%s, messages=%d)", model, len(messages))

    try:
        response = await chat(messages=messages, model=model, stream=True)
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        logger.exception("VLM 推理失败: %s", e)
        # 异常时返回空，pipeline 层会捕获 err 并写入 state.error
        return

    logger.debug("VLM 推理完成 (model=%s)", model)


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
        "只根据 AI 的回答内容，用一句话概括 AI 在摄像头画面中实际看到了什么对象。"
        "注意: 用户说的话可能描述了画面中没有的物体（比如用户问'红灯是什么意思'但画面中根本没有红灯），"
        "这种情况下只信 AI 回答中描述的物体，不要从用户话语中推断。"
        "如果 AI 回答只提到了人脸/人/房间，就只说这些。不要无中生有。\n\n"
        f"用户说的话: {asr_text}\nAI 实际看到的: {vlm_response}"
    )

    try:
        response = await chat(
            messages=[{"role": "user", "content": prompt}],
            model=config.SUMMARY_MODEL,
            max_tokens=50,
        )
        summary = response.choices[0].message.content.strip()
        logger.debug("视觉摘要: %s", summary)
        return summary
    except Exception as e:
        logger.exception("摘要生成失败: %s", e)
        return "用户展示了某个画面"
