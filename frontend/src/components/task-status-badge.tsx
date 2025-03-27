import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

interface TaskStatusBadgeProps {
  messages: Array<{
    outcome?: string
  }>
}

export function TaskStatusBadge({ messages }: TaskStatusBadgeProps) {
  // Check if the last message has an outcome
  const isCompleted = messages.length > 0 && "outcome" in messages[messages.length - 1]

  return (
    <Badge
      variant="outline"
      className={cn(
        "ml-2 text-xs",
        isCompleted ? "border-green-500 text-green-500" : "border-amber-500 text-amber-500",
      )}
    >
      {isCompleted ? "Completed" : "In Progress"}
    </Badge>
  )
}