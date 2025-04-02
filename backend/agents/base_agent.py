import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import uuid
import redis.asyncio as redis
import aiohttp

from backend.core.config import settings, logger, get_agent_channel, get_agent_heartbeat_key
from backend.core.redis_client import get_redis_pool, publish_message, set_key_with_ttl
from backend.models.models import BaseMessage, Message, Task, TaskResult, MessageIntent, TaskEvent, TaskOutcome
from backend.factories.factories import MessageFactory, TaskResultFactory
from backend.tools.agent_tools import ToolExecutionMixin

class BaseAgent(ToolExecutionMixin):
    """Abstract base class for all agents in the framework."""

    def __init__(self, agent_name: str, redis_client: redis.Redis, llm_model: Optional[str] = None, api_url: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initializes the BaseAgent.

        Args:
            agent_name: The unique name of the agent.
            api_key: Optional API key for external services (e.g., LLMs).
        """
        super().__init__(agent_name=agent_name, redis_client=redis_client)
        
        self.channel_name = f"{agent_name}_channel"
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
        
    async def publish_to_frontend(self, event_type: str, data: Dict[str, Any]):
        """Publishes messages to the central frontend channel via Redis."""
        payload = {
            "type": event_type,
            "agent": self.agent_name,
            "data": data,
        }
        try:
            # Use the helper or direct redis client publish
            await self.redis_publisher.publish(settings.FRONTEND_CHANNEL, payload)
            # Or: await self.redis_client.publish(settings.FRONTEND_CHANNEL, json.dumps(payload))
            logger.debug(f"Published to {settings.FRONTEND_CHANNEL}: {event_type}")
        except Exception as e:
            logger.error(f"Failed to publish to frontend channel: {e}", exc_info=True)

    async def request_tool_execution(self, tool_name: str, tool_input: Dict[str, Any], task_context: Optional[Any] = None) -> Optional[str]:
        """
        Asynchronously requests execution of a tool via the ToolCore API.

        Args:
            tool_name: The name of the tool to execute.
            tool_input: A dictionary containing the input parameters for the tool.
            task_context: Optional data related to the task that initiated this tool call,
                          useful when handling the response.

        Returns:
            The unique execution_id if the request was successful, otherwise None.
        """
        toolcore_url = f"{settings.TOOLCORE_API_URL}/execute/"
        execution_id = str(uuid.uuid4()) # Generate unique ID for tracking

        payload = {
            "tool_name": tool_name,
            "tool_input": tool_input,
            "callback_channel": self.redis_channel, # Tell ToolCore where to send results
            "execution_id": execution_id
        }
        logger.info(f"Agent {self.agent_name} requesting tool '{tool_name}' with execution_id: {execution_id}")
        logger.debug(f"Tool request payload: {payload}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(toolcore_url, json=payload) as response:
                    if response.status == 202: # Accepted for background processing
                        response_data = await response.json()
                        api_execution_id = response_data.get("execution_id")
                        job_id = response_data.get("job_id") # Background task ID

                        if api_execution_id != execution_id:
                             logger.warning(f"API execution_id mismatch: Sent {execution_id}, Received {api_execution_id}. Using received.")
                             # Potentially update execution_id if ToolCore guarantees its uniqueness better
                             # execution_id = api_execution_id # Or handle error

                        logger.info(f"Tool '{tool_name}' execution accepted by ToolCore. Execution ID: {execution_id}, Job ID: {job_id}")
                        # Store context about the pending call, keyed by execution_id
                        self.pending_tool_calls[execution_id] = {
                            "tool_name": tool_name,
                            "tool_input": tool_input,
                            "task_context": task_context, # Store context if needed later
                            "status": "PENDING"
                        }
                        return execution_id
                    else:
                        error_detail = await response.text()
                        logger.error(f"Error requesting tool execution '{tool_name}'. Status: {response.status}. Detail: {error_detail}")
                        return None
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Connection error requesting tool execution '{tool_name}': {e}", exc_info=True)
            return None
        except asyncio.TimeoutError:
            logger.error(f"Timeout requesting tool execution '{tool_name}'", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error requesting tool execution '{tool_name}': {e}", exc_info=True)
            return None
        
    async def handle_redis_message(self, message_data: Dict[str, Any]):
        """ Processes messages received on the agent's Redis channel. """
        message_type = message_data.get("type")
        data = message_data.get("data", {})

        logger.debug(f"[{self.agent_name}] Handling Redis message: type={message_type}")

        if message_type == "TOOL_COMPLETE":
            await self.handle_tool_response(data)
        # Add elif blocks here for other message types agent needs to handle
        # elif message_type == "DIRECT_COMMAND":
        #    await self.handle_direct_command(data)
        else:
            logger.warning(f"[{self.agent_name}] Received unknown message type on agent channel: {message_type}")

    async def handle_tool_response(self, tool_result_data: Dict[str, Any]):
        """ Processes the result of a tool execution received via Redis. """
        execution_id = tool_result_data.get("execution_id")
        status = tool_result_data.get("status")
        result = tool_result_data.get("result")
        error = tool_result_data.get("error")

        if not execution_id:
            logger.warning(f"[{self.agent_name}] Received tool response without execution_id.")
            return

        if execution_id not in self.pending_tool_calls:
            logger.warning(f"[{self.agent_name}] Received tool response for unknown/handled execution_id: {execution_id}")
            return

        pending_call_info = self.pending_tool_calls.pop(execution_id)
        tool_name = pending_call_info["tool_name"]
        task_context = pending_call_info["task_context"]

        logger.info(f"[{self.agent_name}] Received result for tool '{tool_name}' (ID: {execution_id}). Status: {status}")
        await self.publish_to_frontend("agent_status", {"status": "PROCESSING_TOOL_RESULT", "tool_name": tool_name, "execution_id": execution_id, "result_status": status})

        if status == "success":
            logger.debug(f"[{self.agent_name}] Tool '{tool_name}' result: {result}")
            await self._process_successful_tool_result(tool_name, result, execution_id, task_context) # Pass execution_id
        else:
            logger.error(f"[{self.agent_name}] Tool '{tool_name}' (ID: {execution_id}) failed. Error: {error}")
            await self._process_failed_tool_result(tool_name, error, execution_id, task_context) # Pass execution_id

    # Placeholder methods to be implemented by subclasses
    async def _process_successful_tool_result(self, tool_name: str, result: Any, execution_id: str, context: Any):
        raise NotImplementedError(f"{self.__class__.__name__} must implement _process_successful_tool_result")

    async def _process_failed_tool_result(self, tool_name: str, error: str, execution_id: str, context: Any):
        raise NotImplementedError(f"{self.__class__.__name__} must implement _process_failed_tool_result")

        # Placeholder methods to be implemented by subclasses
    async def _process_successful_tool_result(self, tool_name: str, result: Any, context: Any):
        """Agent-specific logic for handling successful tool results."""
        logger.warning(f"_process_successful_tool_result not implemented in {self.__class__.__name__}")
        # Example: self.add_message_to_history({"role": "tool", "tool_name": tool_name, "content": json.dumps(result)})
        # Example: await self.generate_response() # Trigger next LLM call

    async def _process_failed_tool_result(self, tool_name: str, error: str, context: Any):
        """Agent-specific logic for handling failed tool results."""
        logger.warning(f"_process_failed_tool_result not implemented in {self.__class__.__name__}")
        # Example: self.add_message_to_history({"role": "system", "content": f"Tool {tool_name} failed: {error}"})
            # Example: await self.generate_response() # Trigger next LLM call, maybe informing user
                
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
        """ Listens for messages on the agent's dedicated Redis channel. (Final Version) """
        if not self.redis_client:
            logger.error(f"{self.agent_name} cannot listen, Redis client not available.")
            return

        while self.is_running: # Outer loop for handling reconnections
            try:
                self.pubsub = self.redis_client.pubsub()
                await self.pubsub.subscribe(self.channel_name)
                logger.info(f"[{self.agent_name}] Subscribed to channel '{self.channel_name}'.")

                # Inner loop for processing messages
                while self.is_running:
                    # Use get_message with timeout to allow checking self.is_running
                    message = await self.pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if not self.is_running: break # Check immediately after potential block

                    if message and message["type"] == "message":
                        data = message["data"].decode("utf-8")
                        logger.debug(f"[{self.agent_name}] received raw message: {data[:150]}...")
                        try:
                            message_data = json.loads(data)
                            # Route ALL messages from channel to the central handler
                            await self.handle_redis_message(message_data)
                        except json.JSONDecodeError:
                            logger.error(f"[{self.agent_name}] failed to decode JSON: {data[:100]}...")
                        except Exception as e: # Catch errors within message processing
                            logger.error(f"[{self.agent_name}] Error in handle_redis_message: {e}", exc_info=True)
                    # If message is None (timeout), loop continues checking self.is_running

            except redis.exceptions.ConnectionError as e:
                logger.error(f"[{self.agent_name}] Redis connection error in listener: {e}. Retrying in 5s...")
                await asyncio.sleep(5) # Wait before retrying subscription
            except asyncio.CancelledError:
                logger.info(f"[{self.agent_name}] Listener task cancelled.")
                break # Exit outer loop
            except Exception as e:
                logger.error(f"Unexpected error in [{self.agent_name}] listener outer loop: {e}", exc_info=True)
                await asyncio.sleep(5) # Wait before retrying subscription
            finally:
                # Clean up pubsub if it exists before potentially retrying subscription
                if self.pubsub:
                    try:
                        await self.pubsub.unsubscribe(self.channel_name)
                        # Consider closing pubsub if necessary, depends on redis library usage
                        # await self.pubsub.close()
                    except Exception as e:
                        logger.warning(f"[{self.agent_name}] Error unsubscribing/closing pubsub in finally block: {e}")
                    self.pubsub = None
        logger.info(f"[{self.agent_name}] Listener task finished.")


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

    async def publish_to_frontend(self, event_type: str, data: Dict[str, Any]):
        """Publishes messages to the central frontend channel via Redis."""
        payload = {
            "type": event_type,
            "agent": self.agent_name,
            "data": data,
        }
        await self.redis_publisher.publish(settings.FRONTEND_CHANNEL, payload)
        logger.debug(f"[{self.agent_name}] Published to {settings.FRONTEND_CHANNEL}: {event_type}")

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

    async def request_tool_execution(self, tool_name: str, tool_input: Dict[str, Any], task_context: Optional[Any] = None) -> Optional[str]:
        """ Asynchronously requests execution of a tool via the ToolCore API. """
        toolcore_url = f"{settings.TOOLCORE_API_URL}/execute/"
        execution_id = f"{self.agent_name}-{tool_name}-{uuid.uuid4()}" # More descriptive ID

        payload = {
            "tool_name": tool_name,
            "tool_input": tool_input,
            "callback_channel": self.channel_name, # Our agent channel
            "execution_id": execution_id
        }
        logger.info(f"[{self.agent_name}] Requesting tool '{tool_name}' (Exec ID: {execution_id})")
        await self.publish_to_frontend("agent_status", {"status": "AWAITING_TOOL", "tool_name": tool_name, "execution_id": execution_id}) # Publish status

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(toolcore_url, json=payload, timeout=settings.TOOLCORE_API_TIMEOUT) as response: # Add timeout
                    if response.status == 202:
                        response_data = await response.json()
                        api_execution_id = response_data.get("execution_id")
                        job_id = response_data.get("job_id")
                        logger.info(f"[{self.agent_name}] Tool '{tool_name}' accepted by ToolCore. Execution ID: {api_execution_id}, Job ID: {job_id}")
                        self.pending_tool_calls[execution_id] = { # Use OUR execution_id as key
                            "tool_name": tool_name,
                            "tool_input": tool_input,
                            "task_context": task_context,
                            "status": "PENDING"
                        }
                        return execution_id # Return OUR id
                    else:
                        error_detail = await response.text()
                        logger.error(f"[{self.agent_name}] Error requesting tool '{tool_name}'. Status: {response.status}. Detail: {error_detail}")
                        await self.publish_to_frontend("agent_error", {"error": f"Tool request failed: {response.status}", "tool_name": tool_name})
                        return None
        except aiohttp.ClientConnectorError as e:
            logger.error(f"[{self.agent_name}] Connection error requesting tool '{tool_name}': {e}", exc_info=True)
            await self.publish_to_frontend("agent_error", {"error": "ToolCore connection failed", "tool_name": tool_name})
            return None
        except asyncio.TimeoutError:
            logger.error(f"[{self.agent_name}] Timeout requesting tool '{tool_name}'", exc_info=True)
            await self.publish_to_frontend("agent_error", {"error": "ToolCore request timed out", "tool_name": tool_name})
            return None
        except Exception as e:
            logger.error(f"[{self.agent_name}] Unexpected error requesting tool '{tool_name}': {e}", exc_info=True)
            await self.publish_to_frontend("agent_error", {"error": "Unexpected error during tool request", "tool_name": tool_name})
            return None

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