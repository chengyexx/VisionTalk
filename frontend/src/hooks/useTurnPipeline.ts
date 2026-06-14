import { useRef, useState, useCallback, useEffect } from "react";
import type { CameraHandle } from "../components/Camera";
import { useKeyFrameDetector } from "./useKeyFrameDetector";
import { useVAD } from "./useVAD";
import { useAudioCapture } from "./useAudioCapture";
import type { WSStatus } from "./useWebSocket";

interface TurnPipelineOptions {
  cameraRef: React.RefObject<CameraHandle | null>;
  wsStatus: WSStatus;
  isAiSpeaking: () => boolean;
  /** TTS 音频是否正在播放 — 用于防止麦克风收录 AI 语音 (反馈回路) */
  isAudioPlaying: () => boolean;
  /** 用户打断回调 — 外部负责 stopAudio + 提示 + interrupt 消息 */
  onBargeIn: () => void;
  /** 发送管线轮次 */
  onSendTurn: (audioB64: string, frameB64: string) => void;
  /** 状态变更回调 */
  onStatusChange?: (state: TurnPipelineState) => void;
}

export interface TurnPipelineState {
  isSpeaking: boolean;
  vadState: string;
  frameCount: number;
  diffReason: string;
}

const MIN_TURN_INTERVAL = 2000; // 相邻两轮最少间隔 2 秒
const MIN_AUDIO_B64_LEN = 200;  // Base64 音频至少 200 字符

/**
 * 管线协调器 — VAD 触发 + 关键帧检测 + 发送完整轮次。
 *
 * 覆盖业务: 打断逻辑 (barge-in)、冷却守卫、帧差分过滤、音频长度守卫。
 */
export function useTurnPipeline({
  cameraRef,
  wsStatus,
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
  const isRecordingRef = useRef(false);

  const { shouldSend: shouldSendFrame } = useKeyFrameDetector();
  const audioCapture = useAudioCapture();

  // ── 状态变更通知 ──
  const notifyChange = useCallback(() => {
    onStatusChange?.({ isSpeaking, vadState, frameCount, diffReason });
  }, [onStatusChange, isSpeaking, vadState, frameCount, diffReason]);

  useEffect(() => {
    notifyChange();
  }, [isSpeaking, vadState, frameCount, diffReason, notifyChange]);

  // ── 语音开始 ──
  const handleSpeechStart = useCallback(async () => {
    if (wsStatus !== "connected") return;

    // 防御: AI 正在说话或 TTS 正在播放 → 此时检测到的"语音"可能是
    // 扬声器播放的 AI 语音被麦克风收录 (反馈回路)
    if (isAiSpeaking() || isAudioPlaying()) {
      // Barge-in — 用户打断 (AI 生成中或 TTS 播放中)
      // 关键: 只停止录音，不重启。让 VAD 在 TTS 结束后自然回到 idle，
      //       下次 VAD 检测到的才是真正的用户语音。
      isRecordingRef.current = false;
      onBargeIn();
      await audioCapture.stop();
      return;
    }

    // 正常开始
    await audioCapture.start();
    isRecordingRef.current = true;
    const frame = cameraRef.current?.captureFrame();
    if (frame) {
      lastFrameRef.current = frame;
      setFrameCount((c) => c + 1);
    }
  }, [cameraRef, audioCapture, wsStatus, isAiSpeaking, isAudioPlaying, onBargeIn]);

  // ── 语音结束 ──
  const handleSpeechEnd = useCallback(async () => {
    if (!isRecordingRef.current) return;
    isRecordingRef.current = false;
    const audioB64 = await audioCapture.stop();
    const frame = lastFrameRef.current;

    if (!audioB64) {
      setDiffReason("无音频");
      return;
    }

    // 冷却守卫
    const now = Date.now();
    if (now - lastTurnSentRef.current < MIN_TURN_INTERVAL) {
      setDiffReason("冷却中...");
      return;
    }

    // 音频长度守卫
    if (audioB64.length < MIN_AUDIO_B64_LEN) {
      setDiffReason("音频过短");
      return;
    }

    // 帧差分过滤
    const result = await shouldSendFrame(frame, true);
    if (!result.shouldSend) {
      setDiffReason(result.reason);
      return;
    }
    setDiffReason(result.reason);

    if (wsStatus === "connected") {
      lastTurnSentRef.current = now;
      onSendTurn(audioB64, frame || "");
    }
  }, [audioCapture, shouldSendFrame, wsStatus, onSendTurn]);

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
