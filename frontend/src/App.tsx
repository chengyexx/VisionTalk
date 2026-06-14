import { useRef, useState, useCallback, useEffect } from "react";
import Camera from "./components/Camera";
import type { CameraHandle } from "./components/Camera";
import { useWebSocket } from "./hooks/useWebSocket";
import { useKeyFrameDetector } from "./hooks/useKeyFrameDetector";
import { useVAD } from "./hooks/useVAD";
import { useAudioCapture } from "./hooks/useAudioCapture";
import "./App.css";

const WS_URL = "ws://localhost:8000/ws";

interface Message {
  id: string;
  role: "user" | "assistant" | "assistant-streaming" | "system";
  content: string;
  timestamp: number;
}

let _msgId = 0;
function newMsg(role: Message["role"], content: string): Message {
  return { id: String(++_msgId), role, content, timestamp: Date.now() };
}

/** --- Base64 → Blob (for inline audio playback) --- */
function b64toBlob(b64: string, mime = "audio/mp3"): string {
  const raw = atob(b64);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
  return URL.createObjectURL(new Blob([bytes], { type: mime }));
}

export default function App() {
  const cameraRef = useRef<CameraHandle>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [wsStatus, setWsStatus] = useState<"connected"|"connecting"|"disconnected">("disconnected");
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [vadState, setVadState] = useState("idle");
  const [frameCount, setFrameCount] = useState(0);
  const [diffReason, setDiffReason] = useState("");
  const [retryIn, setRetryIn] = useState(0);
  const [audioPlaying, setAudioPlaying] = useState(false);
  const [currentModel, setCurrentModel] = useState("deepseek/deepseek-chat");
  const [wsRetry, setWsRetry] = useState(0);

  const isAiSpeakingRef = useRef(false);
  const streamingMsgRef = useRef<Message | null>(null);
  const lastFrameRef = useRef("");
  const audioElRef = useRef<HTMLAudioElement | null>(null);

  // ── WebSocket + 消息处理 ──
  const onWsMessage = useCallback((data: unknown) => {
    const m = data as Record<string, unknown>;
    switch (m.type) {
      case "state_change": {
        const st = m.state as string;
        if (st === "thinking") isAiSpeakingRef.current = true;
        if (st === "idle")   isAiSpeakingRef.current = false;
        setMessages((p) => [...p, newMsg("system", st === "thinking" ? "AI 思考中…" : "就绪")]);
        break;
      }
      case "vlm_token": {
        const tok = m.text as string;
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === "assistant-streaming") {
            const copy = [...prev];
            copy[copy.length - 1] = { ...last, content: last.content + tok, timestamp: Date.now() };
            return copy;
          }
          return [...prev, { id: String(++_msgId), role: "assistant-streaming" as const, content: tok, timestamp: Date.now() }];
        });
        break;
      }
      case "tts_chunk": {
        const b64 = m.audio_b64 as string;
        if (!b64) break;
        const url = b64toBlob(b64);
        setAudioPlaying(true);
        const a = new Audio(url);
        audioElRef.current = a;
        a.onended = () => setAudioPlaying(false);
        a.play().catch(() => setAudioPlaying(false));
        break;
      }
      case "turn_end": {
        const p = m.payload as Record<string, unknown>;
        const vlm = (p?.vlm_response as string) || "";
        const asr = (p?.asr_text as string) || "";
        if (p?.error) {
          setMessages((prev) => [...prev, newMsg("system", `错误: ${p.error}`)]);
          return;
        }
        if (asr) setMessages((prev) => [...prev, newMsg("user", asr)]);
        setMessages((prev) => {
          const filtered = prev.filter((x) => x.role !== "assistant-streaming");
          return [...filtered, newMsg("assistant", vlm)];
        });
        break;
      }
      case "error": {
        setMessages((prev) => [...prev, newMsg("system", `错误: ${m.message}`)]);
        break;
      }
    }
  }, []);

  const onWsStatus = useCallback((s: "connected"|"connecting"|"disconnected", retry: number) => {
    setWsStatus(s);
    setWsRetry(retry);
  }, []);

  const { send } = useWebSocket({ url: WS_URL, onMessage: onWsMessage, onStatusChange: onWsStatus });

  // ── Audio capture + VAD ──
  const { shouldSend: shouldSendFrame } = useKeyFrameDetector();
  const audioCapture = useAudioCapture();
  const isRecordingRef = useRef(false);

  const handleSpeechStart = useCallback(async () => {
    if (isAiSpeakingRef.current) {
      // Barge-in
      isAiSpeakingRef.current = false;
      setAudioPlaying(false);
      audioElRef.current?.pause();
      audioElRef.current = null;
      isRecordingRef.current = false;
      setMessages((prev) => [...prev, newMsg("system", "打断 — 重新聆听…")]);
      if (wsStatus === "connected") send({ type: "interrupt" });
      await audioCapture.stop();
      await audioCapture.start();
      isRecordingRef.current = true;
      const frame = cameraRef.current?.captureFrame();
      if (frame) { lastFrameRef.current = frame; setFrameCount((c) => c + 1); }
      return;
    }
    // Normal start
    setMessages((prev) => [...prev, newMsg("system", "聆听中…")]);
    await audioCapture.start();
    isRecordingRef.current = true;
    const frame = cameraRef.current?.captureFrame();
    if (frame) { lastFrameRef.current = frame; setFrameCount((c) => c + 1); }
  }, [audioCapture, wsStatus, send]);

  const handleSpeechEnd = useCallback(async () => {
    if (!isRecordingRef.current) return;
    isRecordingRef.current = false;
    const audioB64 = await audioCapture.stop();
    const frame = lastFrameRef.current;
    if (!audioB64) { setDiffReason("无音频"); return; }
    const result = await shouldSendFrame(frame, true);
    if (!result.shouldSend) { setDiffReason(result.reason); return; }
    setDiffReason(result.reason);
    if (wsStatus === "connected") {
      send({ type: "start_turn", audio_b64: audioB64, image_b64: frame || "" });
    }
  }, [audioCapture, shouldSendFrame, wsStatus, send]);

  const { isSpeaking: vadSpeaking, vadState: vadSt } = useVAD({
    onSpeechStart: handleSpeechStart,
    onSpeechEnd: handleSpeechEnd,
  });
  useEffect(() => { setIsSpeaking(vadSpeaking); setVadState(vadSt); }, [vadSpeaking, vadSt]);

  // ── Model switch ──
  const handleModelSwitch = useCallback(async (modelId: string) => {
    setCurrentModel(modelId);
    try {
      await fetch("http://localhost:8000/api/model/switch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type: "vlm", model: modelId }),
      });
      setMessages((prev) => [...prev, newMsg("system", `模型: ${modelId.split("/")[1]}`)]);
    } catch {
      setMessages((prev) => [...prev, newMsg("system", "切换失败")]);
    }
  }, []);

  // ── Render ──
  const statusLabel = wsStatus === "connected" ? "ONLINE"
    : wsStatus === "connecting" ? `CONNECTING ${wsRetry > 0 ? `(${wsRetry}s)` : ""}`
    : "OFFLINE";

  return (
    <div className="app">
      {/* Top Bar */}
      <header className="top-bar">
        <div className="top-bar-left">
          <span className="app-title">VISION TALK</span>
          <div className="status-group">
            <div className="status-item">
              <div className={`status-dot ${wsStatus === "connected" ? "online" : wsStatus === "connecting" ? "connecting" : "offline"}`} />
              <span>{statusLabel}</span>
            </div>
            <div className="status-item">
              <span className={`mic-indicator ${isSpeaking ? "active" : ""}`}>◉</span>
              <span>{isSpeaking ? "SPEAKING" : vadState}</span>
            </div>
            <span className="frame-count">FRM:{frameCount.toString().padStart(4, "0")}</span>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span className="status-item" style={{ fontSize: 11 }}>{diffReason}</span>
          <button
            className="model-chip"
            onClick={() => {
              const models = ["deepseek/deepseek-chat", "openai/gpt-4o", "openai/gpt-4o-mini"];
              const idx = models.indexOf(currentModel);
              handleModelSwitch(models[(idx + 1) % models.length]);
            }}
          >
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
            {diffReason && <span className="camera-badge">{diffReason}</span>}
            {audioPlaying && <span className="camera-badge">AUDIO PLAYING</span>}
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
              <div className="chat-empty">开始对话 — AI 将看到你的画面</div>
            ) : (
              <div className="chat-messages">
                {messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`msg ${
                      msg.role === "user" ? "msg-user"
                      : msg.role === "system" ? "msg-system"
                      : msg.role === "assistant-streaming" ? "msg-assistant msg-streaming"
                      : "msg-assistant"
                    }`}
                  >
                    {msg.content}
                    {msg.role === "assistant-streaming" && <span className="cursor" />}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Audio strip */}
          <div className="audio-strip">
            <div className="audio-bars">
              {[...Array(5)].map((_, i) => <div key={i} className="audio-bar" />)}
            </div>
            <span>{audioPlaying ? "SPEAKING" : "STANDBY"}</span>
          </div>
        </div>
      </main>
    </div>
  );
}
