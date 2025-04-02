import React, { useEffect, useState, useMemo, useCallback } from "react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Search, Menu, Wrench, AlertCircle } from "lucide-react";
import { Agent, ChatThread } from "@/types/models"; // Assuming these types are correctly defined
import axios from "axios";
import { cn } from "@/lib/utils"; // Import cn for conditional classes

// Define Tool type locally if not imported
interface Tool {
    name: string;
    description: string;
    tags?: string; // Optional tags
    parameters?: string; // Expecting JSON string or object
}

interface ChatListProps {
    // activeChatId: string; // Might be same as activeThreadId? Removed if redundant
    agents: Agent[];
    chatThreads: ChatThread[];
    agentStatuses: { [key: string]: string }; // Assuming 'online'/'offline' or similar
    activeThreadId: string | null; // Can be null if no thread is active
    isConnected: boolean;
    createDirectThread: (agentId: string) => void;
    setActiveThreadId: (threadId: string | null) => void;
    setChatThreads: React.Dispatch<React.SetStateAction<ChatThread[]>>; // Still passing setter - consider context later
    formatTimestamp: (timestamp: string) => string; // Utility function
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL;

export function ChatList({
    agents,
    chatThreads,
    agentStatuses,
    activeThreadId,
    isConnected,
    createDirectThread,
    setActiveThreadId,
    setChatThreads, // Keep passing for now due to time constraints
    formatTimestamp,
}: ChatListProps) {
    const [tools, setTools] = useState<Tool[]>([]);
    const [searchTerm, setSearchTerm] = useState("");
    const [fetchError, setFetchError] = useState<string | null>(null);

    // Fetch tools on component mount
    useEffect(() => {
        const fetchTools = async () => {
            if (!API_BASE_URL) {
                console.error("API Base URL is not configured. Set NEXT_PUBLIC_API_BASE_URL environment variable.");
                setFetchError("API endpoint not configured.");
                return;
            }
            try {
                setFetchError(null); // Clear previous error
                const response = await axios.get(`${API_BASE_URL}/tools`);
                // TODO: Add validation here (e.g., using Zod) to ensure response.data matches Tool[]
                setTools(response.data || []);
            } catch (error) {
                console.error("Error fetching tools:", error);
                setFetchError("Failed to load tools. Please check the connection or backend service.");
                // Provide user feedback - maybe a toast notification?
            }
        };
        fetchTools();
    }, []); // Empty dependency array ensures this runs only once on mount

    // Memoized filtering logic
    const filteredThreads = useMemo(() => {
        if (!searchTerm) {
            return chatThreads;
        }
        const lowerCaseSearch = searchTerm.toLowerCase();
        return chatThreads.filter(thread =>
            thread.name?.toLowerCase().includes(lowerCaseSearch) ||
            thread.lastMessage?.toLowerCase().includes(lowerCaseSearch) ||
            (thread.type === 'direct' && agents.find(a => thread.participants.includes(a.id) && a.id !== 'commander')?.name.toLowerCase().includes(lowerCaseSearch))
        );
    }, [chatThreads, searchTerm, agents]);

    const handleSearchChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
        setSearchTerm(event.target.value);
    }, []);

    // Function to create or activate a tool thread
    const createOrActivateToolThread = useCallback((toolName: string) => {
        // Generate a predictable ID for tool threads based on the tool name
        const toolThreadId = `tool-${toolName}`;

        const existingThread = chatThreads.find(thread => thread.id === toolThreadId);

        if (existingThread) {
            setActiveThreadId(existingThread.id);
        } else {
            // Create a new tool thread
            const newThread: ChatThread = {
                id: toolThreadId, // Use predictable ID
                name: toolName,
                participants: ["commander", "tools-agent"], // Define participants clearly
                timestamp: new Date().toISOString(),
                type: "tool",
                lastMessage: `Tool channel for ${toolName}`, // Initial placeholder message
            };

            // Update state using the passed setter
            // TODO: Refactor state management (Context/Zustand) to avoid passing setChatThreads
            setChatThreads((prev) => [newThread, ...prev]); // Add new thread to the top
            setActiveThreadId(newThread.id);
        }
    }, [chatThreads, setActiveThreadId, setChatThreads]); // Dependencies needed for closure

    return (
        // Ensure width consistency, maybe use flex-shrink-0 if parent is flex
        <div className="w-full sm:w-80 md:w-96 flex flex-col border-r border-border bg-background flex-shrink-0">
            {/* Header */}
            <div className="p-4 border-b border-border flex justify-between items-center">
                <h1 className="text-xl font-semibold">Conversations</h1>
                {/* Consider adding functionality to this menu */}
                <Button variant="ghost" size="icon" aria-label="Menu">
                    <Menu className="h-5 w-5" />
                </Button>
            </div>

            {/* Search Bar */}
            <div className="p-4">
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                        placeholder="Search chats or tools..."
                        value={searchTerm}
                        onChange={handleSearchChange}
                        className="pl-10 bg-muted rounded-lg text-sm h-10"
                        aria-label="Search conversations"
                    />
                </div>
            </div>

             {/* Agents Section - Only visible if search is empty */}
             {!searchTerm && (
                <>
                    <div className="px-4 pb-2">
                        <p className="text-xs font-semibold text-muted-foreground mb-2 uppercase tracking-wide">Agents</p>
                         {/* Add horizontal scrolling for overflow */}
                        <ScrollArea className="w-full whitespace-nowrap">
                             <div className="flex space-x-4 pb-2">
                                {agents.filter(a => a.id !== "commander").map((agent) => (
                                    <div
                                        key={agent.id}
                                        className="flex flex-col items-center cursor-pointer hover:opacity-80 transition-opacity w-16" // Fixed width
                                        onClick={() => createDirectThread(agent.id)}
                                        title={`Chat with ${agent.name}`}
                                    >
                                        <div className="relative">
                                            <Avatar className="h-12 w-12 border">
                                                <AvatarFallback className={cn(agent.avatarColor || 'bg-muted', "text-white font-semibold")}>
                                                    {agent.name.charAt(0).toUpperCase()}
                                                </AvatarFallback>
                                            </Avatar>
                                            {/* Use agentStatuses prop */}
                                            {agentStatuses[agent.id] === 'online' && (
                                                <span className="absolute bottom-0 right-0 block h-3 w-3 rounded-full bg-green-500 ring-2 ring-background" />
                                            )}
                                        </div>
                                        <p className="text-xs mt-1 font-medium text-center truncate w-full">{agent.name}</p>
                                    </div>
                                ))}
                             </div>
                         </ScrollArea>
                    </div>
                    <Separator className="my-2" />
                </>
            )}

             {/* Tools Section - Only visible if search is empty */}
             {!searchTerm && (
                 <>
                    <div className="px-4 pb-2">
                        <p className="text-xs font-semibold text-muted-foreground mb-2 uppercase tracking-wide">Tools</p>
                        {fetchError && (
                             <div className="text-xs text-red-500 flex items-center gap-1">
                                 <AlertCircle className="h-3 w-3"/> {fetchError}
                             </div>
                        )}
                        <div className="space-y-1 max-h-48 overflow-y-auto"> {/* Limit height and scroll */}
                            {tools.map((tool) => (
                                <div
                                    key={tool.name}
                                    className={cn(`flex items-center space-x-3 p-2 rounded-lg cursor-pointer transition-colors`,
                                        activeThreadId === `tool-${tool.name}`
                                            ? "bg-primary/10 text-primary-foreground" // Adjusted active style
                                            : "hover:bg-muted/50"
                                    )}
                                    onClick={() => createOrActivateToolThread(tool.name)}
                                    title={tool.description}
                                >
                                    <Avatar className="h-8 w-8">
                                        <AvatarFallback className="bg-muted">
                                            <Wrench className="h-4 w-4 text-muted-foreground" />
                                        </AvatarFallback>
                                    </Avatar>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium truncate">{tool.name}</p>
                                        {/* <p className="text-xs text-muted-foreground truncate">{tool.description}</p> */}
                                    </div>
                                </div>
                            ))}
                            {tools.length === 0 && !fetchError && <p className="text-xs text-muted-foreground">No tools available.</p>}
                         </div>
                    </div>
                    <Separator className="my-2" />
                 </>
             )}


            {/* Recent Chats Section Header */}
            <div className="px-4 pb-2">
                 <p className="text-xs font-semibold text-muted-foreground mb-2 uppercase tracking-wide">
                    {searchTerm ? 'Search Results' : 'Recent Chats'}
                 </p>
            </div>

            {/* Chat Threads List */}
            <ScrollArea className="flex-1 overflow-y-auto">
                <div className="space-y-1 p-2">
                     {filteredThreads.length === 0 && (
                         <p className="text-sm text-muted-foreground text-center py-4">
                             {searchTerm ? 'No matching chats found.' : 'No recent chats.'}
                         </p>
                     )}
                    {filteredThreads.map((thread) => {
                         // Determine avatar details based on thread type
                         const getAvatarDetails = () => {
                            if (thread.type === "collaborative") {
                                return { fallback: "AC", color: "bg-purple-600" }; // Example color
                            } else if (thread.type === "tool") {
                                return { icon: Wrench, color: "bg-gray-500" };
                            } else if (thread.type === "direct") {
                                const participantAgent = agents.find(a => thread.participants.includes(a.id) && a.id !== "commander");
                                return { fallback: participantAgent?.name.charAt(0).toUpperCase() || '?', color: participantAgent?.avatarColor || "bg-gray-400" };
                            }
                            return { fallback: '?', color: "bg-gray-400" }; // Default fallback
                         };
                         const avatar = getAvatarDetails();

                         return (
                             <div
                                key={thread.id}
                                className={cn(`flex items-center space-x-3 p-2 rounded-lg cursor-pointer transition-colors`,
                                    activeThreadId === thread.id
                                        ? "bg-primary/10"
                                        : "hover:bg-muted/50"
                                )}
                                onClick={() => setActiveThreadId(thread.id)}
                            >
                                <Avatar className="h-9 w-9">
                                    <AvatarFallback className={cn(avatar.color, "text-white font-semibold text-xs")}>
                                        {avatar.icon ? <avatar.icon className="h-4 w-4" /> : avatar.fallback}
                                    </AvatarFallback>
                                </Avatar>
                                <div className="flex-1 min-w-0">
                                    <div className="flex justify-between items-center">
                                        <p className="text-sm font-medium truncate">{thread.name || 'Unnamed Chat'}</p>
                                        {thread.timestamp && (
                                            <p className="text-xs text-muted-foreground flex-shrink-0 ml-2">
                                                {formatTimestamp(thread.timestamp)}
                                            </p>
                                        )}
                                    </div>
                                    {thread.lastMessage && (
                                        <p className="text-xs text-muted-foreground truncate mt-1">
                                            {thread.lastMessage}
                                        </p>
                                    )}
                                </div>
                                {thread.unreadCount && thread.unreadCount > 0 && (
                                    <div className="ml-2 flex-shrink-0 h-5 w-5 bg-primary rounded-full flex items-center justify-center">
                                        <span className="text-[10px] font-bold text-primary-foreground">
                                            {thread.unreadCount > 9 ? '9+' : thread.unreadCount}
                                        </span>
                                    </div>
                                )}
                            </div>
                         );
                    })}
                </div>
            </ScrollArea>

            {/* Connection Status Footer */}
            <div className="p-3 border-t border-border mt-auto"> {/* Use mt-auto to push to bottom */}
                <div className="flex items-center space-x-2">
                    <div className={cn("h-2.5 w-2.5 rounded-full transition-colors", isConnected ? 'bg-green-500' : 'bg-red-500')} />
                    <p className="text-xs font-medium text-muted-foreground">
                        {isConnected ? 'Connected' : 'Disconnected'}
                    </p>
                </div>
            </div>
        </div>
    );
}