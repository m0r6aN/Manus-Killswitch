// src/contexts/websocket-context.tsx
"use client";

import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useRef,
  useCallback,
  ReactNode,
} from "react";
import { useToast } from "@/app/hooks/use-toast";

interface WebSocketPayloadMap {
  connect: { client_type: string; client_version: string };
  ping: { timestamp: string };
  pong: { timestamp: string };
  stream_update: { task_id: string; agent: string; delta: string };
  [key: string]: Record<string, unknown>; // fallback support for unknown types
}

export interface WebSocketMessage<
  T extends keyof WebSocketPayloadMap = string
> {
  type: T;
  payload: T extends keyof WebSocketPayloadMap
    ? WebSocketPayloadMap[T]
    : unknown;
  [key: string]: unknown;
}

interface WebSocketContextType {
  socket: WebSocket | null;
  isConnected: boolean;
  agentStatuses: { [key: string]: boolean };
  sendMessage: (message: WebSocketMessage) => void;
  error: Error | null;
  connectionAttempts: number;
  manuallyDisconnected: boolean;
  reconnect: () => void;
  disconnect: () => void;
}

const WebSocketContext = createContext<WebSocketContextType>({
  socket: null,
  isConnected: false,
  agentStatuses: {},
  sendMessage: () => {},
  error: null,
  connectionAttempts: 0,
  manuallyDisconnected: false,
  reconnect: () => {},
  disconnect: () => {},
});

WebSocketContext.displayName = "WebSocketContext";

export const useWebSocket = () => useContext(WebSocketContext);

interface WebSocketProviderProps {
  children: ReactNode;
  url?: string;
  maxReconnectAttempts?: number;
  reconnectInterval?: number;
  reconnectBackoffMultiplier?: number;
}

export const WebSocketProvider: React.FC<WebSocketProviderProps> = ({
  children,
  url = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws/tasks",
  maxReconnectAttempts = 10,
  reconnectInterval = 2000,
  reconnectBackoffMultiplier = 1.5,
}) => {
  const socketRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [agentStatuses, setAgentStatuses] = useState<{
    [key: string]: boolean;
  }>({});
  const [error, setError] = useState<Error | null>(null);
  const [connectionAttempts, setConnectionAttempts] = useState(0);
  const [manuallyDisconnected, setManuallyDisconnected] = useState(false);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const socketUrlRef = useRef(url);
  const { toast } = useToast();

  const streamBuffersRef = useRef<{ [key: string]: string }>({});
  const messageQueueRef = useRef<string[]>([]);

  const connectWebSocket = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (manuallyDisconnected) {
      console.log("Not reconnecting because connection was manually closed");
      return;
    }

    try {
      if (socketRef.current) {
        socketRef.current.close();
      }

      console.log(
        `Connecting to WebSocket (Attempt ${
          connectionAttempts + 1
        }/${maxReconnectAttempts})...`
      );
      let wsUrl = socketUrlRef.current;
      if (wsUrl.startsWith("http://")) {
        wsUrl = wsUrl.replace("http://", "ws://");
      } else if (wsUrl.startsWith("https://")) {
        wsUrl = wsUrl.replace("https://", "wss://");
      }

      const ws = new WebSocket(wsUrl);
      socketRef.current = ws;

      ws.onopen = () => {
        console.log("WebSocket connected successfully");
        setIsConnected(true);
        setError(null);
        setConnectionAttempts(0);

        toast({
          title: "Connected",
          description: "Successfully connected to agent network.",
        });

        messageQueueRef.current.forEach((message) => {
          ws.send(message);
        });
        messageQueueRef.current = [];

        try {
          ws.send(
            JSON.stringify({
              type: "connect",
              payload: {
                client_type: "web_ui",
                client_version: "1.0.0",
              },
            })
          );
        } catch (e) {
          console.error("Error sending handshake message:", e);
        }
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.event === "stream_update") {
            const { task_id, agent, delta } = data.data;
            const key = `${task_id}_${agent}`;
            streamBuffersRef.current[key] =
              (streamBuffersRef.current[key] || "") + delta;
            const streamEvent = new CustomEvent("llm-stream", {
              detail: { key, fullText: streamBuffersRef.current[key], delta },
            });
            window.dispatchEvent(streamEvent);
            return;
          }

          if (data.agent_status) {
            setAgentStatuses(data.agent_status);
          }

          if (data.type === "ping") {
            ws.send(
              JSON.stringify({
                type: "pong",
                timestamp: new Date().toISOString(),
              })
            );
          }
        } catch (error) {
          console.error(
            "Failed to parse WebSocket message:",
            error,
            "Raw data:",
            event.data
          );
        }
      };

      ws.onerror = (event) => {
        console.error("WebSocket error:", event);
        setError(new Error("WebSocket connection error"));
      };

      ws.onclose = (event) => {
        console.log(
          `WebSocket disconnected with code ${event.code} and reason: ${
            event.reason || "No reason provided"
          }`
        );
        setIsConnected(false);

        if (!manuallyDisconnected) {
          toast({
            title: "Disconnected",
            description: `Lost connection to agent network. ${
              event.reason || "Attempting to reconnect..."
            }`,
            variant: "destructive",
          });

          if (
            connectionAttempts < maxReconnectAttempts &&
            event.code !== 1000 &&
            event.code !== 1001
          ) {
            const nextAttempt = connectionAttempts + 1;
            setConnectionAttempts(nextAttempt);
            const backoffTime =
              reconnectInterval *
              Math.pow(reconnectBackoffMultiplier, nextAttempt - 1);
            reconnectTimeoutRef.current = setTimeout(() => {
              connectWebSocket();
            }, backoffTime);
          } else {
            toast({
              title: "Connection Failed",
              description: `Unable to reconnect after ${maxReconnectAttempts} attempts. Please try again later.`,
              variant: "destructive",
            });
          }
        }
      };
    } catch (err) {
      console.error("Error setting up WebSocket:", err);
      setError(
        err instanceof Error
          ? err
          : new Error("Failed to create WebSocket connection")
      );
    }
  }, [
    connectionAttempts,
    manuallyDisconnected,
    maxReconnectAttempts,
    reconnectInterval,
    reconnectBackoffMultiplier,
    toast,
  ]);

  useEffect(() => {
    connectWebSocket();
    return () => {
      setManuallyDisconnected(true);
      if (reconnectTimeoutRef.current)
        clearTimeout(reconnectTimeoutRef.current);
      if (socketRef.current)
        socketRef.current.close(1000, "Component unmounted");
    };
  });

  useEffect(() => {
    let pingInterval: NodeJS.Timeout | null = null;
    if (socketRef.current && isConnected) {
      pingInterval = setInterval(() => {
        if (socketRef.current?.readyState === WebSocket.OPEN) {
          socketRef.current.send(
            JSON.stringify({
              type: "ping",
              timestamp: new Date().toISOString(),
            })
          );
        }
      }, 30000);
    }
    return () => {
      if (pingInterval) clearInterval(pingInterval);
    };
  }, [isConnected]);

  const reconnect = useCallback(() => {
    setManuallyDisconnected(false);
    setConnectionAttempts(0);
    connectWebSocket();
  }, [connectWebSocket]);

  const disconnect = useCallback(() => {
    setManuallyDisconnected(true);
    if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    if (socketRef.current)
      socketRef.current.close(1000, "Manually disconnected");
    setIsConnected(false);
  }, []);

  const sendMessage = useCallback(
    (message: WebSocketMessage) => {
      try {
        const messageString =
          typeof message === "string" ? message : JSON.stringify(message);
        if (
          socketRef.current &&
          socketRef.current.readyState === WebSocket.OPEN
        ) {
          socketRef.current.send(messageString);
        } else {
          messageQueueRef.current.push(messageString);
          if (!reconnectTimeoutRef.current && !manuallyDisconnected)
            reconnect();
          else {
            toast({
              title: "Message Queued",
              description:
                "You're currently offline. Message will be sent when connection is restored.",
              variant: "default",
            });
          }
        }
      } catch (err) {
        setError(
          err instanceof Error ? err : new Error("Failed to send message")
        );
        toast({
          title: "Send Error",
          description: "Failed to send message to server.",
          variant: "destructive",
        });
      }
    },
    [reconnect, manuallyDisconnected, toast]
  );

  return (
    <WebSocketContext.Provider
      value={{
        socket: socketRef.current,
        isConnected,
        agentStatuses,
        sendMessage,
        error,
        connectionAttempts,
        manuallyDisconnected,
        reconnect,
        disconnect,
      }}
    >
      {children}
    </WebSocketContext.Provider>
  );
};
