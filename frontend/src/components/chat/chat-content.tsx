// No critical changes identified for a quick fix. Keep as is.
import React, { useRef, useEffect } from 'react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Card, CardContent } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator'; // Import Separator
import { format } from 'date-fns'; // For timestamp formatting
import { cn } from "@/lib/utils"; // For conditional classes
//import StreamBox from './stream-box';


// Define message type again for clarity within this component
interface DisplayMessage {
    id: string;
    agent: string;
    content: string;
    timestamp: string;
    intent?: string;
    event?: string;
    outcome?: string;
    isUser: boolean;
    type: string; // e.g., 'message', 'error', 'system'
}

interface ChatContentProps {
    messages: DisplayMessage[];
}

const ChatContent: React.FC<ChatContentProps> = ({ messages }) => {
    const viewportRef = useRef<HTMLDivElement>(null);


    // Auto-scroll to bottom when messages change
    useEffect(() => {
        if (viewportRef.current) {
            // Small delay can sometimes help ensure layout is fully computed
            const timer = setTimeout(() => {
                 if (viewportRef.current) {
                    viewportRef.current.scrollTop = viewportRef.current.scrollHeight;
                 }
            }, 50);
            return () => clearTimeout(timer);
        }
    }, [messages]);


    const formatTimestamp = (isoString: string) => {
        try {
            return format(new Date(isoString), 'HH:mm:ss');
        } catch (e) {
            console.error("Failed to format timestamp:", isoString, e); // Log error
            // Attempt to return a basic time if possible, otherwise fallback
            const date = new Date(isoString);
            if (!isNaN(date.getTime())) {
                return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`
            }
            return 'invalid date'; // Fallback for completely invalid date
        }
    };

    return (
        // Ensure ScrollArea viewport has the ref if direct child isn't scrollable
        // Check shadcn docs for ScrollArea ref usage if needed
        <ScrollArea className="flex-1 overflow-y-auto p-4" ref={viewportRef}>
            <div className="space-y-4 pb-4"> {/* Add padding bottom */}
                {messages.map((msg) => (
                    <div
                        key={msg.id}
                        className={cn("flex", msg.isUser ? "justify-end" : "justify-start")}
                    >
                        <Card className={cn(
                            "max-w-xs md:max-w-md lg:max-w-lg xl:max-w-xl", // Responsive max width
                            msg.isUser ? "bg-blue-100 dark:bg-blue-900" : "bg-white dark:bg-gray-800",
                            msg.type === 'error' ? "bg-red-100 dark:bg-red-900 border-red-500" : "", // Style errors
                            msg.type === 'system' ? "bg-yellow-100 dark:bg-yellow-900 border-yellow-500" : "" // Example system style
                        )}>
                            <CardContent className="p-3">
                                <div className="flex justify-between items-center mb-1">
                                    <p className="text-xs font-semibold">
                                        {/* Handle System messages specifically if needed */}
                                        {msg.agent === 'System' ? 'System' : (msg.isUser ? 'You' : msg.agent)}
                                    </p>
                                    <p className="text-xs text-gray-500 dark:text-gray-400">
                                        {formatTimestamp(msg.timestamp)}
                                    </p>
                                </div>
                                {/* Display intent/event/outcome if available */}
                                {(msg.intent || msg.event || msg.outcome) && (
                                    <>
                                        <p className="text-xs text-gray-600 dark:text-gray-400 break-words mb-1">
                                            {msg.intent && `Intent: ${msg.intent} `}
                                            {msg.event && `Event: ${msg.event} `}
                                            {msg.outcome && `Outcome: ${msg.outcome}`}
                                        </p>
                                        <Separator className="my-1" />
                                    </>
                                )}
                                {/* Use pre-wrap to preserve formatting, especially for code/JSON */}
                                <p className="text-sm whitespace-pre-wrap break-words">{msg.content}</p>
                            </CardContent>
                        </Card>
                    </div>
                ))}

                {messages.length === 0 && (
                    <div className="text-center text-gray-500 dark:text-gray-400 mt-10">
                        Start the conversation by typing below...
                    </div>
                )}
            </div>
        </ScrollArea>
    );
};

export default ChatContent;