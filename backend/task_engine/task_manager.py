# task_manager.py

from backend.models.models import Task, TaskEvent, MessageIntent, TaskOutcome, TaskResult, ReasoningEffort
from task_factory import TaskFactory
import asyncio
import json
import uuid
import time
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import datetime as dt
from redis.asyncio import Redis
from loguru import logger

class TaskManager:
    """
    Manages task creation, routing, and tracking for a multi-agent system.
    Integrates with TaskFactory for reasoning effort assessment.
    """
    
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.active_tasks: Dict[str, Dict[str, Any]] = {}
        self.task_history: List[Dict[str, Any]] = []
        
    async def create_and_submit_task(self, 
                               content: str, 
                               agent: str, 
                               target_agent: str,
                               intent: MessageIntent = MessageIntent.START_TASK,
                               event: TaskEvent = TaskEvent.PLAN,
                               confidence: float = 0.9,
                               priority: Optional[int] = None,
                               deadline_pressure: Optional[float] = None) -> Tuple[Task, Dict]:
        """
        Creates a task using TaskFactory and submits it to the task queue
        """
        # Generate a unique task ID if not provided
        task_id = f"task_{uuid.uuid4().hex[:10]}"
        
        # Calculate priority if not provided
        if priority is None:
            # Default priority based on intent
            priority_map = {
                MessageIntent.START_TASK: 5,
                MessageIntent.MODIFY_TASK: 7,
                MessageIntent.CHECK_STATUS: 3,
                MessageIntent.CHAT: 1
            }
            priority = priority_map.get(intent, 5)
        
        # Calculate deadline pressure if not provided
        if deadline_pressure is None:
            # Default to medium pressure
            deadline_pressure = 0.5
        
        # Create the task with our factory
        task, diagnostics = TaskFactory.create_task(
            task_id=task_id,
            agent=agent,
            content=content,
            target_agent=target_agent,
            intent=intent,
            event=event,
            confidence=confidence,
            priority=priority,
            deadline_pressure=deadline_pressure
        )
        
        # Enhance priority based on reasoning effort
        effort_priority_boost = {
            ReasoningEffort.LOW: 0,
            ReasoningEffort.MEDIUM: 2,
            ReasoningEffort.HIGH: 5
        }
        adjusted_priority = priority + effort_priority_boost.get(task.reasoning_effort, 0)
        
        # Store task in active tasks with metadata
        self.active_tasks[task_id] = {
            "task": task,
            "diagnostics": diagnostics,
            "priority": adjusted_priority,
            "start_time": time.time(),
            "agent_interactions": []
        }
        
        # Log the task creation
        logger.info(f"Created task {task_id} with effort {task.reasoning_effort.value.upper()}, " +
                   f"priority {adjusted_priority}, target agent: {target_agent}")
        
        # Submit to Redis task queue with priority
        await self.redis.zadd(
            "task_queue", 
            {json.dumps({"task_id": task_id, "task": task.model_dump()}): adjusted_priority}
        )
        
        # Publish task creation event
        await self.redis.publish(
            "task_events",
            json.dumps({
                "event": "task_created",
                "task_id": task_id,
                "agent": agent,
                "target_agent": target_agent,
                "reasoning_effort": task.reasoning_effort.value,
                "priority": adjusted_priority,
                "timestamp": datetime.now().isoformat()
            })
        )
        
        return task, diagnostics
    
    async def record_agent_interaction(self, task_id: str, agent: str, action: str, 
                                      content: str, duration: float) -> None:
        """Record an agent's interaction with a task"""
        if task_id in self.active_tasks:
            self.active_tasks[task_id]["agent_interactions"].append({
                "agent": agent,
                "action": action,
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "duration": duration
            })
            
            # Publish interaction event
            await self.redis.publish(
                "task_events",
                json.dumps({
                    "event": "agent_interaction",
                    "task_id": task_id,
                    "agent": agent,
                    "action": action,
                    "duration": duration,
                    "timestamp": datetime.now().isoformat()
                })
            )
    
    async def complete_task(self, task_id: str, outcome: TaskOutcome, 
                          result_content: str, contributing_agents: List[str] = None) -> Optional[TaskResult]:
        """Mark a task as complete and record metrics"""
        if task_id not in self.active_tasks:
            logger.warning(f"Attempted to complete unknown task {task_id}")
            return None
            
        task_data = self.active_tasks[task_id]
        task = task_data["task"]
        
        # Calculate duration
        end_time = time.time()
        duration = end_time - task_data["start_time"]
        
        # Create task result
        task_result = TaskResult(
            task_id=task_id,
            agent=task.agent,
            content=result_content,
            intent=task.intent,
            target_agent=task.target_agent,
            event=TaskEvent.COMPLETE,
            confidence=task.confidence,
            reasoning_effort=task.reasoning_effort,
            outcome=outcome,
            contributing_agents=contributing_agents or [task.target_agent]
        )
        
        # Record task outcome for model improvement
        TaskFactory.record_task_outcome(
            task_id=task_id,
            diagnostics=task_data["diagnostics"],
            actual_duration=duration,
            success=(outcome == TaskOutcome.COMPLETED or outcome == TaskOutcome.MERGED),
            feedback=None  # Could be added later
        )
        
        # Add to history and remove from active tasks
        task_data["end_time"] = end_time
        task_data["duration"] = duration
        task_data["outcome"] = outcome.value
        task_data["result"] = task_result.model_dump()
        
        self.task_history.append(task_data)
        del self.active_tasks[task_id]
        
        # Publish task completion event
        await self.redis.publish(
            "task_events",
            json.dumps({
                "event": "task_completed",
                "task_id": task_id,
                "outcome": outcome.value,
                "duration": duration,
                "reasoning_effort": task.reasoning_effort.value,
                "timestamp": datetime.now().isoformat()
            })
        )
        
        logger.info(f"Completed task {task_id} with outcome {outcome.value}, " +
                   f"duration {duration:.2f}s, effort {task.reasoning_effort.value.upper()}")
        
        return task_result
    
    async def get_next_task(self, agent: str, max_wait_time: float = 0.5) -> Optional[Task]:
        """Get the highest priority task for an agent with a timeout"""
        # Get highest priority task
        result = await self.redis.zpopmax("task_queue")
        
        if not result:
            return None
            
        task_json, priority = result[0]
        task_data = json.loads(task_json)
        task_id = task_data["task_id"]
        
        # Create Task from dict
        task = Task.model_validate(task_data["task"])
        
        # If this task is not targeted at this agent, put it back and return None
        if task.target_agent != agent:
            # Put it back in the queue with same priority
            await self.redis.zadd("task_queue", {task_json: priority})
            return None
            
        # Record task assignment
        await self.record_agent_interaction(task_id, agent, "assigned", "", 0)
        
        # Log assignment
        logger.info(f"Assigned task {task_id} to {agent}, " +
                  f"effort {task.reasoning_effort.value.upper()}, priority {priority}")
                  
        return task
        
    def get_active_task_count(self) -> int:
        """Get count of active tasks"""
        return len(self.active_tasks)
        
    def get_task_stats(self) -> Dict[str, Any]:
        """Get statistics about tasks and performance"""
        total_tasks = len(self.task_history) + len(self.active_tasks)
        completed_tasks = len(self.task_history)
        active_tasks = len(self.active_tasks)
        
        # Effort distribution
        effort_counts = {
            "low": 0,
            "medium": 0,
            "high": 0
        }
        
        # Outcome distribution
        outcome_counts = {
            "completed": 0,
            "merged": 0,
            "escalated": 0
        }
        
        # Calculate average durations by effort
        durations_by_effort = {
            "low": [],
            "medium": [],
            "high": []
        }
        
        # Process completed tasks
        for task_data in self.task_history:
            task = task_data["task"]
            effort = task.reasoning_effort.value
            effort_counts[effort] += 1
            
            if "outcome" in task_data:
                outcome_counts[task_data["outcome"]] += 1
                
            if "duration" in task_data:
                durations_by_effort[effort].append(task_data["duration"])
                
        # Process active tasks
        for task_data in self.active_tasks.values():
            task = task_data["task"]
            effort = task.reasoning_effort.value
            effort_counts[effort] += 1
        
        # Calculate averages
        avg_durations = {}
        for effort, durations in durations_by_effort.items():
            if durations:
                avg_durations[effort] = sum(durations) / len(durations)
            else:
                avg_durations[effort] = 0
                
        return {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "active_tasks": active_tasks,
            "effort_distribution": effort_counts,
            "outcome_distribution": outcome_counts,
            "avg_duration_by_effort": avg_durations
        }