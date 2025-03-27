import asyncio
import json
from typing import Any, Dict, Optional, Union, List
from datetime import datetime, timezone

from backend.agents.base_agent import BaseAgent
from backend.core.config import settings, logger, get_agent_heartbeat_key
from backend.core.redis_client import get_key # Use our redis client functions
from backend.models.models import Message, Task, TaskResult, MessageIntent, TaskEvent, TaskOutcome, WebSocketMessage # Import needed models
from backend.factories.factories import MessageFactory # Use factories

class CoordinatorAgent(BaseAgent):
    """
    Coordinator Agent: Monitors agent readiness and overall system health.
    Inherits from BaseAgent for consistency.
    """

    def __init__(self):
        super().__init__(agent_name=settings.COORDINATOR_AGENT_NAME)
        # Get required agents from settings
        self.required_agents: List[str] = settings.REQUIRED_AGENTS_FOR_READY
        self.ready_timeout: int = settings.AGENT_READY_TIMEOUT
        self.check_interval: int = settings.AGENT_CHECK_INTERVAL
        self._monitor_task: Optional[asyncio.Task] = None
        logger.info(f"{self.agent_name} initialized. Monitoring: {self.required_agents}")

    async def start(self):
        """Starts the Coordinator's monitoring loop after BaseAgent setup."""
        await super().start() # Initialize BaseAgent (Redis, heartbeat, etc.)

        # Announce presence after BaseAgent start
        notes = await self.get_notes()
        await self.publish_to_frontend(MessageFactory.create_message(
             task_id="system_init", agent=self.agent_name, content=notes['content'], intent=MessageIntent.SYSTEM
        ))

        # Wait for agents initially (optional, can just start monitoring)
        initial_ready = await self.wait_for_all_agents()
        if not initial_ready:
            logger.warning("Not all required agents ready during initial check, continuing monitoring.")

        # Start the persistent monitoring loop
        self._monitor_task = asyncio.create_task(self._monitor_system_status_loop())
        logger.info(f"{self.agent_name} monitoring loop started.")

    async def stop(self):
        """Stops the monitoring loop and BaseAgent."""
        logger.info(f"Stopping {self.agent_name} monitoring...")
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                logger.info(f"{self.agent_name} monitoring loop cancelled.")
            except Exception as e:
                 logger.error(f"Error during monitor task shutdown for {self.agent_name}: {e}")
            self._monitor_task = None
        await super().stop() # Stop BaseAgent (heartbeat, listener)

    async def _monitor_system_status_loop(self):
        """Periodically checks agent status and publishes updates."""
        while self.is_running:
            try:
                status_data = await self.check_system_status()

                # Store aggregated status in Redis (optional but useful)
                status_key = "system_status"
                await self.redis_client.set(status_key, json.dumps(status_data), ex=30) # Short expiry

                # Publish status update to frontend channel
                ws_message = WebSocketMessage(
                    type="system_status_update", # Specific type for frontend
                    payload=status_data
                )
                await self.publish_to_frontend(ws_message) # BaseAgent method handles serialization
                logger.debug(f"Published system status update: Ready={status_data['system_ready']}")

                await asyncio.sleep(self.check_interval * 2) # Check less frequently than agent heartbeats themselves

            except asyncio.CancelledError:
                logger.info(f"{self.agent_name} monitoring loop stopping.")
                break
            except Exception as e:
                logger.error(f"Error in {self.agent_name} monitoring loop: {e}")
                # Avoid rapid looping on error
                await asyncio.sleep(self.check_interval * 4)

    async def is_agent_ready(self, agent_name: str) -> bool:
        """Check if a specific agent's heartbeat key exists and is 'alive'."""
        if not self.redis_client:
            logger.warning("Redis client not available for readiness check.")
            return False
        try:
            heartbeat_key = get_agent_heartbeat_key(agent_name)
            heartbeat_value = await get_key(self.redis_client, heartbeat_key)
            is_ready = heartbeat_value == "alive"
            logger.trace(f"Readiness check for {agent_name} (Key: {heartbeat_key}): {'Ready' if is_ready else 'Not Ready'} (Value: {heartbeat_value})")
            return is_ready
        except Exception as e:
            logger.error(f"Error checking readiness for {agent_name}: {e}")
            return False

    async def check_system_status(self) -> dict:
        """Checks readiness of all required agents."""
        agent_status = {}
        for agent_name in self.required_agents:
            is_ready = await self.is_agent_ready(agent_name)
            agent_status[agent_name] = "alive" if is_ready else "offline"

        all_ready = all(agent_status.values())
        missing = [agent for agent, ready in agent_status.items() if not ready]

        status_data = {
            "system_ready": all_ready,
            "agent_status": agent_status,
            "missing_agents": missing,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        return status_data

    async def wait_for_all_agents(self) -> bool:
        """Waits until all required agents are ready or timeout occurs."""
        logger.info(f"Waiting up to {self.ready_timeout}s for required agents...")
        start_time = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start_time) < self.ready_timeout:
            status = await self.check_system_status()
            if status["system_ready"]:
                logger.success("All required agents are ready.")
                return True

            logger.info(f"Waiting for agents: {status['missing_agents']}...")
            await asyncio.sleep(self.check_interval)

        logger.warning(f"Timeout reached after {self.ready_timeout}s waiting for agents.")
        status = await self.check_system_status() # Log final status
        logger.warning(f"Final missing agents: {status['missing_agents']}")
        return False

    # --- Handle Incoming Messages (Implement BaseAgent abstract methods) ---

    async def handle_start_task(self, task: Task):
        logger.warning(f"{self.agent_name} received unexpected START_TASK: {task.content[:50]}...")
        await self.publish_error(task.task_id, "Coordinator does not accept general tasks.", task.agent)

    async def handle_modify_task(self, task_update: Union[Task, TaskResult]):
        logger.warning(f"{self.agent_name} received unexpected MODIFY_TASK from {task_update.agent}")

    async def handle_chat_message(self, message: Message):
        logger.info(f"{self.agent_name} received CHAT from {message.agent}: {message.content[:50]}...")
        # Could implement a status query via chat, e.g., if message.content == "status"
        if "status" in message.content.lower():
             status_data = await self.check_system_status()
             reply_content = f"System Status: {'Ready' if status_data['system_ready'] else 'Not Ready'}. Missing: {status_data['missing_agents'] or 'None'}"
             reply = MessageFactory.create_message(
                 task_id=message.task_id,
                 agent=self.agent_name,
                 content=reply_content,
                 target_agent=message.agent
             )
             await self.publish_to_agent(message.agent, reply) # Reply directly
             await self.publish_to_frontend(reply) # Also show in UI
        else:
             # Default reply for other chat
             reply = MessageFactory.create_message(
                 task_id=message.task_id,
                 agent=self.agent_name,
                 content="Coordinator acknowledges chat.",
                 target_agent=message.agent
             )
             await self.publish_to_agent(message.agent, reply)


    async def handle_tool_response(self, tool_result: TaskResult):
         logger.warning(f"{self.agent_name} received unexpected TOOL_RESPONSE from {tool_result.agent}")

    # --- Specific Methods ---
    async def get_notes(self) -> Dict[str, Any]:
         # Overrides placeholder from original code
         return {
              "agent": self.agent_name,
              "content": f"{self.agent_name} online and monitoring system health.",
              "status": "active" # Added status field
         }

    async def process_response(self, response: Any, originating_agent: str):
         # Implementation for BaseAgent abstract method
         logger.debug(f"{self.agent_name} received generic process_response call from {originating_agent}")
         # No specific action needed typically for Coordinator