import { useRef, useCallback, useMemo, useState, useEffect } from "react";
import Camera from "./components/Camera";
import type { CameraHandle } from "./components/Camera";
import Mascot, { type MascotState } from "./components/Mascot";
import { useConversation } from "./hooks/useConversation";
import { useTurnPipeline } from "./hooks/useTurnPipeline";
import type { WSStatus } from "./hooks/useWebSocket";
import "./App.css";

const WS_URL = "ws://localhost:8000/ws";
const MODELS = ["dashscope/qwen-vl-max", "dashscope/qwen-vl-plus", "deepseek/deepseek-chat"];

function statusLabel(s: WSStatus, retry: number): string {
  switch (s) {
    case "connected": return "ONLINE";
    case "reconnecting": return `RETRY ${retry > 0 ? `(${retry}s)` : ""}`;
    case "connecting": return `CONNECTING ${retry > 0 ? `(${retry}s)` : ""}`;
    default: return "OFFLINE";
  }
}

function statusDotClass(s: WSStatus): string {
  switch (s) {
    case "connected": return "online";
    case "reconnecting":
    case "connecting": return "connecting";
    default: return "offline";
  }
}

export default function App() {
  const cameraRef = useRef<CameraHandle>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const audioPlayingRef = useRef(false);
  const [startledAt, setStartledAt] = useState(0);
  const [running, setRunning] = useState(false);

  // ── 对话层 ──
  const {
    messages,
    wsStatus,
    retryIn,
    currentModel,
    audioPlaying,
    isAiSpeaking,
    isThinking,
    send,
    switchModel,
    interrupt,
  } = useConversation({
    wsUrl: WS_URL,
  });

  audioPlayingRef.current = audioPlaying;

  // ── 管线层 ──
  const { isSpeaking, vadState, frameCount, diffReason } = useTurnPipeline({
    cameraRef,
    wsStatus,
    active: running,
    isAiSpeaking,
    isAudioPlaying: () => audioPlayingRef.current,
    onBargeIn: () => {
      setStartledAt(Date.now());
      interrupt();
    },
    onSendTurn: useCallback(
      (audioB64: string, frameB64: string) => {
        console.log("[SendTurn] audio=%db frame=%db", audioB64.length, frameB64.length);
        send({ type: "start_turn", audio_b64: audioB64, image_b64: frameB64 });
      },
      [send]
    ),
  });

  // ── 熊猫状态推导 ──
  const mascotState: MascotState = useMemo(() => {
    if (!running && wsStatus === "connected") return "idle";
    if (Date.now() - startledAt < 2000) return "startled";
    if (wsStatus !== "connected") return "idle";
    if (isSpeaking) return "listening";
    if (isThinking) return "thinking";
    if (isAiSpeaking() || audioPlaying) return "speaking";
    return "idle";
  }, [wsStatus, isSpeaking, isThinking, audioPlaying, startledAt, isAiSpeaking]);

  // Clear startled after timer
  useEffect(() => {
    if (startledAt === 0) return;
    const t = setTimeout(() => setStartledAt(0), 2200);
    return () => clearTimeout(t);
  }, [startledAt]);

  // ── 新消息自动滚到底 ──
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

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
          <span className="app-title">Vision Talk</span>
          <div className="status-group">
            <div className="status-item">
              <div className={`status-dot ${statusDotClass(wsStatus)}`} />
              <span>{statusLabel(wsStatus, retryIn)}</span>
            </div>
            <div className="status-item">
              <span className={`mic-indicator ${isSpeaking ? "active" : ""}`}>
                {isSpeaking ? "●" : "○"}
              </span>
              <span>{isSpeaking ? "说话中" : vadState}</span>
            </div>
            <span className="frame-count">
              FRM {frameCount.toString().padStart(4, "0")}
            </span>
          </div>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          {running && diffReason && (
            <span className="status-item" style={{ fontSize: 10, color: "var(--text-dim)" }}>
              {diffReason}
            </span>
          )}
          <button className="model-chip" onClick={cycleModel}>
            {currentModel.split("/")[1] || currentModel}
          </button>
          <button
            className={`toggle-btn ${running ? "on" : "off"}`}
            onClick={() => setRunning((v) => !v)}
          >
            {running ? "⏸ 暂停" : "▶ 开始"}
          </button>
        </div>
      </header>

      {/* Main */}
      <main className="app-main">
        {/* Left: Camera + VAD indicator */}
        <div className="left-panel">
          <div className={`camera-feed ${!running && wsStatus === "connected" ? "paused" : ""}`}>
            <Camera ref={cameraRef} width={640} height={480} mirrored />
            <div className="camera-label">{running ? "LIVE" : "PAUSED"}</div>
            {(running && diffReason || audioPlaying) && (
              <span className="camera-badge">
                {audioPlaying ? "🔊" : diffReason}
              </span>
            )}
          </div>
          <div className={`vad-indicator ${running && isSpeaking ? "speaking" : ""}`}>
            {!running ? "⏸ 已暂停" : isSpeaking ? "● 正在听" : vadState === "silence" ? "静音中" : "准备就绪"}
          </div>
        </div>

        {/* Right: Mascot + Chat + Audio */}
        <div className="right-panel">
          <div className="mascot-area">
            <Mascot state={mascotState} />
          </div>

          <div className="chat-panel">
            <div className="chat-header">
              <span>对话</span>
              <span>{messages.length} 条</span>
            </div>
            {messages.length === 0 ? (
              <div className="chat-empty">
                <span>🎤</span>
                <span>开始说话 — AI 能看到你</span>
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
                <div ref={chatEndRef} />
              </div>
            )}
          </div>

          <div className="audio-footer">
            <div className="audio-bars">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="audio-bar" />
              ))}
            </div>
            <span className="audio-label">
              {audioPlaying ? "AI 正在说话" : "待机"}
            </span>
          </div>
        </div>
      </main>
    </div>
  );
}
