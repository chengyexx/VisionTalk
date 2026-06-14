import { useRef, useCallback } from "react";

/**
 * Browser microphone capture using MediaRecorder API → WAV/PCM.
 *
 * WebM/Opus 编码在 SenseVoice 等 ASR 接口上解析异常，
 * 会导致 API 返回固定误导文本而非真实转写。
 * 这里在采集完成后转码为 WAV (16-bit PCM, 单声道) 再 Base64 发送。
 */
export function useAudioCapture() {
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startTimeRef = useRef(0);

  const start = useCallback(async (): Promise<void> => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      const recorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : "audio/mp4",
      });

      chunksRef.current = [];
      startTimeRef.current = Date.now();

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      recorder.start(100); // Collect chunks every 100ms
      mediaRecorderRef.current = recorder;
    } catch (err) {
      console.error("[Audio] Failed to start capture:", err);
    }
  }, []);

  // WebM/MP4 blob → PCM WAV buffer (returns null if blob too short to decode)
  async function blobToWav(blob: Blob): Promise<ArrayBuffer | null> {
    // 防御: WebM/Opus 最小可解码大小约 1KB，低于此值通常是空 header
    if (blob.size < 1000) {
      console.warn("[Audio] Blob too small to decode (%d bytes)", blob.size);
      return null;
    }

    const arrayBuffer = await blob.arrayBuffer();
    const audioCtx = new AudioContext({ sampleRate: 16000 });
    let audioBuffer: AudioBuffer;
    try {
      audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
    } catch {
      console.warn("[Audio] decodeAudioData failed (blob=%d bytes)", blob.size);
      await audioCtx.close();
      return null;
    }
    await audioCtx.close();

    const sr = audioBuffer.sampleRate;
    const channel = audioBuffer.getChannelData(0);
    const len = channel.length;

    // 16-bit PCM WAV header + data
    const wav = new ArrayBuffer(44 + len * 2);
    const view = new DataView(wav);

    function writeStr(offset: number, s: string) {
      for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i));
    }

    writeStr(0, "RIFF");
    view.setUint32(4, 36 + len * 2, true);
    writeStr(8, "WAVE");
    writeStr(12, "fmt ");
    view.setUint32(16, 16, true);          // subchunk size (PCM)
    view.setUint16(20, 1, true);           // PCM = 1
    view.setUint16(22, 1, true);           // mono
    view.setUint32(24, sr, true);          // sample rate
    view.setUint32(28, sr * 2, true);      // byte rate
    view.setUint16(32, 2, true);           // block align
    view.setUint16(34, 16, true);          // bits per sample
    writeStr(36, "data");
    view.setUint32(40, len * 2, true);

    // Write PCM samples (float32 → int16)
    let offset = 44;
    for (let i = 0; i < len; i++) {
      const s = Math.max(-1, Math.min(1, channel[i]));
      const int16 = s < 0 ? s * 0x8000 : s * 0x7fff;
      view.setInt16(offset, int16, true);
      offset += 2;
    }

    return wav;
  }

  const stop = useCallback(async (): Promise<string | null> => {
    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state === "inactive") return null;

    return new Promise((resolve) => {
      recorder.onstop = async () => {
        try {
          const durationMs = Date.now() - startTimeRef.current;
          const blob = new Blob(chunksRef.current, { type: recorder.mimeType });
          chunksRef.current = [];

          // 防御: 录音不足 150ms 时 WebM/Opus 帧不完整，无法解码
          if (durationMs < 150 || blob.size < 1000) {
            console.warn(
              "[Audio] Recording too short: %dms, %d bytes — skipping",
              durationMs,
              blob.size
            );
            resolve(null);
            return;
          }

          // WebM/MP4 → WAV → Base64
          const wavBuffer = await blobToWav(blob);
          if (!wavBuffer) {
            resolve(null);
            return;
          }
          const bytes = new Uint8Array(wavBuffer);
          let binary = "";
          for (let i = 0; i < bytes.length; i++) {
            binary += String.fromCharCode(bytes[i]);
          }
          resolve(btoa(binary));
        } catch (err) {
          console.error("[Audio] WAV conversion failed:", err);
          resolve(null);
        }

        // Stop all tracks
        recorder.stream.getTracks().forEach((t) => t.stop());
      };

      recorder.stop();
    });
  }, []);

  return { start, stop };
}
