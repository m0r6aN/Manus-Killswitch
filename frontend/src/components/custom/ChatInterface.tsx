import React, { useState, useEffect, useCallback } from 'react';
import ChatContent from './ChatContent'; // Your component for displaying messages
import ChatInput from './ChatInput';   // Your component for user input
import StreamBox from './StreamBox';   // Your StreamBox component

// Define the structure for WebSocket messages (adjust based on your actual backend)
interface WebSocketEventData {
  event: 'stream_update' | 'stream_start' | 'stream_end' | 'final_result' | 'chat_message' | 'error' | string; // Add other events
  data: {
    agent: string;
    task_id?: string; // Task ID is crucial for streams
    message_id?: string; // For regular messages
    delta?: string;   // For stream_update
    content?: string; // For final_result, chat_message, error
    timestamp?: string;
    intent?: string; // Add intent field
    event?: string; // Add event field
    outcome?: string;
    isUser?: boolean;
    // Add other potential fields: outcome, isUser etc.
  };
}

interface DisplayMessage { // Keep your display structure consistent
  id: string;
  agent: string;
  content: string;
  timestamp: string;
  intent?: string;
  event?: string;
  outcome?: string;
  isUser: boolean;
  type: 'message' | 'error' | string; // Add a type field
  task_id?: string; // Good to keep track if related to a task
}

// Structure for tracking active streams and their content
interface ActiveStream {
  taskId: string;
  agent: string;
  content: string;
}

const ChatInterface: React.FC = () => {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  // Use an object for activeStreams for easier access/update by key
  const [activeStreams, setActiveStreams] = useState<Record<string, ActiveStream>>({});
  const [websocket, setWebsocket] = useState<WebSocket | null>(null);

  // --- WebSocket Connection ---
  useEffect(() => {
    // Replace with your actual WebSocket server URL
    const ws = new WebSocket('ws://localhost:8000/ws/some_client_id');

    ws.onopen = () => {
      console.log('WebSocket Connected');
      setWebsocket(ws);
    };

    ws.onmessage = (event) => {
      try {
        const message: WebSocketEventData = JSON.parse(event.data);
        console.log('WS Message Received:', message); // Log incoming messages
        handleWebSocketMessage(message);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', event.data, error);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket Error:', error);
      // Add error handling UI feedback if needed
    };

    ws.onclose = () => {
      console.log('WebSocket Disconnected');
      setWebsocket(null);
      setActiveStreams({}); // Clear active streams on disconnect
      // Optionally try to reconnect
    };

    // Cleanup on component unmount
    return () => {
      ws.close();
    };
  }, []); // Runs only once on mount

  // --- Handling Incoming Messages ---
  const handleWebSocketMessage = useCallback((eventData: WebSocketEventData) => {
    const { event, data } = eventData;
    const { agent, task_id, delta, content, message_id } = data;
    const streamKey = task_id && agent ? `${task_id}_${agent}` : null;

    switch (event) {
      case 'stream_start':
        if (streamKey && task_id) {
          console.log(`Stream Start: ${streamKey}`);
          // Initialize the stream in our state, potentially with placeholder text
          setActiveStreams(prev => ({
            ...prev,
            [streamKey]: {
                taskId: task_id,
                agent: agent,
                content: `⚡ ${agent} is typing...\n` // Initial placeholder
            }
          }));
        } else {
            console.warn("Stream start event missing task_id or agent", data);
        }
        break;

      case 'stream_update':
        if (streamKey && delta) {
          // Append delta to the existing content for the specific stream
          setActiveStreams(prev => {
            const currentStream = prev[streamKey];
            // Ensure the stream exists before trying to update
            if (!currentStream) {
                 console.warn(`Received stream_update for unknown stream: ${streamKey}`);
                 // Optionally start it now if we missed the start event
                 // return { ...prev, [streamKey]: { taskId: task_id!, agent: agent, content: delta } };
                 return prev; // Or ignore if start is mandatory
            }
            // Clean initial placeholder if it exists
            const newContent = currentStream.content.startsWith(`⚡ ${agent} is typing...\n`)
                ? delta
                : currentStream.content + delta;

            return {
              ...prev,
              [streamKey]: {
                ...currentStream,
                content: newContent // Append delta
              }
            };
          });
        }
        break;

      case 'stream_end': // Or potentially use 'final_result' if that contains the full text
        if (streamKey) {
            console.log(`Stream End: ${streamKey}`);
            // Option 1: Use content from state if 'final_result' isn't guaranteed
            const finalContentFromState = activeStreams[streamKey]?.content;

            // Option 2: Prefer 'content' from the event data if available and represents the true final state
            const finalContent = content ?? finalContentFromState ?? ''; // Use event content if provided

            if (finalContent) {
                // Add the completed stream content as a regular message
                 addMessage({
                    id: message_id || `${task_id}_${Date.now()}`, // Create an ID
                    agent: agent,
                    content: finalContent,
                    timestamp: data.timestamp || new Date().toISOString(),
                    isUser: false,
                    type: 'message', // Or determine type based on content/outcome?
                    task_id: task_id,
                    // Pass other relevant fields from 'data' if available (intent, outcome etc)
                    intent: data.intent,
                    event: data.event, // Could be 'complete' etc.
                    outcome: data.outcome,
                 });
            }

          // Remove the stream from active streams
          setActiveStreams(prev => {
            const { [streamKey]: _, ...rest } = prev; // Destructure to remove key
            return rest;
          });
        }
        break;

     case 'final_result': // Handle case where full final text comes separately
        if (streamKey && content) {
             console.log(`Final Result Received: ${streamKey}`);
             // Add this as a final message
             addMessage({
               id: message_id || `${task_id}_${Date.now()}`,
               agent: agent,
               content: content,
               timestamp: data.timestamp || new Date().toISOString(),
               isUser: false,
               type: 'message',
               task_id: task_id,
               intent: data.intent,
               event: data.event,
               outcome: data.outcome,
             });

             // Ensure it's removed from active streams if not already done by stream_end
             setActiveStreams(prev => {
                const { [streamKey]: _, ...rest } = prev;
                return rest;
             });
        }
         break;

      case 'chat_message':
        if (content) {
           addMessage({
                id: message_id || `msg_${Date.now()}`,
                agent: agent, // Could be 'user' or an agent name
                content: content,
                timestamp: data.timestamp || new Date().toISOString(),
                isUser: agent === 'user', // Determine if it's the user's own message
                type: 'message',
                intent: data.intent,
             });
        }
        break;

      case 'error':
         if (content) {
            addMessage({
                id: message_id || `err_${Date.now()}`,
                agent: agent || 'System', // Default to System if agent unknown
                content: `Error: ${content}`,
                timestamp: data.timestamp || new Date().toISOString(),
                isUser: false,
                type: 'error', // Special type for styling
                task_id: task_id, // Associate error with task if possible
            });
             // Also remove stream if error relates to an active one
             if (streamKey) {
                 setActiveStreams(prev => {
                    const { [streamKey]: _, ...rest } = prev;
                    return rest;
                 });
             }
         }
          break;

      default:
        console.log('Received unhandled WebSocket event:', event);
    }
  }, [activeStreams]); // Include activeStreams dependency for final content access on end

  // Helper to add a message to state
  const addMessage = (msg: DisplayMessage) => {
    setMessages(prev => [...prev, msg]);
  };

  // --- Sending Messages ---
  const handleSendMessage = (userInput: string) => {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        // 1. Immediately display the user's message
        const userMessage: DisplayMessage = {
            id: `user_${Date.now()}`,
            agent: 'user',
            content: userInput,
            timestamp: new Date().toISOString(),
            isUser: true,
            type: 'message',
        };
        addMessage(userMessage);

        // 2. Send the message to the backend via WebSocket
        // Adjust the payload structure according to your backend expectations
        const payload = {
            type: "chat_message", // Or 'start_task' etc.
            payload: {
                content: userInput,
                // Include client_id, task_id if needed
            }
        };
        websocket.send(JSON.stringify(payload));

    } else {
      console.error('WebSocket is not connected.');
      // Show error to user?
       addMessage({
           id: `err_ws_${Date.now()}`,
           agent: 'System',
           content: 'Error: Not connected to server. Cannot send message.',
           timestamp: new Date().toISOString(),
           isUser: false,
           type: 'error',
       });
    }
  };

  // Get active stream data as an array for rendering
  const currentActiveStreams = Object.values(activeStreams);

  return (
    <div className="flex flex-col h-screen bg-gray-100 dark:bg-gray-900">
      {/* Pass only historical messages to ChatContent */}
      <ChatContent messages={messages} />

      {/* Render active StreamBoxes separately below chat history */}
      <div className="p-4 space-y-2">
        {currentActiveStreams.map(stream => (
          <StreamBox
            key={`${stream.taskId}_${stream.agent}`} // Unique key
            taskId={stream.taskId}
            agent={stream.agent}
            content={stream.content} // Pass the current content
            // Add styling as needed
            className="max-w-xs md:max-w-md lg:max-w-lg xl:max-w-xl bg-gray-200 dark:bg-gray-700 rounded p-2 text-sm"
          />
        ))}
      </div>

      {/* Your Chat Input Component */}
      <ChatInput onSendMessage={handleSendMessage} isConnected={false} />
    </div>
  );
};

export default ChatInterface;