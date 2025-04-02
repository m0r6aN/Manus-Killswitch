import { useWebSocket } from "@/contexts/websocket-context"
import { cn } from "@/lib/utils"
import { WifiOff } from "lucide-react"

export function ConnectionStatusWrapper() {
  const { isConnected } = useWebSocket()

  return (
    <div className="flex items-center justify-center text-xs">
      <div className={cn("flex items-center gap-1.5", isConnected ? "text-muted-foreground" : "text-destructive")}>
        {!isConnected && <WifiOff className="h-3 w-3" />}
        <span>{isConnected ? "Connected" : "Disconnected"}</span>
      </div>
    </div>
  )
}

