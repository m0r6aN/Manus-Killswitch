// components/StreamBox.tsx
import React, { useEffect, useState } from 'react';

interface StreamBoxProps {
    taskId: string;
    agent: string;
    content: string;
    className?: string;
}

const StreamBox: React.FC<StreamBoxProps> = ({ taskId, agent, content, className }) => {
    // Optional: Display agent/task info if needed
    // <p className="text-xs text-gray-500">Streaming from {agent} (Task: {taskId})</p>
  
    return (
      <div className={`whitespace-pre-wrap p-2 rounded-lg bg-black text-green-400 font-mono shadow-inner text-sm ${className || ''}`}>
        {/* Directly render the passed content */}
        <pre>
          {content}
          {/* Keep the cursor only if content is actively being updated (tricky without events) */}
          {/* Maybe add cursor only if content length > 0 ? */}
          {content && <span className="animate-pulse inline-block">█</span>}
        </pre>
      </div>
    );
  };

export default StreamBox;
