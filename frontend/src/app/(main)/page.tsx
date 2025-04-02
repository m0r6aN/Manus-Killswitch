"use client"; // Required for useState, useEffect, hooks

import React, { useState, useCallback, useEffect } from "react";
import Sidebar from "@/components/nav/sidebar";
import { ChatList } from "@/components/chat/chat-list";
import ChatContent from "@/components/chat/chat-content";
import { CodePanel } from "@/components/tools/code-panel";
import ChatInput from "@/components/chat/chat-input";
import { useWebSocket } from "@/contexts/websocket-context";
import { LayoutWrapper } from "@/components/layout/layout-wrapper";
import { ConnectionStatus } from "@/components/chat/connection-status";

interface DisplayMessage {
  id: string; // Use task_id or generate unique ID for display
  agent: string;
  content: string;
  timestamp: string; // Keep as string for display simplicity
  intent?: string;
  event?: string;
  outcome?: string;
  isUser: boolean; // Flag to indicate user message
  type: string; // The original WebSocket message type
}

export default function Home() {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [clientId, setClientId] = useState<string | null>(null);
  const [agentStatus, setAgentStatus] = useState<{ [key: string]: string }>({});
  const { socket, isConnected, sendMessage, connectionAttempts } = useWebSocket();

  // Handle incoming messages from WebSocket
  useEffect(() => {
    if (!socket) return;

    const handleIncomingMessage = (event: MessageEvent) => {
      try {
        const wsMsg = JSON.parse(event.data);

        console.log("Received WS Message:", wsMsg);

        // Handle connection confirmation and client ID
        if (wsMsg.type === "connection_established") {
          setClientId(wsMsg.payload?.client_id || null);

          // Add system message about connection
          const connectionMessage: DisplayMessage = {
            id: `conn-${Date.now()}`,
            agent: "System",
            content: `Connection established. Client ID: ${
              wsMsg.payload?.client_id || "Unknown"
            }`,
            timestamp: new Date().toISOString(),
            isUser: false,
            type: "system",
          };

          setMessages((prev) => [...prev, connectionMessage]);
          return;
        }

        // Handle agent status updates from WS Server (on-demand check)
        if (wsMsg.type === "agent_status") {
          console.log("Received on-demand agent status:", wsMsg.payload);
          return; // Don't display status in chat
        }

        // --- Coordinator's Status Update ---
        if (wsMsg.type === "system_status_update") {
          const statusPayload = wsMsg.payload;
          console.log(
            "Received System Status Update from Coordinator:",
            statusPayload
          );

          // Update agent status
          setAgentStatus(statusPayload.agent_status || {});

          // Add a discrete status message if needed
          const readyStatus = statusPayload.system_ready;
          if (readyStatus !== undefined) {
            const statusMessage: DisplayMessage = {
              id: `status-${Date.now()}`,
              agent: "System",
              content: readyStatus
                ? "All systems ready and operational."
                : "Some systems are offline or not responding.",
              timestamp: new Date().toISOString(),
              isUser: false,
              type: "status",
            };

            setMessages((prev) => [...prev, statusMessage]);
          }

          return;
        }

        // Process regular messages - display in chat
        if (
          wsMsg.type === "message" ||
          wsMsg.type === "task_update" ||
          wsMsg.type === "task_result"
        ) {
          const newDisplayMessage: DisplayMessage = {
            id: wsMsg.payload?.task_id || `msg-${Date.now()}`,
            agent: wsMsg.payload?.agent || "System",
            content: wsMsg.payload?.content || JSON.stringify(wsMsg.payload),
            timestamp: wsMsg.payload?.timestamp || new Date().toISOString(),
            intent: wsMsg.payload?.intent,
            event: wsMsg.payload?.event,
            outcome: wsMsg.payload?.outcome,
            isUser: false,
            type: wsMsg.type,
          };

          setMessages((prev) => [...prev, newDisplayMessage]);
        }
      } catch (error) {
        console.error(
          "Failed to parse WebSocket message:",
          error,
          "Data:",
          event.data
        );
      }
    };

    // Add message event listener
    socket.addEventListener("message", handleIncomingMessage);

    // Clean up
    return () => {
      socket.removeEventListener("message", handleIncomingMessage);
    };
  }, [socket]);

  // Add a system message when reconnection happens
  useEffect(() => {
    if (connectionAttempts > 0) {
      const reconnectMessage: DisplayMessage = {
        id: `reconnect-${Date.now()}`,
        agent: "System",
        content: `Reconnection attempt ${connectionAttempts} in progress...`,
        timestamp: new Date().toISOString(),
        isUser: false,
        type: "system",
      };

      setMessages((prev) => [...prev, reconnectMessage]);
    }
  }, [connectionAttempts]);

  const handleSendMessage = useCallback(
    (inputText: string) => {
      if (inputText.trim()) {
        console.log(`Sending message: ${inputText}`);
        // Determine if it's a command or chat/task
        const messageType = inputText.startsWith("/")
          ? "command"
          : "start_task";

        const wsMessage = {
          type: messageType,
          payload: {
            content: inputText,
          },
        };

        // Add user message to display immediately
        const userDisplayMessage: DisplayMessage = {
          id: `user-${Date.now()}`,
          agent: clientId || "User",
          content: inputText,
          timestamp: new Date().toISOString(),
          isUser: true,
          type: "my_message", // Custom type for styling user messages
        };

        setMessages((prev) => [...prev, userDisplayMessage]);

        // This will queue message if disconnected
        sendMessage(wsMessage);
      }
    },
    [clientId, sendMessage]
  );

  // Example active chat data (replace with dynamic data later)
  const activeChat = { id: "chat1", name: "Main Task" };

  return (
    <LayoutWrapper>
      {/* Pass components as children to LayoutWrapper */}
      <Sidebar agentStatus={agentStatus} isConnected={isConnected} />
      <ChatList
        activeChatId=""
        agents={[]}
        chatThreads={[]}
        agentStatuses={agentStatus}
        activeThreadId={activeChat.id}
        isConnected={isConnected}
        createDirectThread={() => {}}
        setActiveThreadId={() => {}}
        setChatThreads={() => {}}
        formatTimestamp={(timestamp) => timestamp}
      />
      <div className="flex flex-col h-full">
        {" "}
        {/* Container for ChatContent and ChatInput */}
        {/* Add connection status bar at the top */}
        <div className="p-2 border-b">
          <ConnectionStatus />
        </div>
        <ChatContent messages={messages} />
        <ChatInput
          onSendMessage={handleSendMessage}
          isConnected={isConnected}
          isReconnecting={connectionAttempts > 0}
        />
      </div>
      <CodePanel
        outputContent=""
        codeInput={
          "// Tool interactions will appear here\n" +
          JSON.stringify(messages.slice(-1)[0] || {}, null, 2)
        }
        isConnected={isConnected}
        isCodePanelOpen={true}
        setCodeInput={() => {}}
        setIsCodePanelOpen={() => {}}
        sendCode={() => {}}
        testCode={() => {}}
        clearCode={() => {}}
      />
    </LayoutWrapper>
  );
}