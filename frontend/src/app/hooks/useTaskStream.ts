// src/hooks/useTaskStream.ts
import { useEffect, useState } from "react";
import { useWebSocket } from "@/contexts/websocket-context";

interface Task {
  task_id: string;
  content: string;
  target_agent: string;
  reasoning_effort: string;
  reasoning_strategy: string;
  [key: string]: unknown;
}

export function useTaskStream() {
  const [activeTasks, setActiveTasks] = useState<Task[]>([]);
  const [completedTasks, setCompletedTasks] = useState<Task[]>([]);
  const { socket } = useWebSocket();

  useEffect(() => {
    if (!socket) return;

    const handleMessage = (event: MessageEvent) => {
      try {
        const { type, payload } = JSON.parse(event.data);

        if (type === "task") {
          setActiveTasks((prev) => [...prev, payload.task]);
        }

        if (type === "task_result") {
          setCompletedTasks((prev) => [...prev, payload]);
          setActiveTasks((prev) => prev.filter((t) => t.task_id !== payload.task_id));
        }
      } catch (err) {
        console.warn("Failed to parse task stream message:", event.data, err);
      }
    };

    socket.addEventListener("message", handleMessage);
    return () => socket.removeEventListener("message", handleMessage);
  }, [socket]);

  return {
    activeTasks,
    completedTasks,
  };
}