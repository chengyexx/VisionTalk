import { useRef, useState, useCallback } from "react";

/** Base64 -> Blob URL (for inline audio playback) */
function b64toBlob(b64: string, mime = "audio/mp3"): string {
  const raw = atob(b64);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
  return URL.createObjectURL(new Blob([bytes], { type: mime }));
}

/**
 * 管理 TTS 音频播放 — WebSocket 推送的 Base64 音频块转为 Blob URL 并播放。
 * 覆盖业务: 前一段播放自动中断、URL 自动回收、打断时停止等。
 */
export function useAudioPlayback() {
  const [playing, setPlaying] = useState(false);
  const audioElRef = useRef<HTMLAudioElement | null>(null);

  /** 停止当前播放 + 回收 Blob URL */
  const stop = useCallback(() => {
    const el = audioElRef.current;
    if (el) {
      el.pause();
      if (el.src) URL.revokeObjectURL(el.src);
      audioElRef.current = null;
    }
    setPlaying(false);
  }, []);

  /** 播放 Base64 音频块 — 内部管理 Blob URL 生命周期 */
  const playChunk = useCallback((b64: string) => {
    // 中断正在播放的片段
    stop();

    const url = b64toBlob(b64);
    setPlaying(true);
    const a = new Audio(url);
    audioElRef.current = a;
    a.onended = () => {
      setPlaying(false);
      URL.revokeObjectURL(url);
    };
    a.play().catch(() => {
      setPlaying(false);
      URL.revokeObjectURL(url);
    });
  }, [stop]);

  return { playing, playChunk, stop };
}
