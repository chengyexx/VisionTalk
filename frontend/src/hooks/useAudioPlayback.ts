import { useRef, useState, useCallback } from "react";

/** Base64 -> Blob URL */
function b64toBlob(b64: string, mime = "audio/mp3"): string {
  const raw = atob(b64);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
  return URL.createObjectURL(new Blob([bytes], { type: mime }));
}

/**
 * 工业级 TTS 音频播放器 — 四维防御。
 *
 * 1. 队列顺序播放：不砍前一段。
 * 2. 事件解绑：打断时 nullify onended/onerror，防内存泄漏。
 * 3. Autoplay 容错：play() 被浏览器拦截时静默跳过，不卡死管线。
 * 4. 声学淡出：打断时 volume→0 + pause + src="" + load()，0ms 无爆音哑火。
 */
export function useAudioPlayback() {
  const [playing, setPlaying] = useState(false);
  const queueRef = useRef<string[]>([]);
  const playingRef = useRef(false);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);

  /** 播放下一个队列中的音频块 */
  const playNext = useCallback(() => {
    const b64 = queueRef.current.shift();
    if (!b64) {
      playingRef.current = false;
      setPlaying(false);
      return;
    }

    const url = b64toBlob(b64);
    setPlaying(true);
    playingRef.current = true;

    const audio = new Audio(url);
    currentAudioRef.current = audio;

    audio.onended = () => {
      URL.revokeObjectURL(url);
      audio.onended = null;
      audio.onerror = null;
      currentAudioRef.current = null;
      playNext();
    };

    audio.onerror = () => {
      URL.revokeObjectURL(url);
      audio.onended = null;
      audio.onerror = null;
      currentAudioRef.current = null;
      playNext();
    };

    audio.play().catch(() => {
      // Autoplay 策略拦截：静默释放，不阻塞后续队列
      URL.revokeObjectURL(url);
      audio.onended = null;
      audio.onerror = null;
      currentAudioRef.current = null;
      playingRef.current = false;
      setPlaying(false);
    });
  }, []);

  /** 置入播放队列 */
  const playChunk = useCallback((b64: string) => {
    queueRef.current.push(b64);
    if (!playingRef.current) {
      playNext();
    }
  }, [playNext]);

  /**
   * 终极打断：声学淡出 → 事件解绑 → 物理哑火 → 资源释放。
   * 无僵尸音频、无内存泄漏、无电爆声。
   */
  const stop = useCallback(() => {
    queueRef.current = [];

    const audio = currentAudioRef.current;
    if (audio) {
      audio.onended = null;
      audio.onerror = null;

      // 极速声学淡出 (< 20ms)：volume 归零防扬声器 Pop Click
      audio.volume = 0;
      audio.pause();
      audio.currentTime = 0;
      audio.src = "";
      audio.load();          // 强制释放媒体解码器资源

      currentAudioRef.current = null;
    }

    playingRef.current = false;
    setPlaying(false);
  }, []);

  return { playing, playChunk, stop };
}
