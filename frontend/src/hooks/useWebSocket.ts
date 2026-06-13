import { useEffect, useRef, useState, useCallback } from "react";

export type WSStatus = "connecting" | "connected" | "disconnected" | "reconnecting";

interface UseWebSocketOptions {
  url: string;
  onMessage?: (data: unknown) => void;
  reconnect?: boolean;
}

const MAX_RETRIES = 5;
const BASE_DELAY = 1000; // 1s
const MAX_DELAY = 30000; // 30s

export function useWebSocket({ url, onMessage, reconnect = true }: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const retryCountRef = useRef(0);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const intentionalCloseRef = useRef(false);
  const [status, setStatus] = useState<WSStatus>("disconnected");
  const [retryIn, setRetryIn] = useState(0);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const clearRetry = useCallback(() => {
    if (retryTimerRef.current) {
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (!reconnect) return;
    if (retryCountRef.current >= MAX_RETRIES) {
      setStatus("disconnected");
      setRetryIn(0);
      return;
    }

    const delay = Math.min(BASE_DELAY * Math.pow(2, retryCountRef.current), MAX_DELAY);
    retryCountRef.current += 1;
    setStatus("reconnecting");
    setRetryIn(Math.ceil(delay / 1000));

    retryTimerRef.current = setTimeout(() => {
      setRetryIn(0);
      connect();
    }, delay);
  }, [reconnect]);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    if (wsRef.current?.readyState === WebSocket.CONNECTING) return;

    setStatus("connecting");
    const ws = new WebSocket(url);

    ws.onopen = () => {
      console.log("[WS] Connected");
      retryCountRef.current = 0;
      setStatus("connected");
      setRetryIn(0);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessageRef.current?.(data);
      } catch {
        console.warn("[WS] Non-JSON message:", event.data);
      }
    };

    ws.onclose = () => {
      console.log("[WS] Disconnected");
      wsRef.current = null;
      if (!intentionalCloseRef.current) {
        scheduleReconnect();
      } else {
        setStatus("disconnected");
      }
    };

    ws.onerror = () => {
      // onclose will fire after this, triggering reconnect
    };

    wsRef.current = ws;
  }, [url, scheduleReconnect]);

  const disconnect = useCallback(() => {
    intentionalCloseRef.current = true;
    clearRetry();
    wsRef.current?.close();
    wsRef.current = null;
    setStatus("disconnected");
    setRetryIn(0);
  }, [clearRetry]);

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    } else {
      console.warn("[WS] Cannot send: not connected");
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      intentionalCloseRef.current = true;
      clearRetry();
      wsRef.current?.close();
    };
  }, [connect, clearRetry]);

  return { status, retryIn, send, connect, disconnect };
}
