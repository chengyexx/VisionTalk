import { useRef, useCallback } from "react";

/**
 * Browser microphone capture using MediaRecorder API.
 * Captures audio in short chunks when VAD detects speech.
 */
export function useAudioCapture() {
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const start = useCallback(async (): Promise<void> => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "audio/mp4",
      });

      chunksRef.current = [];

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

  const stop = useCallback(async (): Promise<string | null> => {
    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state === "inactive") return null;

    return new Promise((resolve) => {
      recorder.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType });
        chunksRef.current = [];

        // Convert to base64
        const buffer = await blob.arrayBuffer();
        const bytes = new Uint8Array(buffer);
        let binary = "";
        for (let i = 0; i < bytes.length; i++) {
          binary += String.fromCharCode(bytes[i]);
        }
        resolve(btoa(binary));

        // Stop all tracks
        recorder.stream.getTracks().forEach((t) => t.stop());
      };

      recorder.stop();
    });
  }, []);

  return { start, stop };
}
