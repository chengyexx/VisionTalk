"""
Vision Talk — LangGraph 管线编排
ASR → VLM → TTS 条件路由状态机。

路由逻辑:
  START → ASR ─┬─ [有文本] → VLM ─┬─ [有回复] → TTS → END
               │                  │
               └─ [静音/失败] → END
                                  └─ [失败] → END

设计原则:
- 严格 Pydantic 状态模型 — 所有字段有明确类型和默认值
- 输入前置 — key_frame / audio_chunk 必须在管线调用前注入 State
- 节点不主动拉取外部数据 — 所有依赖从 State 读取
"""
import asyncio
import base64
import contextvars
import logging
from typing import Any
from pydantic import BaseModel, Field

from langgraph.graph import StateGraph, END, START

from app.core.asr import transcribe
from app.core.vlm import (
    SYSTEM_PROMPT,
    assemble_multimodal_message,
    summarize_visual,
    vlm_inference,
)
from app.core.tts import synthesize, split_sentences

logger = logging.getLogger("vision_talk.pipeline")

# ── 旁路推流回调 ────────────────────────────────────────────────
# Context-local 变量，由 PipelineExecutor.execute() 注入。
# 使用 ContextVar 而非模块级全局变量 — 确保多 WebSocket 连接并发时
# 每个连接拥有独立的 sender 上下文，互不干扰。
# vlm_node 通过此回调将 token/audio 直接推送到 WebSocket，
# 实现全双工: VLM 边生成边推送，不等整句结束。
_ws_sender_ctx: contextvars.ContextVar[Any] = contextvars.ContextVar(
    "ws_sender", default=None
)

_DEFAULT_VOID_SENDER: Any = None  # 哨兵值，用于安全类型比对


def _set_ws_sender(sender: Any) -> contextvars.Token:
    """注入旁路推流回调并返回 token，调用方用 token 恢复现场。"""
    return _ws_sender_ctx.set(sender)


def _clear_ws_sender(token: contextvars.Token) -> None:
    """通过 token 恢复 ContextVar 到注入前的值。"""
    _ws_sender_ctx.reset(token)


async def _push(type_: str, **kwargs) -> None:
    """推送消息到当前上下文对应的 WebSocket (如果已注入 sender)"""
    sender = _ws_sender_ctx.get()
    if sender:
        await sender({"type": type_, **kwargs})


# ── 严格状态模型 ──────────────────────────────────────────────────

class ConversationState(BaseModel):
    """全局对话状态。所有节点从 State 读、向 State 写。"""

    # ── 前置输入 (管线调用前必须填充) ──
    audio_chunk: str = Field(
        default="",
        description="Base64 编码的用户语音 (WebM/Opus)",
    )
    key_frame: str = Field(
        default="",
        description="当前摄像头帧 (Base64 JPEG)。空字符串 = 无画面",
    )

    # ── 管线中间产物 ──
    asr_text: str = Field(default="", description="ASR 语音识别结果")
    vlm_response: str = Field(default="", description="VLM 完整文本回复")
    tts_audio: bytes = Field(default=b"", description="TTS 合成音频 (聚合)")

    # ── 跨轮记忆 ──
    visual_summary: str = Field(
        default="",
        description="上一轮画面的文字摘要 (记忆压缩产物)",
    )
    messages: list[dict] = Field(
        default_factory=list,
        description="对话历史 (纯文本，不含历史图片 Base64)",
    )

    # ── 控制信号 ──
    interrupted: bool = Field(default=False, description="打断标志")
    error: str = Field(default="", description="最近一次错误信息")


def initial_state() -> ConversationState:
    """工厂: 创建干净的首轮状态"""
    return ConversationState()


# ── 节点 (Mock 骨架 — 后续步骤填充) ────────────────────────────

async def asr_node(state: ConversationState) -> dict:
    """语音识别: audio_chunk → asr_text。不操作 messages。"""
    audio = state.audio_chunk
    if not audio:
        return {"error": "No audio data in state"}

    text = await transcribe(audio)
    if not text:
        return {"asr_text": "", "error": "ASR returned empty (silence / error)"}

    return {"asr_text": text, "error": ""}


async def vlm_node(state: ConversationState) -> dict:
    """多模态推理: 组装消息 → 流式推理 → 消化流 → 写 messages。

    这是整个管线的「大脑」节点 — 唯一负责多模态消息组装和历史管理。
    ASR 和 TTS 都不触碰 messages。
    """
    asr_text = state.asr_text
    key_frame = state.key_frame or None
    visual_summary = state.visual_summary or None

    if not asr_text:
        return {"error": "No ASR text to infer on"}

    # ── 1. 组装多模态 user message ──
    user_msg = assemble_multimodal_message(
        asr_text=asr_text,
        key_frame=key_frame,
        visual_summary=visual_summary,
    )

    # ── 2. 构建完整消息列表: system + history + 新 user message ──
    history = list(state.messages)          # 深拷贝历史
    full_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]
    full_messages.extend(history)           # 纯文本历史 (无历史图片 Base64)
    full_messages.append(user_msg)          # 当前轮多模态 user message

    # ── 3. 全双工旁路推流: token → 前端打字机, 整句 → TTS → 前端播放 ──
    full_response = ""
    sentence_buffer = ""
    SENTENCE_ENDS = {"。", "！", "？", ".", "!", "?"}

    try:
        async for token in vlm_inference(full_messages):
            full_response += token
            sentence_buffer += token

            # 旁路 A: 每个 token 实时推给前端 (打字机效果)
            await _push("vlm_token", text=token)

            # 旁路 B: 遇到句子结束标点 → 立刻合成语音推送
            if token in SENTENCE_ENDS:
                sentence = sentence_buffer.strip()
                if sentence:
                    audio_bytes = await synthesize(sentence)
                    if audio_bytes:
                        chunk_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                        await _push("tts_chunk", audio_b64=chunk_b64)
                sentence_buffer = ""

    except Exception as e:
        return {"error": f"VLM inference failed: {e}", "vlm_response": ""}

    # 扫尾: 最后一句没有标点的残留文本
    if sentence_buffer.strip():
        audio_bytes = await synthesize(sentence_buffer.strip())
        if audio_bytes:
            chunk_b64 = base64.b64encode(audio_bytes).decode("utf-8")
            await _push("tts_chunk", audio_b64=chunk_b64)

    if not full_response:
        return {"vlm_response": "", "error": "VLM returned empty response"}

    # ── 4. 记忆压缩: 提取画面文字摘要 (阅后即焚) ──
    # 从对话文本推断画面内容，不使用 key_frame → 零视觉 Token 消耗
    new_summary = await summarize_visual(asr_text, full_response)

    # ── 5. 更新 messages 历史 ──
    # 只存纯文本！图片 Base64 是 transient payload，阅后即焚。
    new_messages = history + [
        {"role": "user", "content": asr_text},
        {"role": "assistant", "content": full_response},
    ]

    # ── 6. 清理当前帧 + 返回 ──
    # key_frame 阅后即焚 — 绝不进入 LangGraph 持久化状态
    return {
        "vlm_response": full_response,
        "visual_summary": new_summary,
        "messages": new_messages,
        "key_frame": "",
        "error": "",
    }


async def tts_node(state: ConversationState) -> dict:
    """语音合成: vlm_response → tts_audio。纯 I/O，不碰状态。

    [未来全双工锚点] Phase 5:
    当前 tts_node 等 vlm_node 完全执行完毕才启动 (LangGraph 串行)。
    未来通过 asyncio.Queue 或 AsyncGenerator 边收 VLM 句子边并发合成，
    降低首字响应延迟 (TTFB)。
    """
    text = state.vlm_response
    if not text:
        return {"error": "No VLM response to synthesize"}

    audio_bytes = await synthesize(text)
    return {"tts_audio": audio_bytes, "error": ""}


# ── 路由函数 (条件边) ──────────────────────────────────────────

def _route_after_asr(state: ConversationState) -> str:
    """ASR 节点后路由: 有识别文本 → VLM, 否则 → END (短路)"""
    if state.asr_text and not state.error:
        return "vlm"
    return END


def _route_after_vlm(state: ConversationState) -> str:
    """VLM 节点后路由: 有回复文本 → TTS, 否则 → END (短路)"""
    if state.vlm_response and not state.error:
        return "tts"
    return END


# ── 图构建 ─────────────────────────────────────────────────────

def build_graph() -> Any:
    """编译 LangGraph 管线 (无 checkpointer — 每次 invoke 都是全新执行)。

    路由逻辑:
        START → ASR ─┬─ [有文本] → VLM ─┬─ [有回复] → TTS → END
                     │                  │
                     └─ [失败/静音] → END
                                        └─ [失败] → END

    不使用 checkpointer — 每轮 start_turn 都从干净状态开始执行，
    避免 LangGraph 从历史 checkpoint 中回放旧节点的输出导致
    ASR/VLM 始终返回相同结果。
    """
    builder = StateGraph(ConversationState)

    builder.add_node("asr", asr_node)
    builder.add_node("vlm", vlm_node)
    builder.add_node("tts", tts_node)

    builder.add_edge(START, "asr")

    # ASR → 条件路由: 有文本 → VLM, 否则短路到 END
    builder.add_conditional_edges("asr", _route_after_asr, {
        "vlm": "vlm",
        END: END,
    })

    # VLM → 条件路由: 有回复 → TTS, 否则短路到 END
    builder.add_conditional_edges("vlm", _route_after_vlm, {
        "tts": "tts",
        END: END,
    })

    builder.add_edge("tts", END)

    return builder.compile()


# ── 管线执行器 ─────────────────────────────────────────────────

class PipelineExecutor:
    """管理单次会话的管线生命周期。

    使用方式:
        executor = PipelineExecutor()
        result = await executor.execute(
            audio_b64="...",
            frame_b64="...",
        )
    """

    def __init__(self, thread_id: str = "vision-talk-session"):
        self.graph = build_graph()
        self.state = initial_state()
        self._thread_id = thread_id
        self._config = {"configurable": {"thread_id": thread_id}}

        # 打断信号
        self.interrupt_event = asyncio.Event()
        self.interrupt_event.clear()

    # ── 生命周期 ──

    def reset(self) -> None:
        """重置为全新会话 (清空历史 + 记忆)"""
        self.state = initial_state()
        self.interrupt_event.clear()

    def interrupt(self) -> None:
        """设置打断标志 (由 WebSocket 层在收到 interrupt 消息时调用)"""
        self.interrupt_event.set()

    def is_interrupted(self) -> bool:
        return self.interrupt_event.is_set()

    # ── 核心执行 ──

    async def execute(
        self,
        audio_b64: str,
        frame_b64: str = "",
        text_queue: asyncio.Queue | None = None,
        audio_queue: asyncio.Queue | None = None,
        ws_sender: Any = None,
    ) -> ConversationState:
        """
        执行一轮完整对话管线 (ASR → VLM → TTS)。

        Args:
            audio_b64:  Base64 用户语音 (必传)
            frame_b64:  Base64 摄像头关键帧 (可选)
            text_queue: VLM token 流式推送队列 (已弃用，用 ws_sender)
            audio_queue: TTS 音频流式推送队列 (已弃用，用 ws_sender)
            ws_sender:  旁路推流回调 async fn(dict) — 用于全双工流式推送

        Returns:
            更新后的 ConversationState (含 asr_text/vlm_response/tts_audio)

        Raises:
            ValueError: audio_b64 为空 (前置条件不满足)
        """
        if not audio_b64:
            raise ValueError("audio_b64 is required — pipeline cannot run without user speech")

        if self.is_interrupted():
            self.reset()
            return self.state

        # 注入旁路推流回调 (ContextVar token 模式，保证 finally 恢复)
        if ws_sender is None:
            ws_sender = _DEFAULT_VOID_SENDER
        token = _set_ws_sender(ws_sender)

        # 注入本轮的输入到状态中
        self.state.audio_chunk = audio_b64
        self.state.key_frame = frame_b64 or ""
        self.state.error = ""

        # 清空中间产物 (上一轮的残留)
        self.state.asr_text = ""
        self.state.vlm_response = ""
        self.state.tts_audio = b""

        # ── 执行 LangGraph ──
        try:
            result = await self.graph.ainvoke(
                self.state.model_dump(),
                config=self._config,
            )

            self.state = ConversationState(**result)
            return self.state

        except Exception as e:
            self.state.error = str(e)
            logger.exception("Pipeline 执行失败: %s", e)
            return self.state

        finally:
            _clear_ws_sender(token)  # 通过 token 恢复，避免跨连接污染
