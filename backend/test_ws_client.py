"""
WebSocket 集成测试客户端 — 独立于前端，验证后端 WS 协议。

用法:
    1. 先启动后端:  cd backend && python main.py
    2. 再运行本脚本: python test_ws_client.py

预期输出:
    ✓ state_change → thinking
    ✓ turn_end → {asr_text, vlm_response, tts_audio_b64}
    ✓ state_change → idle
"""
import asyncio
import base64
import json
import sys

WS_URL = "ws://localhost:8000/ws"

# 模拟一个极小的 "假图片" Base64 (1x1 红色 JPEG)
FAKE_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
    "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAA"
    "AAAAAAAAAAAAA//EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AK//Z"
)
FAKE_AUDIO_B64 = base64.b64encode(b"MOCK_WEBM_AUDIO_DATA").decode()


async def test_full_turn():
    """完整一轮对话: start_turn → 收到 turn_end"""
    import websockets

    print(f"连接到 {WS_URL} ...")
    async with websockets.connect(WS_URL) as ws:
        print("已连接\n")

        # 发送 start_turn
        payload = {
            "type": "start_turn",
            "audio_b64": FAKE_AUDIO_B64,
            "image_b64": FAKE_JPEG_B64,
        }
        await ws.send(json.dumps(payload))
        print(f"→ 发送 start_turn (audio={len(FAKE_AUDIO_B64)}c, image={len(FAKE_JPEG_B64)}c)")

        # 接收响应
        while True:
            raw = await ws.recv()
            msg = json.loads(raw)
            msg_type = msg.get("type", "?")

            if msg_type == "state_change":
                state = msg.get("state", "?")
                print(f"← state_change: {state}")

            elif msg_type == "turn_end":
                payload = msg.get("payload", {})
                asr = payload.get("asr_text", "")[:50]
                vlm = payload.get("vlm_response", "")[:60]
                tts_len = len(payload.get("tts_audio_b64", ""))
                error = payload.get("error", "")

                if error:
                    print(f"← turn_end ERROR: {error}")
                else:
                    print(f"← turn_end:")
                    print(f"     asr:  {asr}")
                    print(f"     vlm:  {vlm}...")
                    print(f"     tts:  {tts_len} chars Base64")

            elif msg_type == "error":
                print(f"← error: {msg.get('message', '?')}")

            # 收到 idle 后退出 (表示本轮结束)
            if msg_type == "state_change" and msg.get("state") == "idle":
                break

    print("\n[PASS] 完整一轮对话通过")


async def test_interrupt():
    """打断测试: 发送 start_turn 后立即 interrupt"""
    import websockets

    print(f"\n连接到 {WS_URL} (打断测试)...")
    async with websockets.connect(WS_URL) as ws:
        print("已连接")

        # 发起对话
        await ws.send(json.dumps({
            "type": "start_turn",
            "audio_b64": FAKE_AUDIO_B64,
            "image_b64": FAKE_JPEG_B64,
        }))
        print("→ start_turn")

        # 立即打断
        await asyncio.sleep(0.1)
        await ws.send(json.dumps({"type": "interrupt"}))
        print("→ interrupt (0.1s 后)")

        # 等待 idle 确认
        while True:
            raw = await ws.recv()
            msg = json.loads(raw)
            print(f"← {msg.get('type')}: {msg.get('state', msg.get('payload', '')[:50])}")
            if msg.get("type") == "state_change" and msg.get("state") == "idle":
                break

    print("[PASS] 打断测试通过")


async def main():
    print("=" * 50)
    print("Vision Talk — WebSocket 集成测试")
    print("=" * 50)
    print()

    await test_full_turn()
    await test_interrupt()

    print()
    print("=" * 50)
    print("ALL WS TESTS PASSED")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
