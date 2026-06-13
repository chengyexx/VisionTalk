import { useRef } from "react";
import Camera from "./components/Camera";
import type { CameraHandle } from "./components/Camera";
import "./App.css";

function App() {
  const cameraRef = useRef<CameraHandle>(null);
  const lastCaptureRef = useRef<string | null>(null);

  const handleCapture = () => {
    const frame = cameraRef.current?.captureFrame();
    if (frame) {
      lastCaptureRef.current = frame;
      console.log("[Vision Talk] Frame captured:", frame.substring(0, 50) + "...");
    } else {
      console.warn("[Vision Talk] Capture failed: no frame");
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
          <p className="capture-hint">视觉休眠中 — 仅在事件触发时抓帧</p>
        </div>

        <div className="controls">
          <button onClick={handleCapture} className="capture-btn">
            手动抓帧（模拟事件触发）
          </button>
          {lastCaptureRef.current && (
            <img
              src={lastCaptureRef.current}
              alt="Last capture"
              className="last-capture"
              width={160}
            />
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
