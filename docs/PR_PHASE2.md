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

## Commit 2: 定时间隔抓帧

**变更：**
- Camera 组件内实现 `setInterval` 定时抓帧
- 每 2 秒通过 `getScreenshot()` 获取 Base64 JPEG
- 通过 `onFrame` 回调抛出帧数据

**文件：**
- `frontend/src/components/Camera.tsx` — 添加抓帧逻辑

```tsx
useEffect(() => {
  const timer = setInterval(() => {
    const screenshot = webcamRef.current?.getScreenshot();
    if (screenshot) onFrame?.(screenshot);
  }, 2000); // 每 2 秒一帧
  return () => clearInterval(timer);
}, [onFrame]);
```

**验证：** 控制台每隔 2 秒输出 Base64 字符串。

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

## Commit 5: 帧差分关键帧检测

**变更：**
- 新建 `frontend/src/utils/frameDiff.ts`
- 实现像素级帧差分算法：对比相邻两帧像素差异比例
- 差异超过阈值（如 5%）→ 标记为关键帧 → 才发送
- 集成到 Camera → RingBuffer → WebSocket 链路上

**文件：**
- `frontend/src/utils/frameDiff.ts`
- `frontend/src/hooks/useKeyFrameDetector.ts`

```ts
function isKeyFrame(prev: ImageData, curr: ImageData, threshold = 0.05): boolean {
  // 像素级对比，差异像素比例 > threshold 则返回 true
}
```

**验证：** 静止画面不发送，挥手/移动触发发送。

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
- [ ] 每 2 秒抓一帧 Base64
- [ ] WebSocket 连通，帧数据送达后端
- [ ] RingBuffer 正确覆盖旧帧
- [ ] 静止画面不触发关键帧发送
- [ ] 挥手/移动触发关键帧发送
- [ ] 不说话无任何数据上传
- [ ] 开始说话立即触发关键帧 + 音频采集
