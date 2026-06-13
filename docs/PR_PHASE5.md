# PR5 — 高级特性

> 语音打断、多模型切换、全双工流式优化 — 把体验推到接近真人对话。

---

## Commit 1: 语音打断 (Barge-in)

**变更：**
- 前端 `useVAD.ts`：AI 播放期间 VAD 检测到用户说话 → 发送 `interrupt` 信号
- 前端 `AudioPlayer.tsx`：收到 interrupt 回调 → 立即停止播放
- 后端 `websocket.py`：接收 `interrupt` 消息 → 调用 `graph.interrupt()`
- 后端 `graph.py`：LangGraph 状态机重置，清空当前 TTS 队列
- 中断后自动进入新一轮对话（重新采集音频 + 关键帧）

**文件：**
- `frontend/src/hooks/useVAD.ts` — 播放期间 VAD 监听
- `frontend/src/components/AudioPlayer.tsx` — 停止播放
- `backend/app/routes/websocket.py` — interrupt 消息处理
- `backend/app/services/graph.py` — 状态重置

```
AI 正在说话...
  ↓ 用户插话 "不是，我说的是..."
前端 VAD 检测 → send({ type: "interrupt" })
后端 ⏹️ 停止 TTS → 重置 LangGraph
前端 ⏹️ 停止播放 → 采集新音频
  ↓ 新一轮 ASR → VLM → TTS
AI 重新回答（基于新输入）
```

**验证：** AI 说话时用户插话 → 立即停止 → 重新回答。

---

## Commit 2: 多模型切换 UI

**变更：**
- 前端新建 `src/components/ModelSelector.tsx` — 下拉选择器
- 前端 `src/hooks/useModelConfig.ts` — 管理当前模型选择状态
- 后端新增 `POST /api/model/switch` 端点
- 后端 `llm_client.py` — 运行时动态切换模型
- 支持 DeepSeek / GPT-4o / Qwen-VL / Claude 等

**文件：**
- `frontend/src/components/ModelSelector.tsx`
- `frontend/src/hooks/useModelConfig.ts`
- `backend/app/routes/model.py`
- `backend/app/services/llm_client.py`

```
ModelSelector:
  ┌──────────────────────┐
  │ DeepSeek     ▼      │
  │ ├ DeepSeek-V3        │  ← 默认
  │ ├ GPT-4o             │
  │ ├ Qwen-VL-Max        │
  │ └ Claude-3.5-Sonnet  │
  └──────────────────────┘
```

**验证：** 切换模型后，下一轮对话使用新模型。

---

## Commit 3: 全双工流式优化

**变更：**
- 后端 VLM 节点：收到首 token 立即开始 TTS 合成（不等完整回复）
- 后端 `tts.py`：支持流式输入，边接收文本边合成语音
- 前端 `AudioPlayer.tsx`：首 chunk 到达即开始播放，降低 TTFB
- WebSocket 多路复用：音频 chunk + 文本 token 同一通道交错传输
- 前端按消息类型分发给 AudioPlayer / ChatPanel

**文件：**
- `backend/app/services/vlm.py` — 流式 yield 给 TTS
- `backend/app/services/tts.py` — 流式输入合成
- `backend/app/routes/websocket.py` — 多路复用
- `frontend/src/components/AudioPlayer.tsx` — 流式播放
- `frontend/src/hooks/usePipeline.ts` — 消息分发

```
优化前：VLM 完整回复(3s) → TTS(2s) → 播放    TTFB ≈ 5s
优化后：VLM 首 token(0.5s) → TTS 开始 → 播放   TTFB ≈ 1s

消息流：
  ← { type: "audio", chunk: bytes }
  ← { type: "text", token: "你" }
  ← { type: "audio", chunk: bytes }
  ← { type: "text", token: "好" }
  ...
```

**验证：** 首字节响应时间 < 2 秒，语音流畅不卡顿。

---

## PR 验证 Checklist

- [ ] AI 说话时插话 → 立即停止 → 重新回答
- [ ] 模型下拉列表显示所有可用模型
- [ ] 切换模型后对话正常使用新模型
- [ ] TTFB < 2 秒
- [ ] 文字逐字显示 + 语音同步播放
- [ ] 无音频卡顿、断句错误
