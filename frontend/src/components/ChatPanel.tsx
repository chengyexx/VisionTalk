import { useRef, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";

interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
}

interface ChatPanelProps {
  messages: Message[];
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === "user";
  const isSystem = msg.role === "system";

  return (
    <motion.div
      className={`message ${isUser ? "user" : isSystem ? "system" : "assistant"}`}
      initial={{ opacity: 0, x: isUser ? 20 : -20, scale: 0.96 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      transition={{ type: "spring", stiffness: 300, damping: 24 }}
    >
      <div className="message-content">{msg.content}</div>
      <div className="message-time">{formatTime(msg.timestamp)}</div>
    </motion.div>
  );
}

export function ChatPanel({ messages }: ChatPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  if (messages.length === 0) {
    return (
      <div className="chat-panel empty">
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
        >
          开始对话 — AI 将看到你的画面并回应
        </motion.p>
      </div>
    );
  }

  return (
    <div className="chat-panel">
      <AnimatePresence mode="popLayout">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} msg={msg} />
        ))}
      </AnimatePresence>
      <div ref={bottomRef} />
    </div>
  );
}
