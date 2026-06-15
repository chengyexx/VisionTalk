import { useRef, useState, useCallback } from "react";
import { useWebSocket, type WSStatus } from "./useWebSocket";
import { useAudioPlayback } from "./useAudioPlayback";

export interface Message {
  id: string;
  role: "user" | "assistant" | "assistant-streaming" | "system";
  content: string;
  timestamp: number;
}

let _msgId = 0;
function newMsg(role: Message["role"], content: string): Message {
  return { id: String(++_msgId), role, content, timestamp: Date.now() };
}

interface UseConversationOptions {
  wsUrl: string;
  /** 外部调用: 打断时执行（停止录音/重置） */
  onInterrupt?: () => void;
  /** AI 进入 idle 状态时回调 */
  onAiIdle?: () => void;
}

/**
 * 对话状态管理 — 消息历史 + WebSocket + 模型切换 + 打断协调。
 * 统一管理所有与 conversational state 相关的逻辑。
 */
export function useConversation({ wsUrl, onInterrupt, onAiIdle }: UseConversationOptions) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [wsStatus, setWsStatus] = useState<WSStatus>("disconnected");
  const [retryIn, setRetryIn] = useState(0);
  const [currentModel, setCurrentModel] = useState("dashscope/qwen-vl-max");

  const { playing: audioPlaying, playChunk, stop: stopAudio } = useAudioPlayback();
  const isAiSpeakingRef = useRef(false);

  // ── WebSocket 消息分发 ──
  const onWsMessage = useCallback(
    (data: unknown) => {
      const m = data as Record<string, unknown>;
      switch (m.type) {
        case "asr_final": {
          const asrText = m.text as string;
          if (asrText) {
            setMessages((prev) => [...prev, newMsg("user", asrText)]);
          }
          break;
        }
        case "state_change": {
          const st = m.state as string;
          if (st === "thinking") isAiSpeakingRef.current = true;
          if (st === "idle") {
            isAiSpeakingRef.current = false;
            onAiIdle?.();
          }
          setMessages((p) => [
            ...p,
            newMsg("system", st === "thinking" ? "AI 思考中..." : "就绪"),
          ]);
          break;
        }
        case "vlm_token": {
          const tok = m.text as string;
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === "assistant-streaming") {
              const copy = [...prev];
              copy[copy.length - 1] = {
                ...last,
                content: last.content + tok,
                timestamp: Date.now(),
              };
              return copy;
            }
            return [
              ...prev,
              {
                id: String(++_msgId),
                role: "assistant-streaming" as const,
                content: tok,
                timestamp: Date.now(),
              },
            ];
          });
          break;
        }
        case "tts_chunk": {
          const b64 = m.audio_b64 as string;
          if (b64) playChunk(b64);
          break;
        }
        case "turn_end": {
          const p = m.payload as Record<string, unknown>;
          const vlm = (p?.vlm_response as string) || "";
          if (p?.error) {
            setMessages((prev) => [...prev, newMsg("system", `错误: ${p.error}`)]);
            return;
          }
          setMessages((prev) => {
            console.log("[turn_end] before — msgs=%d roles=%s",
              prev.length,
              prev.map((x: Message) => x.role.charAt(0)).join(""));
            // 移除流式残影 + 内部状态标记 ("AI 思考中..." / "就绪")
            const cleaned = prev.filter(
              (x) =>
                x.role !== "assistant-streaming" &&
                !(x.role === "system" && (x.content === "AI 思考中..." || x.content === "就绪"))
            );
            const result = [...cleaned, newMsg("assistant", vlm)];
            console.log("[turn_end] after — msgs=%d roles=%s",
              result.length,
              result.map((x: Message) => x.role.charAt(0)).join(""));
            return result;
          });
          break;
        }
        case "error": {
          setMessages((prev) => [...prev, newMsg("system", `错误: ${m.message}`)]);
          break;
        }
      }
    },
    [playChunk]
  );

  const onWsStatusChange = useCallback(
    (s: WSStatus, retry: number) => {
      setWsStatus(s);
      setRetryIn(retry);
    },
    []
  );

  const { send } = useWebSocket({
    url: wsUrl,
    onMessage: onWsMessage,
    onStatusChange: onWsStatusChange,
  });

  // ── 模型切换 ──
  const switchModel = useCallback(
    async (modelId: string) => {
      setCurrentModel(modelId);
      try {
        await fetch("http://localhost:8000/api/model/switch", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ type: "vlm", model: modelId }),
        });
        setMessages((prev) => [
          ...prev,
          newMsg("system", `模型: ${modelId.split("/")[1]}`),
        ]);
      } catch {
        setMessages((prev) => [...prev, newMsg("system", "切换失败")]);
      }
    },
    []
  );

  // ── 打断 (Barge-in) ──
  const interrupt = useCallback(() => {
    isAiSpeakingRef.current = false;
    stopAudio();
    onInterrupt?.();
    send({ type: "interrupt" });
    setMessages((prev) => [...prev, newMsg("system", "打断 — 重新聆听...")]);
  }, [send, stopAudio, onInterrupt]);

  return {
    messages,
    wsStatus,
    retryIn,
    currentModel,
    audioPlaying,
    isAiSpeaking: () => isAiSpeakingRef.current,
    send,
    switchModel,
    interrupt,
  };
}
