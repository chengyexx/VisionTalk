import { useEffect, useRef, useState, useCallback } from "react";

export type VADState = "loading" | "listening" | "error";

interface UseVADOptions {
  onSpeechStart?: () => void;
  onSpeechEnd?: (audio: Float32Array) => void;
}

/** Float32Array PCM 16kHz → WAV → Base64 */
function float32ToWavB64(audio: Float32Array): string {
  const sampleRate = 16000;
  const len = audio.length;
  const buf = new ArrayBuffer(44 + len * 2);
  const view = new DataView(buf);

  const writeStr = (off: number, s: string) => {
    for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i));
  };
  writeStr(0, "RIFF");
  view.setUint32(4, 36 + len * 2, true);
  writeStr(8, "WAVE");
  writeStr(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeStr(36, "data");
  view.setUint32(40, len * 2, true);

  let off = 44;
  for (let i = 0; i < len; i++) {
    const s = Math.max(-1, Math.min(1, audio[i]));
    view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    off += 2;
  }

  const bytes = new Uint8Array(buf);
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
}

/**
 * Browser-side Voice Activity Detection using Silero VAD v5 model.
 * Uses VAD's built-in audio buffer — no separate MediaRecorder needed.
 */
export function useVAD({ onSpeechStart, onSpeechEnd }: UseVADOptions = {}) {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [vadState, setVadState] = useState<VADState>("loading");
  const vadRef = useRef<unknown>(null);
  const callbacksRef = useRef({ onSpeechStart, onSpeechEnd });
  callbacksRef.current = { onSpeechStart, onSpeechEnd };

  const start = useCallback(async () => {
    try {
      setVadState("loading");
      const vadModule = await import("@ricky0123/vad-web");

      const vad = await vadModule.MicVAD.new({
        onSpeechStart: () => {
          setIsSpeaking(true);
          callbacksRef.current.onSpeechStart?.();
        },
        onSpeechEnd: (audio: Float32Array) => {
          setIsSpeaking(false);
          if (audio && audio.length > 0) {
            const b64 = float32ToWavB64(audio);
            (_vadAudioRef as any).current = b64;
            callbacksRef.current.onSpeechEnd?.(audio);
          }
        },
        onVADMisfire: () => {},
        model: "v5",
        baseAssetPath: "/models/",
        // 更快检测到语音开头 (默认 400ms → 150ms)
        minSpeechMs: 150,
        ortConfig: (ort: any) => {
          ort.env.wasm.wasmPaths =
            "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.26.0/dist/";
        },
      });

      vad.start();
      vadRef.current = vad;
      setVadState("listening");
    } catch (err) {
      console.error("[VAD] Failed to start:", err);
      setVadState("error");
    }
  }, []);

  const stop = useCallback(() => {
    const vad = vadRef.current as { destroy?: () => void } | null;
    vad?.destroy?.();
    vadRef.current = null;
    setIsSpeaking(false);
    setVadState("loading");
  }, []);

  useEffect(() => {
    start();
    return () => { stop(); };
  }, [start, stop]);

  return { isSpeaking, vadState, start, stop };
}

/** Ref to access latest VAD audio Base64 — set by onSpeechEnd callback */
const _vadAudioRef = { current: "" };
export function getVadAudioB64(): string {
  return _vadAudioRef.current;
}
