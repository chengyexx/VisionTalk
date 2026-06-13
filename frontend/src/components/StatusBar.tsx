import { motion } from "motion/react";
import type { WSStatus } from "../hooks/useWebSocket";
import type { VADState } from "../hooks/useVAD";

interface StatusBarProps {
  wsStatus: WSStatus;
  vadState: VADState;
  isSpeaking: boolean;
  frameCount?: number;
}

const statusLabels: Record<WSStatus, string> = {
  connected: "已连接",
  connecting: "连接中",
  disconnected: "未连接",
};

export function StatusBar({ wsStatus, vadState, isSpeaking, frameCount }: StatusBarProps) {
  return (
    <motion.div
      className="status-bar"
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      <div className={`status-item ws-${wsStatus}`}>
        <span className="status-dot" />
        <span className="status-text">{statusLabels[wsStatus]}</span>
      </div>

      <div className={`status-item vad-${vadState}`}>
        <span className={`mic-icon ${isSpeaking ? "active" : ""}`}>●</span>
        <span className="status-text">
          {vadState === "listening" ? (isSpeaking ? "说话中" : "监听中") : vadState === "loading" ? "加载VAD" : "VAD错误"}
        </span>
      </div>

      {frameCount !== undefined && (
        <div className="status-item">
          <span className="status-mono">{frameCount} frames</span>
        </div>
      )}
    </motion.div>
  );
}
