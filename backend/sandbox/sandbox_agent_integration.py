# sandbox_agent_integration.py (Refactored Bridge)

import asyncio
import json
import aiohttp # Make sure aiohttp is imported
from typing import Dict, Any, Optional
from datetime import datetime

# Assuming these imports are correctly configured relative to this file's location
from backend.agents.base_agent import BaseAgent
from backend.core.config import settings, logger
from backend.core.redis_client import get_redis_pool, publish_message
from backend.models.models import TaskEvent, TaskOutcome, TaskResult
from backend.factories.factories import TaskResultFactory

# Define required settings attributes explicitly for clarity
SANDBOX_API_URL = getattr(settings, "SANDBOX_API_URL", "http://localhost:8001")
TOOL_AGENT_NAME = getattr(settings, "TOOL_AGENT_NAME", "python_sandbox")
FRONTEND_CHANNEL = getattr(settings, "FRONTEND_CHANNEL", "frontend_channel")

class SandboxAgentBridge:
    """
    Refactored Bridge: Listens for Python Sandbox results, formats them as TaskResult,
    and publishes them to the appropriate agent channel and frontend channel.
    """

    def __init__(self, redis_pool=None):
        self.redis_pool = redis_pool
        # Removed self.tools_channel and self.agent_tool_calls

    async def initialize(self):
        """Initialize the bridge."""
        if not self.redis_pool:
            self.redis_pool = await get_redis_pool()

        # Start listening for Python sandbox execution results
        # NOTE: Assumes the sandbox executor publishes messages to "sandbox:execution_results"
        #       containing at least: {"execution_id": ..., "task_id": ..., "requesting_agent": ...}
        asyncio.create_task(self._listen_for_execution_results())
        logger.info("SandboxAgentBridge initialized and listening for execution results")

    async def _listen_for_execution_results(self):
        """Listen for execution result notifications from the Python sandbox."""
        if not self.redis_pool:
            logger.error("Redis not available, cannot listen for execution results")
            return

        channel = "sandbox:execution_results"
        pubsub = None
        while True: # Outer loop for reconnection
            try:
                pubsub = self.redis_pool.pubsub()
                await pubsub.subscribe(channel)
                logger.info(f"SandboxAgentBridge subscribed to Redis channel: {channel}")

                async for message in pubsub.listen():
                    if message["type"] == "message":
                        try:
                            # Decode message data
                            message_data_str = message["data"].decode("utf-8")
                            logger.debug(f"Bridge received raw sandbox result notification: {message_data_str}")
                            result_notification = json.loads(message_data_str)

                            execution_id = result_notification.get("execution_id")
                            task_id = result_notification.get("task_id")
                            # *** CRITICAL ASSUMPTION: 'requesting_agent' is in the notification ***
                            requesting_agent_id = result_notification.get("requesting_agent")

                            if execution_id and task_id and requesting_agent_id:
                                # Process the execution result notification
                                await self._process_execution_result(execution_id, task_id, requesting_agent_id)
                            else:
                                logger.warning(f"Missing data in sandbox result notification: {result_notification}")

                        except json.JSONDecodeError:
                             logger.error(f"Bridge failed to decode JSON message: {message_data_str}")
                        except Exception as e:
                            logger.error(f"Error processing sandbox result notification in bridge: {e}", exc_info=True)

            except asyncio.CancelledError:
                logger.info("SandboxAgentBridge listener task cancelled.")
                if pubsub: await pubsub.unsubscribe(channel)
                break # Exit the loop cleanly
            except Exception as e: # Catch Redis connection errors etc.
                logger.error(f"SandboxAgentBridge Redis listener error: {e}", exc_info=True)
                if pubsub:
                    try: await pubsub.unsubscribe(channel)
                    except: pass # Ignore errors during cleanup
                pubsub = None
                logger.info("Waiting 5 seconds before retrying Redis subscription...")
                await asyncio.sleep(5)

    async def _process_execution_result(self, execution_id: str, task_id: str, agent_id: str):
        """
        Fetch full result, format as TaskResult, and publish to agent/frontend.

        Args:
            execution_id: The execution ID from the sandbox.
            task_id: The original task ID.
            agent_id: The ID of the agent who requested the execution.
        """
        try:
            # 1. Fetch the full result from the sandbox API
            async with aiohttp.ClientSession() as session:
                # Use the SANDBOX_API_URL setting
                async with session.get(f"{SANDBOX_API_URL}/result/{execution_id}", timeout=15.0) as response:
                    if response.status == 202:
                        logger.info(f"Execution {execution_id} still pending, skipping processing for now.")
                        # Optionally, could reschedule a check later, but letting agent retry might be simpler
                        return
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Failed to get execution result for {execution_id} from sandbox API. Status: {response.status}, Detail: {error_text}")
                        # Optionally publish an error back to the agent? Or just log?
                        return # Cannot proceed without full result

                    result_payload = await response.json() # This is the full ExecutionResult model

            # 2. Format the result for the agent framework using TaskResult
            status = result_payload.get("status", "error")
            stdout = result_payload.get("stdout", "")
            stderr = result_payload.get("stderr", "")
            error_message = result_payload.get("error_message")
            output_files = result_payload.get("output_files", {}) # Dict[filename, base64_content]
            execution_time = result_payload.get("execution_time", 0)

            # Create user-friendly content string summarizing the result
            content = f"# Python Code Execution Result\n\n"
            if status == "success":
                content += f"✅ **Success** (Execution ID: {execution_id}, Time: {execution_time:.2f}s)\n\n"
                outcome = TaskOutcome.SUCCESS
            elif status == "timeout":
                content += f"⏱️ **Timeout** (Execution ID: {execution_id})\n\n"
                outcome = TaskOutcome.FAILURE
            else:
                content += f"❌ **Error** (Execution ID: {execution_id}): {error_message or 'Unknown error'}\n\n"
                outcome = TaskOutcome.FAILURE

            if stdout: content += f"## Standard Output\n```\n{stdout}\n```\n\n"
            if stderr: content += f"## Standard Error\n```\n{stderr}\n```\n\n"
            if output_files: content += f"## Output Files\nGenerated {len(output_files)} file(s): {', '.join(f'`{f}`' for f in output_files.keys())}\n"

            # 3. Create the TaskResult object
            task_result = TaskResultFactory.create_task_result(
                task_id=task_id,
                # Use the TOOL_AGENT_NAME setting for the source agent
                agent=TOOL_AGENT_NAME,
                content=content,
                target_agent=agent_id, # Target the original requesting agent
                event=TaskEvent.TOOL_COMPLETE, # Signal tool completion
                outcome=outcome,
                confidence=1.0,
                metadata={ # Include detailed metadata for the agent's patched handler
                    "tool": "python_sandbox",
                    "execution_id": execution_id,
                    "status": status, # Raw status from sandbox
                    "execution_time": execution_time,
                    "stdout": stdout,
                    "stderr": stderr,
                    "output_files": list(output_files.keys()), # Just list names in metadata
                    "error_message": error_message
                }
            )

            # 4. Publish the TaskResult to the specific agent's channel
            agent_channel = f"agent:{agent_id}" # Standard channel format
            if self.redis_pool:
                await publish_message(
                    self.redis_pool,
                    agent_channel,
                    task_result.serialize() # Publish the serialized TaskResult
                )
                logger.info(f"Published sandbox result for {execution_id} to agent channel: {agent_channel}")

                # 5. Also publish to the frontend channel for UI visibility
                await publish_message(
                    self.redis_pool,
                    FRONTEND_CHANNEL,
                    task_result.serialize()
                )
                logger.debug(f"Published sandbox result for {execution_id} to frontend channel: {FRONTEND_CHANNEL}")

            # Removed publishing to the generic 'tools_channel'
            # Removed tracking dictionary logic

        except aiohttp.ClientError as e:
             logger.error(f"HTTP error fetching result for {execution_id}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Error processing execution result {execution_id} in bridge: {e}", exc_info=True)


# Patch for BaseAgent to handle Python sandbox tool results
async def handle_tool_response_sandbox(self, tool_result: TaskResult):
    """
    Enhanced handle_tool_response method for BaseAgent that properly handles
    Python sandbox execution results received as TaskResult objects.
    (No changes needed here from your previous version)
    """
    # ... (Keep your existing patch logic here) ...
    # It correctly checks for tool == "python_sandbox" in metadata
    # It extracts details from TaskResult.metadata and TaskResult.content
    # It calls _process_successful_tool_result or _process_failed_tool_result

# Cache the original method
original_handle_tool_response = BaseAgent.handle_tool_response # Assuming BaseAgent is imported

# Apply the patch
def apply_sandbox_patches():
    """Apply patches to integrate the Python sandbox with the agent framework."""
    from backend.agents.base_agent import BaseAgent # Ensure BaseAgent is imported here
    global original_handle_tool_response
    original_handle_tool_response = BaseAgent.handle_tool_response
    BaseAgent.handle_tool_response = handle_tool_response_sandbox
    logger.info("Applied Python sandbox patches to BaseAgent")

# Function to initialize the bridge (can be called at startup)
async def initialize_sandbox_bridge():
    """Initialize the sandbox bridge."""
    bridge = SandboxAgentBridge()
    await bridge.initialize()
    # No need to return the bridge unless something else needs a direct reference
    logger.info("SandboxAgentBridge initialization complete")

# In your main application startup:
# apply_sandbox_patches()
# asyncio.create_task(initialize_sandbox_bridge())
