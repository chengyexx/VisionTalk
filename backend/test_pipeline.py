"""
连通性测试: 验证 LangGraph 骨架可以正常编译和执行。
mock 节点输出 print，确保图跑通无异常。
"""
import asyncio
import sys
sys.path.insert(0, ".")


async def test_build():
    """测试: 图编译无报错"""
    from app.core.pipeline import build_graph, ConversationState
    graph = build_graph()
    print("[TEST] build_graph() — PASSED")
    return graph


async def test_multimodal_message_structure():
    """测试: assemble_multimodal_message 输出符合 OpenAI/LiteLLM 规范"""
    from app.core.vlm import assemble_multimodal_message

    msg = assemble_multimodal_message(
        asr_text="这是什么？",
        key_frame="<<BASE64_JPEG>>",
        visual_summary="一块开发板",
    )

    assert msg["role"] == "user"
    assert isinstance(msg["content"], list), f"content should be list, got {type(msg['content'])}"
    content_types = [c["type"] for c in msg["content"]]
    assert "text" in content_types
    assert "image_url" in content_types
    print("[TEST] Multimodal message structure — PASSED")


async def test_silence():
    """测试: 音频过短 → ASR 返回空字符串 (防御性)"""
    from app.core.pipeline import PipelineExecutor

    executor = PipelineExecutor(thread_id="test-silence")
    result = await executor.execute(audio_b64="short")
    assert result.error != "" or result.asr_text == "", \
        f"Expected error or empty ASR for short audio, got asr_text='{result.asr_text}'"
    print("[TEST] Silence defense — PASSED")


async def test_split_sentences():
    """测试: TTS 分句逻辑"""
    from app.core.tts import split_sentences

    result = split_sentences("我看到一块板子。上面有红灯！这是什么？")
    assert len(result) == 3, f"Expected 3 sentences, got {len(result)}: {result}"
    assert result[0] == "我看到一块板子。"
    assert result[2] == "这是什么？"
    print("[TEST] Split sentences — PASSED")


async def test_single_turn():
    """测试: 单轮 pipeline 执行"""
    from app.core.pipeline import PipelineExecutor, ConversationState

    executor = PipelineExecutor(thread_id="test-001")

    result = await executor.execute(
        audio_b64="<<MOCK_AUDIO_BASE64>>",
        frame_b64="<<MOCK_FRAME_BASE64>>",
    )

    assert result.error == "", f"Unexpected error: {result.error}"
    assert result.asr_text != "", f"ASR should not be empty: got '{result.asr_text}'"
    # VLM mock tokens: "我看到画面中是一块绿色的PCB开发板，上面有一个红色LED在闪烁。这通常表示电源正常工作。"
    assert "PCB" in result.vlm_response, f"VLM: {result.vlm_response}"
    assert result.tts_audio == b"MOCK_AUDIO_PAYLOAD", f"TTS: {result.tts_audio}"
    # VLM 节点是消息历史的唯一操盘者
    assert len(result.messages) >= 2, f"messages should have user+assistant, got {len(result.messages)}"
    assert result.messages[-2]["role"] == "user"
    assert result.messages[-1]["role"] == "assistant"
    # key_frame 应在 VLM 处理后清除
    assert result.key_frame == "", f"key_frame should be cleared, got {len(result.key_frame)} chars"
    print("[TEST] Single turn — PASSED")


async def test_multi_turn():
    """测试: 多轮对话状态延续"""
    from app.core.pipeline import PipelineExecutor

    executor = PipelineExecutor(thread_id="test-002")

    # Turn 1
    r1 = await executor.execute(audio_b64="<<AUDIO_1>>", frame_b64="<<FRAME_1>>")
    assert r1.error == ""
    msg_count_1 = len(r1.messages)
    print(f"  Turn 1: asr={r1.asr_text}, vlm={r1.vlm_response[:30]}..., messages={msg_count_1}")

    # Turn 2 — 消息应该累积
    r2 = await executor.execute(audio_b64="<<AUDIO_2>>", frame_b64="<<FRAME_2>>")
    assert r2.error == ""
    msg_count_2 = len(r2.messages)
    print(f"  Turn 2: asr={r2.asr_text}, vlm={r2.vlm_response[:30]}..., messages={msg_count_2}")
    assert msg_count_2 > msg_count_1, f"Messages should accumulate: {msg_count_2} > {msg_count_1}"

    print("[TEST] Multi-turn — PASSED")


async def test_precondition():
    """测试: 空 audio 触发 ValueError (前置条件校验)"""
    from app.core.pipeline import PipelineExecutor

    executor = PipelineExecutor(thread_id="test-003")
    try:
        await executor.execute(audio_b64="")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        print(f"[TEST] Precondition check — PASSED (got: {e})")


async def test_reset():
    """测试: reset() 清空状态"""
    from app.core.pipeline import PipelineExecutor, initial_state, ConversationState

    executor = PipelineExecutor(thread_id="test-004")
    await executor.execute(audio_b64="<<MOCK_AUDIO_12345>>")
    executor.reset()

    assert executor.state == initial_state()
    print("[TEST] Reset — PASSED")


async def main():
    print("=" * 50)
    print("Vision Talk — Pipeline Connectivity Tests")
    print("=" * 50)
    print()

    await test_build()
    await test_multimodal_message_structure()
    await test_split_sentences()
    await test_silence()
    await test_single_turn()
    await test_multi_turn()
    await test_precondition()
    await test_reset()

    print()
    print("=" * 50)
    print("ALL TESTS PASSED")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
