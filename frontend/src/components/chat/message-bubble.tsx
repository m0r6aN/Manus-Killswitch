import React, { useState, useCallback } from "react";
// Assume Message, MessageIntent, ToolResult types are correctly defined in @/types/models
import { Message, MessageIntent, ToolResult } from "@/types/models";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { ToolExecutionModal } from "@/components/tools/tool-execution-modal"; // Assuming this component exists
import axios, { AxiosError } from "axios";
import { useToast } from "@/components/ui/use-toast"; // Use toast for feedback
import { AlertCircle, Bot } from "lucide-react"; // Icons
import { cn } from "@/lib/utils";

interface MessageBubbleProps {
    message: Message;
    isCommander: boolean; // Is the message from the "commander" (user)?
    agentColor: string; // Pre-determined color for the agent avatar
    agentName: string; // Display name for the agent
    // IMPORTANT: Removing direct state setters to improve component responsibility
    // Instead, the parent should handle updates based on events/requests from this component.
    // setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
    // updateThreadWithLastMessage: (message: Message) => void;

    // New prop to request tool execution from the parent
    onExecuteToolRequest: (
        toolName: string,
        params: Record<string, any>, // Allow any type for params initially
        taskId: string | undefined // Pass task ID for context
    ) => Promise<ToolResult | null>; // Parent handles execution and returns result (or null on failure)
}

// Fetch API Base URL from environment variables
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

interface ToolMetadata {
    name: string;
    description?: string;
    parameters?: Record<string, { type: string; description?: string; required?: boolean }>; // Structured params
}

export function MessageBubble({
    message,
    isCommander,
    agentColor,
    agentName,
    onExecuteToolRequest, // Use the callback prop
}: MessageBubbleProps) {
    const [isExecuteModalOpen, setIsExecuteModalOpen] = useState(false);
    const [selectedTool, setSelectedTool] = useState<string | null>(null);
    const [toolMetadata, setToolMetadata] = useState<ToolMetadata | null>(null);
    // Initialize params based on metadata schema later
    const [toolParams, setToolParams] = useState<Record<string, any>>({});
    const [isFetchingMetadata, setIsFetchingMetadata] = useState(false);
    const [isExecuting, setIsExecuting] = useState(false);
    const [fetchMetaError, setFetchMetaError] = useState<string | null>(null);
    const { toast } = useToast();

    // Fetch metadata when opening the modal
    const handleOpenExecuteModal = useCallback(async (toolName: string) => {
         if (!API_BASE_URL) {
             console.error("API Base URL not configured.");
              toast({ variant: "destructive", title: "Configuration Error", description: "Cannot fetch tool details." });
             return;
         }

        setSelectedTool(toolName);
        setIsExecuteModalOpen(true);
        setIsFetchingMetadata(true);
        setFetchMetaError(null);
        setToolMetadata(null); // Clear previous metadata
        setToolParams({}); // Clear previous params

        try {
            const response = await axios.get<ToolMetadata>(`${API_BASE_URL}/tools/${toolName}`);
            const fetchedMetadata = response.data;
            setToolMetadata(fetchedMetadata);

            // Initialize params based on fetched schema
            const initialParams: Record<string, any> = {};
            if (fetchedMetadata.parameters) {
                Object.keys(fetchedMetadata.parameters).forEach((paramKey) => {
                    // Set default value based on type (e.g., empty string, 0, false)
                     initialParams[paramKey] = ''; // Default to empty string for simplicity
                     // TODO: Could add more sophisticated default value logic based on param type
                });
            }
            setToolParams(initialParams);

        } catch (error) {
            console.error("Error fetching tool metadata:", error);
            const errorMsg = error instanceof AxiosError && error.response?.data?.detail
                ? error.response.data.detail
                : "Failed to fetch tool details.";
             setFetchMetaError(errorMsg);
             toast({ variant: "destructive", title: "Error", description: errorMsg });
             // Keep modal open to show error? Or close? Closing for now.
             // setIsExecuteModalOpen(false);
        } finally {
            setIsFetchingMetadata(false);
        }
    }, [toast]); // Add toast dependency

    const handleToolParamChange = useCallback((key: string, value: any) => {
        // TODO: Add validation/parsing based on toolMetadata schema if needed
        setToolParams((prev) => ({ ...prev, [key]: value }));
    }, []);

    const handleExecute = useCallback(async () => {
        if (!selectedTool || !toolMetadata) return; // Need tool and metadata

        // Basic validation (check required fields)
        let validationError = null;
        if (toolMetadata.parameters) {
             for (const paramKey in toolMetadata.parameters) {
                 if (toolMetadata.parameters[paramKey]?.required && !toolParams[paramKey]) {
                     validationError = `Parameter "${paramKey}" is required.`;
                     break;
                 }
             }
         }

         if (validationError) {
             toast({ variant: "destructive", title: "Validation Error", description: validationError });
             return;
         }


        setIsExecuting(true);
        try {
            // Call the parent function to handle execution
            const result = await onExecuteToolRequest(selectedTool, toolParams, message.task_id);

            if (result) {
                 toast({ title: "Tool Executed", description: `"${selectedTool}" ran successfully.` });
                 // Parent should have updated the message list with the result.
                 // The bubble itself doesn't need to call setMessages anymore.
            } else {
                 // Error handled by parent, toast might be redundant but okay
                 toast({ variant: "destructive", title: "Execution Failed", description: `"${selectedTool}" failed to execute.` });
            }

        } catch (err) {
            // This catch block might be redundant if onExecuteToolRequest handles errors internally
             console.error('Execution request failed locally', err);
             toast({ variant: "destructive", title: "Execution Error", description: "An unexpected error occurred." });
        } finally {
            setIsExecuting(false);
            setIsExecuteModalOpen(false); // Close modal on completion/error
        }
    }, [selectedTool, toolParams, message.task_id, onExecuteToolRequest, toast, toolMetadata]); // Include dependencies

    const handleCancel = useCallback(() => {
        setIsExecuteModalOpen(false);
        setSelectedTool(null);
        setToolMetadata(null);
        setToolParams({});
        setFetchMetaError(null);
    }, []);

    // Determine message background color based on sender
    const messageBgColor = isCommander
        ? "bg-primary text-primary-foreground"
        : "bg-muted text-foreground";

    return (
        <div className={cn("flex w-full mb-4", isCommander ? "justify-end" : "justify-start")}>
            <div className={cn("flex items-start gap-3 max-w-[80%]", isCommander ? "flex-row-reverse" : "flex-row")}>
                {/* Avatar */}
                 <Avatar className="h-7 w-7 mt-1 flex-shrink-0 border">
                    {/* Use provided color, fallback */}
                    <AvatarFallback className={cn(agentColor || 'bg-gray-400', "text-[10px] font-bold text-white")}>
                        {/* Use first letter, fallback to icon */}
                        {agentName ? agentName.charAt(0).toUpperCase() : <Bot size={12}/>}
                    </AvatarFallback>
                </Avatar>

                {/* Message Content Area */}
                <div className="flex flex-col">
                     {/* Agent Name & Timestamp */}
                    <div className={cn("flex items-center gap-2 mb-0.5", isCommander ? "justify-end" : "justify-start")}>
                         {!isCommander && <p className="text-xs font-medium">{agentName || 'Agent'}</p>}
                        <p className="text-[10px] text-muted-foreground">
                            {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </p>
                    </div>

                    {/* Bubble Content */}
                    <div className={cn("mt-1 p-3 rounded-lg shadow-sm", messageBgColor)}>
                        {/* Main message content */}
                        <p className="text-sm whitespace-pre-wrap break-words">{message.content}</p>

                        {/* Tool Suggestions */}
                        {message.intent === MessageIntent.REQUEST_TOOL && message.toolSuggestions && message.toolSuggestions.length > 0 && (
                            <div className="mt-2 pt-2 border-t border-foreground/10">
                                <p className="text-xs font-semibold mb-1 opacity-80">Suggested Tools:</p>
                                <div className="flex flex-wrap gap-1.5">
                                    {message.toolSuggestions.map((toolName) => (
                                        <Button
                                            key={toolName}
                                            variant={isCommander ? "secondary" : "outline"} // Different variant for commander
                                            size="xs" // Smaller button size
                                            onClick={() => handleOpenExecuteModal(toolName)}
                                            className="text-xs"
                                        >
                                            {toolName}
                                        </Button>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Tool Result Display */}
                        {/* Check for intent TOOL_EXECUTE and presence of toolResult */}
                        {message.intent === MessageIntent.TOOL_EXECUTE && message.toolResult && (
                            <div className="mt-2 pt-2 border-t border-foreground/10">
                                <p className="text-xs font-semibold mb-1 opacity-80">
                                    Tool Result ({message.agent}): {/* Show which tool agent ran */}
                                </p>
                                {/* Use pre for formatted output, handle error display */}
                                <pre className={cn(
                                     "text-xs p-2 rounded overflow-x-auto max-h-40", // Limit height, allow scroll
                                     isCommander ? "bg-primary/80" : "bg-background/50", // Slightly different bg
                                     message.toolResult.error ? "border border-red-500/50" : ""
                                 )}>
                                     {message.toolResult.error
                                          ? <span className="text-red-400">{`Error: ${message.toolResult.error}`}</span>
                                          : message.toolResult.output || <span className="opacity-60">(No output)</span>
                                     }
                                </pre>
                            </div>
                        )}
                    </div>
                </div>
            </div>

             {/* Tool Execution Modal */}
             {/* Render modal outside the main flow if needed, or keep here */}
             <ToolExecutionModal
                // Pass structured metadata if available
                toolName={toolMetadata?.name || selectedTool || ''}
                toolDescription={toolMetadata?.description || ""}
                parametersSchema={toolMetadata?.parameters} // Pass schema
                paramValues={toolParams} // Pass current values
                isOpen={isExecuteModalOpen}
                isExecuting={isExecuting}
                isLoading={isFetchingMetadata} // Show loading state for metadata
                error={fetchMetaError} // Show metadata fetch error in modal
                onChange={handleToolParamChange} // Pass param change handler
                onExecute={handleExecute}
                onCancel={handleCancel}
             />
        </div>
    );
}
