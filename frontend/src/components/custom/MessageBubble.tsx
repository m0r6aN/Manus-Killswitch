// src/components/chat/MessageBubble.tsx
import { useState } from "react";
import { Message, MessageIntent } from "@/types/models";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import axios from "axios";

interface MessageBubbleProps {
  message: Message;
  isCommander: boolean;
  agentColor: string;
  agentName: string;
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  updateThreadWithLastMessage: (message: Message) => void;
}

export function MessageBubble({ 
  message, 
  isCommander, 
  agentColor, 
  agentName, 
  setMessages, 
  updateThreadWithLastMessage 
}: MessageBubbleProps) {
  const [isExecuteModalOpen, setIsExecuteModalOpen] = useState(false);
  const [selectedTool, setSelectedTool] = useState<string | null>(null);
  const [toolParams, setToolParams] = useState<Record<string, string>>({});
  const [isExecuting, setIsExecuting] = useState(false);

  const handleOpenExecuteModal = async (toolName: string) => {
    setSelectedTool(toolName);
    try {
      // Fetch tool metadata to get parameters
      const response = await axios.get(`http://localhost:5000/tools/${toolName}`);
      const tool = response.data;
      const params = tool.parameters ? JSON.parse(tool.parameters) : {};
      // Initialize parameter inputs
      const initialParams: Record<string, string> = {};
      Object.keys(params).forEach((param) => {
        initialParams[param] = "";
      });
      setToolParams(initialParams);
      setIsExecuteModalOpen(true);
    } catch (error) {
      console.error("Error fetching tool metadata:", error);
      setMessages(prev => [...prev, {
        task_id: message.task_id,
        agent: "tools-agent",
        content: `Failed to fetch metadata for tool "${toolName}".`,
        intent: MessageIntent.TOOL_EXECUTE,
        timestamp: new Date().toISOString(),
        toolResult: { output: "", error: "Failed to fetch tool metadata" },
      }]);
    }
  };

  const handleExecuteTool = async () => {
    if (!selectedTool) return;
    setIsExecuting(true);
    try {
      const response = await axios.post("http://localhost:5000/execute", {
        name: selectedTool,
        params: toolParams,
      });
      const resultMessage: Message = {
        task_id: message.task_id,
        agent: "tools-agent",
        content: `Tool "${selectedTool}" executed.`,
        intent: MessageIntent.TOOL_EXECUTE,
        timestamp: new Date().toISOString(),
        toolResult: response.data,
      };
      setMessages(prev => [...prev, resultMessage]);
      updateThreadWithLastMessage(resultMessage);
      setIsExecuteModalOpen(false);
    } catch (error) {
      const errorMessage: Message = {
        task_id: message.task_id,
        agent: "tools-agent",
        content: `Failed to execute tool "${selectedTool}".`,
        intent: MessageIntent.TOOL_EXECUTE,
        timestamp: new Date().toISOString(),
        toolResult: { output: "", error: (error as Error).message },
      };
      setMessages(prev => [...prev, errorMessage]);
      updateThreadWithLastMessage(errorMessage);
    } finally {
      setIsExecuting(false);
    }
  };

  return (
    <div className={`flex ${isCommander ? "justify-end" : "justify-start"}`}>
      <div className={`flex ${isCommander ? "flex-row-reverse" : "flex-row"} items-start space-x-3 max-w-[70%]`}>
        <Avatar className="h-8 w-8 mt-1">
          <AvatarFallback className={`${agentColor} text-white font-semibold`}>
            {agentName.charAt(0)}
          </AvatarFallback>
        </Avatar>
        <div>
          <div className="flex items-center space-x-2">
            <p className="text-sm font-semibold">{agentName}</p>
            <p className="text-xs text-muted-foreground">
              {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </p>
          </div>
          <div className={`mt-1 p-3 rounded-xl ${
            isCommander 
              ? "bg-primary text-primary-foreground" 
              : "bg-muted text-foreground"
          }`}>
            <p className="text-sm">{message.content}</p>
            {message.toolSuggestions && message.toolSuggestions.length > 0 && (
              <div className="mt-2">
                <p className="text-xs font-semibold">Suggested Tools:</p>
                <div className="flex flex-wrap gap-2 mt-1">
                  {message.toolSuggestions.map((toolName) => (
                    <Button
                      key={toolName}
                      variant="outline"
                      size="sm"
                      onClick={() => handleOpenExecuteModal(toolName)}
                    >
                      {toolName}
                    </Button>
                  ))}
                </div>
              </div>
            )}
            {message.toolResult && (
              <div className="mt-2">
                <p className="text-xs font-semibold">Tool Result:</p>
                <pre className="text-xs bg-background p-2 rounded">
                  {message.toolResult.output}
                  {message.toolResult.error && (
                    <p className="text-red-500">{message.toolResult.error}</p>
                  )}
                </pre>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}