"use client"; // Required for useState, useEffect, hooks

import React, { useState, useEffect, useCallback } from 'react';
import Sidebar from '@/components/custom/Sidebar';
import { ChatList } from '@/components/custom/ChatList';
import ChatContent from '@/components/custom/ChatContent';
import { CodePanel } from '@/components/custom/CodePanel';
import ChatInput from '@/components/custom/ChatInput'; // Import ChatInput
import useWebSocket from '@/app/hooks/useWebSocket';
import { LayoutWrapper } from '@/components/custom/LayoutWrapper';

// Define a type for your messages
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
  const { sendMessage: wsSend, isConnected } = useWebSocket(process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws');

  const handleIncomingMessage = useCallback((event: MessageEvent) => {
    try {
      const wsMsg = JSON.parse(event.data);
      
      console.log('Received WS Message:', wsMsg);

      // Handle connection confirmation and client ID (existing logic)
      // ...

      // Handle agent status updates from WS Server (on-demand check)
      if (wsMsg.type === 'agent_status') {
           // Maybe merge this with coordinator status or prioritize coordinator's update?
           // For now, let's keep it separate or let coordinator overwrite
           // setAgentStatus(wsMsg.payload || {});
           console.log("Received on-demand agent status:", wsMsg.payload);
           return; // Don't display status in chat
      }

      // --- Coordinator's Status Update ---
      if (wsMsg.type === 'system_status_update') {
        const statusPayload = wsMsg.payload;
        console.log("Received System Status Update from Coordinator:", statusPayload);

        // Directly use the agent_status object (which is Record<string, string>)
        // No need to convert back to boolean here!
        setAgentStatus(statusPayload.agent_status || {}); // Update state directly

        // Optionally use statusPayload.system_ready (boolean) for an overall indicator
        const isSystemReady = statusPayload.system_ready || false;
        console.log("Overall System Readiness:", isSystemReady);
        // TODO: Display isSystemReady indicator somewhere if needed

        return; // Don't display the raw status update object in the chat log
   }
   

      // Handle workflow plan results (existing logic)
      // ...

      // Process other chat messages, task updates, results etc. (existing logic)
      // ...

    } catch (error) {
      console.error('Failed to parse WebSocket message:', error, 'Data:', event.data);
    }
  }, [clientId]); // Removed wsSend dependency as it's stable via useWebSocket hook

   // Add the message listener effect using the hook
   useEffect(() => {
     // Assuming useWebSocket handles adding/removing the listener internally
     // If not, you'd get the add/remove functions from the hook and use them here
     // For simplicity, let's assume the hook manages the listener based on the callback provided
     const ws = useWebSocket(process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws', handleIncomingMessage);

     // Cleanup function if needed (depends on hook implementation)
     return () => {
       // ws.disconnect(); // Or however the hook exposes cleanup
     };
   }, [handleIncomingMessage]); // Re-run if handleIncomingMessage changes (due to clientId change)

  const handleSendMessage = (inputText: string) => {
    if (inputText.trim() && isConnected) {
      console.log(`Sending message: ${inputText}`);
      // Determine if it's a command or chat/task
      const messageType = inputText.startsWith('/') ? "command" : "start_task"; // Simple example

      const wsMessage = {
        type: messageType, // Use "start_task" for general input for now
        payload: {
          content: inputText,
          // task_id: null // Let backend generate for new tasks
        },
      };
      wsSend(JSON.stringify(wsMessage));

      // Optionally add user message to display immediately
      const userDisplayMessage: DisplayMessage = {
            id: `user-${Date.now()}`,
            agent: clientId || 'User',
            content: inputText,
            timestamp: new Date().toISOString(),
            isUser: true,
            type: 'my_message', // Custom type for styling user messages
          };
      setMessages((prevMessages) => [...prevMessages, userDisplayMessage]);

    } else if (!isConnected) {
        console.error("WebSocket not connected. Cannot send message.");
         const errorDisplayMessage: DisplayMessage = {
                id: `err-conn-${Date.now()}`,
                agent: 'System',
                content: `Error: WebSocket not connected. Cannot send message.`,
                timestamp: new Date().toISOString(),
                isUser: false,
                type: 'error',
         };
         setMessages((prevMessages) => [...prevMessages, errorDisplayMessage]);
    }
  };

  // Example active chat data (replace with dynamic data later)
  const activeChat = { id: 'chat1', name: 'Main Task' };

  return (
    <LayoutWrapper>
        {/* Pass components as children to LayoutWrapper */}
        <Sidebar agentStatus={agentStatus} isConnected={isConnected} />
        <ChatList 
          activeChatId=''
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
        <div className="flex flex-col h-full"> {/* Container for ChatContent and ChatInput */}
            <ChatContent messages={messages} />
            <ChatInput onSendMessage={handleSendMessage} isConnected={isConnected} />
        </div>
        <CodePanel 
          outputContent=''
          codeInput={"// Tool interactions will appear here\n" + JSON.stringify(messages.slice(-1)[0], null, 2)}
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