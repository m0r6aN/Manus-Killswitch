"use client"

import { cn } from "@/lib/utils"
import { CheckCircle2, Circle } from "lucide-react"

interface TaskListItemProps {
  task: {
    task_id: string
    content: string
    isCompleted: boolean
  }
  isActive: boolean
  onClick: () => void
}

export function TaskListItem({ task, isActive, onClick }: TaskListItemProps) {
  return (
    <div
      className={cn(
        "flex items-start gap-2 p-2 rounded-md cursor-pointer transition-colors",
        isActive ? "bg-accent text-accent-foreground" : "hover:bg-gray-100 dark:hover:bg-gray-800",
      )}
      onClick={onClick}
    >
      <div className="mt-0.5 text-primary">
        {task.isCompleted ? <CheckCircle2 className="h-4 w-4" /> : <Circle className="h-4 w-4" />}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{task.content}</p>
        <p className="text-xs text-muted-foreground">ID: {task.task_id.substring(0, 8)}...</p>
      </div>
    </div>
  )
}

