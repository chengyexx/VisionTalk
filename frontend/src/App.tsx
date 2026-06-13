import { useRef, useState, useCallback } from "react";
import Camera from "./components/Camera";
import type { CameraHandle } from "./components/Camera";
import { StatusBar } from "./components/StatusBar";
import { ChatPanel } from "./components/ChatPanel";
import { AudioPlayer } from "./components/AudioPlayer";
import { useWebSocket } from "./hooks/useWebSocket";
import { useKeyFrameDetector } from "./hooks/useKeyFrameDetector";
import { useVAD } from "./hooks/useVAD";
import "./App.css";

const WS_URL = "ws://localhost:8000/ws";

interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
}

let msgId = 0;
function newMsg(role: Message["role"], content: string): Message {
  return { id: String(++msgId), role, content, timestamp: Date.now() };
}

function App() {
  const cameraRef = useRef<CameraHandle>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [lastAck, setLastAck] = useState<string>("");
  const [diffReason, setDiffReason] = useState<string>("");
  const [frameCount, setFrameCount] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);

  const handleMessage = useCallback((data: unknown) => {
    const msg = data as Record<string, unknown>;
    if (msg.type === "frame_ack") {
      setLastAck(`帧已接收 (${(msg.size as number)?.toLocaleString()} bytes)`);
    }
    if (msg.type === "tts_audio") {
      setIsPlaying(true);
    }
  }, []);

  const { status: wsStatus, send } = useWebSocket({ url: WS_URL, onMessage: handleMessage });
  const { shouldSend } = useKeyFrameDetector();

  const trySendFrame = useCallback(async () => {
    const frame = cameraRef.current?.captureFrame();
    if (!frame) return;

    const result = await shouldSend(frame, true);
    if (!result.shouldSend) {
      setDiffReason(result.reason);
      return;
    }

    setDiffReason(result.reason);
    setFrameCount((c) => c + 1);
    if (wsStatus === "connected") {
      send({ type: "frame", data: frame });
    }
  }, [shouldSend, wsStatus, send]);

  const { isSpeaking, vadState } = useVAD({
    onSpeechStart: () => {
      setMessages((prev) => [...prev, newMsg("system", "检测到语音...")]);
      trySendFrame();
    },
    onSpeechEnd: () => {},
  });

  return (
    <div className="app">
      <StatusBar wsStatus={wsStatus} vadState={vadState} isSpeaking={isSpeaking} frameCount={frameCount} />

      <main className="app-main">
        <div className="camera-panel">
          <Camera ref={cameraRef} width={640} height={480} mirrored />
          <div className="camera-overlay">
            {diffReason && <span className="overlay-badge">{diffReason}</span>}
            {lastAck && <span className="overlay-badge ack">{lastAck}</span>}
          </div>
        </div>

        <div className="chat-panel-container">
          <ChatPanel messages={messages} />
          <AudioPlayer isPlaying={isPlaying} onEnded={() => setIsPlaying(false)} />

          <button onClick={trySendFrame} className="capture-btn">
            手动发送帧
          </button>
        </div>
      </main>
    </div>
  );
}

export default App;
