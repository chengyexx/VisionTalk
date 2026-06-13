# PR2 — 边缘端预处理

> 在浏览器端实现轻量级视频帧管理与语音检测，只把关键信息送向云端。

---

## Commit 1: 添加 Camera 组件

**变更：**
- 安装 `react-webcam` 依赖
- 新建 `src/components/Camera.tsx`，封装摄像头采集
- 支持分辨率、镜像、静音等基础配置

**文件：**
- `frontend/package.json` — 新增 react-webcam
- `frontend/src/components/Camera.tsx`

```tsx
// Camera.tsx 核心结构
interface CameraProps {
  onFrame?: (frame: string) => void;
  width?: number;
  height?: number;
  mirrored?: boolean;
}

export const Camera: React.FC<CameraProps> = ({ onFrame, ... }) => {
  const webcamRef = useRef<Webcam>(null);
  // 定时抓帧逻辑在后续 commit
  return <Webcam ref={webcamRef} audio={false} ... />;
};
```

---

## Commit 2: 事件驱动按需抓帧

**变更：**
- Camera 组件改为「视觉休眠」模式：**不主动定时抓帧**
- 暴露 `captureFrame()` 方法，仅在外部事件（VAD 触发）时被调用
- 帧数据写入 `RingBuffer` 缓存，不直接发送

**文件：**
- `frontend/src/components/Camera.tsx` — 按需抓帧接口

```tsx
// Camera.tsx — 暴露命令式抓帧方法
const Camera = forwardRef((props, ref) => {
  const webcamRef = useRef<Webcam>(null);
  
  useImperativeHandle(ref, () => ({
    captureFrame: (): string | null => {
      return webcamRef.current?.getScreenshot() ?? null;
    }
  }));
  
  return <Webcam ref={webcamRef} audio={false} ... />;
});
```

**设计意图：** 系统平时处于「视觉休眠」状态，零 CPU / 零网络开销。仅在 VAD 检测到用户说话时才抓一帧，将视觉成本从流式计算降为事件式计算。

**验证：** Camera 画面正常显示，`captureFrame()` 调用返回 Base64 字符串。

---

## Commit 3: WebSocket 图片传输

**变更：**
- 前端新建 `src/hooks/useWebSocket.ts`，封装 WebSocket 连接、重连
- 前端新建 `src/services/imageSender.ts`，将帧数据通过 WebSocket 发送
- 后端 `app/routes/websocket.py` 实现接收帧并回显确认

**文件：**
- `frontend/src/hooks/useWebSocket.ts`
- `frontend/src/services/imageSender.ts`
- `backend/app/routes/websocket.py`

```
前端抓帧 → Base64 → WebSocket.send() → 后端 receive → 回显 ack
```

**验证：** 后端日志输出 "收到帧，大小: xxx bytes"，前端收到 ack。

---

## Commit 4: Ring Buffer 帧缓冲

**变更：**
- 新建 `frontend/src/utils/RingBuffer.ts`
- 固定容量（如 30 帧），FIFO 覆盖旧帧
- 提供 `push(frame)`, `getLatest()`, `getAll()` 接口

**文件：**
- `frontend/src/utils/RingBuffer.ts`

```ts
class RingBuffer<T> {
  private buffer: T[];
  private capacity: number;
  
  push(item: T): void { ... }     // 满了覆盖最旧
  getLatest(): T | null { ... }   // 最新一帧
  getAll(): T[] { ... }           // 所有帧快照
  size(): number { ... }
}
```

**验证：** 单元测试验证满容量覆盖行为。

---

## Commit 5: VAD + 帧差分联合触发

**变更：**
- 新建 `frontend/src/utils/frameDiff.ts`，实现像素级帧差分算法
- 差异超过阈值（如 5%）→ 标记为关键帧
- **与 VAD 联合决策**：「用户正在说话」且「画面有显著变化」两个条件同时满足，才发送当前帧
- 集成到 Camera → RingBuffer → 联合触发 → WebSocket 链路

**文件：**
- `frontend/src/utils/frameDiff.ts`
- `frontend/src/hooks/useKeyFrameDetector.ts`

```ts
function isKeyFrame(prev: ImageData, curr: ImageData, threshold = 0.05): boolean {
  // 像素级对比，差异像素比例 > threshold 则返回 true
}

// 联合触发逻辑
async function shouldSendFrame(
  latestFrame: string, 
  lastSentFrame: string | null, 
  isSpeaking: boolean
): Promise<boolean> {
  if (!isSpeaking) return false;                    // VAD 触发为前提
  if (!lastSentFrame) return true;                   // 首次必发
  return isKeyFrame(lastSentFrame, latestFrame);     // 画面有变化才发
}
```

**验证：** 不说话时不发送；说话但画面未变不发送；说话 + 画面变化才发送。

---

## Commit 6: 本地 VAD 静音检测

**变更：**
- 安装 `@ricky0123/vad-web`（浏览器端 VAD 库）
- 新建 `frontend/src/hooks/useVAD.ts`
- 检测到人声 → 触发音频采集 + 当前关键帧打包上传
- 无声音期间不发送任何数据

**文件：**
- `frontend/package.json` — +@ricky0123/vad-web
- `frontend/src/hooks/useVAD.ts`

```ts
function useVAD(onSpeechStart: () => void, onSpeechEnd: () => void) {
  // 加载 Silero VAD 模型
  // 监听麦克风，回调语音起止事件
}
```

**验证：** 不说话无发送，开始说话立即触发帧上传。

---

## PR 验证 Checklist

- [ ] Camera 正常打开，显示实时画面
- [ ] `captureFrame()` 按需返回 Base64，无定时器运行
- [ ] WebSocket 连通，帧数据送达后端
- [ ] RingBuffer 正确覆盖旧帧
- [ ] 不说话时不发送任何帧数据（视觉休眠）
- [ ] 说话 + 画面变化 → 发送关键帧
- [ ] 说话但画面未变 → 不发送（节省 token）
- [ ] VAD 检测到人声时触发帧采集 + 音频上传
