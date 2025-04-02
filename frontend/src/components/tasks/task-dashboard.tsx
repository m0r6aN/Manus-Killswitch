// src/components/dashboard/TaskDashboard.tsx
import React from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AgentStatusPanel } from "@/components/chat/agent-status-panel"; // Assuming this exists and works
import { useWebSocket } from "@/contexts/websocket-context"; // Assuming context provides this hook
import { useTaskStream } from "@/app/hooks/useTaskStream"; // Assuming hook provides task data
import { Badge } from "@/components/ui/badge";
import { Task } from "@/types/models"; // Ensure Task type includes fields used below
import { normalizeAgentStatuses } from "@/lib/utils"; // Assuming this utility exists

// Define a more specific Task type for this component's needs if Task from models is too broad
// interface DashboardTask extends Pick<Task, 'task_id' | 'content' | 'target_agent' | 'reasoning_strategy' | 'reasoning_effort'> {}

const TaskDashboard: React.FC = () => {
    // Assuming hooks provide correctly typed and updated data
    const { agentStatuses } = useWebSocket();
    const { activeTasks, completedTasks, isLoading } = useTaskStream(); // Assuming hook provides loading state

    // Consider memoizing normalized statuses if normalization is expensive and agentStatuses updates frequently
    const normalizedStatuses = React.useMemo(
        () => normalizeAgentStatuses(agentStatuses),
        [agentStatuses]
    );

    const containerVariants = {
        hidden: { opacity: 0 },
        visible: {
            opacity: 1,
            transition: {
                staggerChildren: 0.05, // Stagger animation for list items
            },
        },
    };

    const itemVariants = {
        hidden: { opacity: 0, y: 10 },
        visible: { opacity: 1, y: 0 },
        exit: { opacity: 0, y: -10, transition: { duration: 0.2 } },
    };

    return (
        <div className="p-4 md:p-6 lg:p-8 max-w-7xl mx-auto">
            <h1 className="text-2xl font-semibold mb-6 text-foreground">Real-Time Task Dashboard</h1>

            {/* Agent Status */}
            <AgentStatusPanel agentStatus={normalizedStatuses} />

            {/* Loading State */}
            {isLoading && (
                 <div className="text-center py-10 text-muted-foreground">Loading tasks...</div>
            )}

            {/* Active Tasks Section */}
            {!isLoading && (
                <section className="my-8">
                    <h2 className="text-xl font-semibold mb-4 text-foreground">Active Tasks ({activeTasks.length})</h2>
                    {activeTasks.length === 0 ? (
                        <p className="text-muted-foreground text-sm">No active tasks at the moment.</p>
                    ) : (
                        // Consider virtualization (e.g., react-window) if this list can grow very large (>50-100 items)
                        <motion.div
                             className="space-y-3"
                             variants={containerVariants}
                             initial="hidden"
                             animate="visible"
                        >
                             <AnimatePresence initial={false}>
                                {activeTasks.map((task: Task) => ( // Use Task type from import
                                    <motion.div
                                        key={task.task_id} // Key is crucial for AnimatePresence
                                        layout // Animate layout changes
                                        variants={itemVariants}
                                        exit="exit" // Use defined exit variant
                                        className="border border-border dark:border-muted rounded-lg p-4 bg-card shadow-sm overflow-hidden"
                                    >
                                        <div className="flex justify-between items-start gap-2">
                                            <p className="font-medium text-foreground break-words flex-1">
                                                {task.content || "No content provided"}
                                            </p>
                                            {task.reasoning_effort && (
                                                <Badge variant="secondary" className="whitespace-nowrap">
                                                     {task.reasoning_effort.toUpperCase()}
                                                </Badge>
                                             )}
                                        </div>
                                        <div className="text-xs mt-2 text-muted-foreground">
                                            {task.target_agent && `Target: ${task.target_agent}`}
                                            {task.target_agent && task.reasoning_strategy && " • "}
                                            {task.reasoning_strategy && `Strategy: ${task.reasoning_strategy}`}
                                        </div>
                                         {/* TODO: Add progress indicator or agent working on it if available */}
                                    </motion.div>
                                ))}
                             </AnimatePresence>
                        </motion.div>
                    )}
                </section>
            )}

             {/* Completed Tasks Section */}
             {!isLoading && (
                <section className="my-8">
                    <h2 className="text-xl font-semibold mb-4 text-foreground">Recently Completed Tasks</h2>
                     {completedTasks.length === 0 ? (
                         <p className="text-muted-foreground text-sm">No tasks completed recently.</p>
                     ) : (
                         <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {/* Limit displayed completed tasks for performance, add pagination/load more if needed */}
                            {completedTasks.slice(0, 6).map((task: Task) => (
                                <div
                                    key={task.task_id} // Added key here
                                    className="p-3 border border-border dark:border-muted rounded-md bg-muted/50 dark:bg-muted/30 text-sm transition-colors hover:bg-muted/70"
                                >
                                    <p className="font-medium text-foreground truncate mb-1" title={task.content}>
                                        {task.content || "No content provided"}
                                    </p>
                                    <div className="text-xs text-muted-foreground">
                                        Status: Completed
                                         {task.reasoning_effort && ` • Effort: ${task.reasoning_effort.toUpperCase()}`}
                                         {/* TODO: Display outcome if available */}
                                         {/* {task.outcome && ` • Outcome: ${task.outcome}`} */}
                                    </div>
                                </div>
                            ))}
                         </div>
                      )}
                     {completedTasks.length > 6 && (
                        <div className="text-center mt-4">
                             {/* Placeholder for pagination or "view all" */}
                             <button className="text-sm text-primary hover:underline">View all completed tasks</button>
                        </div>
                     )}
                </section>
              )}
        </div>
    );
};

export default TaskDashboard;