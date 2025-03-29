# task_intelligence_hub.py

import asyncio
import json
import time
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import os
import numpy as np
from redis.asyncio import Redis

# Import our system components

from backend.factories.factories import TaskFactory
from backend.models.models import MessageIntent, Task, TaskEvent, TaskOutcome, TaskResult
from backend.task_engine.task_manager import TaskManager
from task_clustering import TaskClusteringSystem, TaskRouter


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TaskIntelligenceHub")

class TaskIntelligenceHub:
    """
    Central integration service that connects TaskFactory, TaskManager, and TaskClustering
    to provide intelligent task routing, monitoring, and analytics.
    """
    
    def __init__(
        self, 
        redis_client: Redis,
        config: Dict[str, Any] = None
    ):
        self.redis = redis_client
        self.config = config or self._get_default_config()
        
        # Initialize core components
        self.task_manager = TaskManager(redis_client)
        self.clustering_system = TaskClusteringSystem(
            embedding_model=self.config["clustering"]["embedding_model"],
            n_clusters=self.config["clustering"]["n_clusters"],
            clustering_method=self.config["clustering"]["method"],
            visualization_path=self.config["paths"]["visualization_path"],
            min_samples=self.config["clustering"]["min_samples"]
        )
        self.task_router = TaskRouter(
            default_agent=self.config["routing"]["default_agent"],
            clustering_system=self.clustering_system,
            learning_rate=self.config["routing"]["learning_rate"],
            log_path=self.config["paths"]["log_path"]
        )
        
        # Internal state
        self.last_clustering_time = None
        self.integration_status = {
            "hub_started_at": datetime.now().isoformat(),
            "task_analysis_count": 0,
            "clustering_updates": 0,
            "auto_tuning_updates": 0,
            "learning_rate_adjustments": 0
        }
        self.event_counters = {
            "tasks_created": 0,
            "tasks_completed": 0,
            "tasks_routed": 0,
            "agents_updated": 0
        }
        
        # Subscribers and background tasks
        self.subscribers = []
        self._background_tasks = []
        
        # Configure auto-tuning
        if self.config["auto_tuning"]["enabled"]:
            TaskFactory.AUTO_TUNING_ENABLED = True
            TaskFactory.RETAIN_HISTORY = self.config["auto_tuning"]["retain_history"]
            TaskFactory.HISTORY_LIMIT = self.config["auto_tuning"]["history_limit"]
            TaskFactory.MIN_SAMPLES_FOR_TUNING = self.config["auto_tuning"]["min_samples"]
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Default configuration for TaskIntelligenceHub."""
        return {
            "clustering": {
                "enabled": True,
                "method": "kmeans",
                "embedding_model": "all-MiniLM-L6-v2",
                "n_clusters": 5,
                "min_samples": 100,
                "update_frequency": 3600  # seconds (1 hour)
            },
            "routing": {
                "default_agent": "Claude",
                "learning_rate": 0.1,  # exploration rate
                "min_confidence": 0.5,
                "fallback_strategy": "performance"  # performance, random, or specified
            },
            "auto_tuning": {
                "enabled": True,
                "retain_history": True,
                "history_limit": 1000,
                "min_samples": 10,
                "adaptive_learning_rate": True
            },
            "paths": {
                "visualization_path": "./visualizations",
                "log_path": "./logs",
                "model_path": "./models"
            },
            "agents": {
                "available": ["Claude", "GPT", "Grok", "Gemini"]
            },
            "websocket": {
                "status_update_frequency": 10  # seconds
            }
        }
    
    async def start(self):
        """Start the TaskIntelligenceHub and its background tasks."""
        logger.info("Starting TaskIntelligenceHub...")
        
        # Create required directories
        os.makedirs(self.config["paths"]["visualization_path"], exist_ok=True)
        os.makedirs(self.config["paths"]["log_path"], exist_ok=True)
        os.makedirs(self.config["paths"]["model_path"], exist_ok=True)
        
        # Subscribe to Redis channels
        self._background_tasks.append(asyncio.create_task(self._subscribe_to_events()))
        
        # Start background analysis task
        self._background_tasks.append(asyncio.create_task(self._periodic_task_analysis()))
        
        # Start WebSocket status updates if configured
        if self.config["websocket"]["status_update_frequency"] > 0:
            self._background_tasks.append(asyncio.create_task(self._send_status_updates()))
            
        logger.info("TaskIntelligenceHub started successfully")
    
    async def stop(self):
        """Stop the TaskIntelligenceHub and clean up resources."""
        logger.info("Stopping TaskIntelligenceHub...")
        
        # Cancel all background tasks
        for task in self._background_tasks:
            task.cancel()
            
        try:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        except asyncio.CancelledError:
            pass
            
        logger.info("TaskIntelligenceHub stopped")
    
    async def _subscribe_to_events(self):
        """Subscribe to Redis channels for system events."""
        pubsub = self.redis.pubsub()
        await pubsub.subscribe("task_events")
        
        logger.info("Subscribed to task_events channel")
        
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    await self._handle_event(message["data"])
        except asyncio.CancelledError:
            await pubsub.unsubscribe("task_events")
            raise
    
    async def _handle_event(self, event_data):
        """Process incoming events from Redis."""
        try:
            event = json.loads(event_data)
            event_type = event.get("event")
            
            if event_type == "task_created":
                await self._handle_task_created(event)
            elif event_type == "task_completed":
                await self._handle_task_completed(event)
            elif event_type == "agent_interaction":
                await self._handle_agent_interaction(event)
        except Exception as e:
            logger.error(f"Error processing event: {e}")
    
    async def _handle_task_created(self, event):
        """Handle task creation events."""
        task_id = event.get("task_id")
        agent = event.get("agent")
        target_agent = event.get("target_agent")
        reasoning_effort = event.get("reasoning_effort")
        
        logger.info(f"Task {task_id} created by {agent}, assigned to {target_agent}, effort: {reasoning_effort}")
        self.event_counters["tasks_created"] += 1
        
        # We could emit a WebSocket event here for real-time dashboard updates
        status_update = {
            "type": "task_created",
            "data": {
                "task_id": task_id,
                "agent": agent,
                "target_agent": target_agent,
                "reasoning_effort": reasoning_effort
            },
            "timestamp": datetime.now().isoformat()
        }
        await self._broadcast_status(status_update)
    
    async def _handle_task_completed(self, event):
        """Handle task completion events."""
        task_id = event.get("task_id")
        outcome = event.get("outcome")
        duration = event.get("duration")
        reasoning_effort = event.get("reasoning_effort")
        
        logger.info(f"Task {task_id} completed with outcome {outcome}, duration: {duration}s, effort: {reasoning_effort}")
        self.event_counters["tasks_completed"] += 1
        
        # We could emit a WebSocket event here for real-time dashboard updates
        status_update = {
            "type": "task_completed",
            "data": {
                "task_id": task_id,
                "outcome": outcome,
                "duration": duration,
                "reasoning_effort": reasoning_effort
            },
            "timestamp": datetime.now().isoformat()
        }
        await self._broadcast_status(status_update)
    
    async def _handle_agent_interaction(self, event):
        """Handle agent interaction events."""
        task_id = event.get("task_id")
        agent = event.get("agent")
        action = event.get("action")
        duration = event.get("duration")
        
        logger.debug(f"Agent {agent} performed {action} on task {task_id}, duration: {duration}s")
        self.event_counters["agents_updated"] += 1
    
    async def create_and_route_task(
        self, 
        content: str, 
        agent: str, 
        intent: MessageIntent = MessageIntent.START_TASK,
        event: TaskEvent = TaskEvent.PLAN,
        confidence: float = 0.9,
        deadline_pressure: Optional[float] = None
    ) -> Tuple[Task, Dict, str]:
        """
        Create a task and intelligently route it to the best agent.
        
        Returns:
            Tuple containing:
            - Task object
            - Task diagnostics
            - Assigned agent
        """
        # Get list of available agents
        available_agents = self.config["agents"]["available"]
        
        # Create the task (without assigning a target agent yet)
        task_id = f"task_{int(time.time() * 1000)}"
        
        # First, use TaskFactory to assess complexity and reasoning effort
        task_base, diagnostics = TaskFactory.create_task(
            task_id=task_id,
            agent=agent,
            content=content,
            target_agent="pending",  # Will be assigned by the router
            intent=intent,
            event=event,
            confidence=confidence,
            deadline_pressure=deadline_pressure
        )
        
        # Use TaskRouter to find the best agent
        target_agent, routing_decision = self.task_router.route_task(
            task_id=task_id,
            content=content,
            available_agents=available_agents,
            diagnostics=diagnostics
        )
        
        # Update the task with the chosen target agent
        task = Task(
            task_id=task_id,
            agent=agent,
            content=content,
            intent=intent,
            target_agent=target_agent,
            event=event,
            confidence=confidence,
            timestamp=task_base.timestamp,
            reasoning_effort=task_base.reasoning_effort
        )
        
        # Log the routing decision
        logger.info(f"Task {task_id} routed to {target_agent} using {routing_decision['method']} method")
        self.event_counters["tasks_routed"] += 1
        
        # Submit the task via TaskManager
        await self.task_manager.create_and_submit_task(
            content=content,
            agent=agent,
            target_agent=target_agent,
            intent=intent,
            event=event,
            confidence=confidence,
            deadline_pressure=deadline_pressure
        )
        
        # Add routing metadata to diagnostics
        diagnostics["routing"] = routing_decision
        
        return task, diagnostics, target_agent
    
    async def complete_task(
        self, 
        task_id: str, 
        outcome: TaskOutcome, 
        result_content: str, 
        contributing_agents: List[str] = None
    ) -> Optional[TaskResult]:
        """Complete a task and record metrics for learning."""
        # Get task result from TaskManager
        task_result = await self.task_manager.complete_task(
            task_id=task_id,
            outcome=outcome,
            result_content=result_content,
            contributing_agents=contributing_agents
        )
        
        if task_result:
            # Extract task information
            task_data = self.task_manager.task_history[-1]  # Most recent task should be the one we just completed
            
            # Update the router with performance metrics
            agent = task_result.target_agent
            duration = task_data["duration"]
            success = (outcome == TaskOutcome.COMPLETED or outcome == TaskOutcome.MERGED)
            
            self.task_router.update_agent_stats(agent, duration, success)
            
            # Publish event for dashboard updates
            status_update = {
                "type": "task_completed",
                "data": {
                    "task_id": task_id,
                    "agent": agent,
                    "outcome": outcome.value,
                    "duration": duration,
                    "reasoning_effort": task_result.reasoning_effort.value
                },
                "timestamp": datetime.now().isoformat()
            }
            await self._broadcast_status(status_update)
            
            logger.info(f"Task {task_id} completed and metrics recorded")
        
        return task_result
    
    async def _periodic_task_analysis(self):
        """Periodically analyze tasks, update clustering, and adjust system parameters."""
        try:
            while True:
                # Wait for initial data collection
                await asyncio.sleep(60)  # Check every minute
                
                # Get completed task count
                completed_tasks = self.event_counters["tasks_completed"]
                
                # If we have enough completed tasks and enough time has passed, run clustering
                if (completed_tasks >= self.config["clustering"]["min_samples"] and
                    (self.last_clustering_time is None or 
                     (datetime.now() - self.last_clustering_time).total_seconds() >= self.config["clustering"]["update_frequency"])):
                    
                    await self._update_clustering()
                    
                    # Adjust exploration rate if needed
                    if self.config["auto_tuning"]["adaptive_learning_rate"]:
                        await self._adjust_exploration_rate()
                        
                    # Update status
                    self.last_clustering_time = datetime.now()
                    self.integration_status["clustering_updates"] += 1
                    
                    status_update = {
                        "type": "clustering_updated",
                        "data": {
                            "clusters_found": self.clustering_system.cluster_model is not None,
                            "timestamp": self.last_clustering_time.isoformat()
                        },
                        "timestamp": datetime.now().isoformat()
                    }
                    await self._broadcast_status(status_update)
        except asyncio.CancelledError:
            logger.info("Periodic task analysis cancelled")
            raise
    
    async def _update_clustering(self):
        """Update the task clustering based on collected task history."""
        logger.info("Updating task clustering...")
        
        # Get task history from TaskManager
        task_history = self.task_manager.task_history
        
        # Run the clustering analysis
        results = self.clustering_system.run_analysis(task_history)
        
        if results["status"] == "success":
            # Update the router with the new clustering system
            self.task_router.clustering_system = self.clustering_system
            
            # Log results
            logger.info(f"Clustering update successful: found {results['clusters_found']} clusters")
            logger.info(f"Best agents by cluster: {results['best_agents_by_cluster']}")
            
            self.integration_status["task_analysis_count"] += 1
        else:
            logger.warning(f"Clustering update failed: {results.get('message', 'Unknown error')}")
    
    async def _adjust_exploration_rate(self):
        """Adaptively adjust the exploration rate (learning rate) based on system performance."""
        # Decrease exploration as system matures
        # Start high (0.2) for exploration, then decrease as we gain confidence
        
        completed_tasks = self.event_counters["tasks_completed"]
        task_threshold = self.config["clustering"]["min_samples"] * 5
        
        if completed_tasks > task_threshold:
            # Gradually decrease learning rate as we gather more data
            new_rate = max(0.05, self.config["routing"]["learning_rate"] * 0.9)
            
            if new_rate != self.config["routing"]["learning_rate"]:
                logger.info(f"Adjusting exploration rate: {self.config['routing']['learning_rate']} -> {new_rate}")
                
                self.config["routing"]["learning_rate"] = new_rate
                self.task_router.learning_rate = new_rate
                
                self.integration_status["learning_rate_adjustments"] += 1
    
    async def _send_status_updates(self):
        """Periodically send status updates to connected clients."""
        try:
            while True:
                await asyncio.sleep(self.config["websocket"]["status_update_frequency"])
                
                # Prepare stats from TaskManager
                task_stats = self.task_manager.get_task_stats()
                
                # Add information about clustering and router
                system_status = {
                    "task_stats": task_stats,
                    "integration_status": self.integration_status,
                    "event_counters": self.event_counters,
                    "config": {
                        "clustering_enabled": self.config["clustering"]["enabled"],
                        "auto_tuning_enabled": self.config["auto_tuning"]["enabled"],
                        "learning_rate": self.config["routing"]["learning_rate"]
                    }
                }
                
                # Add clustering information if available
                if hasattr(self.clustering_system, 'cluster_model') and self.clustering_system.cluster_model is not None:
                    system_status["clustering"] = {
                        "clusters_found": len(self.clustering_system.determine_best_agent_per_cluster()),
                        "last_updated": self.last_clustering_time.isoformat() if self.last_clustering_time else None,
                    }
                
                # Broadcast to all subscribers
                status_message = {
                    "type": "system_status",
                    "data": system_status,
                    "timestamp": datetime.now().isoformat()
                }
                await self._broadcast_status(status_message)
        except asyncio.CancelledError:
            logger.info("Status updates cancelled")
            raise
    
    async def _broadcast_status(self, status):
        """Broadcast status updates to all subscribers."""
        message = json.dumps(status)
        await self.redis.publish("system_status", message)
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status and metrics."""
        return {
            "integration_status": self.integration_status,
            "event_counters": self.event_counters,
            "task_manager": {
                "active_tasks": self.task_manager.get_active_task_count(),
                "total_tasks": len(self.task_manager.task_history) + self.task_manager.get_active_task_count()
            },
            "clustering": {
                "enabled": self.config["clustering"]["enabled"],
                "last_updated": self.last_clustering_time.isoformat() if self.last_clustering_time else None,
                "model_ready": hasattr(self.clustering_system, 'cluster_model') and self.clustering_system.cluster_model is not None
            },
            "routing": {
                "learning_rate": self.config["routing"]["learning_rate"],
                "default_agent": self.config["routing"]["default_agent"]
            },
            "auto_tuning": {
                "enabled": self.config["auto_tuning"]["enabled"],
                "history_limit": self.config["auto_tuning"]["history_limit"]
            }
        }
    
    async def update_config(self, new_config: Dict[str, Any]) -> Dict[str, Any]:
        """Update system configuration with new settings."""
        # Merge new config with existing
        for section, settings in new_config.items():
            if section in self.config:
                if isinstance(settings, dict):
                    self.config[section].update(settings)
                else:
                    self.config[section] = settings
        
        # Apply configuration changes to components
        if "auto_tuning" in new_config:
            if "enabled" in new_config["auto_tuning"]:
                TaskFactory.AUTO_TUNING_ENABLED = new_config["auto_tuning"]["enabled"]
            if "retain_history" in new_config["auto_tuning"]:
                TaskFactory.RETAIN_HISTORY = new_config["auto_tuning"]["retain_history"]
            if "history_limit" in new_config["auto_tuning"]:
                TaskFactory.HISTORY_LIMIT = new_config["auto_tuning"]["history_limit"]
            if "min_samples" in new_config["auto_tuning"]:
                TaskFactory.MIN_SAMPLES_FOR_TUNING = new_config["auto_tuning"]["min_samples"]
        
        if "routing" in new_config and "learning_rate" in new_config["routing"]:
            self.task_router.learning_rate = new_config["routing"]["learning_rate"]
        
        logger.info("Configuration updated")
        return self.config
    
    async def get_agent_performance(self) -> Dict[str, Any]:
        """Get detailed agent performance metrics."""
        # This would combine data from TaskRouter and TaskManager
        agent_performance = {}
        
        # Get agent stats from router
        for agent, stats in self.task_router.agent_stats.items():
            agent_performance[agent] = {
                "success_rate": stats.get("success_rate", 0),
                "avg_duration": stats.get("avg_duration", 0),
                "tasks_completed": stats.get("tasks_completed", 0)
            }
        
        # If we have clustering info, add agent performance by cluster
        if hasattr(self.clustering_system, 'agent_performance') and self.clustering_system.agent_performance:
            for agent, clusters in self.clustering_system.agent_performance.items():
                if agent in agent_performance:
                    agent_performance[agent]["cluster_performance"] = {}
                    for cluster_id, perf in clusters.items():
                        agent_performance[agent]["cluster_performance"][cluster_id] = {
                            "success_rate": perf.get("success_rate", 0),
                            "avg_duration": perf.get("avg_duration", 0),
                            "tasks_count": perf.get("tasks_count", 0),
                            "match_score": perf.get("cluster_match_score", 0)
                        }
        
        return agent_performance
    
    async def get_task_factory_stats(self) -> Dict[str, Any]:
        """Get statistics about TaskFactory configuration and performance."""
        # Return the current keyword weights and thresholds
        stats = {
            "version": TaskFactory.VERSION,
            "auto_tuning_enabled": TaskFactory.AUTO_TUNING_ENABLED,
            "keyword_weights": {
                category: {
                    "weight": data["weight"],
                    "keyword_count": len(data["keywords"])
                }
                for category, data in TaskFactory.KEYWORD_WEIGHTS.items()
            },
            "thresholds": TaskFactory.WORD_COUNT_THRESHOLDS,
            "outcome_history_size": len(TaskFactory.outcome_history)
        }
        
        return stats
    
    async def get_clustering_visualization(self) -> Optional[str]:
        """Get the path to the latest clustering visualization."""
        if self.last_clustering_time is None:
            return None
            
        # Find the latest visualization file
        viz_path = self.config["paths"]["visualization_path"]
        files = [f for f in os.listdir(viz_path) if f.startswith("task_clusters_") and f.endswith(".png")]
        
        if not files:
            return None
            
        # Sort files by creation time (most recent first)
        files.sort(key=lambda f: os.path.getctime(os.path.join(viz_path, f)), reverse=True)
        
        return os.path.join(viz_path, files[0])
    
    async def api_get_router_decisions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent routing decisions for API/dashboard."""
        if not hasattr(self.task_router, 'decision_log'):
            return []
            
        # Return the most recent decisions
        decisions = self.task_router.decision_log[-limit:] if limit > 0 else self.task_router.decision_log
        return decisions
    
    async def api_get_task_history(self, limit: int = 100, status: str = None) -> List[Dict[str, Any]]:
        """Get task history for API/dashboard with optional filtering."""
        # Combine active and completed tasks
        all_tasks = []
        
        # Add active tasks if needed
        if status is None or status == "active":
            for task_id, task_data in self.task_manager.active_tasks.items():
                task_info = {
                    "task_id": task_id,
                    "status": "active",
                    "agent": task_data["task"].agent,
                    "target_agent": task_data["task"].target_agent,
                    "content": task_data["task"].content,
                    "reasoning_effort": task_data["task"].reasoning_effort.value,
                    "start_time": task_data["start_time"],
                    "duration_so_far": time.time() - task_data["start_time"],
                    "priority": task_data["priority"],
                    "diagnostics": task_data["diagnostics"]
                }
                all_tasks.append(task_info)
        
        # Add completed tasks if needed
        if status is None or status == "completed":
            for task_data in self.task_manager.task_history:
                task_info = {
                    "task_id": task_data["task"].task_id,
                    "status": "completed",
                    "agent": task_data["task"].agent,
                    "target_agent": task_data["task"].target_agent,
                    "content": task_data["task"].content,
                    "reasoning_effort": task_data["task"].reasoning_effort.value,
                    "start_time": task_data["start_time"],
                    "end_time": task_data.get("end_time"),
                    "duration": task_data.get("duration"),
                    "outcome": task_data.get("outcome"),
                    "diagnostics": task_data["diagnostics"]
                }
                all_tasks.append(task_info)
        
        # Sort by start_time (newest first)
        all_tasks.sort(key=lambda t: t["start_time"], reverse=True)
        
        # Apply limit
        if limit > 0:
            all_tasks = all_tasks[:limit]
            
        return all_tasks

# Example of how to use this in an async application
async def example_usage():
    # Create Redis client
    redis = Redis.from_url("redis://localhost")
    
    # Create and start the TaskIntelligenceHub
    hub = TaskIntelligenceHub(redis)
    await hub.start()
    
    try:
        # Create and route a task
        task, diagnostics, agent = await hub.create_and_route_task(
            content="Analyze this dataset and create a visualization",
            agent="User123",
            confidence=0.8
        )
        
        print(f"Task routed to: {agent}")
        print(f"Reasoning effort: {task.reasoning_effort.value}")
        print(f"Routing method: {diagnostics['routing']['method']}")
        
        # Allow background tasks to run
        await asyncio.sleep(5)
        
        # Get system status
        status = hub.get_system_status()
        print(f"System status: {status}")
        
        # Complete the task
        result = await hub.complete_task(
            task_id=task.task_id,
            outcome=TaskOutcome.COMPLETED,
            result_content="Analysis complete. Visualization attached.",
            contributing_agents=[agent]
        )
        
        print(f"Task completed: {result is not None}")
        
        # Allow background tasks to run
        await asyncio.sleep(5)
        
        # Update configuration
        new_config = {
            "routing": {
                "learning_rate": 0.05
            }
        }
        updated_config = await hub.update_config(new_config)
        print(f"Updated learning rate: {updated_config['routing']['learning_rate']}")
        
    finally:
        # Stop the hub
        await hub.stop()
        
        # Close Redis connection
        await redis.close()

if __name__ == "__main__":
    asyncio.run(example_usage())