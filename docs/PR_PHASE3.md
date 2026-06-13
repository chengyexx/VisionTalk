# PR3 — 云端 AI 管线

> 基于 LangGraph 编排 ASR → VLM → TTS 多智能体对话管线，LiteLLM 统一多模型接入。

---

## Commit 1: LiteLLM 集成

**变更：**
- 安装 `litellm`、`python-dotenv`
- 新建 `backend/.env.example`（API Key 模板）
- 新建 `backend/app/services/llm_client.py`，封装 LiteLLM 统一调用
- 支持 DeepSeek 为主模型，可切换 OpenAI / Qwen 等

**文件：**
- `backend/requirements.txt` — +litellm, python-dotenv
- `backend/.env.example`
- `backend/app/services/llm_client.py`

```python
# llm_client.py 核心接口
from litellm import completion

async def chat(messages: list, model: str = "deepseek/deepseek-chat", stream: bool = False):
    """统一 LLM 调用入口，自动处理 fallback"""
    response = await acompletion(model=model, messages=messages, stream=stream)
    return response
```

**验证：** 运行测试脚本，确认 DeepSeek API 调用成功。

---

## Commit 2: LangGraph 状态机骨架

**变更：**
- 安装 `langgraph`, `langchain-core`
- 新建 `backend/app/services/graph.py`，定义对话状态机结构
- 定义 `ConversationState`：消息历史、当前帧、ASR 文本、VLM 回复、TTS 音频
- 定义三个节点占位：`asr_node`, `vlm_node`, `tts_node`
- 配置 `MemorySaver` checkpoint

**文件：**
- `backend/requirements.txt` — +langgraph, langchain-core
- `backend/app/services/graph.py`

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

class ConversationState(TypedDict):
    messages: list           # 对话历史
    audio_chunk: bytes       # 当前音频片段
    key_frame: str           # 当前关键帧 (Base64)
    asr_text: str            # 语音识别结果
    vlm_response: str        # 视觉模型回复
    tts_audio: bytes         # 合成语音
    interrupted: bool        # 是否被打断

builder = StateGraph(ConversationState)
builder.add_node("asr", asr_node)
builder.add_node("vlm", vlm_node)
builder.add_node("tts", tts_node)
builder.set_entry_point("asr")
builder.add_edge("asr", "vlm")
builder.add_edge("vlm", "tts")
builder.add_edge("tts", END)

graph = builder.compile(checkpointer=MemorySaver())
```

**验证：** 空状态机可编译，无运行时错误。

---

## Commit 3: ASR 语音识别节点

**变更：**
- 新建 `backend/app/services/asr.py`
- 实现 `asr_node`：接收音频 bytes → 调用 ASR API → 输出文本
- 支持 DeepSeek Audio / Whisper API 两种后端
- 将识别结果写入 `ConversationState.asr_text`

**文件：**
- `backend/app/services/asr.py`
- `backend/app/services/graph.py` — asr_node 实现

```python
async def transcribe(audio: bytes, model: str = "whisper-1") -> str:
    """语音转文本"""
    # 调用 ASR API，返回识别文本
    ...

async def asr_node(state: ConversationState) -> dict:
    text = await transcribe(state["audio_chunk"])
    return {"asr_text": text, "messages": state["messages"] + [{"role": "user", "content": text}]}
```

**验证：** 发送一段音频，日志输出识别文本。

---

## Commit 4: VLM 视觉推理节点

**变更：**
- 新建 `backend/app/services/vlm.py`
- 实现 `vlm_node`：拼接关键帧 + ASR 文本 → 调用 VLM 多模态推理
- 通过 LiteLLM 以 vision 格式传入 Base64 图片
- 流式返回 AI 文本回复

**文件：**
- `backend/app/services/vlm.py`
- `backend/app/services/graph.py` — vlm_node 实现

```python
async def vlm_node(state: ConversationState) -> dict:
    """视觉 + 文本 → 流式 AI 回复"""
    messages = [
        {"role": "system", "content": "你是 Vision Talk 助手，能看到用户摄像头画面。"},
        {"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{state['key_frame']}"}},
            {"type": "text", "text": state["asr_text"]}
        ]}
    ]
    response = await chat(messages=messages, stream=True)
    full_text = ""
    async for chunk in response:
        full_text += chunk
        # 流式推送到 TTS
    return {"vlm_response": full_text}
```

**验证：** 传测试图片 + "这是什么？" → 输出图片描述。

---

## Commit 5: TTS + 流式推送

**变更：**
- 新建 `backend/app/services/tts.py`
- 实现 `tts_node`：VLM 文本 → TTS 合成语音 → WebSocket 流式推回
- 支持 DeepSeek TTS / Edge TTS
- WebSocket 分片传输音频，前端边收边播

**文件：**
- `backend/app/services/tts.py`
- `backend/app/services/graph.py` — tts_node 实现
- `backend/app/routes/websocket.py` — 流式推送逻辑

```python
async def synthesize(text: str) -> AsyncIterator[bytes]:
    """文本 → 流式语音 chunks"""
    ...

async def tts_node(state: ConversationState) -> dict:
    audio_chunks = []
    async for chunk in synthesize(state["vlm_response"]):
        audio_chunks.append(chunk)
        # 通过 WebSocket 实时推送每个 chunk
        await ws.send(chunk)
    return {"tts_audio": b"".join(audio_chunks)}
```

**验证：** 端到端：文本输入 → 听到语音输出。

---

## Commit 6: LangGraph 记忆降维（Token 压缩）

**变更：**
- 在 VLM 节点执行后，提取「文本描述摘要」替代原始图像存入对话历史
- `ConversationState` 新增 `visual_summary` 字段，存储上轮画面的文字概括
- 每轮发给 VLM 的上下文只包含：「最新 1 张图片 + 历史视觉摘要（纯文本）」
- 历史图片的 Base64 数据在每轮结束后丢弃，不随对话累积

**文件：**
- `backend/app/services/graph.py` — 状态字段 + 压缩逻辑
- `backend/app/services/vlm.py` — 生成视觉摘要

```python
class ConversationState(TypedDict):
    messages: list           # 对话历史（纯文本，不含历史图片）
    audio_chunk: bytes
    key_frame: str           # 仅保留当前帧 (Base64)
    visual_summary: str      # 上轮画面的文本摘要 ← 新增
    asr_text: str
    vlm_response: str
    tts_audio: bytes
    interrupted: bool

async def summarize_visual(key_frame: str, vlm_response: str) -> str:
    """用轻量模型提取当前画面的文字描述，替代图片存入记忆"""
    summary = await chat(
        messages=[{"role": "user", "content": f"用一句话概括这轮对话中用户展示的画面：回复内容是'{vlm_response}'"}],
        model="deepseek/deepseek-chat"  # 用纯文本模型即可，成本极低
    )
    return summary

async def vlm_node(state: ConversationState) -> dict:
    # 构建消息：仅包含当前图片 + 历史文本（不含历史图片 Base64）
    user_content = [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{state['key_frame']}"}}]
    
    if state.get("visual_summary"):
        user_content.append({"type": "text", "text": f"[之前的画面] {state['visual_summary']}"})
    
    user_content.append({"type": "text", "text": state["asr_text"]})
    
    messages = [{"role": "system", "content": "你是 Vision Talk 助手…"}]
    # 历史消息只包含纯文本，不包含图片
    messages.extend(state["messages"])
    messages.append({"role": "user", "content": user_content})
    
    response = await chat(messages=messages, stream=True)
    full_text = ""
    async for chunk in response:
        full_text += chunk
    
    # 生成视觉摘要替代原始图片
    summary = await summarize_visual(state["key_frame"], full_text)
    
    return {
        "vlm_response": full_text,
        "visual_summary": summary,
        "key_frame": None,  # 清除本轮图片，防止后续轮次携带
        "messages": state["messages"] + [
            {"role": "user", "content": f"[用户展示了]{summary}\n{state['asr_text']}"},
            {"role": "assistant", "content": full_text}
        ]
    }
```

**设计意图：**

```
第 1 轮：     [图片₁ Base64] + "这是什么？"           → Token: ~800
第 2 轮：     "上轮画面是一块开发板，红灯闪烁" + [图片₂] + "怎么修？" → Token: ~600
第 3 轮：     "上轮是示波器显示波形" + [图片₃] + "正常吗？"        → Token: ~600

不做降维的话：
第 3 轮：     [图片₁] [图片₂] [图片₃] + 文本              → Token: ~2000+
```

单张 1080p 图片约 500-800 token，降维后每轮视觉成本恒定控制在 ~600 token，多轮对话成本线性而非指数增长。

**验证：** 3 轮对话后，每次 API 请求仅包含 1 张图片，历史记录为纯文本摘要。

---

## PR 验证 Checklist

- [ ] LiteLLM 调用 DeepSeek 成功
- [ ] LangGraph 状态机编译无报错
- [ ] ASR 节点正确识别语音为文本
- [ ] VLM 节点正确理解图片 + 文本，生成回复
- [ ] TTS 节点合成可听语音
- [ ] WebSocket 流式推送音频 chunk 正常
- [ ] Checkpoint 恢复：模拟断线后状态可恢复
- [ ] 多轮对话后 API 请求仅含 1 张图片（Token 压缩生效）
- [ ] 视觉摘要正确概括历史画面内容
