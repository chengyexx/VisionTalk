import { useRef, useState, useCallback, useEffect } from "react";
import type { CameraHandle } from "../components/Camera";
import { useKeyFrameDetector } from "./useKeyFrameDetector";
import { useVAD, getVadAudioB64 } from "./useVAD";
import type { WSStatus } from "./useWebSocket";

interface TurnPipelineOptions {
  cameraRef: React.RefObject<CameraHandle | null>;
  wsStatus: WSStatus;
  active: boolean;
  isAiSpeaking: () => boolean;
  isAudioPlaying: () => boolean;
  onBargeIn: () => void;
  onSendTurn: (audioB64: string, frameB64: string) => void;
  onStatusChange?: (state: TurnPipelineState) => void;
}

export interface TurnPipelineState {
  isSpeaking: boolean;
  vadState: string;
  frameCount: number;
  diffReason: string;
}

const MIN_TURN_INTERVAL = 2000;
const MIN_AUDIO_B64_LEN = 200;

export function useTurnPipeline({
  cameraRef,
  wsStatus,
  active,
  isAiSpeaking,
  isAudioPlaying,
  onBargeIn,
  onSendTurn,
  onStatusChange,
}: TurnPipelineOptions) {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [vadState, setVadState] = useState("idle");
  const [frameCount, setFrameCount] = useState(0);
  const [diffReason, setDiffReason] = useState("");

  const lastFrameRef = useRef("");
  const lastTurnSentRef = useRef(0);

  const { shouldSend: shouldSendFrame, reset: resetFrameDetector } = useKeyFrameDetector();

  const notifyChange = useCallback(() => {
    onStatusChange?.({ isSpeaking, vadState, frameCount, diffReason });
  }, [onStatusChange, isSpeaking, vadState, frameCount, diffReason]);

  useEffect(() => {
    notifyChange();
  }, [isSpeaking, vadState, frameCount, diffReason, notifyChange]);

  // ── 发送当前轮次 ──
  const trySend = useCallback(
    async (audioB64: string | null, frame: string): Promise<boolean> => {
      if (!audioB64) return false;
      const now = Date.now();
      if (now - lastTurnSentRef.current < MIN_TURN_INTERVAL) {
        setDiffReason("冷却中...");
        return false;
      }
      if (audioB64.length < MIN_AUDIO_B64_LEN) {
        setDiffReason("音频过短");
        return false;
      }
      const result = await shouldSendFrame(frame, true);
      if (!result.shouldSend) {
        setDiffReason(result.reason);
        return false;
      }
      setDiffReason(result.reason);
      if (wsStatus === "connected") {
        lastTurnSentRef.current = now;
        resetFrameDetector();
        onSendTurn(audioB64, frame || "");
        return true;
      }
      return false;
    },
    [shouldSendFrame, resetFrameDetector, wsStatus, onSendTurn],
  );

  // ── 语音开始 ──
  const handleSpeechStart = useCallback(() => {
    if (!active) return;
    if (wsStatus !== "connected") return;

    // 用户抢话：发送 interrupt
    if (isAiSpeaking() || isAudioPlaying()) {
      onBargeIn();
    }

    // 抓一帧画面
    const frame = cameraRef.current?.captureFrame();
    if (frame) {
      lastFrameRef.current = frame;
      setFrameCount((c) => c + 1);
    }
  }, [cameraRef, wsStatus, active, isAiSpeaking, isAudioPlaying, onBargeIn]);

  // ── 语音结束 ──
  const handleSpeechEnd = useCallback(async () => {
    if (!active) return;
    const audioB64 = getVadAudioB64();
    const frame = lastFrameRef.current;

    if (!audioB64) {
      setDiffReason("无音频");
      return;
    }

    if (audioB64.length < 200) {
      setDiffReason("音频过短");
      return;
    }

    if (isAiSpeaking() || isAudioPlaying()) return;

    const sent = await trySend(audioB64, frame || "");
    if (!sent) setDiffReason("发送失败");
  }, [active, trySend, isAiSpeaking, isAudioPlaying]);

  // ── VAD 集成 ──
  const vad = useVAD({
    onSpeechStart: handleSpeechStart,
    onSpeechEnd: handleSpeechEnd,
  });
  useEffect(() => {
    setIsSpeaking(vad.isSpeaking);
    setVadState(vad.vadState);
  }, [vad.isSpeaking, vad.vadState]);

  return { isSpeaking, vadState, frameCount, diffReason };
}
