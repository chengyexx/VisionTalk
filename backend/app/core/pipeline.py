"""
Vision Talk — LangGraph 管线编排
ASR → VLM → TTS 状态机 (PR3 Commit 2 骨架)。

Graph: START → asr → vlm → tts → END

设计原则:
- 严格 Pydantic 状态模型 — 所有字段有明确类型和默认值
- 输入前置 — key_frame / audio_chunk 必须在管线调用前注入 State
- 节点不主动拉取外部数据 — 所有依赖从 State 读取
"""
import asyncio
import base64
from typing import Any
from pydantic import BaseModel, Field

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver


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
    """语音识别: audio_chunk → asr_text"""
    audio = state.audio_chunk
    if not audio:
        return {"error": "No audio data in state"}
    # TODO Step 3: 接入真实 ASR
    print(f"[ASR Mock] Received audio ({len(audio)} chars)")
    return {"asr_text": "[MOCK] 用户识别文本", "error": ""}


async def vlm_node(state: ConversationState) -> dict:
    """多模态推理: key_frame + asr_text + history → vlm_response"""
    frame_len = len(state.key_frame)
    text = state.asr_text
    print(f"[VLM Mock] frame={frame_len} chars, text='{text}'")
    # TODO Step 4: 接入真实 VLM (vision streaming)
    return {
        "vlm_response": f"[MOCK] 看到画面并针对'{text}'的回复",
        "error": "",
    }


async def tts_node(state: ConversationState) -> dict:
    """语音合成: vlm_response → tts_audio"""
    response = state.vlm_response
    if not response:
        return {"error": "No VLM response to synthesize"}
    print(f"[TTS Mock] synthesizing '{response[:40]}...'")
    # TODO Step 5: 接入真实 TTS (sentence-level streaming)
    return {"tts_audio": b"MOCK_AUDIO", "error": ""}


# ── 图构建 ─────────────────────────────────────────────────────

def build_graph() -> Any:
    """编译 LangGraph 管线"""
    builder = StateGraph(ConversationState)

    builder.add_node("asr", asr_node)
    builder.add_node("vlm", vlm_node)
    builder.add_node("tts", tts_node)

    builder.add_edge(START, "asr")
    builder.add_edge("asr", "vlm")
    builder.add_edge("vlm", "tts")
    builder.add_edge("tts", END)

    memory = MemorySaver()
    return builder.compile(checkpointer=memory)


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
    ) -> ConversationState:
        """
        执行一轮完整对话管线 (ASR → VLM → TTS)。

        Args:
            audio_b64:  Base64 用户语音 (必传)
            frame_b64:  Base64 摄像头关键帧 (可选)
            text_queue: VLM token 流式推送队列 (可选)
            audio_queue: TTS 音频流式推送队列 (可选)

        Returns:
            更新后的 ConversationState (含 asr_text/vlm_response/tts_audio)

        Raises:
            ValueError: audio_b64 为空 (前置条件不满足)
        """
        # ── 前置输入校验 (Pydantic 层面的强约束) ──
        if not audio_b64:
            raise ValueError("audio_b64 is required — pipeline cannot run without user speech")

        if self.is_interrupted():
            self.reset()
            return self.state

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
                self.state.model_dump(),  # Pydantic → dict
                config=self._config,
            )

            # 将结果反序列化回 Pydantic 模型
            self.state = ConversationState(**result)
            return self.state

        except Exception as e:
            self.state.error = str(e)
            print(f"[Pipeline] Execution failed: {e}")
            return self.state
