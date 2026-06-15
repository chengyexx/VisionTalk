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
  // AI 说话期间用户插话 → 暂存等 AI 讲完再发
  const pendingAudioRef = useRef<string | null>(null);
  const pendingFrameRef = useRef("");

  const { shouldSend: shouldSendFrame, reset: resetFrameDetector } = useKeyFrameDetector();
  const audioCapture = useAudioCapture();
  const lastTtsEndRef = useRef(0);

  const notifyChange = useCallback(() => {
    onStatusChange?.({ isSpeaking, vadState, frameCount, diffReason });
  }, [onStatusChange, isSpeaking, vadState, frameCount, diffReason]);

  useEffect(() => {
    notifyChange();
  }, [isSpeaking, vadState, frameCount, diffReason, notifyChange]);

  // ── 发送当前轮次 (公共逻辑) ──
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
        resetFrameDetector();  // 每轮成功后重置帧基准，静态画面不再挡路
        onSendTurn(audioB64, frame || "");
        return true;
      }
      return false;
    },
    [shouldSendFrame, resetFrameDetector, wsStatus, onSendTurn],
  );

  // ── AI 空闲时发送暂存的插话 ──
  const flushPending = useCallback(async () => {
    const audio = pendingAudioRef.current;
    const frame = pendingFrameRef.current;
    if (!audio) return;

    // 标记 TTS 结束时刻 — 500ms 内忽略麦克风收到的残余音频
    lastTtsEndRef.current = Date.now();

    console.log("[TurnPipeline] AI 空闲，发送暂存轮次");
    const sent = await trySend(audio, frame);
    if (sent) {
      pendingAudioRef.current = null;
      pendingFrameRef.current = "";
    }
    // trySend 失败 → pending 保留，等下次 idle 重试
  }, [trySend]);

  // ── 语音开始 ──
  const handleSpeechStart = useCallback(async () => {
    if (wsStatus !== "connected") return;

    // 用户抢话：先发送 interrupt + 物理掐断音频
    if (isAiSpeaking() || isAudioPlaying()) {
      onBargeIn();
      // 退晕期：扬声器物理惯性残余 200ms 内不启动录音，防僵尸音频回路
      await new Promise((r) => setTimeout(r, 200));
    }

    const ok = await audioCapture.start();
    if (!ok) {
      console.warn("[TurnPipeline] audioCapture.start() 失败");
      isRecordingRef.current = false;
      return;
    }
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

    // TTS 反馈回路保护: 麦克风收到的残余 TTS 音频 → 500ms 窗口内直接丢弃
    if (Date.now() - lastTtsEndRef.current < 500) {
      console.log("[TurnPipeline] TTS 保护期，丢弃疑似回声");
      setDiffReason("TTS保护期");
      return;
    }

    // AI 还在说话 → 暂存，等 AI 讲完再发
    if (isAiSpeaking() || isAudioPlaying()) {
      pendingAudioRef.current = audioB64;
      pendingFrameRef.current = frame || "";
      console.log("[TurnPipeline] AI 正在讲话，暂存用户语音");
      return;
    }

    const sent = await trySend(audioB64, frame || "");
    if (!sent) {
      // trySend 失败 (冷却期/帧差/短音频) → 暂存等待下次机会
      pendingAudioRef.current = audioB64;
      pendingFrameRef.current = frame || "";
    }
  }, [audioCapture, trySend, isAiSpeaking, isAudioPlaying]);

  // ── VAD 集成 ──
  const vad = useVAD({
    onSpeechStart: handleSpeechStart,
    onSpeechEnd: handleSpeechEnd,
  });
  useEffect(() => {
    setIsSpeaking(vad.isSpeaking);
    setVadState(vad.vadState);
  }, [vad.isSpeaking, vad.vadState]);

  return { isSpeaking, vadState, frameCount, diffReason, flushPending };
}
