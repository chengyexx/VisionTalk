import { useRef, useState, useCallback } from "react";
import Camera from "./components/Camera";
import type { CameraHandle } from "./components/Camera";
import { useWebSocket } from "./hooks/useWebSocket";
import { useKeyFrameDetector } from "./hooks/useKeyFrameDetector";
import { useVAD } from "./hooks/useVAD";
import "./App.css";

const WS_URL = "ws://localhost:8000/ws";

function App() {
  const cameraRef = useRef<CameraHandle>(null);
  const [lastCapture, setLastCapture] = useState<string | null>(null);
  const [lastAck, setLastAck] = useState<string>("");
  const [diffReason, setDiffReason] = useState<string>("");

  const handleMessage = useCallback((data: unknown) => {
    const msg = data as Record<string, unknown>;
    if (msg.type === "frame_ack") {
      setLastAck(`✅ ${msg.message} (${(msg.size as number)?.toLocaleString()} bytes)`);
    }
  }, []);

  const { status, send } = useWebSocket({
    url: WS_URL,
    onMessage: handleMessage,
  });

  const { shouldSend } = useKeyFrameDetector();

  /** Send current camera frame if it passes VAD + frame diff check. */
  const trySendFrame = useCallback(async () => {
    const frame = cameraRef.current?.captureFrame();
    if (!frame) {
      console.warn("[Vision Talk] Capture failed: no frame");
      return;
    }

    setLastCapture(frame);

    const result = await shouldSend(frame, true);

    if (!result.shouldSend) {
      setDiffReason(`⏭️ 跳过: ${result.reason}`);
      return;
    }

    setDiffReason(`📸 发送: ${result.reason}`);

    if (status === "connected") {
      send({ type: "frame", data: frame });
    } else {
      setLastAck("⚠️ WebSocket 未连接");
    }
  }, [shouldSend, status, send]);

  // VAD triggers frame capture on speech start
  const { isSpeaking, vadState } = useVAD({
    onSpeechStart: () => {
      console.log("[VAD] Speech started");
      trySendFrame();
    },
    onSpeechEnd: () => {
      console.log("[VAD] Speech ended");
    },
  });

  return (
    <div className="app">
      <header className="app-header">
        <h1>Vision Talk</h1>
        <p>AI 视觉对话助手</p>
      </header>

      <main className="app-main">
        <div className="camera-section">
          <Camera ref={cameraRef} width={640} height={480} mirrored />
          <p className="capture-hint">
            {isSpeaking ? "🔊 检测到语音，正在采集" : "视觉休眠中 — VAD 监听中"}
            <span className={`ws-status ws-${status}`}>
              {status === "connected" ? "🟢" : status === "connecting" ? "🟡" : "🔴"}
            </span>
            <span className={`vad-status vad-${vadState}`}>
              {vadState === "listening" ? "🎤" : vadState === "loading" ? "⏳" : "❌"}
            </span>
          </p>
        </div>

        <div className="controls">
          <button onClick={trySendFrame} className="capture-btn">
            手动抓帧发送
          </button>
          {diffReason && <p className="diff-msg">{diffReason}</p>}
          {lastAck && <p className="ack-msg">{lastAck}</p>}
          {lastCapture && (
            <img src={lastCapture} alt="Last capture" className="last-capture" width={160} />
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
