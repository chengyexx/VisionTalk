"""
记忆压缩专项测试 — 验证「阅后即焚」架构。

核心断言:
1. API Payload (发给 VLM) 包含当前帧图片 — 瞬态，不进 messages
2. LangGraph messages 历史永远只存纯文本 — 零 Base64 残留
3. visual_summary 每轮更新 — 最新一句话摘要
4. key_frame 每轮后清空 — 阅后即焚
5. 多轮对话 State 体积线性增长 — Token 恒定可控
"""
import asyncio
import sys
sys.path.insert(0, ".")

from app.core.pipeline import PipelineExecutor, initial_state


def _has_base64(state_messages: list[dict]) -> bool:
    """检查 messages 中是否有 Base64 图片残留 (绝不应有)"""
    for msg in state_messages:
        content = msg.get("content", "")
        if isinstance(content, str) and "base64" in content:
            return True
        if isinstance(content, list):
            for part in content:
                if part.get("type") == "image_url":
                    return True
    return False


async def test_api_payload_has_image():
    """测试: VLM API 请求中包含当前帧图片 (瞬态 payload)"""
    from app.core.vlm import assemble_multimodal_message

    msg = assemble_multimodal_message(
        asr_text="这是什么？",
        key_frame="<<FAKE_JPEG_BASE64>>",
        visual_summary=None,
    )
    content = msg["content"]
    has_image = any(c.get("type") == "image_url" for c in content)
    assert has_image, "API payload must include image for VLM to see"
    print("[TEST] API payload has image — PASSED")


async def test_messages_never_store_image():
    """测试: 多轮对话后 messages 中绝不出现 Base64"""
    executor = PipelineExecutor(thread_id="mem-test-001")

    for i in range(3):
        result = await executor.execute(
            audio_b64=f"<<AUDIO_ROUND_{i}>>",
            frame_b64=f"<<FRAME_ROUND_{i}>>",
        )
        assert result.error == "", f"Round {i} failed: {result.error}"

    assert not _has_base64(result.messages), \
        "messages 中检测到 Base64 图片残留 — 阅后即焚失败！"
    print(f"[TEST] No image in messages after 3 rounds ({len(result.messages)} msgs) — PASSED")


async def test_visual_summary_updates():
    """测试: visual_summary 每轮更新"""
    executor = PipelineExecutor(thread_id="mem-test-002")

    r1 = await executor.execute(audio_b64="<<AUDIO_1>>", frame_b64="<<FRAME_1>>")
    summary_1 = r1.visual_summary
    assert summary_1 != "", "Round 1: visual_summary should not be empty"
    assert "摘要" in summary_1, f"Round 1 summary: {summary_1}"

    r2 = await executor.execute(audio_b64="<<AUDIO_2>>", frame_b64="<<FRAME_2>>")
    summary_2 = r2.visual_summary
    assert summary_2 != "", "Round 2: visual_summary should not be empty"

    print(f"  Round 1 summary: {summary_1}")
    print(f"  Round 2 summary: {summary_2}")
    print("[TEST] Visual summary updates — PASSED")


async def test_key_frame_cleared():
    """测试: key_frame 每轮后必清空 (阅后即焚核心)"""
    executor = PipelineExecutor(thread_id="mem-test-003")

    result = await executor.execute(
        audio_b64="<<MOCK_AUDIO_12345>>",
        frame_b64="<<LARGE_FRAME_12345>>",
    )
    assert result.key_frame == "", \
        f"key_frame should be cleared, got {len(result.key_frame)} chars"
    print("[TEST] key_frame cleared after each round — PASSED")


async def test_token_linear_growth():
    """测试: 多轮对话 State 体积线性增长 (非指数)

    验证核心指标:
    - messages 条数 = 轮数 × 2 (user + assistant per round)
    - messages 总字符数线性增长
    - visual_summary 始终是单句话 (非累积历史)
    """
    executor = PipelineExecutor(thread_id="mem-test-004")
    sizes = []

    for i in range(4):
        result = await executor.execute(
            audio_b64=f"<<AUDIO_R{i}>>",
            frame_b64=f"<<FRAME_R{i}>>",
        )
        assert result.error == "", f"Round {i}: {result.error}"

        # 计算 messages 总字符数 (如果存了图片会是数万字符)
        total_chars = sum(
            len(str(msg.get("content", "")))
            for msg in result.messages
            if isinstance(msg.get("content"), str)
        )
        sizes.append(total_chars)

        print(f"  Round {i}: messages={len(result.messages)}, "
              f"chars={total_chars}, summary_len={len(result.visual_summary)}")

    # 线性验证: 轮数 4x → messages 8 条, 每轮增长 ~2 条
    assert len(result.messages) == 8, f"Expected 8 messages, got {len(result.messages)}"

    # 体积增长应为线性 (如果存了图片, 第一条就数千字符)
    assert sizes[0] < 500, f"Round 0 too large ({sizes[0]} chars) — image leaked into messages?"
    assert sizes[-1] < 2000, f"Round 3 too large ({sizes[-1]} chars) — exponential growth?"

    # 增长率: 第 1 轮到第 3 轮的增长不应超过 5 倍 (指数增长会是 10x+)
    growth_ratio = sizes[-1] / max(sizes[0], 1)
    assert growth_ratio < 5, f"Growth ratio {growth_ratio:.1f}x — possible image leak"

    print(f"[TEST] Linear token growth (ratio={growth_ratio:.1f}x) — PASSED")


async def test_visual_summary_used_in_context():
    """测试: visual_summary 在下轮被用作上下文 [之前看到的]"""
    executor = PipelineExecutor(thread_id="mem-test-005")

    # Round 1: 建立摘要
    r1 = await executor.execute(audio_b64="<<AUDIO_1>>", frame_b64="<<FRAME_1>>")
    assert r1.visual_summary != ""

    # Round 2: 摘要应出现在下一轮的 API payload 中
    from app.core.vlm import assemble_multimodal_message
    msg = assemble_multimodal_message(
        asr_text="继续看",
        key_frame="<<FRAME_2>>",
        visual_summary=r1.visual_summary,
    )
    content_texts = [
        c["text"] for c in msg["content"]
        if c.get("type") == "text"
    ]
    has_context = any(r1.visual_summary in t for t in content_texts)
    assert has_context, f"visual_summary not used in next round context: {content_texts}"

    print(f"[TEST] Visual summary as context — PASSED")


async def main():
    print("=" * 60)
    print("Vision Talk — Memory Compression Tests (阅后即焚)")
    print("=" * 60)
    print()

    await test_api_payload_has_image()
    await test_messages_never_store_image()
    await test_visual_summary_updates()
    await test_key_frame_cleared()
    await test_token_linear_growth()
    await test_visual_summary_used_in_context()

    print()
    print("=" * 60)
    print("ALL MEMORY COMPRESSION TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
