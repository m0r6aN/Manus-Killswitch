// src/contexts/websocket-context.tsx
"use client"

import React, { createContext, useContext, useEffect, useState, useRef, useCallback, ReactNode } from 'react';
import { useToast } from '@/app/hooks/use-toast';

interface ActiveStream {
  taskId: string;
  agent: string;
  // Optional: maybe store initial content or status here
}
const [activeStreams, setActiveStreams] = useState<ActiveStream[]>([]);
const streamBuffersRef = useRef<{ [key: string]: string }>({});

// Define a more flexible message type
interface WebSocketMessage {
  type: string;
  payload: any;
  [key: string]: any; // Allow additional properties
}

interface WebSocketContextType {
  socket: WebSocket | null;
  isConnected: boolean;
  agentStatuses: { [key: string]: boolean };
  sendMessage: (message: WebSocketMessage | any) => void; // Accept any object that can be stringified
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
  disconnect: () => {}
});

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
  url = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws/tasks',
  maxReconnectAttempts = 10,
  reconnectInterval = 2000, // Start with 2 seconds
  reconnectBackoffMultiplier = 1.5 // Multiply by this factor each attempt
}) => {
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [agentStatuses, setAgentStatuses] = useState<{ [key: string]: boolean }>({});
  const [error, setError] = useState<Error | null>(null);
  const [connectionAttempts, setConnectionAttempts] = useState(0);
  const [manuallyDisconnected, setManuallyDisconnected] = useState(false);
  
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const socketUrlRef = useRef(url);
  const { toast } = useToast();

  // Queue for messages that couldn't be sent due to disconnection
  const messageQueueRef = useRef<string[]>([]);

  // Create and set up WebSocket connection
  const connectWebSocket = useCallback(() => {
    // Clear any existing reconnect timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    // Don't attempt to reconnect if manually disconnected
    if (manuallyDisconnected) {
      console.log('Not reconnecting because connection was manually closed');
      return;
    }

    try {
      // Close existing socket if it exists
      if (socket) {
        socket.close();
      }

      console.log(`Connecting to WebSocket (Attempt ${connectionAttempts + 1}/${maxReconnectAttempts})...`);
      console.log(`WebSocket URL: ${socketUrlRef.current}`);
      
      // Try different paths if you're having issues
      // If the main URL doesn't work, try these alternatives
      let wsUrl = socketUrlRef.current;
      
      // If URL is provided by env variable, make sure it's properly formatted
      if (wsUrl.startsWith('http://')) {
        wsUrl = wsUrl.replace('http://', 'ws://');
      } else if (wsUrl.startsWith('https://')) {
        wsUrl = wsUrl.replace('https://', 'wss://');
      }
      
      // Create WebSocket with the proper URL
      const ws = new WebSocket(wsUrl);
      
      // Add custom headers if needed (these can be added via URL params)
      // const ws = new WebSocket(wsUrl + '?token=your-auth-token');
      
      // Log everything for debugging
      console.log('WebSocket connecting...');
      
      ws.onopen = () => {
        console.log('WebSocket connected successfully');
        setIsConnected(true);
        setError(null);
        setConnectionAttempts(0);
        
        toast({
          title: 'Connected',
          description: 'Successfully connected to agent network.',
        });
        
        // Add to activeStreams state
        const activeStream: ActiveStream = { taskId: '', agent: '' };
        setActiveStreams([activeStream])

        // Send any queued messages
        if (messageQueueRef.current.length > 0) {
          console.log(`Sending ${messageQueueRef.current.length} queued messages`);
          
          messageQueueRef.current.forEach(message => {
            ws.send(message);
          });
          
          // Clear the queue
          messageQueueRef.current = [];
        }
        
        // Send initial handshake message if required by server
        try {
          ws.send(JSON.stringify({
            type: 'connect',
            payload: {
              client_type: 'web_ui',
              client_version: '1.0.0'
            }
          }));
          console.log('Sent initial handshake message');
        } catch (e) {
          console.error('Error sending handshake message:', e);
        }
      };

      ws.onmessage = (event) => {
        try {
          console.log('Raw message received:', event.data);
          const data = JSON.parse(event.data);
          console.log('Parsed message:', data);
      
          if (data.event === 'stream_update') {
            const { task_id, agent, delta } = data.data;
          
            const key = `${task_id}_${agent}`;
            streamBuffersRef.current[key] = (streamBuffersRef.current[key] || "") + delta;
          
            // Optional: Emit to your component or global state
            const event = new CustomEvent("llm-stream", {
              detail: { key, fullText: streamBuffersRef.current[key], delta }
            });
            window.dispatchEvent(event);
            return; // Don't fall through to default
          }

          // Handle agent status updates
          if (data.agent_status) {
            setAgentStatuses(data.agent_status);
          }
      
          // Handle heartbeat/ping responses
          if (data.type === 'ping') {
            ws.send(JSON.stringify({ type: 'pong', timestamp: new Date().toISOString() }));
          }
      
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error, 'Raw data:', event.data);
        }
      };
      

      ws.onerror = (event) => {
        console.error('WebSocket error:', event);
        setError(new Error('WebSocket connection error'));
        
        // Try to get more detailed error information if possible
        // Note: The WebSocket API doesn't provide much error detail for security reasons
        console.log('WebSocket error event:', event);
      };

      ws.onclose = (event) => {
        console.log(`WebSocket disconnected with code ${event.code} and reason: ${event.reason || 'No reason provided'}`);
        setIsConnected(false);
        
        // Log the close code for debugging
        console.log(`Close code ${event.code} explanation: ${getCloseCodeExplanation(event.code)}`);
        
        // Don't show toast if manually disconnected
        if (!manuallyDisconnected) {
          toast({
            title: 'Disconnected',
            description: `Lost connection to agent network. ${
              event.reason ? `Reason: ${event.reason}` : 'Attempting to reconnect...'
            }`,
            variant: 'destructive',
          });
          
          // Attempt to reconnect if:
          // 1. Not manually disconnected
          // 2. Haven't exceeded max attempts
          // 3. Not a normal closure (1000) or going away (1001)
          if (connectionAttempts < maxReconnectAttempts && event.code !== 1000 && event.code !== 1001) {
            const nextAttempt = connectionAttempts + 1;
            setConnectionAttempts(nextAttempt);
            
            // Calculate backoff time using exponential backoff
            const backoffTime = reconnectInterval * Math.pow(reconnectBackoffMultiplier, nextAttempt - 1);
            console.log(`Scheduling reconnect in ${backoffTime}ms (attempt ${nextAttempt})`);
            
            reconnectTimeoutRef.current = setTimeout(() => {
              connectWebSocket();
            }, backoffTime);
          } else if (connectionAttempts >= maxReconnectAttempts) {
            toast({
              title: 'Connection Failed',
              description: `Unable to reconnect after ${maxReconnectAttempts} attempts. Please try again later.`,
              variant: 'destructive',
            });

            // Remove from activeStreams state
            

          }
        }
      };

      setSocket(ws);
    } catch (err) {
      console.error('Error setting up WebSocket:', err);
      setError(err instanceof Error ? err : new Error('Failed to create WebSocket connection'));
      
      // Attempt reconnect if not manually disconnected
      if (!manuallyDisconnected && connectionAttempts < maxReconnectAttempts) {
        const nextAttempt = connectionAttempts + 1;
        setConnectionAttempts(nextAttempt);
        
        const backoffTime = reconnectInterval * Math.pow(reconnectBackoffMultiplier, nextAttempt - 1);
        reconnectTimeoutRef.current = setTimeout(() => {
          connectWebSocket();
        }, backoffTime);
      }
    }
  }, [
    connectionAttempts, 
    manuallyDisconnected, 
    maxReconnectAttempts, 
    reconnectInterval, 
    reconnectBackoffMultiplier, 
    socket, 
    toast
  ]);

  // Helper function to understand WebSocket close codes
  const getCloseCodeExplanation = (code: number): string => {
    const explanations: Record<number, string> = {
      1000: 'Normal closure - the connection successfully completed whatever purpose for which it was created.',
      1001: 'Going away - the endpoint is going away (e.g. server shutdown, browser page navigation).',
      1002: 'Protocol error - the endpoint terminated the connection due to a protocol error.',
      1003: 'Unsupported data - the connection was terminated because it received data of a type it cannot accept.',
      1004: 'Reserved. A meaning might be defined in the future.',
      1005: 'No status received - indicates that no status code was provided even though one was expected.',
      1006: 'Abnormal closure - connection was closed abnormally (no close frame).',
      1007: 'Invalid frame payload data - the endpoint terminated the connection because a message contained inconsistent data.',
      1008: 'Policy violation - the endpoint terminated the connection because it received a message that violates its policy.',
      1009: 'Message too big - the endpoint terminated the connection because a data frame was too large.',
      1010: 'Mandatory extension - the client terminated the connection because it expected the server to negotiate extensions.',
      1011: 'Internal server error - the server terminated the connection because it encountered an unexpected condition.',
      1012: 'Service restart - the server is restarting.',
      1013: 'Try again later - the server is terminating the connection due to a temporary condition.',
      1014: 'Bad gateway - the server was acting as a gateway and received an invalid response from the upstream server.',
      1015: 'TLS handshake failure - the connection was closed due to a failure to perform a TLS handshake.',
      403: 'Forbidden - the server refused the connection (often CORS or auth issues).'
    };
    
    return explanations[code] || `Unknown close code: ${code}`;
  };

  // Set up ping interval to keep connection alive
  useEffect(() => {
    let pingInterval: NodeJS.Timeout | null = null;
    
    if (socket && isConnected) {
      // Send ping every 30 seconds to keep connection alive
      pingInterval = setInterval(() => {
        try {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: 'ping', timestamp: new Date().toISOString() }));
          }
        } catch (err) {
          console.error('Error sending ping:', err);
        }
      }, 30000);
    }
    
    return () => {
      if (pingInterval) {
        clearInterval(pingInterval);
      }
    };
  }, [socket, isConnected]);

  // Initial connection
  useEffect(() => {
    connectWebSocket();
    
    // Clean up on unmount
    return () => {
      setManuallyDisconnected(true); // Prevent auto-reconnect on unmount
      
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      
      if (socket) {
        socket.close(1000, 'Component unmounted');
      }
    };
  }, [connectWebSocket]);

  // Manual reconnect function
  const reconnect = useCallback(() => {
    setManuallyDisconnected(false);
    setConnectionAttempts(0);
    connectWebSocket();
  }, [connectWebSocket]);

  // Manual disconnect function
  const disconnect = useCallback(() => {
    setManuallyDisconnected(true);
    
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    if (socket) {
      socket.close(1000, 'Manually disconnected');
    }
    
    setIsConnected(false);
  }, [socket]);

  // Function to send a message through the socket
  const sendMessage = useCallback((message: WebSocketMessage | any) => {
    try {
      const messageString = typeof message === 'string' ? message : JSON.stringify(message);
      
      if (socket && isConnected && socket.readyState === WebSocket.OPEN) {
        console.log('Sending message:', messageString);
        socket.send(messageString);
      } else {
        console.warn('Socket not connected, queuing message for later');
        
        // Queue message for when connection is restored
        messageQueueRef.current.push(messageString);
        
        // If we're not already trying to reconnect, and we're not manually disconnected, initiate reconnect
        if (!reconnectTimeoutRef.current && !manuallyDisconnected) {
          console.log('Initiating reconnect due to send attempt while disconnected');
          reconnect();
        } else {
          toast({
            title: 'Message Queued',
            description: 'You\'re currently offline. Message will be sent when connection is restored.',
            variant: 'default',
          });
        }
      }
    } catch (err) {
      console.error('Error sending message:', err);
      setError(err instanceof Error ? err : new Error('Failed to send message'));
      
      toast({
        title: 'Send Error',
        description: 'Failed to send message to server.',
        variant: 'destructive',
      });
    }
  }, [socket, isConnected, manuallyDisconnected, reconnect, toast]);

  return (
    <WebSocketContext.Provider value={{ 
      socket, 
      isConnected, 
      agentStatuses, 
      sendMessage, 
      error,
      connectionAttempts,
      manuallyDisconnected,
      reconnect,
      disconnect
    }}>
      {children}
    </WebSocketContext.Provider>
  );
};