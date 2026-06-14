import { useEffect, useRef, useState, useCallback } from "react";

export type VADState = "loading" | "listening" | "error";

interface UseVADOptions {
  onSpeechStart?: () => void;
  onSpeechEnd?: () => void;
}

/**
 * Browser-side Voice Activity Detection using Silero VAD model.
 * Detects human speech in real-time from the microphone.
 *
 * Model files are served from public/models/:
 *   - silero_vad_v5.onnx     (ONNX model)
 *   - vad.worklet.bundle.min.js (AudioWorklet)
 *   - ort-wasm-*.wasm        (ONNX Runtime WASM)
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

      // Dynamic import to avoid bundling issues
      const vadModule = await import("@ricky0123/vad-web");

      const vad = await vadModule.MicVAD.new({
        onSpeechStart: () => {
          setIsSpeaking(true);
          callbacksRef.current.onSpeechStart?.();
        },
        onSpeechEnd: () => {
          setIsSpeaking(false);
          callbacksRef.current.onSpeechEnd?.();
        },
        onVADMisfire: () => {
          // Brief noise detected, not sustained speech
        },
        // v5 model is smaller and faster than legacy
        model: "v5",
        // ONNX model + AudioWorklet → served from public/models/
        baseAssetPath: "/models/",
        // onnxruntime-web WASM 不能放 /public (Vite 禁止动态 import):
        // 走 jsDelivr CDN 加载 .wasm + .mjs, 避免 Vite 报 404
        ortConfig: (ort) => {
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
    return () => {
      stop();
    };
  }, [start, stop]);

  return { isSpeaking, vadState, start, stop };
}
