import { useState, useEffect, useRef, useCallback } from 'react';

// Define connection options type if needed
interface SocketOptions {
  reconnectionAttempts?: number;
  // Add other Socket.IO options as needed
}

const useWebSocket = (url: string, onMessage?: (event: MessageEvent) => void, options?: SocketOptions) => {
  const [isConnected, setIsConnected] = useState(false);
  // Use useRef to hold the socket instance without causing re-renders on change
  const socketRef = useRef<WebSocket | null>(null);

  // Use useRef for the message handler to avoid dependency changes in useEffect
  const messageHandlerRef = useRef(onMessage);
  useEffect(() => {
    messageHandlerRef.current = onMessage;
  }, [onMessage]);


  useEffect(() => {
    if (!url) return; // Don't connect if URL is not provided

    console.log(`Attempting to connect WebSocket to: ${url}`);
    // Use native WebSocket API
    const ws = new WebSocket(url);
    socketRef.current = ws;

    ws.onopen = () => {
      console.log('WebSocket Connected');
      setIsConnected(true);
    };

    ws.onclose = (event) => {
      console.log('WebSocket Disconnected:', event.reason, 'Code:', event.code);
      setIsConnected(false);
      socketRef.current = null; // Clear ref on close
      // Optional: Implement reconnection logic here if needed
    };

    ws.onerror = (error) => {
      console.error('WebSocket Error:', error);
      setIsConnected(false); // Assume disconnected on error
      // Error event often precedes close event
    };

    ws.onmessage = (event) => {
      // Use the handler from the ref
      if (messageHandlerRef.current) {
        messageHandlerRef.current(event);
      } else {
        console.log('WebSocket message received, but no handler attached:', event.data);
      }
    };

    // Cleanup function: close the WebSocket connection when the component unmounts or URL changes
    return () => {
      if (ws) {
        console.log('Closing WebSocket connection...');
        ws.close();
        socketRef.current = null;
      }
    };
  }, [url]); // Reconnect if the URL changes

  // Function to send messages
  const sendMessage = useCallback((message: string) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(message);
    } else {
      console.error('Cannot send message: WebSocket is not connected or not ready.');
      // Optionally queue message or throw error
    }
  }, []); // Empty dependency array: sendMessage function instance doesn't change


  return { isConnected, sendMessage };
};

export default useWebSocket;