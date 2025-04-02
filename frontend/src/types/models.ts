// src/types/models.ts

// Enums matching the Python models
export enum MessageIntent {
  CHAT = "chat",
  START_TASK = "start_task",
  CHECK_STATUS = "check_status",
  MODIFY_TASK = "modify_task",
  CODE_EXECUTE = "code_execute",
  TOOL_SUGGEST = "tool_suggest",
  TOOL_EXECUTE = "tool_execute",
  OPTIMIZE = "optimize",
  ANALYZE = "analyze",
  RESPOND = "respond",
  REVIEW = "review"
}

export enum TaskEvent {
  PLAN = "plan",
  EXECUTE = "execute",
  REFINE = "refine",
  COMPLETE = "complete",
  ESCALATE = "escalate"
}

export enum TaskOutcome {
  MERGED = "merged",
  COMPLETED = "completed",
  ESCALATED = "escalated"
}

// Base Message interface
export interface Message {
  task_id: string;
  agent: string;
  content: string;
  intent: MessageIntent;
  timestamp: string;
  toolSuggestions?: string[];
  toolResult?: { output: string; error?: string };
}

// Task interface extending Message
export interface Task extends Message {
  target_agent: string;
  event: TaskEvent;
  confidence?: number;
  reasoning_effort?: string;
  reasoning_strategy?: string;
  created_at: string;
}

// TaskResult interface extending Task
export interface TaskResult extends Task {
  outcome: TaskOutcome;
  contributing_agents: string[];
}

// Agent interface
export interface Agent {
  id: string;
  name: string;
  avatarColor: string;
  isOnline: boolean;
  capabilities?: string[];
  description?: string;
}

// Chat thread interface
export interface ChatThread {
  id: string;
  name: string;
  participants: string[];
  lastMessage?: string;
  timestamp?: string;
  unreadCount?: number;
  type: "collaborative" | "tool" | "direct";
}

export interface ToolData {
  name: string;
  description?: string;
  //parameters?: string;
  path?: string;
  entrypoint?: string;
  type?: 'function' | 'script' | 'module';
  version?: string;
  tags?: string;
  language: string;
  code: string;
}
