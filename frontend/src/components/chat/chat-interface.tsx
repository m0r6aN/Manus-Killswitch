import React, { useState, useEffect, useCallback, useRef } from "react";
import ChatContent from "./chat-content";
import ChatInput from "./chat-input";
import StreamBox from "./stream-box"; // Assuming this component is simple and functional
import { useToast } from "@/app/hooks/use-toast"

// Fetch WebSocket URL from environment variables
// Add logic to append client ID if needed
const WS_URL = import.meta.env.NEXT_PUBLIC_WS_URL;
const CLIENT_ID = `client_${Math.random().toString(36).substring(7)}`; // Example dynamic client ID

// Define the structure for WebSocket messages (adjust based on your actual backend)
// Ensure this matches your backend EXACTLY
interface WebSocketIncomingData {
  event:
    | "stream_update"
    | "stream_start"
    | "stream_end"
    | "final_result"
    | "chat_message"
    | "error"
    | "agent_status"
    | string; // Added agent_status
  data: {
    agent: string; // Should always be present?
    task_id?: string;
    message_id?: string;
    delta?: string;
    content?: string;
    timestamp?: string;
    intent?: string;
    event?: string; // Can overlap with outer event, maybe rename one? e.g., data_event
    outcome?: string;
    isUser?: boolean; // Usually determined by agent='user'
    // For agent_status event
    status?: "online" | "offline" | string;
    // Add other potential fields from your backend
  };
}

interface DisplayMessage {
  id: string;
  agent: string;
  content: string;
  timestamp: string;
  intent?: string;
  event?: string; // Inner event if present
  outcome?: string;
  isUser: boolean;
  type: "message" | "error" | "system"; // Define types clearly
  task_id?: string;
}

interface ActiveStream {
  taskId: string;
  agent: string;
  content: string;
}

// Component props (optional, if needed for parent integration)
interface ChatInterfaceProps {
  // Add props if this component needs configuration from a parent
  initialMessages?: DisplayMessage[];
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({
  initialMessages = [],
}) => {
  const [messages, setMessages] = useState<DisplayMessage[]>(initialMessages);
  const [activeStreams, setActiveStreams] = useState<
    Record<string, ActiveStream>
  >({});
  const [isConnected, setIsConnected] = useState(false);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const websocket = useRef<WebSocket | null>(null);
  const reconnectAttempt = useRef<number>(0);
  const reconnectTimeout = useRef<NodeJS.Timeout | null>(null);
  const { toast } = useToast();

  // --- WebSocket Connection Logic ---
  const connectWebSocket = useCallback(() => {
    if (!WS_URL) {
      console.error(
        "WebSocket URL is not configured. Set VITE_WS_URL environment variable."
      );
      toast({
        variant: "destructive",
        title: "Configuration Error",
        description: "WebSocket endpoint is not configured.",
      });
      return;
    }

    // Ensure client ID is appended correctly based on backend expectation
    const fullWsUrl = `${WS_URL}/${CLIENT_ID}`;
    console.log(`Attempting to connect WebSocket to: ${fullWsUrl}`);
    setIsReconnecting(true); // Indicate connection attempt

    const ws = new WebSocket(fullWsUrl);
    websocket.current = ws; // Assign to ref immediately

    ws.onopen = () => {
      console.log("WebSocket Connected");
      setIsConnected(true);
      setIsReconnecting(false);
      reconnectAttempt.current = 0; // Reset reconnect attempts on success
      toast({
        title: "Connection Status",
        description: "Connected to server.",
      });
      // Optional: Send a 'hello' message or authentication token if required
      // ws.send(JSON.stringify({ type: "authenticate", token: "..." }));
    };

    ws.onclose = (event) => {
      console.log("WebSocket Disconnected:", event.code, event.reason);
      setIsConnected(false);
      setIsReconnecting(false); // Stop showing reconnecting state immediately on close
      setActiveStreams({}); // Clear active streams on disconnect
      websocket.current = null; // Clear the ref

      // Implement exponential backoff reconnect strategy
      if (reconnectAttempt.current < 5) {
        // Limit reconnect attempts
        const delay = Math.pow(2, reconnectAttempt.current) * 1000; // Exponential backoff (1s, 2s, 4s, 8s, 16s)
        console.log(
          `WebSocket closed. Attempting to reconnect in ${
            delay / 1000
          } seconds... (Attempt ${reconnectAttempt.current + 1})`
        );
        toast({
          title: "Connection Lost",
          description: `Attempting to reconnect in ${delay / 1000}s...`,
          variant: "destructive",
        });
        setIsReconnecting(true); // Show reconnecting state while waiting
        if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current); // Clear existing timeout
        reconnectTimeout.current = setTimeout(() => {
          reconnectAttempt.current++;
          connectWebSocket(); // Retry connection
        }, delay);
      } else {
        console.error("WebSocket reconnection attempts exceeded.");
        toast({
          variant: "destructive",
          title: "Connection Failed",
          description:
            "Could not reconnect to the server after multiple attempts.",
        });
        setIsReconnecting(false); // Give up reconnecting
      }
    };

    ws.onerror = (error) => {
      console.error("WebSocket Error:", error);
      // The 'onclose' event will usually fire after an error, triggering reconnect logic
      toast({
        variant: "destructive",
        title: "WebSocket Error",
        description: "An error occurred with the connection.",
      });
      setIsReconnecting(false); // Stop showing reconnecting if error occurs before close
      // Consider explicitly calling ws.close() here if onerror doesn't always trigger onclose
    };

    ws.onmessage = (event) => {
      try {
        const message: WebSocketIncomingData = JSON.parse(event.data as string);
        console.log("WS Message Received:", message); // Log incoming messages
        handleWebSocketMessage(message); // Process the message
      } catch (error) {
        console.error("Failed to parse WebSocket message:", event.data, error);
        addSystemMessage(`Received malformed data from server.`, "error");
      }
    };
  }, [toast]); // Include toast in dependencies

  // --- Effect for Initial Connection & Cleanup ---
  useEffect(() => {
    connectWebSocket(); // Initial connection attempt

    // Cleanup function
    return () => {
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current); // Clear any pending reconnect timeout
      }
      if (websocket.current) {
        console.log("Closing WebSocket connection on component unmount.");
        websocket.current.onclose = null; // Prevent reconnect logic from firing on manual close
        websocket.current.close();
        websocket.current = null;
      }
    };
  }, [connectWebSocket]); // Depend on the memoized connect function

  // Helper to add a regular or error message
  const addMessage = useCallback(
    (msg: Omit<DisplayMessage, "id"> & { id?: string }) => {
      // Ensure unique ID
      const messageWithId: DisplayMessage = {
        ...msg,
        id: msg.id || `${msg.agent}_${Date.now()}_${Math.random()}`,
      };
      setMessages((prev) => [...prev, messageWithId]);
    },
    []
  );

  // Helper to add a system message
  const addSystemMessage = useCallback(
    (content: string, type: "system" | "error" = "system") => {
      addMessage({
        agent: "System",
        content: content,
        timestamp: new Date().toISOString(),
        isUser: false,
        type: type, // Use type argument
      });
    },
    [addMessage]
  );

  // --- Message Handling Logic ---
  const handleWebSocketMessage = useCallback(
    (eventData: WebSocketIncomingData) => {
      const { event, data } = eventData;
      const { agent, task_id, delta, content, message_id, status } = data || {}; // Safely destructure data

      // Ensure agent is present for most events
      if (!agent && !["error", "agent_status"].includes(event)) {
        // Allow error/status without agent
        console.warn("Received event without agent:", eventData);
        addSystemMessage(`Received event missing agent information.`, "error");
        return;
      }

      // Use task_id and agent for stream identification
      const streamKey = task_id && agent ? `${task_id}_${agent}` : null;

      switch (event) {
        case "stream_start":
          if (streamKey && task_id && agent) {
            console.log(`Stream Start: ${streamKey}`);
            setActiveStreams((prev) => ({
              ...prev,
              [streamKey]: { taskId: task_id, agent: agent, content: "" }, // Start with empty content
            }));
          } else {
            console.warn("Stream start event missing task_id or agent", data);
          }
          break;

        case "stream_update":
          if (streamKey && delta !== undefined && delta !== null) {
            // Check delta exists
            setActiveStreams((prev) => {
              const currentStream = prev[streamKey];
              if (!currentStream) {
                // Optionally handle updates for streams we missed the start of
                console.warn(
                  `Received stream_update for unknown stream: ${streamKey}. Starting stream now.`
                );
                return {
                  ...prev,
                  [streamKey]: {
                    taskId: task_id!,
                    agent: agent!,
                    content: delta,
                  },
                };
                // return prev; // Or ignore if start is mandatory
              }
              return {
                ...prev,
                [streamKey]: {
                  ...currentStream,
                  content: currentStream.content + delta,
                },
              };
            });
          } // Ignore if delta is missing
          break;

        case "stream_end":
        case "final_result": // Treat end and final_result similarly for adding message
          if (streamKey) {
            console.log(
              `${
                event === "stream_end" ? "Stream End" : "Final Result"
              }: ${streamKey}`
            );
            const finalContent =
              content ?? activeStreams[streamKey]?.content ?? ""; // Prefer event content, fallback to state

            if (finalContent || event === "stream_end") {
              // Add message even if empty on stream_end
              addMessage({
                id: message_id || `${task_id}_${Date.now()}`,
                agent: agent!, // Assert agent exists based on streamKey check
                content: finalContent,
                timestamp: data?.timestamp || new Date().toISOString(),
                isUser: false,
                type: "message",
                task_id: task_id,
                intent: data?.intent,
                event: data?.event, // Inner event
                outcome: data?.outcome,
              });
            }

            // Remove the stream from active streams
            setActiveStreams((prev) => {
              const { [streamKey]: _, ...rest } = prev;
              console.log(_);
              return rest;
            });
          }
          break;

        case "chat_message":
          if (agent && content !== undefined && content !== null) {
            addMessage({
              id: message_id || `msg_${agent}_${Date.now()}`,
              agent: agent,
              content: content,
              timestamp: data?.timestamp || new Date().toISOString(),
              // Determine isUser based on agent name (adjust if needed)
              isUser:
                agent.toLowerCase() === "user" ||
                agent.toLowerCase() === "commander",
              type: "message",
              intent: data?.intent,
              outcome: data?.outcome,
              event: data?.event,
            });
          }
          break;

        case "error":
          addMessage({
            id: message_id || `err_${Date.now()}`,
            agent: agent || "System", // Default to System if agent unknown
            // Prepend "Error: " for clarity unless content already indicates it
            content: content
              ? content.toLowerCase().startsWith("error")
                ? content
                : `Error: ${content}`
              : "An unspecified error occurred.",
            timestamp: data?.timestamp || new Date().toISOString(),
            isUser: false,
            type: "error",
            task_id: task_id, // Associate error with task if possible
          });
          // Also remove stream if error relates to an active one
          if (streamKey) {
            setActiveStreams((prev) => {
              const { [streamKey]: _, ...rest } = prev;
              console.log(_);
              return rest;
            });
          }
          break;

        // Example: Handling Agent Status Updates
        case "agent_status":
          if (agent && status) {
            console.log(`Agent Status: ${agent} is now ${status}`);
            // TODO: Update agent status in a shared state (Context/Zustand)
            // For now, maybe show a system message:
            addSystemMessage(`Agent ${agent} is now ${status}.`);
          }
          break;

        default:
          console.warn(
            "Received unhandled WebSocket event type:",
            event,
            eventData
          );
        // Optionally add a system message for unhandled types during development
        // addSystemMessage(`Received unhandled event: ${event}`, 'system');
      }
    },
    [activeStreams, addMessage, addSystemMessage]
  ); // Include activeStreams, addMessage, and addSystemMessage dependencies for final content access on end/final

  // --- Sending Messages ---
  const handleSendMessage = useCallback(
    (userInput: string, model: string) => {
      // Accept model from input
      if (
        websocket.current &&
        websocket.current.readyState === WebSocket.OPEN
      ) {
        // 1. Immediately display the user's message (Optimistic UI)
        const userMessage: DisplayMessage = {
          id: `user_${Date.now()}`,
          agent: "user", // Or 'commander' depending on your convention
          content: userInput,
          timestamp: new Date().toISOString(),
          isUser: true,
          type: "message",
        };
        addMessage(userMessage);

        // 2. Send the message to the backend via WebSocket
        // Adjust the payload structure EXACTLY to your backend needs
        const payload = {
          type: "chat_message", // Or 'user_input', 'send_task' etc.
          payload: {
            client_id: CLIENT_ID, // Send client ID
            content: userInput,
            model_preference: model, // Send selected model
            // Add other context if needed: active_thread_id, etc.
          },
        };
        try {
          websocket.current.send(JSON.stringify(payload));
        } catch (error) {
          console.error("Failed to send message:", error);
          addSystemMessage(
            "Failed to send message. Connection issue?",
            "error"
          );
          // Revert optimistic UI? (Remove user message) - Optional
          // setMessages(prev => prev.filter(m => m.id !== userMessage.id));
        }
      } else {
        console.error("WebSocket is not connected. Cannot send message.");
        addSystemMessage(
          "Cannot send message. Not connected to server.",
          "error"
        );
        // Optionally queue message for later sending when reconnected (more complex)
      }
    },
    [addMessage]
  ); // No websocket ref dependency needed here

  // Get active stream data as an array for rendering
  const currentActiveStreams = Object.values(activeStreams);

  return (
    // Use a key for ChatInterface if needed for full reset on critical prop changes
    <div className="flex flex-col h-full max-h-screen bg-background">
      {" "}
      {/* Use h-full */}
      {/* Pass only historical messages to ChatContent */}
      <ChatContent messages={messages} />
      {/* Render active StreamBoxes separately below chat history */}
      {currentActiveStreams.length > 0 && (
        <div className="p-4 space-y-2 border-t border-border bg-muted/50 max-h-48 overflow-y-auto flex-shrink-0">
          {currentActiveStreams.map((stream) => (
            <StreamBox
              key={`${stream.taskId}_${stream.agent}`} // Unique key
              taskId={stream.taskId}
              agent={stream.agent}
              content={stream.content} // Pass the current content
              // Add styling as needed
              className="max-w-full" // Allow full width within container
            />
          ))}
        </div>
      )}
      {/* Chat Input Component */}
      <ChatInput
        onSendMessage={handleSendMessage}
        isConnected={isConnected}
        isReconnecting={isReconnecting && !isConnected} // Show reconnecting only if not yet connected
        // Pass other props like maxTokens if needed
      />
    </div>
  );
};

export default ChatInterface;
