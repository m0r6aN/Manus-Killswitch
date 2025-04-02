// No critical changes identified for a quick fix. Keep as is.
// components/StreamBox.tsx
import React from 'react';
import { cn } from "@/lib/utils"; // Import cn

interface StreamBoxProps {
    taskId: string;
    agent: string;
    content: string;
    className?: string;
}

const StreamBox: React.FC<StreamBoxProps> = ({ taskId, agent, content, className }) => {
    // Simple display for streaming content

    return (
        <div className={cn(
            `whitespace-pre-wrap p-3 rounded-md shadow-inner text-sm
             bg-gradient-to-b from-gray-100 to-gray-200
             dark:from-gray-700 dark:to-gray-800
             border border-border`, // Use theme colors/border
            className // Allow overriding styles
        )}>
             <p className="text-xs font-medium text-muted-foreground mb-1">
                 Streaming from: <span className="font-semibold text-foreground">{agent}</span> (Task ID: {taskId})
             </p>
             {/* Use <pre> inside for better monospace/formatting control if needed */}
             <div className="font-mono text-xs text-foreground/90"> {/* Use monospace for code-like streams */}
                 {content}
                 {/* Blinking cursor at the end */}
                 {<span className="animate-pulse inline-block w-[2px] h-3 bg-primary align-text-bottom ml-0.5"></span>}
             </div>
        </div>
    );
};

export default StreamBox;