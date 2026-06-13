import { useRef, useState, useCallback } from "react";
import Camera from "./components/Camera";
import type { CameraHandle } from "./components/Camera";
import { useWebSocket } from "./hooks/useWebSocket";
import "./App.css";

const WS_URL = "ws://localhost:8000/ws";

function App() {
  const cameraRef = useRef<CameraHandle>(null);
  const [lastCapture, setLastCapture] = useState<string | null>(null);
  const [lastAck, setLastAck] = useState<string>("");

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

  const handleCapture = () => {
    const frame = cameraRef.current?.captureFrame();
    if (!frame) {
      console.warn("[Vision Talk] Capture failed: no frame");
      return;
    }

    setLastCapture(frame);

    if (status === "connected") {
      send({ type: "frame", data: frame });
    } else {
      setLastAck("⚠️ WebSocket 未连接");
    }
  };

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
            视觉休眠中 — 仅在事件触发时抓帧
            <span className={`ws-status ws-${status}`}>
              {status === "connected" ? "🟢" : status === "connecting" ? "🟡" : "🔴"}
            </span>
          </p>
        </div>

        <div className="controls">
          <button onClick={handleCapture} className="capture-btn">
            抓帧并发送
          </button>
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
