import { useRef, useCallback } from "react";
import Camera from "./components/Camera";
import type { CameraHandle } from "./components/Camera";
import { useConversation } from "./hooks/useConversation";
import { useTurnPipeline } from "./hooks/useTurnPipeline";
import type { WSStatus } from "./hooks/useWebSocket";
import "./App.css";

const WS_URL = "ws://localhost:8000/ws";
const MODELS = ["dashscope/qwen-vl-max", "dashscope/qwen-vl-plus", "deepseek/deepseek-chat"];

/** 状态文本映射 */
function statusLabel(s: WSStatus, retry: number): string {
  switch (s) {
    case "connected":
      return "ONLINE";
    case "reconnecting":
      return `RETRY ${retry > 0 ? `(${retry}s)` : ""}`;
    case "connecting":
      return `CONNECTING ${retry > 0 ? `(${retry}s)` : ""}`;
    default:
      return "OFFLINE";
  }
}

function statusDotClass(s: WSStatus): string {
  switch (s) {
    case "connected":
      return "online";
    case "reconnecting":
    case "connecting":
      return "connecting";
    default:
      return "offline";
  }
}

export default function App() {
  const cameraRef = useRef<CameraHandle>(null);

  // ── 对话层 ──
  const {
    messages,
    wsStatus,
    retryIn,
    currentModel,
    audioPlaying,
    send,
    switchModel,
    interrupt,
    isAiSpeaking,
  } = useConversation({
    wsUrl: WS_URL,
  });

  // ── 管线层 ──
  const { isSpeaking, vadState, frameCount, diffReason } = useTurnPipeline({
    cameraRef,
    wsStatus,
    isAiSpeaking,
    onBargeIn: interrupt,
    onSendTurn: useCallback(
      (audioB64: string, frameB64: string) => {
        send({ type: "start_turn", audio_b64: audioB64, image_b64: frameB64 });
      },
      [send]
    ),
  });

  // ── 模型切换 ──
  const cycleModel = () => {
    const idx = MODELS.indexOf(currentModel);
    switchModel(MODELS[(idx + 1) % MODELS.length]);
  };

  return (
    <div className="app">
      {/* Top Bar */}
      <header className="top-bar">
        <div className="top-bar-left">
          <span className="app-title">VISION TALK</span>
          <div className="status-group">
            <div className="status-item">
              <div className={`status-dot ${statusDotClass(wsStatus)}`} />
              <span>{statusLabel(wsStatus, retryIn)}</span>
            </div>
            <div className="status-item">
              <span className={`mic-indicator ${isSpeaking ? "active" : ""}`}>
                ◉
              </span>
              <span>{isSpeaking ? "SPEAKING" : vadState}</span>
            </div>
            <span className="frame-count">
              FRM:{frameCount.toString().padStart(4, "0")}
            </span>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span className="status-item" style={{ fontSize: 11 }}>
            {diffReason}
          </span>
          <button className="model-chip" onClick={cycleModel}>
            {currentModel.split("/")[1] || currentModel}
          </button>
        </div>
      </header>

      {/* Main */}
      <main className="app-main">
        {/* Camera Feed */}
        <div className="camera-feed">
          <Camera ref={cameraRef} width={1280} height={720} mirrored />
          <div className="camera-osd camera-corners" />
          <div className="camera-label">LIVE FEED</div>
          <div className="camera-info">
            {diffReason && (
              <span className="camera-badge">{diffReason}</span>
            )}
            {audioPlaying && (
              <span className="camera-badge">AUDIO PLAYING</span>
            )}
          </div>
        </div>

        {/* Side Panel */}
        <div className="side-panel">
          {/* Chat HUD */}
          <div className="chat-hud">
            <div className="chat-header">
              <span>TRANSCRIPT</span>
              <span>{messages.length} msgs</span>
            </div>
            {messages.length === 0 ? (
              <div className="chat-empty">
                开始对话 — AI 将看到你的画面
              </div>
            ) : (
              <div className="chat-messages">
                {messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`msg ${
                      msg.role === "user"
                        ? "msg-user"
                        : msg.role === "system"
                          ? "msg-system"
                          : msg.role === "assistant-streaming"
                            ? "msg-assistant msg-streaming"
                            : "msg-assistant"
                    }`}
                  >
                    {msg.content}
                    {msg.role === "assistant-streaming" && (
                      <span className="cursor" />
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Audio strip */}
          <div className="audio-strip">
            <div className="audio-bars">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="audio-bar" />
              ))}
            </div>
            <span>{audioPlaying ? "SPEAKING" : "STANDBY"}</span>
          </div>
        </div>
      </main>
    </div>
  );
}
