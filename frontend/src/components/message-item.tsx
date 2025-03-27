import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"

interface MessageItemProps {
  message: {
    agent: string
    content: string
    timestamp: string
    outcome?: string
  }
}

export function MessageItem({ message }: MessageItemProps) {
  const isOutcome = "outcome" in message

  return (
    <div className={cn("flex gap-3", isOutcome && "pl-8")}>
      {!isOutcome && (
        <Avatar className="h-8 w-8">
          <AvatarFallback className="bg-primary/20 text-primary">{message.agent.charAt(0)}</AvatarFallback>
        </Avatar>
      )}

      <div className="flex-1">
        {!isOutcome && (
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-medium">{message.agent}</span>
            <span className="text-xs text-muted-foreground">{new Date(message.timestamp).toLocaleTimeString()}</span>
          </div>
        )}

        <Card className={cn(isOutcome ? "bg-accent" : "bg-card", "overflow-hidden")}>
          <CardContent className={cn("p-3 text-sm", isOutcome && "text-accent-foreground")}>
            {message.content}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

