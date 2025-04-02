"use client"

import React from "react"; // Import React
import { cn } from "@/lib/utils"
import { CheckCircle2, Circle } from "lucide-react"

// More specific type for the task prop within this component
interface TaskItemData {
    task_id: string;
    content: string;
    isCompleted: boolean; // Assuming this boolean reliably reflects completion
}

interface TaskListItemProps {
    task: TaskItemData;
    isActive: boolean;
    onClick: () => void;
}

export function TaskListItem({ task, isActive, onClick }: TaskListItemProps) {
    // Handle keyboard interaction for accessibility
    const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault(); // Prevent default space scroll / enter submit
            onClick();
        }
    };

    return (
        <div
            className={cn(
                "flex items-start gap-3 p-2 rounded-md cursor-pointer transition-colors", // Increased gap slightly
                isActive
                    ? "bg-accent text-accent-foreground"
                    : "hover:bg-muted/50 dark:hover:bg-muted/80", // Adjusted hover colors
                 "focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2" // Added focus styles
            )}
            onClick={onClick}
            onKeyDown={handleKeyDown} // Added keyboard handler
            role="button" // Added role
            tabIndex={0} // Make it focusable
            aria-current={isActive ? "page" : undefined} // Indicate active state for screen readers
        >
            {/* Icon based on completion status */}
            <div className={cn(
                 "mt-0.5 flex-shrink-0", // Prevent icon shrinking
                 task.isCompleted ? "text-green-600 dark:text-green-500" : "text-muted-foreground" // Color based on status
            )}>
                {task.isCompleted
                    ? <CheckCircle2 className="h-4 w-4" aria-label="Completed" />
                    : <Circle className="h-4 w-4" aria-label="In progress" />
                }
            </div>
            {/* Task content and ID */}
            <div className="flex-1 min-w-0">
                 <p className="text-sm font-medium truncate" title={task.content}>
                     {task.content || "Untitled Task"}
                 </p>
                <p className="text-xs text-muted-foreground" title={`Task ID: ${task.task_id}`}>
                     ID: {task.task_id.substring(0, 8)}...
                 </p>
            </div>
        </div>
    )
}