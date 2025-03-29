import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import redis.asyncio as redis
import aiohttp

from backend.core.config import settings, logger, get_agent_channel, get_agent_heartbeat_key
from backend.core.redis_client import get_redis_pool, publish_message, set_key_with_ttl
from backend.models.models import BaseMessage, Message, Task, TaskResult, MessageIntent, TaskEvent, TaskOutcome
from backend.factories.factories import MessageFactory, TaskResultFactory

class BaseAgent(ABC):
    """Abstract base class for all agents in the framework."""

    def __init__(self, agent_name: str, llm_model: Optional[str] = None, api_url: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initializes the BaseAgent.

        Args:
            agent_name: The unique name of the agent.
            api_key: Optional API key for external services (e.g., LLMs).
        """
        self.agent_name = agent_name
        self.model = llm_model
        self.api_url = api_url
        self.api_key = api_key
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        self.is_running = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._listener_task: Optional[asyncio.Task] = None
        self.channel_name = get_agent_channel(self.agent_name)
        self.heartbeat_key = get_agent_heartbeat_key(self.agent_name)
        self.http_session: Optional[aiohttp.ClientSession] = None
        self.tools_api_url = settings.TOOLS_API_URL

        logger.info(f"Initializing {self.agent_name}...")

    async def initialize(self):
        """Asynchronously initialize resources like Redis connection and HTTP session."""
        if not self.redis_client:
            self.redis_client = await get_redis_pool()
        if not self.http_session:
            self.http_session = aiohttp.ClientSession()
        logger.info(f"{self.agent_name} initialized successfully.")

    async def start(self):
        """Starts the agent's main loop and heartbeat."""
        if self.is_running:
            logger.warning(f"{self.agent_name} is already running.")
            return

        await self.initialize() # Ensure resources are ready

        self.is_running = True
        logger.info(f"{self.agent_name} starting...")

        # Start heartbeat
        self._heartbeat_task = asyncio.create_task(self._send_heartbeat_loop())

        # Start listening to Redis channel
        self._listener_task = asyncio.create_task(self._listen_for_messages())

        logger.success(f"{self.agent_name} started successfully. Listening on channel '{self.channel_name}'.")

        # Optionally send a startup message
        await self.publish_system_message("Agent started and ready.")

    async def stop(self):
        """Stops the agent's loops and cleans up resources."""
        if not self.is_running:
            logger.warning(f"{self.agent_name} is not running.")
            return

        logger.info(f"{self.agent_name} stopping...")
        self.is_running = False

        # Stop listener task
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                logger.info(f"{self.agent_name} listener task cancelled.")
            except Exception as e:
                 logger.error(f"Error during listener task shutdown for {self.agent_name}: {e}")
            self._listener_task = None

        # Stop heartbeat task
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                logger.info(f"{self.agent_name} heartbeat task cancelled.")
            except Exception as e:
                 logger.error(f"Error during heartbeat task shutdown for {self.agent_name}: {e}")
            self._heartbeat_task = None

        # Clean up pubsub
        if self.pubsub:
            try:
                 # Unsubscribe might be needed depending on redis-py version and usage
                 await self.pubsub.unsubscribe(self.channel_name)
                 await self.pubsub.close()
                 logger.info(f"{self.agent_name} unsubscribed and closed pubsub.")
            except Exception as e:
                logger.error(f"Error closing pubsub for {self.agent_name}: {e}")
            self.pubsub = None

        # Close HTTP session
        if self.http_session:
            await self.http_session.close()
            self.http_session = None
            logger.info(f"{self.agent_name} HTTP session closed.")

        # Note: Redis pool is managed globally, not closed here.

        logger.success(f"{self.agent_name} stopped successfully.")
         # Optionally send a shutdown message
        # await self.publish_system_message("Agent stopped.") # Might fail if redis conn closed


    async def _send_heartbeat_loop(self):
        """Periodically sends a heartbeat signal to Redis."""
        logger.info(f"{self.agent_name} starting heartbeat loop (Interval: {settings.HEARTBEAT_INTERVAL}s, TTL: {settings.HEARTBEAT_TTL}s).")
        while self.is_running:
            try:
                if self.redis_client:
                    await set_key_with_ttl(
                        self.redis_client,
                        self.heartbeat_key,
                        "alive",
                        settings.HEARTBEAT_TTL
                    )
                    logger.trace(f"{self.agent_name} sent heartbeat.")
                else:
                    logger.warning(f"{self.agent_name} cannot send heartbeat, Redis client not available.")
                await asyncio.sleep(settings.HEARTBEAT_INTERVAL)
            except asyncio.CancelledError:
                logger.info(f"{self.agent_name} heartbeat loop cancelled.")
                break
            except Exception as e:
                logger.error(f"Error in {self.agent_name} heartbeat loop: {e}")
                # Avoid busy-looping on persistent errors
                await asyncio.sleep(settings.HEARTBEAT_INTERVAL * 2)

    async def _listen_for_messages(self):
        """Listens for messages on the agent's dedicated Redis channel."""
        if not self.redis_client:
            logger.error(f"{self.agent_name} cannot listen, Redis client not available.")
            return

        self.pubsub = self.redis_client.pubsub()
        await self.pubsub.subscribe(self.channel_name)
        logger.info(f"{self.agent_name} subscribed to channel '{self.channel_name}'.")

        while self.is_running:
            try:
                # Use listen() which handles reconnections better potentially
                async for message in self.pubsub.listen():
                     if message is None or not self.is_running:
                         continue # Skip null messages or if stopping

                     if message["type"] == "subscribe":
                         logger.info(f"{self.agent_name} successfully subscribed: {message}")
                         continue
                     if message["type"] == "unsubscribe":
                         logger.info(f"{self.agent_name} successfully unsubscribed: {message}")
                         break # Stop listening if unsubscribed

                     if message["type"] == "message":
                         logger.debug(f"{self.agent_name} received raw message on '{message['channel']}': {message['data']}")
                         # Process the message in a separate task to avoid blocking listener
                         asyncio.create_task(self.handle_incoming_message(message["data"]))
                     else:
                         logger.warning(f"{self.agent_name} received unexpected pubsub message type: {message['type']}")

            except redis.exceptions.ConnectionError as e:
                logger.error(f"{self.agent_name} Redis connection error in listener: {e}. Attempting to reconnect...")
                await asyncio.sleep(5) # Wait before potentially retrying (handled by redis-py?)
                # Re-subscribe might be necessary depending on redis-py auto-reconnect behavior
                if self.is_running and self.pubsub:
                    try:
                        await self.pubsub.subscribe(self.channel_name)
                        logger.info(f"{self.agent_name} re-subscribed after connection error.")
                    except Exception as sub_e:
                        logger.error(f"{self.agent_name} failed to re-subscribe: {sub_e}")
                        # Consider stopping the agent if re-subscription fails repeatedly
                        await self.stop()
                        break
            except asyncio.CancelledError:
                 logger.info(f"{self.agent_name} listener loop cancelled.")
                 break
            except Exception as e:
                logger.error(f"Unexpected error in {self.agent_name} listener loop: {e}")
                # Avoid busy-looping
                await asyncio.sleep(5)


    async def handle_incoming_message(self, raw_data: str):
        """Parses and dispatches incoming messages based on intent."""
        try:
            # First, try parsing as a generic BaseMessage to get the intent
            # This is a bit hacky, ideally structure would guarantee parsability
            # or we'd have a wrapper structure indicating the type.
            try:
                 temp_data = json.loads(raw_data)
                 intent_str = temp_data.get("intent")
                 message_model = BaseMessage # Default
                 if intent_str == MessageIntent.START_TASK.value:
                     message_model = Task
                 elif intent_str == MessageIntent.MODIFY_TASK.value:
                     # Could be TaskResult or Task, try TaskResult first
                     try:
                         parsed_message = TaskResult.deserialize(raw_data)
                     except Exception:
                         parsed_message = Task.deserialize(raw_data) # Fallback to Task
                 elif intent_str == MessageIntent.CHAT.value:
                     message_model = Message
                 else: # Handle other intents or fallback
                     message_model = BaseMessage
                     # Try parsing with the determined model (or BaseMessage as fallback)
                     parsed_message = message_model.model_validate_json(raw_data)

            except json.JSONDecodeError:
                 logger.error(f"{self.agent_name} received invalid JSON: {raw_data[:100]}...")
                 return
            except Exception as e: # Catch Pydantic validation errors etc.
                 logger.error(f"{self.agent_name} failed to parse message: {e}. Raw data: {raw_data[:100]}...")
                 # Maybe send an error message back?
                 return

            logger.info(f"{self.agent_name} received {type(parsed_message).__name__} (Intent: {parsed_message.intent.value}) from {parsed_message.agent}")

            # Intent-based dispatching
            if parsed_message.intent == MessageIntent.START_TASK and isinstance(parsed_message, Task):
                await self.handle_start_task(parsed_message)
            elif parsed_message.intent == MessageIntent.MODIFY_TASK and (isinstance(parsed_message, Task) or isinstance(parsed_message, TaskResult)):
                 # Can be feedback (Task) or a result (TaskResult)
                 await self.handle_modify_task(parsed_message)
            elif parsed_message.intent == MessageIntent.CHAT and isinstance(parsed_message, Message):
                await self.handle_chat_message(parsed_message)
            elif parsed_message.intent == MessageIntent.CHECK_STATUS:
                 await self.handle_check_status(parsed_message)
            elif parsed_message.intent == MessageIntent.TOOL_RESPONSE and isinstance(parsed_message, TaskResult):
                 await self.handle_tool_response(parsed_message)
            elif parsed_message.intent == MessageIntent.SYSTEM and isinstance(parsed_message, Message):
                await self.handle_system_message(parsed_message)
            elif parsed_message.intent == MessageIntent.ORCHESTRATION and isinstance(parsed_message, Message):
                await self.handle_orchestration_message(parsed_message)
            else:
                logger.warning(f"{self.agent_name} received message with unhandled intent or type mismatch: {parsed_message.intent.value} / {type(parsed_message).__name__}")
                await self.handle_unknown_message(parsed_message)

        except Exception as e:
            logger.exception(f"Error handling incoming message in {self.agent_name}: {e}")
            # Optionally, report error back to system or originating agent
            try:
                task_id = json.loads(raw_data).get("task_id", "unknown")
                await self.publish_error(task_id, f"Error processing message: {e}")
            except Exception as report_e:
                 logger.error(f"Failed to report error for {self.agent_name}: {report_e}")


    # --- Abstract Methods for Intent Handling ---
    # Subclasses should override these with specific logic

    @abstractmethod
    async def handle_start_task(self, task: Task):
        """Handle a new task assignment."""
        logger.warning(f"{self.agent_name} received START_TASK but handle_start_task is not implemented.")
        # Example: Acknowledge receipt
        await self.publish_update(task.task_id, TaskEvent.INFO, "Task received, planning...", task.agent)

    @abstractmethod
    async def handle_modify_task(self, task_update: Task | TaskResult):
        """Handle updates, feedback, or results for an ongoing task."""
        logger.warning(f"{self.agent_name} received MODIFY_TASK but handle_modify_task is not implemented.")

    @abstractmethod
    async def handle_chat_message(self, message: Message):
        """Handle a general chat message."""
        logger.warning(f"{self.agent_name} received CHAT but handle_chat_message is not implemented.")

    async def handle_check_status(self, message: BaseMessage):
        """Handle a request for task status."""
        logger.warning(f"{self.agent_name} received CHECK_STATUS but handle_check_status is not implemented.")
        # Example: Respond with a generic pending status
        await self.publish_update(message.task_id, TaskEvent.INFO, "Status check received, task is pending/in-progress.", message.agent)

    async def handle_tool_response(self, tool_result: TaskResult):
        """Handle the result returned from ToolCore."""
        logger.warning(f"{self.agent_name} received TOOL_RESPONSE but handle_tool_response is not implemented.")

    async def handle_system_message(self, message: Message):
        """Handle system-level messages."""
        logger.info(f"{self.agent_name} received SYSTEM message: {message.content}")
        # Default: Just log it

    async def handle_orchestration_message(self, message: Message):
        """Handle messages related to agent coordination (e.g., from Grok)."""
        logger.info(f"{self.agent_name} received ORCHESTRATION message: {message.content}")
        # Default: Just log it

    async def handle_unknown_message(self, message: BaseMessage):
        """Handle messages with unrecognized intents or formats."""
        logger.warning(f"{self.agent_name} received unknown message type/intent: {message.intent.value}")


    # --- Publishing Methods ---

    async def _publish(self, channel: str, message_obj: BaseMessage):
        """Serializes and publishes a message object to a Redis channel."""
        if not self.redis_client:
            logger.error(f"{self.agent_name} cannot publish, Redis client not available.")
            return
        try:
            message_json = message_obj.serialize()
            await publish_message(self.redis_client, channel, message_json)
            logger.debug(f"{self.agent_name} published to {channel}: {message_obj.intent.value} (TaskID: {message_obj.task_id})")
        except Exception as e:
            logger.error(f"Error serializing/publishing message from {self.agent_name} to {channel}: {e}")

    async def publish_to_agent(self, target_agent_name: str, message_obj: BaseMessage):
        """Sends a message directly to another agent's channel."""
        target_channel = get_agent_channel(target_agent_name)
        await self._publish(target_channel, message_obj)

    async def publish_to_frontend(self, message_obj: BaseMessage):
        """Sends a message to the frontend via the WebSocket server's channel."""
        await self._publish(settings.FRONTEND_CHANNEL, message_obj)

    async def publish_system_message(self, content: str, task_id: str = "system"):
        """Publishes a system message, typically for logging or frontend display."""
        msg = MessageFactory.create_message(
            task_id=task_id,
            agent=self.agent_name,
            content=content,
            intent=MessageIntent.SYSTEM
        )
        await self.publish_to_frontend(msg) # Also send to frontend
        # Optionally publish to a dedicated system channel if needed
        # await self._publish(settings.SYSTEM_CHANNEL, msg)

    async def publish_update(self, task_id: str, event: TaskEvent, content: str, target_agent: str, confidence: Optional[float] = None, outcome: TaskOutcome = TaskOutcome.IN_PROGRESS):
        """Publishes a TaskResult representing an update."""
        result = TaskResultFactory.create_task_result(
            task_id=task_id,
            agent=self.agent_name,
            content=content,
            target_agent=target_agent, # Often the orchestrator or user
            event=event,
            outcome=outcome,
            confidence=confidence if confidence is not None else 0.9 # Default confidence
        )
        # Send update to target agent AND frontend
        await self.publish_to_agent(target_agent, result)
        await self.publish_to_frontend(result) # Keep frontend informed

    async def publish_completion(self, task_id: str, final_content: str, target_agent: str, confidence: float = 1.0, contributing_agents: Optional[List[str]] = None):
         """Publishes a final successful TaskResult."""
         result = TaskResultFactory.create_task_result(
             task_id=task_id,
             agent=self.agent_name,
             content=final_content,
             target_agent=target_agent,
             event=TaskEvent.COMPLETE,
             outcome=TaskOutcome.SUCCESS,
             confidence=confidence,
             contributing_agents=contributing_agents or [self.agent_name]
         )
         await self.publish_to_agent(target_agent, result)
         await self.publish_to_frontend(result)

    async def publish_error(self, task_id: str, error_content: str, target_agent: Optional[str] = None):
         """Publishes a TaskResult indicating failure."""
         # Determine target: specific agent, orchestrator (grok), or just frontend/system
         target = target_agent or settings.GROK_AGENT_NAME # Default to informing Grok

         result = TaskResultFactory.create_task_result(
             task_id=task_id,
             agent=self.agent_name,
             content=f"Error: {error_content}",
             target_agent=target,
             event=TaskEvent.FAIL,
             outcome=TaskOutcome.FAILURE,
             confidence=0.0 # No confidence in failure case
         )
         if target != self.agent_name: # Avoid self-messaging if Grok is the target
              await self.publish_to_agent(target, result)
         await self.publish_to_frontend(result) # Always inform frontend of errors

    # --- ToolCore Interaction ---

    async def request_tool_execution(self, task_id: str, tool_name: str, parameters: Dict[str, Any], orchestrator: str = settings.GROK_AGENT_NAME):
        """Sends a request to ToolCore API to execute a tool."""
        if not self.http_session:
             logger.error(f"{self.agent_name} cannot request tool execution, HTTP session not initialized.")
             await self.publish_error(task_id, "Tool execution failed: Agent HTTP client not ready.", orchestrator)
             return

        url = f"{self.tools_api_url}/execute/"
        payload = {
            "tool_name": tool_name,
            "parameters": parameters,
            "requesting_agent": self.agent_name, # Let ToolCore know who asked
            "task_id": task_id # Link execution back to the task
        }
        logger.info(f"{self.agent_name} requesting tool '{tool_name}' execution for task {task_id} with params: {parameters}")

        # Inform orchestrator/frontend that we are waiting
        await self.publish_update(task_id, TaskEvent.AWAITING_TOOL, f"Requesting execution of tool: {tool_name}", orchestrator)

        try:
            async with self.http_session.post(url, json=payload) as response:
                response_data = await response.json()
                if response.status == 200:
                    logger.success(f"{self.agent_name} received successful preliminary response from ToolCore for '{tool_name}': {response_data}")
                    # IMPORTANT: ToolCore execution might be async. This response usually just acknowledges the request.
                    # The actual result will likely come back via Redis Pub/Sub from the ToolCore *or* the ToolCore API
                    # might return the result directly if execution is fast.
                    # Assuming ToolCore sends result back via Redis (handled in handle_tool_response)
                    # If API returns result directly:
                    if response_data.get("status") == "completed":
                        result_content = response_data.get("result", "Tool executed successfully, but no result content provided.")
                        tool_result = TaskResultFactory.create_task_result(
                            task_id=task_id,
                            agent=settings.TOOLS_AGENT_NAME, # Result comes *from* ToolCore
                            content=str(result_content), # Ensure content is string
                            target_agent=self.agent_name, # Send result back to this agent
                            event=TaskEvent.TOOL_COMPLETE,
                            outcome=TaskOutcome.SUCCESS,
                            confidence=1.0
                        )
                        await self.handle_tool_response(tool_result) # Process the result immediately
                    elif response_data.get("status") == "failed":
                         await self.publish_error(task_id, f"Tool '{tool_name}' execution failed: {response_data.get('error', 'Unknown error')}", orchestrator)
                    else: # Pending/Acknowledged
                         logger.info(f"ToolCore acknowledged request for '{tool_name}', waiting for async result.")

                else:
                    error_detail = response_data.get("detail", await response.text())
                    logger.error(f"{self.agent_name} failed to execute tool '{tool_name}'. Status: {response.status}, Detail: {error_detail}")
                    await self.publish_error(task_id, f"Tool execution request failed (Status {response.status}): {error_detail}", orchestrator)

        except aiohttp.ClientConnectionError as e:
            logger.error(f"{self.agent_name} connection error requesting tool '{tool_name}': {e}")
            await self.publish_error(task_id, f"Tool execution failed: Cannot connect to ToolCore API ({e})", orchestrator)
        except Exception as e:
            logger.exception(f"{self.agent_name} unexpected error requesting tool '{tool_name}': {e}")
            await self.publish_error(task_id, f"Tool execution failed: Unexpected error ({e})", orchestrator)

    # --- Placeholder for LLM Interaction ---
    async def _call_llm(self, prompt: str, **kwargs) -> str:
        """Placeholder method for interacting with an LLM."""
        logger.warning(f"{self.agent_name}._call_llm is a placeholder. Simulating LLM response.")
        await asyncio.sleep(1) # Simulate network latency/processing time
        return f"Placeholder response from {self.agent_name} for prompt: '{prompt[:50]}...'"


    # --- Abstract method from spec example ---
    @abstractmethod
    async def get_notes(self) -> Dict[str, Any]:
         """ Example method returning agent status or notes. """
         pass

    # --- Abstract method from spec example ---
    @abstractmethod
    async def process_response(self, response: Any, originating_agent: str):
         """ Example method for processing responses from other agents. """
         pass