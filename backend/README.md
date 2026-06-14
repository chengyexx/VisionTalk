# Vision Talk — 后端目录结构

```
backend/
├── main.py                 # 启动入口: python main.py
├── requirements.txt        # Python 依赖
├── .env.example            # 环境变量模板
│
└── app/
    ├── main.py             # FastAPI 应用定义 (CORS, lifespan, 路由注册)
    ├── config.py           # 环境变量加载 + 全局配置
    │
    ├── api/                # ── 路由层 ──
    │   ├── websocket.py    #   WS 全双工通信 + 流式推送 + 打断
    │   ├── model.py        #   REST API: 模型切换 / 查询 / 重置
    │   └── health.py       #   健康检查 GET /health
    │
    └── core/               # ── 核心服务层 ──
        ├── llm.py          #   LiteLLM 统一客户端 (多模型 + 运行时切换)
        ├── asr.py          #   语音识别 (Whisper API)
        ├── vlm.py          #   多模态推理 + 视觉记忆压缩
        ├── tts.py          #   语音合成 (Edge TTS 免费 + OpenAI TTS 备选)
        └── pipeline.py     #   LangGraph 管线编排 (ASR → VLM → TTS)
```

## 命名约定

| 目录 | 职责 | 命名规则 |
|------|------|----------|
| `api/` | HTTP 路由 + WebSocket handler | 每个文件一个 `router = APIRouter()` |
| `core/` | 领域逻辑 + AI 服务 | 函数式为主，按能力划分模块 |

## 启动

```bash
cd backend
pip install -r requirements.txt
python main.py          # → http://localhost:8000
```

## API 摘要

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 服务状态 + 当前模型 |
| `/health` | GET | 健康检查 |
| `/ws` | WS | 主对话通道 |
| `/api/model/available` | GET | 可选模型列表 |
| `/api/model/state` | GET | 当前活跃模型 |
| `/api/model/switch` | POST | 运行时切换模型 |
| `/api/model/reset` | POST | 重置为默认模型 |
