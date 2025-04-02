import asyncio
import json
import time
from typing import Any, Dict, Union, List, Optional
from datetime import datetime
import base64
import numpy as np
import os

from backend.agents.base_agent import BaseAgent
from backend.core.config import settings, logger
from backend.models.models import BaseMessage, Task, Message, TaskResult, MessageIntent, TaskEvent, TaskOutcome, ReasoningEffort
from backend.factories.factories import TaskFactory, MessageFactory, TaskResultFactory
from xai_sdk import XAIClient  # Hypothetical; adjust to real xAI SDK
from redis.asyncio import Redis
from backend.services.task_intelligence_hub import TaskIntelligenceHub

class GrokAgent(BaseAgent):
    def __init__(self):
        super().__init__(agent_name=settings.GROK_AGENT_NAME, api_key=settings.GROK_API_KEY)
        self.task_states: Dict[str, Dict[str, Any]] = {}
        self.xai_client = XAIClient(api_key=self.api_key)
        self.hub = TaskIntelligenceHub(redis_client=Redis.from_url(settings.REDIS_URL))
        self.ws = None  # WebSocket connection, set via API or main

    async def _stream_llm(self, prompt: str, ws, task_id: str, system_message: str = None):
        agent_name = self.agent_name
        try:
            stream = await self.xai_client.stream_chat_completion(
                model="grok-3",
                messages=[
                    {"role": "system", "content": system_message or "You are Grok, a helpful orchestration agent built by xAI."},
                    {"role": "user", "content": prompt}
                ],
                stream=True
            )
            full_text = ""
            async for chunk in stream:
                delta = chunk.get("content", "")  # Adjust based on real xAI API
                full_text += delta
                if delta.strip() and ws:
                    await ws.send(json.dumps({
                        "event": "stream_update",
                        "data": {"agent": agent_name, "task_id": task_id, "delta": delta}
                    }))
            return full_text
        except Exception as e:
            logger.error(f"{agent_name} streaming failed: {e}")
            if ws:
                await ws.send(json.dumps({
                    "event": "error",
                    "data": {"agent": agent_name, "task_id": task_id, "error": str(e)}
                }))
            return "[Streaming Error]"

    async def start(self):
        logger.info(f"Starting {self.agent_name}...")
        await self.hub.start()
        await self.sync_task_states()
        asyncio.create_task(self._periodic_tasks())

    async def stop(self):
        logger.info(f"Stopping {self.agent_name}...")
        await self.hub.stop()

    async def handle_start_task(self, task: Task):
        logger.info(f"{self.agent_name} received START_TASK (ID: {task.task_id}): {task.content[:50]}...")
        if not task.content:
            await self.publish_error(task.task_id, "Task content cannot be empty.", task.agent)
            return

        new_task, diagnostics, target_agent = await self.hub.create_and_route_task(
            content=task.content,
            agent=self.agent_name,
            intent=MessageIntent.START_TASK,
            event=TaskEvent.PLAN,
            confidence=0.9
        )

        self.task_states[task.task_id] = {
            "status": TaskEvent.PLAN,
            "original_requester": task.agent,
            "current_step": "initial_proposal",
            "round": 1,
            "history": [f"Task received from {task.agent}: {task.content}"],
            "start_time": datetime.now().timestamp()
        }

        if diagnostics["routing"]["confidence"] < self.hub.config["routing"]["min_confidence"]:
            prompt = f"Task: {task.content}\nRouter picked {target_agent} (confidence: {diagnostics['routing']['confidence']}). Should it be {target_agent} or another agent (e.g., GPT, Claude)? Why?"
            xai_response = await self._stream_llm(prompt, self.ws, task.task_id, "You are Grok, an orchestration expert.")
            if "claude" in xai_response.lower() and target_agent != settings.CLAUDE_AGENT_NAME:
                target_agent = settings.CLAUDE_AGENT_NAME
                diagnostics["routing"]["xai_override"] = xai_response
            elif "gpt" in xai_response.lower() and target_agent != settings.GPT_AGENT_NAME:
                target_agent = settings.GPT_AGENT_NAME
                diagnostics["routing"]["xai_override"] = xai_response
            new_task.target_agent = target_agent

        if len(task.content) > 100:
            effort_prompt = f"Analyze this task complexity: {task.content[:300]}... Rate effort as LOW, MEDIUM, or HIGH."
            effort_response = await self._stream_llm(effort_prompt, self.ws, task.task_id, "You are an expert task analyzer.")
            if any(level in effort_response.upper() for level in ["LOW", "MEDIUM", "HIGH"]):
                detected_level = next(level for level in ["LOW", "MEDIUM", "HIGH"] if level in effort_response.upper())
                diagnostics["effort_override"] = {
                    "original": diagnostics["final_effort"],
                    "grok_assessment": detected_level,
                    "reasoning": effort_response
                }
                new_effort = ReasoningEffort[detected_level]
                new_task.reasoning_effort = new_effort
                TaskFactory.record_task_outcome(task.task_id, diagnostics, 0, True, f"Grok effort override: {effort_response}")

        await self.publish_to_agent(target_agent, new_task)
        await self.publish_update(
            task.task_id,
            TaskEvent.PLAN,
            f"Task assigned to {target_agent} (method: {diagnostics['routing']['method']}, confidence: {diagnostics['routing']['confidence']:.2f})",
            task.agent
        )
        await self.publish_to_frontend(new_task)
        
    async def handle_modify_task(self, task_update: Union[Task, TaskResult]):
        task_id = task_update.task_id
        sender = task_update.agent
        logger.info(f"{self.agent_name} received MODIFY_TASK/RESULT (ID: {task_id}) from {sender} (Event: {task_update.event.value})")

        if task_id not in self.task_states:
            logger.warning(f"Received update for unknown task ID: {task_id}. Ignoring.")
            return

        self.task_states[task_id]["history"].append(f"Update from {sender} ({task_update.event.value}): {task_update.content[:100]}...")
        self.task_states[task_id]["status"] = task_update.event

        if task_update.event == TaskEvent.COMPLETE and task_update.outcome == TaskOutcome.SUCCESS:
            result = await self.hub.complete_task(
                task_id=task_id,
                outcome=TaskOutcome.COMPLETED,
                result_content=task_update.content,
                contributing_agents=[sender]
            )
            duration = datetime.now().timestamp() - self.task_states[task_id]["start_time"]
            TaskFactory.record_task_outcome(task_id, result.metadata.get("diagnostics", {}), duration, True)
            self.hub.task_router.update_agent_stats(sender, duration, True)
            await self.publish_to_agent(self.task_states[task_id]["original_requester"], result)
            await self.publish_to_frontend(result)
            if "dependencies" in self.task_states[task_id]:
                for dep_id in self.task_states[task_id]["dependencies"]:
                    dep_task = self.hub.task_manager.active_tasks.get(dep_id)
                    if dep_task:
                        dep_task["task"].event = TaskEvent.PLAN
                        await self.publish_to_agent(dep_task["task"].target_agent, dep_task["task"])
                        logger.info(f"Triggered dependent task {dep_id}")
            del self.task_states[task_id]
            return

        next_task, diagnostics, next_agent = await self.hub.create_and_route_task(
            content=f"Context: Next step after {sender}'s update\nPrevious: {task_update.content}",
            agent=self.agent_name,
            intent=MessageIntent.MODIFY_TASK,
            event=TaskEvent(task_update.event.value)
        )
        self.task_states[task_id]["current_step"] = diagnostics["routing"]["method"]
        await self.publish_to_agent(next_agent, next_task)
        await self.publish_to_frontend(next_task)

    async def handle_chat_message(self, message: Message):
        """Handle general chat messages, delegating to xAI for dynamic responses."""
        logger.info(f"{self.agent_name} received CHAT from {message.agent}: {message.content[:50]}...")
        prompt = f"User said: {message.content}\nProvide a helpful response or orchestration suggestion."
        system_message = "You are Grok, a helpful agent. Respond naturally or suggest task actions."
        response = await self._stream_llm(prompt, self.ws, message.task_id or f"chat-{id(message)}", system_message)
        chat_response = MessageFactory.create_message(
            task_id=message.task_id or f"chat-{id(message)}",
            agent=self.agent_name,
            content=response,
            intent=MessageIntent.CHAT,
            target_agent=message.agent
        )
        await self.publish_to_frontend(chat_response)

    async def get_notes(self) -> Dict[str, Any]:
        """Return current state overview for BaseAgent compliance."""
        return {
            "agent": self.agent_name,
            "active_tasks": list(self.task_states.keys()),
            "task_details": {k: {kk: vv for kk, vv in v.items() if kk != "history"} for k, v in self.task_states.items()},
            "hub_status": self.hub.get_system_status()
        }

    async def process_response(self, response: Any, originating_agent: str):
        """Generic response processing for BaseAgent compliance."""
        logger.debug(f"{self.agent_name} received generic response from {originating_agent}, delegating...")
        if isinstance(response, (Task, TaskResult)):
            await self.handle_modify_task(response)
        elif isinstance(response, Message):
            await self.handle_chat_message(response)
        else:
            logger.warning(f"Received non-standard response type {type(response)} from {originating_agent}")
            if self.ws:
                await self.ws.send(json.dumps({
                    "event": "unhandled_response",
                    "data": {"type": str(type(response)), "agent": originating_agent},
                    "timestamp": datetime.now().isoformat()
                }))

    async def create_dependent_task(self, content: str, depends_on: str, agent: str, timeout: float = 3600):
        parent_task = self.hub.task_manager.active_tasks.get(depends_on)
        if not parent_task:
            completed = [t for t in self.hub.task_manager.task_history if t["task"].task_id == depends_on]
            if completed:
                return await self.hub.create_and_route_task(content, agent)
            logger.warning(f"Parent task {depends_on} not found for {content}")
            return None, None, None

        task, diagnostics, target_agent = await self.hub.create_and_route_task(
            content=content, agent=agent, event=TaskEvent.WAITING
        )
        task.metadata["depends_on"] = depends_on
        task.metadata["timeout"] = datetime.now().timestamp() + timeout
        if "dependencies" not in self.task_states.get(depends_on, {}):
            self.task_states[depends_on]["dependencies"] = []
        self.task_states[depends_on]["dependencies"].append(task.task_id)
        logger.info(f"Task {task.task_id} waiting on {depends_on}")
        return task, diagnostics, target_agent

    async def sync_task_states(self):
        for task_id, state in self.task_states.items():
            if task_id in self.hub.task_manager.active_tasks:
                self.hub.task_manager.active_tasks[task_id]["grok_state"] = state
        for task_id, task_data in self.hub.task_manager.active_tasks.items():
            if task_id not in self.task_states:
                self.task_states[task_id] = {
                    "status": task_data.get("task", {}).event,
                    "original_requester": task_data.get("task", {}).agent,
                    "current_step": "unknown",
                    "round": 1,
                    "history": [f"Task synced from TaskManager: {task_data.get('task', {}).content}"],
                    "start_time": task_data.get("start_time", datetime.now().timestamp())
                }

    async def _periodic_tasks(self):
        while True:
            await asyncio.sleep(60)
            await self.adjust_learning_rate(self.hub.task_manager.task_history)
            await self.broadcast_visualization()
            await self.reroute_failed_tasks()

    async def adjust_learning_rate(self, task_history: List[Dict]):
        total_tasks = len(task_history)
        if total_tasks > 50 and total_tasks % 20 == 0:
            recent_tasks = task_history[-20:]
            success_rate = sum(1 for t in recent_tasks if t.get("outcome") == "completed") / 20
            current_rate = self.hub.config["routing"]["learning_rate"]
            new_rate = current_rate
            if success_rate > 0.9 and current_rate > 0.05:
                new_rate = max(0.05, current_rate * 0.8)
            elif success_rate < 0.7 and current_rate < 0.3:
                new_rate = min(0.3, current_rate * 1.5)
            if new_rate != current_rate:
                await self.hub.update_config({"routing": {"learning_rate": new_rate}})
                self.hub.task_router.learning_rate = new_rate
                logger.info(f"Adjusted learning rate: {current_rate} -> {new_rate} (success rate: {success_rate:.2f})")
                if self.ws:
                    await self.ws.send(json.dumps({
                        "event": "learning_rate_update",
                        "data": {"new_rate": new_rate, "success_rate": success_rate},
                        "timestamp": datetime.now().isoformat()
                    }))

    async def broadcast_visualization(self):
        viz_path = await self.hub.get_clustering_visualization()
        if viz_path and os.path.exists(viz_path) and self.ws:
            with open(viz_path, "rb") as f:
                image_data = f.read()
            encoded = base64.b64encode(image_data).decode('utf-8')
            await self.ws.send(json.dumps({
                "event": "cluster_visualization",
                "data": {"image_type": "image/png", "image_data": encoded},
                "timestamp": datetime.now().isoformat()
            }))
            logger.info(f"Broadcasted viz: {viz_path}")

    async def name_clusters(self):
        profiles = self.hub.clustering_system.analyze_cluster_characteristics(
            self.hub.clustering_system.cluster_model.labels_ if self.hub.clustering_system.cluster_model else [],
            self.hub.task_manager.task_history
        )
        for cluster_id, profile in profiles.items():
            prompt = f"Cluster: {profile['examples'][:2]}\nEffort: {profile['dominant_effort']}\nComplexity: {profile['avg_complexity']:.2f}\nSuggest a short name."
            name = await self._stream_llm(prompt, self.ws, f"cluster_{cluster_id}", "You are a naming expert.")
            profile["name"] = name.strip()
        return profiles

    async def reroute_failed_tasks(self):
        for task_id, data in list(self.hub.task_manager.active_tasks.items()):
            agent = data["task"].target_agent
            if not await self.hub.task_manager.is_agent_active(agent):  # Assume this method exists
                logger.warning(f"Agent {agent} offline for task {task_id}")
                new_task, diagnostics, new_agent = await self.hub.create_and_route_task(
                    data["task"].content, self.agent_name
                )
                await self.publish_to_agent(new_agent, new_task)
                if self.ws:
                    await self.ws.send(json.dumps({
                        "event": "agent_failure",
                        "data": {"task_id": task_id, "old_agent": agent, "new_agent": new_agent},
                        "timestamp": datetime.now().isoformat()
                    }))
                del self.hub.task_manager.active_tasks[task_id]  # Clean up

    async def get_performance_report(self):
        report = {
            "system_status": self.hub.get_system_status(),
            "agent_performance": await self.hub.get_agent_performance(),
            "task_factory_stats": await self.hub.get_task_factory_stats(),
            "latest_viz": await self.hub.get_clustering_visualization()
        }
        if self.ws:
            await self.ws.send(json.dumps({
                "event": "performance_report",
                "data": report,
                "agent": self.agent_name,
                "timestamp": datetime.now().isoformat()
            }))
        return report

async def main():
    agent = GrokAgent()
    await agent.start()
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        logger.info("GrokAgent main task cancelled.")
    finally:
        await agent.stop()

if __name__ == "__main__":
    asyncio.run(main())