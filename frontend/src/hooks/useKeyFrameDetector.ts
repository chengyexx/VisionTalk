import { useRef, useCallback } from "react";
import { isKeyFrame } from "../utils/frameDiff";

/**
 * Joint VAD + Frame Diff trigger logic.
 * Sends a frame only when BOTH conditions are met:
 * 1. User is speaking (VAD active)
 * 2. Current frame differs from last sent frame
 */
export function useKeyFrameDetector() {
  const lastSentFrameRef = useRef<string | null>(null);

  /**
   * Decide whether to send the current frame.
   * @param frame - Current Base64 frame
   * @param isSpeaking - Whether VAD detects speech (stubbed to true for now)
   * @param threshold - Frame diff threshold (default 0.05)
   * @returns { shouldSend: boolean, reason: string }
   */
  const shouldSend = useCallback(
    async (
      frame: string,
      isSpeaking: boolean,
      threshold: number = 0.05
    ): Promise<{ shouldSend: boolean; reason: string }> => {
      if (!isSpeaking) {
        return { shouldSend: false, reason: "VAD: not speaking" };
      }

      const changed = await isKeyFrame(lastSentFrameRef.current, frame, threshold);

      if (!changed) {
        return { shouldSend: false, reason: "Frame diff: no significant change" };
      }

      lastSentFrameRef.current = frame;
      return { shouldSend: true, reason: "Key frame detected" };
    },
    []
  );

  /** Reset the last-sent frame reference (e.g., after VAD session ends). */
  const reset = useCallback(() => {
    lastSentFrameRef.current = null;
  }, []);

  return { shouldSend, reset };
}
