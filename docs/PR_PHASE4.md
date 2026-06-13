# PR4 — 前后端联调

> 打通端到端对话闭环：用户说话 → AI 看到/听到 → 语音回复。完善 UI 交互与异常处理。

---

## Commit 1: 对话 UI 组件

**变更：**
- 新建 `src/components/ChatPanel.tsx` — 消息气泡列表
- 新建 `src/components/StatusBar.tsx` — 连接状态、VAD 状态、帧率指示
- 新建 `src/components/AudioPlayer.tsx` — 流式音频播放器
- 修改 `src/App.tsx` — 整合 Camera + ChatPanel + StatusBar 布局

**文件：**
- `frontend/src/components/ChatPanel.tsx`
- `frontend/src/components/StatusBar.tsx`
- `frontend/src/components/AudioPlayer.tsx`
- `frontend/src/App.tsx`
- `frontend/src/App.css`

```
┌─────────────────────────────┐
│  StatusBar: 🟢已连接 | 🔊说话中 | 15fps │
├──────────────────┬──────────┤
│                  │ 用户: 这是什么？    │
│   Camera 画面    │ AI: 看起来是一本书...│
│                  │          │
│                  │ [消息输入框]        │
└──────────────────┴──────────┘
```

**验证：** 页面渲染正确，布局响应式正常。

---

## Commit 2: 端到端管线联调

**变更：**
- `App.tsx` 串联完整数据流：
  - Camera 抓帧 → RingBuffer → 帧差分 → 关键帧
  - VAD 检测语音 → 采集音频
  - 关键帧 + 音频 → WebSocket → 后端
  - 后端 ASR → VLM → TTS → WebSocket → 前端
  - AudioPlayer 播放 TTS 语音
- ChatPanel 实时显示对话文本
- 后端 `websocket.py` 完整消息路由

**文件：**
- `frontend/src/App.tsx` — 完整管线串联
- `frontend/src/hooks/usePipeline.ts` — 管线状态管理 hook
- `backend/app/routes/websocket.py` — 消息分发

```
用户说 "你好" 
  → 前端 VAD 触发 → 采集音频 + 抓关键帧
  → WebSocket → 后端 LangGraph
  → ASR: "你好" → VLM: "你好！我看到你了" → TTS: 合成语音
  → WebSocket → 前端 AudioPlayer 播放
  → ChatPanel 显示对话
```

**验证：** 完整对话一轮，听到 AI 语音回复。

---

## Commit 3: 错误处理 & 重连

**变更：**
- `useWebSocket.ts` 添加指数退避重连（1s → 2s → 4s → 8s，最大 30s）
- `StatusBar` 显示重连倒计时
- 后端 WebSocket 异常时返回结构化错误消息
- ChatPanel 显示错误提示（网络断开、API 超时等）
- 前端全局 error boundary

**文件：**
- `frontend/src/hooks/useWebSocket.ts` — 重连逻辑
- `frontend/src/components/StatusBar.tsx` — 重连状态
- `frontend/src/components/ChatPanel.tsx` — 错误消息
- `frontend/src/components/ErrorBoundary.tsx`

```
连接断开 → StatusBar 显示 "⚠️ 重连中 (3s)" → 自动重连 → "🟢 已连接"
API 超时 → ChatPanel 显示 "⏱️ AI 响应超时，请重试"
```

**验证：** 手动断网 → UI 显示重连 → 恢复后自动续连。

---

## PR 验证 Checklist

- [ ] Camera + ChatPanel + StatusBar 布局完整
- [ ] 说话 → VAD 触发 → 帧采集 → 发送
- [ ] AI 语音回复正常播放
- [ ] ChatPanel 实时显示对话记录
- [ ] 断网自动重连，恢复后正常对话
- [ ] API 超时/错误有友好提示
- [ ] 组件异常不导致白屏
