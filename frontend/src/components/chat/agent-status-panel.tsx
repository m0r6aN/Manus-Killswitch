// src/components/dashboard/agent-status-panel.tsx
import React from "react";
import { Badge } from "@/components/ui/badge";
import { CircleCheck, CircleX } from "lucide-react";

interface AgentStatusPanelProps {
  agentStatus: Record<string, "online" | "offline">;
}

export const AgentStatusPanel: React.FC<AgentStatusPanelProps> = ({ agentStatus }) => {
  const agents = Object.entries(agentStatus);

  if (agents.length === 0) return null;

  return (
    <div className="bg-muted/40 dark:bg-muted/20 rounded-md p-4 border border-border mb-6">
      <h3 className="text-sm font-semibold text-muted-foreground mb-2">
        Agent Connectivity
      </h3>
      <div className="flex flex-wrap gap-3">
        {agents.map(([name, status]) => (
          <Badge
            key={name}
            className={`
              px-3 py-1 rounded-full flex items-center gap-1
              ${status === "online" ? "bg-green-600 text-white" : "bg-red-600 text-white"}
            `}
          >
            {status === "online" ? <CircleCheck className="w-4 h-4" /> : <CircleX className="w-4 h-4" />}
            <span className="capitalize">{name}</span>
          </Badge>
        ))}
      </div>
    </div>
  );
};
