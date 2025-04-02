import { Badge } from "@/components/ui/badge";

// Define a clearer structure for the expected message objects
interface StatusMessage {
    outcome?: string | null; // Outcome can be string, null, or undefined
    // Add other fields if necessary for status determination
}

interface TaskStatusBadgeProps {
    messages: Array<StatusMessage>; // Use the clearer type
}

export function TaskStatusBadge({ messages }: TaskStatusBadgeProps) {
    // Determine completion status - IMPROVED LOGIC:
    // Assumes 'completed' if the *last* message exists and has a defined, non-null 'outcome'.
    // CAVEAT: This logic is still based on message structure. A dedicated 'status' field
    // on the Task object itself would be far more reliable in a production system.
    const lastMessage = messages.length > 0 ? messages[messages.length - 1] : null;
    const isCompleted = !!lastMessage && lastMessage.outcome !== undefined && lastMessage.outcome !== null;
    // TODO: Potentially check for specific outcome values like 'success', 'failure', etc.
    // const isCompleted = lastMessage?.outcome === 'success' || lastMessage?.outcome === 'completed';

    const statusText = isCompleted ? "Completed" : "In Progress";
    const badgeVariant = isCompleted ? "success" : "warning"; // Custom variants or use default/outline
    const badgeClassName = isCompleted
        ? "border-green-500 text-green-600 dark:text-green-400 dark:border-green-600" // Example success style
        : "border-amber-500 text-amber-600 dark:text-amber-400 dark:border-amber-600"; // Example warning style

    return (
        <Badge
            // variant="outline" // Using custom classes instead of variant prop here
            className={`ml-2 text-xs font-medium ${badgeClassName}`}
            aria-label={`Task status: ${statusText}`}
        >
            {statusText}
        </Badge>
    );
}

// NOTE: Consider defining custom Badge variants in your theme for 'success', 'warning', etc.
// e.g., in globals.css or theme setup.