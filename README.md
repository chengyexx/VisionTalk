# Vision Talk — AI 视觉对话助手

实时摄像头 + 语音对话。AI 看到你的画面、听懂你的话、用语音回复你。

## 演示视频

🎬 **Vision Talk — 集成视觉听觉的聊天机器人**：https://www.bilibili.com/video/BV1qqLX6QEqH/

## 架构

```
React 19 (TypeScript, Vite)
    │
    │  WebSocket (ws://localhost:8000/ws)
    ↓
FastAPI + LangGraph 全双工管线:
    用户语音 → ASR (Groq Whisper) → VLM (Qwen VL / DeepSeek) → TTS (Edge TTS) → 语音播放
```

旁路推流机制：VLM 每输出一个字就通过 WebSocket 实时推到前端打字机，不等待整句结束。

## 功能

- **实时摄像头** — 帧差分去重，只推关键帧，节省带宽
- **VAD 语音检测** — 自动检测说话起止，无需按钮
- **AI 语音回复** — Microsoft Edge TTS 自然中文语音
- **Barge-in 打断** — AI 说话时可随时插嘴打断
- **流式打字机** — 支持全屏模式，无延迟看到 AI 思考过程
- **多模型热切换** — 支持 Qwen VL Max/Plus (多模态) 和 DeepSeek V3 (纯文本)
- **记忆压缩** — 每轮结束后用纯文本摘要记录画面内容 (阅后即焚)

## 技术栈

| 层 | 技术 | 备注 |
|----|------|------|
| 前端 | React 19, TypeScript, Vite | |
| VAD | @ricky0123/vad-web | 浏览器端语音活动检测 |
| 后端框架 | FastAPI + Uvicorn | |
| 状态机 | LangGraph | ASR → VLM → TTS 条件路由 |
| 模型网关 | LiteLLM | 统一 API，支持多模型 |
| ASR 语音识别 | Groq Whisper (whisper-large-v3) | 免费额度 |
| VLM 多模态推理 | Qwen VL Max / Qwen VL Plus | 支持图片输入 |
| 纯文本推理 | DeepSeek V3 | 不支持图片 |
| TTS 语音合成 | Microsoft Edge TTS (zh-CN-XiaoxiaoNeural) | 免费，无需 API Key |
| 记忆压缩 | DeepSeek Chat | 纯文本摘要 |

## 快速开始

### 1. 后端

```bash
cd backend
python -m venv venv
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置 API Key
cp .env.example .env
# 编辑 .env 填写:
#   DASHSCOPE_API_KEY (Qwen 多模态)
#   OPENAI_API_KEY    (Groq Whisper ASR)
#   DEEPSEEK_API_KEY  (DeepSeek 纯文本 + 摘要)

# 启动
python main.py
# → ws://0.0.0.0:8000/ws
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

打开 `http://localhost:5173`，允许摄像头和麦克风权限，直接开始说话。

## 项目结构

```
backend/
├── main.py                # uvicorn 启动入口
├── requirements.txt
├── .env                   # API Key 配置
├── app/
│   ├── main.py            # FastAPI app + lifespan
│   ├── config.py          # 模型列表 + 环境变量
│   └── api/
│       └── websocket.py   # WebSocket 全双工通信
│   └── core/
│       ├── pipeline.py    # LangGraph 管线编排 (ASR→VLM→TTS)
│       ├── asr.py         # Groq Whisper 语音识别
│       ├── vlm.py         # 多模态推理 + 记忆压缩
│       ├── tts.py         # Edge TTS 语音合成
│       └── logging_config.py

frontend/
├── src/
│   ├── App.tsx            # 主界面
│   ├── components/
│   │   └── Camera.tsx     # 摄像头组件
│   └── hooks/
│       ├── useConversation.ts  # 对话状态 + WS 消息分发
│       ├── useTurnPipeline.ts  # VAD + 音频采集 + 帧差分
│       ├── useAudioPlayback.ts # TTS 播放队列
│       ├── useAudioCapture.ts  # 麦克风采集
│       ├── useWebSocket.ts     # WS 连接 + 自动重连
│       ├── useVAD.ts           # VAD 状态管理
│       └── useKeyFrameDetector.ts # 关键帧检测
├── vite.config.ts
└── package.json
```

## WebSocket 协议

| 类型 | 方向 | 说明 |
|------|------|------|
| `start_turn` | 前端→后端 | 发起新一轮对话 (audio_b64 + image_b64) |
| `interrupt` | 前端→后端 | 打断当前 AI 输出 |
| `state_change` | 后端→前端 | 管线状态 (thinking/idle) |
| `asr_final` | 后端→前端 | ASR 识别结果 (用户说的话) |
| `vlm_token` | 后端→前端 | VLM 流式文本 token (打字机效果) |
| `tts_chunk` | 后端→前端 | TTS 语音分片 (Base64 MP3) |
| `turn_end` | 后端→前端 | 一轮对话结束 (包含完整回复) |
| `error` | 后端→前端 | 管线/推理错误 |

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 + 当前模型状态 |
| POST | `/api/model/switch` | 切换 VLM 模型 |
| WS | `/ws` | WebSocket 全双工对话 |

