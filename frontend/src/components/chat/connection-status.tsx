"use client";

import React from 'react';
import { useWebSocket } from '@/contexts/websocket-context';
import { Button } from '@/components/ui/button';
import { AlertCircle, Wifi, WifiOff, RefreshCw } from 'lucide-react';

export const ConnectionStatus: React.FC = () => {
  const { 
    isConnected, 
    connectionAttempts, 
    reconnect, 
    disconnect,
    error,
    manuallyDisconnected
  } = useWebSocket();

  return (
    <div className="flex items-center gap-2 p-2 rounded-md bg-background border">
      <div className="flex items-center gap-2">
        {isConnected ? (
          <Wifi className="h-5 w-5 text-green-500" />
        ) : (
          <WifiOff className="h-5 w-5 text-red-500" />
        )}
        
        <span className="text-sm font-medium">
          {isConnected 
            ? 'Connected' 
            : manuallyDisconnected 
              ? 'Manually Disconnected'
              : connectionAttempts > 0 
                ? `Reconnecting (${connectionAttempts})...` 
                : 'Disconnected'
          }
        </span>
      </div>

      {error && (
        <div className="flex items-center gap-1 text-red-500">
          <AlertCircle className="h-4 w-4" />
          <span className="text-xs truncate max-w-[150px]">{error.message}</span>
        </div>
      )}

      <div className="flex gap-1 ml-auto">
        {isConnected ? (
          <Button 
            variant="outline" 
            size="sm"
            onClick={disconnect}
            className="h-7 px-2 text-xs"
          >
            Disconnect
          </Button>
        ) : (
          <Button 
            variant="outline" 
            size="sm"
            onClick={reconnect}
            disabled={connectionAttempts > 0 && !manuallyDisconnected}
            className="h-7 px-2 text-xs flex items-center gap-1"
          >
            <RefreshCw className={`h-3 w-3 ${connectionAttempts > 0 ? 'animate-spin' : ''}`} />
            Reconnect
          </Button>
        )}
      </div>
    </div>
  );
};