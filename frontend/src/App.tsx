import { useRef, useState, useCallback } from "react";
import Camera from "./components/Camera";
import type { CameraHandle } from "./components/Camera";
import { StatusBar } from "./components/StatusBar";
import { ChatPanel } from "./components/ChatPanel";
import { AudioPlayer } from "./components/AudioPlayer";
import { useWebSocket } from "./hooks/useWebSocket";
import { useKeyFrameDetector } from "./hooks/useKeyFrameDetector";
import { useVAD } from "./hooks/useVAD";
import { useAudioCapture } from "./hooks/useAudioCapture";
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
  const lastFrameRef = useRef<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [diffReason, setDiffReason] = useState<string>("");
  const [frameCount, setFrameCount] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [audioUrl, setAudioUrl] = useState<string>("");

  // Handle incoming WS messages from LangGraph pipeline
  const handleMessage = useCallback((data: unknown) => {
    const msg = data as Record<string, unknown>;
    switch (msg.type) {
      case "pipeline_start":
        setMessages((prev) => [...prev, newMsg("system", "AI 处理中...")]);
        break;
      case "asr_text":
        setMessages((prev) => [...prev, newMsg("user", msg.text as string)]);
        break;
      case "vlm_text":
        setMessages((prev) => [...prev, newMsg("assistant", msg.text as string)]);
        break;
      case "tts_audio": {
        const data = msg.data as string;
        const format = (msg.format as string) || "mp3";
        const blob = base64ToBlob(data, `audio/${format}`);
        const url = URL.createObjectURL(blob);
        setAudioUrl(url);
        setIsPlaying(true);
        break;
      }
      case "error":
        setMessages((prev) => [...prev, newMsg("system", `错误: ${msg.message}`)]);
        break;
    }
  }, []);

  const { status: wsStatus, send } = useWebSocket({ url: WS_URL, onMessage: handleMessage });
  const { shouldSend } = useKeyFrameDetector();
  const audioCapture = useAudioCapture();
  const isRecordingRef = useRef(false);

  // VAD speech start → start recording audio
  const handleSpeechStart = useCallback(async () => {
    setMessages((prev) => [...prev, newMsg("system", "正在聆听...")]);
    await audioCapture.start();
    isRecordingRef.current = true;

    // Capture frame on speech start
    const frame = cameraRef.current?.captureFrame();
    if (frame) {
      lastFrameRef.current = frame;
      setFrameCount((c) => c + 1);
    }
  }, [audioCapture]);

  // VAD speech end → stop recording → send pipeline message
  const handleSpeechEnd = useCallback(async () => {
    if (!isRecordingRef.current) return;
    isRecordingRef.current = false;

    const audioB64 = await audioCapture.stop();
    const frame = lastFrameRef.current;

    if (!audioB64) {
      setDiffReason("未捕获到音频");
      return;
    }

    // Check if frame has changed
    const result = await shouldSend(frame, true);
    if (!result.shouldSend) {
      setDiffReason(result.reason);
      return;
    }

    setDiffReason(result.reason);

    if (wsStatus === "connected") {
      send({
        type: "pipeline",
        frame: frame,
        audio: audioB64,
      });
      setMessages((prev) => [...prev, newMsg("system", `发送中 (音频: ${audioB64.length} chars)`)]);
    }
  }, [audioCapture, shouldSend, wsStatus, send]);

  const { isSpeaking, vadState } = useVAD({
    onSpeechStart: handleSpeechStart,
    onSpeechEnd: handleSpeechEnd,
  });

  return (
    <div className="app">
      <StatusBar wsStatus={wsStatus} vadState={vadState} isSpeaking={isSpeaking} frameCount={frameCount} />

      <main className="app-main">
        <div className="camera-panel">
          <Camera ref={cameraRef} width={640} height={480} mirrored />
          <div className="camera-overlay">
            {diffReason && <span className="overlay-badge">{diffReason}</span>}
          </div>
        </div>

        <div className="chat-panel-container">
          <ChatPanel messages={messages} />
          <AudioPlayer
            audioUrl={audioUrl}
            isPlaying={isPlaying}
            onEnded={() => setIsPlaying(false)}
          />
        </div>
      </main>
    </div>
  );
}

/** Convert base64 string to Blob for URL.createObjectURL */
function base64ToBlob(base64: string, mimeType: string): Blob {
  const byteChars = atob(base64);
  const bytes = new Uint8Array(byteChars.length);
  for (let i = 0; i < byteChars.length; i++) {
    bytes[i] = byteChars.charCodeAt(i);
  }
  return new Blob([bytes], { type: mimeType });
}

export default App;
