# Vision Talk

AI 视觉对话助手 — 打开摄像头与麦克风，让 AI 看到你看到的、听到你说的，并自然回应。

## 架构

```
┌─────────────────────────────────────┐
│  Frontend (React + Vite)           │
│  ┌───────────┐  ┌────────────────┐ │
│  │ Camera    │  │ Microphone     │ │
│  │ (webcam)  │  │ (WebRTC)       │ │
│  └─────┬─────┘  └──────┬─────────┘ │
│        │               │           │
│  ┌─────┴───────────────┴─────────┐ │
│  │ Ring Buffer + Frame Diff      │ │
│  │ + Local VAD (Edge Preprocess) │ │
│  └───────────────┬───────────────┘ │
│                  │ WebSocket       │
└──────────────────┼─────────────────┘
                   │
┌──────────────────┼─────────────────┐
│  Backend (FastAPI + LangGraph)     │
│  ┌───────────────┴───────────────┐ │
│  │ LangGraph State Machine       │ │
│  │  ASR → VLM → TTS (Streaming)  │ │
│  └───────────────┬───────────────┘ │
│                  │                 │
│  ┌───────────────┴───────────────┐ │
│  │ LiteLLM (Multi-Model Gateway) │ │
│  └───────────────────────────────┘ │
└────────────────────────────────────┘
```

## 技术栈

- **前端**: React + TypeScript + Vite
- **后端**: Python + FastAPI
- **实时通信**: WebSocket
- **AI 管线**: LangGraph 状态机编排
- **多模型网关**: LiteLLM
- **语音**: ASR + TTS
- **视觉**: 帧差分 + SSIM 关键帧检测

## 快速开始

### 后端

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

## 项目结构

```
Vision Talk/
├── frontend/          # React + Vite 前端
│   └── src/
├── backend/           # FastAPI 后端
│   ├── app/
│   │   ├── routes/    # API 路由
│   │   └── services/  # 业务逻辑
│   └── main.py        # 入口
└── README.md
```
