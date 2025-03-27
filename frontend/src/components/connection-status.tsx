// app/components/connection.status.tsx

"use client";

import { useState, useEffect } from "react";
import { Wifi, WifiOff } from "lucide-react";

import { cn } from "@/lib/utils";
import { useToast } from "@/app/hooks/use-toast";
import { useWebSocket } from "@/contexts/websocket-context";

export default function ConnectionStatus() {
  const { isConnected, error } = useWebSocket();
  const { toast } = useToast();
  const [showToast, setShowToast] = useState(false);

  useEffect(() => {
    if (showToast) {
      if (isConnected) {
        toast({
          title: "Connected",
          description: "Successfully connected to the AI Task Manager",
        });
      } else if (error) {
        toast({
          title: "Connection Error",
          description: error.message,
          variant: "destructive",
        });
      }
    } else {
      setShowToast(true);
    }
  }, [isConnected, error, showToast, toast]);

  return (
    <div className="flex items-center gap-2">
      <div
        className={cn(
          "flex h-8 items-center gap-2 rounded-md px-3",
          isConnected
            ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
            : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400"
        )}
      >
        {isConnected ? (
          <>
            <Wifi className="h-4 w-4" />
            <span className="text-xs font-medium">Connected</span>
          </>
        ) : (
          <>
            <WifiOff className="h-4 w-4" />
            <span className="text-xs font-medium">Disconnected</span>
          </>
        )}
      </div>
    </div>
  );
}
