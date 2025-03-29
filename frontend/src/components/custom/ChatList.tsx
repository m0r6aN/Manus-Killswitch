// src/components/chat/ChatList.tsx
import { useEffect, useState } from "react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Search, Menu, Wrench } from "lucide-react";
import { Agent, ChatThread } from "@/types/models";
import axios from "axios";

interface Tool {
  name: string;
  description: string;
  tags: string;
}

interface ChatListProps {
  activeChatId: string;
  agents: Agent[];
  chatThreads: ChatThread[];
  agentStatuses: { [key: string]: string };
  activeThreadId: string;
  isConnected: boolean;
  createDirectThread: (agentId: string) => void;
  setActiveThreadId: (threadId: string) => void;
  setChatThreads: React.Dispatch<React.SetStateAction<ChatThread[]>>;
  formatTimestamp: (timestamp: string) => string;
}

export function ChatList({
  agents,
  chatThreads,
  agentStatuses,
  activeThreadId,
  isConnected,
  createDirectThread,
  setActiveThreadId,
  setChatThreads, 
  formatTimestamp,
}: ChatListProps) {
  const [tools, setTools] = useState<Tool[]>([]);

  useEffect(() => {
    const fetchTools = async () => {
      try {
        const response = await axios.get("http://localhost:8001/tools");
        setTools(response.data);
      } catch (error) {
        console.error("Error fetching tools:", error);
      }
    };
    fetchTools();
  }, []);

  const createToolThread = (toolName: string) => {
    const existingThread = chatThreads.find(
      (thread) => thread.type === "tool" && thread.name === toolName
    );

    if (existingThread) {
      setActiveThreadId(existingThread.id);
      return;
    }

    const newThread: ChatThread = {
      id: `tool-${toolName}-${Date.now()}`,
      name: toolName,
      participants: ["commander", "tools-agent"],
      timestamp: new Date().toISOString(),
      type: "tool",
    };

    setChatThreads((prev) => [...prev, newThread]); // Use setChatThreads here
    setActiveThreadId(newThread.id);
  };

  return (
    <div className="w-96 flex flex-col border-r border-border flex sm:w-96 w-full">
      <div className="p-4 border-b border-border flex justify-between items-center">
        <h1 className="text-2xl font-bold">Chats</h1>
        <Button variant="ghost" size="icon">
          <Menu className="h-5 w-5" />
        </Button>
      </div>

      <div className="p-4">
        <div className="relative">
          <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
          <Input 
            placeholder="Search conversations" 
            className="pl-10 bg-muted rounded-lg text-sm h-10" 
          />
        </div>
      </div>

      <div className="p-4 pb-2">
        <p className="text-sm font-semibold text-foreground mb-3">AGENTS</p>
        <div className="flex space-x-3 overflow-x-auto pb-1">
          {agents.filter(a => a.id !== "commander").map((agent) => (
            <div 
              key={agent.id} 
              className="flex flex-col items-center cursor-pointer hover:scale-105 transition-transform"
              onClick={() => createDirectThread(agent.id)}
            >
              <div className="relative">
                <Avatar className="h-14 w-14">
                  <AvatarFallback className={`${agent.avatarColor} text-white font-semibold`}>
                    {agent.name.charAt(0)}
                  </AvatarFallback>
                </Avatar>
                {agentStatuses[agent.id] && (
                  <span className="absolute bottom-1 right-1 h-5 w-5 rounded-full bg-green-500 border-2 border-background"></span>
                )}
              </div>
              <p className="text-sm mt-2 font-medium">{agent.name}</p>
            </div>
          ))}
        </div>
      </div>

      <Separator className="my-3" />

      <div className="p-4 pb-2">
        <p className="text-sm font-semibold text-foreground mb-3">TOOLS</p>
        <div className="space-y-2">
          {tools.map((tool) => (
            <div
              key={tool.name}
              className={`flex items-center space-x-3 p-3 rounded-xl cursor-pointer transition-colors ${
                activeThreadId === `tool-${tool.name}` 
                  ? "bg-primary/20" 
                  : "hover:bg-muted/50"
              }`}
              onClick={() => createToolThread(tool.name)}
            >
              <Avatar className="h-12 w-12">
                <AvatarFallback className="bg-gray-500">
                  <Wrench className="h-6 w-6" />
                </AvatarFallback>
              </Avatar>
              <div className="flex-1 min-w-0">
                <p className="text-base font-semibold truncate">{tool.name}</p>
                <p className="text-sm text-muted-foreground truncate">{tool.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      <Separator className="my-3" />

      <div className="p-4 pb-2">
        <p className="text-sm font-semibold text-foreground mb-3">RECENT CHATS</p>
      </div>

      <ScrollArea className="flex-1 overflow-y-auto">
        <div className="space-y-2 p-3">
          {chatThreads.map((thread) => (
            <div
              key={thread.id}
              className={`flex items-center space-x-3 p-3 rounded-xl cursor-pointer transition-colors animate-fade-in ${
                activeThreadId === thread.id 
                  ? "bg-primary/20" 
                  : "hover:bg-muted/50"
              }`}
              onClick={() => setActiveThreadId(thread.id)}
            >
              {thread.type === "collaborative" ? (
                <Avatar className="h-12 w-12">
                  <AvatarFallback className="bg-primary/30 text-foreground font-semibold">
                    AC
                  </AvatarFallback>
                </Avatar>
              ) : thread.type === "tool" ? (
                <Avatar className="h-12 w-12">
                  <AvatarFallback className="bg-gray-500">
                    <Wrench className="h-6 w-6" />
                  </AvatarFallback>
                </Avatar>
              ) : (
                <Avatar className="h-12 w-12">
                  <AvatarFallback className={
                    agents.find(a => a.id === thread.participants.find(p => p !== "commander"))?.avatarColor || "bg-gray-500"
                  }>
                    {thread.name?.charAt(0)}
                  </AvatarFallback>
                </Avatar>
              )}
              <div className="flex-1 min-w-0">
                <div className="flex justify-between items-center">
                  <p className="text-base font-semibold truncate">{thread.name}</p>
                  {thread.timestamp && (
                    <p className="text-xs text-muted-foreground">
                      {formatTimestamp(thread.timestamp)}
                    </p>
                  )}
                </div>
                {thread.lastMessage && (
                  <p className="text-sm text-muted-foreground truncate mt-1">
                    {thread.lastMessage}
                  </p>
                )}
              </div>
              {thread.unreadCount && thread.unreadCount > 0 && (
                <div className="flex-shrink-0 h-6 w-6 bg-primary rounded-full flex items-center justify-center">
                  <span className="text-xs text-primary-foreground">
                    {thread.unreadCount}
                  </span>
                </div>
              )}
            </div>
          ))}
        </div>
      </ScrollArea>

      <div className="p-4 border-t border-border">
        <div className="flex items-center space-x-2">
          <div className={`h-3 w-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
          <p className="text-sm font-medium text-foreground">
            {isConnected ? 'Connected' : 'Disconnected'}
          </p>
        </div>
      </div>
    </div>
  );
}