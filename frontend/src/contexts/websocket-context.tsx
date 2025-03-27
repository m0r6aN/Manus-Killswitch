// src/contexts/websocket-context.tsx
"use client"

import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { useToast } from '@/app/hooks/use-toast';
import { Message } from '@/types/models'

interface WebSocketContextType {
  socket: WebSocket | null;
  isConnected: boolean;
  agentStatuses: { [key: string]: boolean };
  sendMessage: (message: Message) => void;
  error: Error | null;
}

const WebSocketContext = createContext<WebSocketContextType>({
  socket: null,
  isConnected: false,
  agentStatuses: {},
  sendMessage: () => {},
  error: null
});

export const useWebSocket = () => useContext(WebSocketContext);

interface WebSocketProviderProps {
  children: ReactNode;
}

export const WebSocketProvider: React.FC<WebSocketProviderProps> = ({ children }) => {
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [agentStatuses, setAgentStatuses] = useState<{ [key: string]: boolean }>({});
  const { toast } = useToast();

  useEffect(() => {
    // Initialize raw WebSocket connection
    const socketUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws/tasks';
    const ws = new WebSocket(socketUrl);

    // Set up event listeners
    ws.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
      toast({
        title: 'Connected',
        description: 'Successfully connected to agent network.',
      });
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('Received:', data);
        // Assuming backend sends agent_status updates in this format
        if (data.agent_status) {
          setAgentStatuses(data.agent_status);
        }
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setIsConnected(false);
      toast({
        title: 'Connection Error',
        description: 'WebSocket connection failed.',
        variant: 'destructive',
      });
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);
      toast({
        title: 'Disconnected',
        description: 'Lost connection to agent network.',
        variant: 'destructive',
      });
    };

    setSocket(ws);

    // Clean up on unmount
    return () => {
      ws.close();
    };
  }, [toast]);

  // Function to send a message through the socket
  const sendMessage = (message: Message) => {
    if (socket && isConnected && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(message));
    } else {
      toast({
        title: 'Connection Error',
        description: 'Cannot send message: Not connected to the server.',
        variant: 'destructive',
      });
    }
  };

  return (
    <WebSocketContext.Provider value={{ socket, isConnected, agentStatuses, sendMessage, error: null }}>
      {children}
    </WebSocketContext.Provider>
  );
};