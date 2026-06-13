"""
LangGraph state machine for Vision Talk conversation pipeline.

Flow: ASR → VLM → TTS → END
With checkpoint support for fault recovery.
"""

from typing import TypedDict

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver


class ConversationState(TypedDict):
    """State carried through the conversation pipeline."""

    # Current turn inputs
    audio_chunk: bytes          # Raw audio from VAD trigger
    key_frame: str              # Current key frame (Base64 JPEG)

    # Intermediate results
    asr_text: str               # Speech-to-text output
    vlm_response: str           # Visual LLM reply
    tts_audio: bytes            # Synthesized speech

    # Conversation history
    messages: list[dict]        # Chat history (text-only, no historical images)
    visual_summary: str         # Text summary of last frame (for token compression)

    # Control
    interrupted: bool           # True if user barge-in detected


def asr_node(state: ConversationState) -> dict:
    """Placeholder: transcribe audio to text."""
    # TODO: PR3-3 — integrate ASR service
    return {"asr_text": ""}


def vlm_node(state: ConversationState) -> dict:
    """Placeholder: visual understanding + response generation."""
    # TODO: PR3-4 — integrate VLM service
    return {"vlm_response": ""}


def tts_node(state: ConversationState) -> dict:
    """Placeholder: synthesize speech from text."""
    # TODO: PR3-5 — integrate TTS service
    return {"tts_audio": b""}


def build_graph() -> StateGraph:
    """Build and compile the Vision Talk conversation graph."""
    builder = StateGraph(ConversationState)

    # Nodes
    builder.add_node("asr", asr_node)
    builder.add_node("vlm", vlm_node)
    builder.add_node("tts", tts_node)

    # Edges: linear pipeline
    builder.set_entry_point("asr")
    builder.add_edge("asr", "vlm")
    builder.add_edge("vlm", "tts")
    builder.add_edge("tts", END)

    # Compile with memory checkpoint for fault recovery
    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)


# Singleton graph instance
graph = build_graph()
