// src/hooks/useWebSocket.ts
import { useEffect, useState, useCallback } from "react";
import { Task } from "@/types/models";

interface AgentStatusMap {
  [agent: string]: "online" | "offline";
}

export function useWebSocket() {
  const [activeTasks, setActiveTasks] = useState<Task[]>([]);
  const [completedTasks, setCompletedTasks] = useState<Task[]>([]);
  const [agentStatus, setAgentStatus] = useState<AgentStatusMap>({});

  const addTask = useCallback((task: Task) => {
    setActiveTasks((prev) => [...prev, task]);
  }, []);

  const completeTask = useCallback((task: Task) => {
    setCompletedTasks((prev) => [...prev, task]);
    setActiveTasks((prev) => prev.filter((t) => t.task_id !== task.task_id));
  }, []);

  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/ws");

    ws.onopen = () => {
      console.log("✅ WebSocket connected");
    };

    ws.onmessage = (event) => {
      const { type, payload } = JSON.parse(event.data);

      switch (type) {
        case "task":
          addTask(payload.task);
          break;
        case "task_result":
          completeTask(payload);
          break;
        case "system_status_update":
          setAgentStatus(payload.agent_status || {});
          break;
        default:
          console.log("Unhandled message type:", type);
      }
    };

    ws.onerror = (err) => {
      console.error("WebSocket error:", err);
    };

    return () => ws.close();
  }, [addTask, completeTask]); 

  return {
    activeTasks,
    completedTasks,
    agentStatus,
    addTask,
    completeTask,
  };
}
