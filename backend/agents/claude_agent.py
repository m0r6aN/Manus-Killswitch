import asyncio
import json
import os
from typing import Any, Dict, List, Optional, Union, AsyncGenerator, Callable

import httpx
from pydantic import BaseModel, Field

from backend.agents.base_agent import BaseAgent
from backend.core.config import settings, logger
from backend.models.models import Task, Message, TaskResult, TaskEvent, TaskOutcome
from backend.factories.factories import MessageFactory, TaskResultFactory

class AnthropicMessage(BaseModel):
    role: str
    content: str

class AnthropicResponse(BaseModel):
    id: str
    model: str
    content: List[Dict[str, Any]]
    usage: Dict[str, int]

class AgentPromptTemplate(BaseModel):
    """Customizable prompt templates for different agent roles."""
    
    critique: str = Field(
        default="""
        You are Claude, an AI assistant serving as a critical evaluator and arbitrator.
        Your task is to critique the proposal or idea presented to you.
        
        Be thorough but fair in your assessment. Consider:
        - Logical consistency and coherence
        - Evidence or reasoning provided
        - Potential weaknesses or vulnerabilities
        - Alternative perspectives or approaches
        - Practical implications and feasibility
        
        Format your critique clearly with specific points of feedback.
        Begin your response with "[Critique by Claude]" and end with a confidence score (0.0-1.0)
        indicating your certainty in your assessment.
        """
    )
    
    conclusion: str = Field(
        default="""
        You are Claude, an AI assistant serving as a final arbitrator and synthesizer.
        Your task is to provide a final conclusion based on all the information, proposals, 
        and critiques in the discussion so far.
        
        Your conclusion should:
        - Synthesize the key insights from the discussion
        - Present a clear, actionable final recommendation
        - Address major concerns or critiques that were raised
        - Provide justification for your decision
        
        Format your conclusion professionally and clearly.
        Begin your response with "[Conclusion by Claude]" and end with a confidence score (0.0-1.0)
        indicating your certainty in this conclusion.
        """
    )
    
    chat: str = Field(
        default="""
        You are Claude, an AI assistant in a multi-agent system. You're responding to a direct message.
        Be helpful, concise, and friendly. You are communicating with {agent_name}.
        """
    )

class ClaudeAgent(BaseAgent):
    """
    Claude Agent: Arbitration & Reconciliation.
    Evaluates responses, facilitates debate, produces synthesized outputs.
    Uses the Anthropic API to generate intelligent responses with streaming support.
    """

    def __init__(self):
        agent_name = os.environ.get("AGENT_NAME")
        llm_model = os.environ.get("LLM_MODEL")
        api_key = os.environ.get("AGENT_API_KEY")
        api_url = os.environ.get("API_URL")
        api_version = os.environ.get("API_VERSION")
        
        super().__init__(agent_name=agent_name, llm_model=llm_model, api_url=api_url, api_key=api_key)
        self.api_base = api_url
        self.api_version = api_version       
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": self.api_version,
                "content-type": "application/json"
            }
        )
        self.task_histories = {}  # Store chat histories per task
        
        # Load custom prompts if available
        self.prompts = self._load_prompt_templates()
        
        # Stream configuration
        self.stream_enabled = getattr(settings, "CLAUDE_STREAM_ENABLED", True)
        self.stream_chunk_size = getattr(settings, "CLAUDE_STREAM_CHUNK_SIZE", 100)  # characters
        
        # Store active streams for cleanup
        self.active_streams = {}

    def _load_prompt_templates(self) -> AgentPromptTemplate:
        """Load custom prompt templates from settings or environment variables."""
        try:
            custom_prompts = {}
            
            # Check for settings-based configuration
            if hasattr(settings, "CLAUDE_PROMPT_TEMPLATES"):
                custom_prompts = settings.CLAUDE_PROMPT_TEMPLATES
            
            # Check for environment variable overrides
            for prompt_type in ["critique", "conclusion", "chat"]:
                env_var = f"CLAUDE_PROMPT_{prompt_type.upper()}"
                if env_var in os.environ:
                    custom_prompts[prompt_type] = os.environ[env_var]
            
            # Create combined prompt template
            return AgentPromptTemplate(**custom_prompts)
            
        except Exception as e:
            logger.warning(f"Error loading custom prompts: {e}. Using defaults.")
            return AgentPromptTemplate()
    
    async def __del__(self):
        await self.stop()

    async def handle_start_task(self, task: Task):
        """Claude typically doesn't initiate tasks, but responds to requests for critique/arbitration."""
        logger.info(f"{self.agent_name} received task (Intent: {task.intent.value}): {task.content[:50]}...")

        # Initialize task history
        self.task_histories[task.task_id] = []

        if task.event == TaskEvent.CRITIQUE:
            await self.perform_critique(task)
        elif task.event == TaskEvent.CONCLUDE:
            await self.perform_conclusion(task)
        else:
            logger.warning(f"{self.agent_name} received unexpected task event: {task.event.value}. Acknowledging.")
            await self.publish_update(task.task_id, TaskEvent.INFO, "Task acknowledged, awaiting specific action (critique/conclude).", task.agent)

    async def handle_modify_task(self, task_update: Union[Task, TaskResult]):
        """Handles requests for critique or conclusion based on updates."""
        logger.info(f"{self.agent_name} received update from {task_update.agent} (Event: {task_update.event.value}): {task_update.content[:50]}...")

        # Ensure we have a history for this task
        if task_update.task_id not in self.task_histories:
            self.task_histories[task_update.task_id] = []
        
        # Add this update to the task history
        self.task_histories[task_update.task_id].append({
            "role": "user" if task_update.agent != self.agent_name else "assistant",
            "content": f"{task_update.agent}: {task_update.content}",
            "event": task_update.event.value if hasattr(task_update, "event") else None
        })

        # Check if this update is a request for Claude's action
        if task_update.target_agent == self.agent_name:
            if task_update.event == TaskEvent.CRITIQUE:
                await self.perform_critique(task_update)
            elif task_update.event == TaskEvent.CONCLUDE:
                await self.perform_conclusion(task_update)
            else:
                logger.warning(f"{self.agent_name} received update with unhandled event {task_update.event.value} directed at it.")
                await self.publish_update(task_update.task_id, TaskEvent.INFO, "Update acknowledged, but action unclear.", task_update.agent)
        else:
            logger.debug(f"{self.agent_name} ignored update not targeted at it.")

    async def _stream_llm(self, prompt: str, ws, task_id: str, system_message: str = None):
        """
        Streams a response from the Anthropic API and pushes deltas to the frontend WebSocket.
        Follows the Manus Killswitch Standard for agent streaming.
        """
        agent_name = self.agent_name
        try:
            # Prepare messages for Anthropic API
            messages = [{"role": "user", "content": prompt}]
            
            # Set up API payload
            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 1000,
                "stream": True
            }
            
            # Add system message if provided
            if system_message:
                payload["system"] = system_message
                
            logger.debug(f"Calling Anthropic API with streaming for task {task_id}")
            
            # Buffer for accumulating the full response
            full_text = ""
            
            # Make streaming request to Anthropic API
            async with self.http_client.stream("POST", self.api_base, json=payload) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    logger.error(f"Anthropic API streaming error: {response.status_code} - {error_text}")
                    await ws.send(json.dumps({
                        "event": "error",
                        "data": {
                            "agent": agent_name,
                            "task_id": task_id,
                            "message": f"API Error: {response.status_code}"
                        }
                    }))
                    return "[Streaming Error]"
                    
                # Process the event stream
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])  # Remove "data: " prefix
                            
                            # Check if this is a content delta
                            if data.get("type") == "content_block_delta":
                                delta = data.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    text = delta.get("text", "")
                                    full_text += text
                                    
                                    # If we have content, send it to the WebSocket
                                    if text.strip():
                                        await ws.send(json.dumps({
                                            "event": "stream_update",
                                            "data": {
                                                "agent": agent_name,
                                                "task_id": task_id,
                                                "delta": text
                                            }
                                        }))
                            
                            # Check if this is a content stop
                            elif data.get("type") == "message_stop":
                                # Send a final_result event
                                await ws.send(json.dumps({
                                    "event": "final_result",
                                    "data": {
                                        "agent": agent_name,
                                        "task_id": task_id,
                                        "text": full_text
                                    }
                                }))
                                break
                                
                        except json.JSONDecodeError as e:
                            logger.warning(f"Error parsing streaming response: {e}")
                            continue
                    
            return full_text
            
        except Exception as e:
            logger.error(f"{agent_name} streaming failed: {str(e)}")
            # Try to notify frontend of error
            try:
                await ws.send(json.dumps({
                    "event": "error",
                    "data": {
                        "agent": agent_name,
                        "task_id": task_id,
                        "message": f"Streaming Error: {str(e)}"
                    }
                }))
            except:
                pass
            return "[Streaming Error]"

    async def call_anthropic_api(
        self, 
        messages: List[Dict[str, str]], 
        system_prompt: str = None, 
        max_tokens: int = 1000,
        stream: bool = False,
        stream_handler: Callable[[str, str], None] = None
    ) -> Optional[Union[str, AsyncGenerator[str, None]]]:
        """
        Call the Anthropic API with the given messages and system prompt.
        
        Args:
            messages: List of message objects with role and content keys
            system_prompt: Optional system prompt to guide Claude's behavior
            max_tokens: Maximum number of tokens to generate
            stream: Whether to stream the response
            stream_handler: Callback for handling stream chunks
            
        Returns:
            If stream=False: Generated text response or None if the call failed
            If stream=True: AsyncGenerator yielding response chunks
        """
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "stream": stream
            }
            
            if system_prompt:
                payload["system"] = system_prompt
                
            logger.debug(f"Calling Anthropic API with payload: {json.dumps(payload, indent=2)}")
            
            if not stream:
                # Standard synchronous request
                response = await self.http_client.post(
                    self.api_base,
                    json=payload
                )
                
                if response.status_code != 200:
                    logger.error(f"Anthropic API error: {response.status_code} - {response.text}")
                    return None
                    
                data = response.json()
                logger.debug(f"Anthropic API response: {json.dumps(data, indent=2)}")
                
                # Extract the content from the first message in the response
                if data and "content" in data and len(data["content"]) > 0:
                    for block in data["content"]:
                        if block["type"] == "text":
                            return block["text"]
                
                return None
            else:
                # Streaming request - returns an AsyncGenerator
                async def stream_response():
                    # Track task_id for the request if available in the first message
                    task_id = None
                    for msg in messages:
                        if "Task " in msg.get("content", ""):
                            # Try to extract task_id from content
                            content = msg["content"]
                            try:
                                task_id = content.split("Task ")[1].split(" ")[0]
                            except IndexError:
                                pass
                            break
                    
                    # Store this stream in active streams
                    if task_id:
                        self.active_streams[task_id] = True
                    
                    # Buffer for accumulating chunks
                    buffer = ""
                    
                    try:
                        async with self.http_client.stream("POST", self.api_base, json=payload) as response:
                            if response.status_code != 200:
                                error_text = await response.aread()
                                logger.error(f"Anthropic API streaming error: {response.status_code} - {error_text}")
                                yield None
                                return
                                
                            logger.debug(f"Stream response started for task: {task_id}")
                            
                            # Process the event stream
                            async for line in response.aiter_lines():
                                if line.startswith("data: "):
                                    try:
                                        data = json.loads(line[6:])  # Remove "data: " prefix
                                        
                                        # Check if this is a content delta
                                        if data.get("type") == "content_block_delta":
                                            delta = data.get("delta", {})
                                            if delta.get("type") == "text_delta":
                                                text = delta.get("text", "")
                                                buffer += text
                                                
                                                # If we have enough content or it's the end, send it
                                                if len(buffer) >= self.stream_chunk_size or data.get("usage"):
                                                    if stream_handler and task_id:
                                                        await stream_handler(task_id, buffer)
                                                    
                                                    chunk = buffer
                                                    buffer = ""
                                                    yield chunk
                                        
                                        # Check if this is a content stop
                                        elif data.get("type") == "message_stop":
                                            # Send any remaining buffer content
                                            if buffer:
                                                if stream_handler and task_id:
                                                    await stream_handler(task_id, buffer)
                                                yield buffer
                                            break
                                            
                                    except json.JSONDecodeError as e:
                                        logger.warning(f"Error parsing streaming response: {e}")
                                        continue
                                        
                    except Exception as e:
                        logger.error(f"Error in stream processing: {e}")
                        yield None
                    
                    finally:
                        # Clean up this stream
                        if task_id and task_id in self.active_streams:
                            del self.active_streams[task_id]
                            logger.debug(f"Stream completed and cleaned up for task: {task_id}")
                
                return stream_response()
                
        except Exception as e:
            logger.error(f"Error calling Anthropic API: {str(e)}")
            return None

    async def stream_handler(self, task_id: str, content_chunk: str):
        """Handler for streaming content chunks to the frontend."""
        # Create a streaming update message
        stream_msg = MessageFactory.create_message(
            task_id=task_id,
            agent=self.agent_name,
            content=content_chunk,
            is_stream_chunk=True  # Flag to indicate this is a stream chunk
        )
        
        # Send to frontend only - not to other agents
        await self.publish_to_frontend(stream_msg)

    async def perform_critique(self, task: Union[Task, TaskResult]):
        """Evaluate the input and provide critique using Claude API."""
        logger.info(f"{self.agent_name} performing CRITIQUE for task {task.task_id}...")
        await self.publish_update(task.task_id, TaskEvent.INFO, "Critiquing proposal...", settings.GROK_AGENT_NAME)

        # Prepare the prompt based on conversation history
        history = self.task_histories.get(task.task_id, [])
        
        # Build a context-rich prompt for critique
        history_text = ""
        for entry in history[-5:]:  # Use the most recent 5 entries to avoid token limits
            if entry["role"] == "user":
                history_text += f"\n[{entry.get('event', 'MESSAGE')}] {entry['content']}\n"
            else:
                history_text += f"\n[RESPONSE] {entry['content']}\n"
                
        # Create the final prompt with history
        prompt = f"""
Task ID: {task.task_id}
Requesting Agent: {task.agent}
Task Content: {task.content}

Previous Context:
{history_text}

Your task is to provide a critical evaluation of the proposal above.
"""
        
        # Get system prompt template for critique
        system_message = self.prompts.critique
        
        # Initialize variables for response tracking
        critique_content = ""
        confidence = 0.75  # Default confidence
        
        # Get the WebSocket instance from the base agent (ensure BaseAgent provides this)
        ws = getattr(self, "websocket", None)
        
        if self.stream_enabled and ws:
            # Use the standardized streaming method that follows the Manus Killswitch Standard
            logger.info(f"Using standardized streaming response for critique on task {task.task_id}")
            
            critique_content = await self._stream_llm(prompt, ws, task.task_id, system_message)
        else:
            # Fall back to standard API response if streaming isn't available
            messages = [{"role": "user", "content": prompt}]
            critique_content = await self.call_anthropic_api(messages, system_message)
            
            if not critique_content:
                # Fallback if API call fails
                critique_content = f"[Critique by {self.agent_name}] I was unable to evaluate this proposal due to technical difficulties. Please try again."
        
        # Try to extract confidence score if present
        try:
            if "confidence: " in critique_content.lower():
                parts = critique_content.lower().split("confidence: ")
                confidence_str = parts[1].strip()
                confidence = float(confidence_str.split()[0])
                confidence = max(0.0, min(1.0, confidence))  # Clamp to valid range
        except:
            logger.debug(f"Couldn't extract confidence score from critique, using default.")
            # Keep default confidence
        
        logger.info(f"Critique generated for {task.task_id}: {critique_content[:100]}...")

        # Add this critique to the task history
        self.task_histories[task.task_id].append({
            "role": "assistant",
            "content": critique_content,
            "event": TaskEvent.CRITIQUE.value
        })

        # Send final critique back to the orchestrator (Grok)
        result = TaskResultFactory.create_task_result(
            task_id=task.task_id,
            agent=self.agent_name,
            content=critique_content,
            target_agent=settings.GROK_AGENT_NAME,  # Send back to orchestrator
            event=TaskEvent.CRITIQUE,  # Indicates this IS the critique
            outcome=TaskOutcome.SUCCESS,  # Critique itself was successful
            confidence=confidence
        )
        await self.publish_to_agent(settings.GROK_AGENT_NAME, result)
        
        # For non-streaming mode, also send the complete result to frontend
        if not self.stream_enabled:
            await self.publish_to_frontend(result)
        else:
            # For streaming, send a "stream complete" message
            await self.publish_update(
                task.task_id, 
                TaskEvent.INFO, 
                f"Critique complete.", 
                settings.GROK_AGENT_NAME,
                metadata={"stream_complete": True, "confidence": confidence}
            )

    async def perform_conclusion(self, task: Union[Task, TaskResult]):
        """Arbitrate and produce a final conclusion using Claude API."""
        logger.info(f"{self.agent_name} performing CONCLUSION for task {task.task_id}...")
        await self.publish_update(task.task_id, TaskEvent.INFO, "Generating final conclusion...", settings.GROK_AGENT_NAME)

        # Prepare the prompt based on conversation history
        history = self.task_histories.get(task.task_id, [])
        
        # Build a context-rich prompt including all history, especially critiques
        history_text = ""
        critiques = []
        
        for entry in history:
            if entry.get("event") == TaskEvent.CRITIQUE.value:
                critiques.append(entry["content"])
            
            # Include all history with event type labels
            if entry["role"] == "user":
                history_text += f"\n[{entry.get('event', 'MESSAGE')}] {entry['content']}\n"
            else:
                history_text += f"\n[RESPONSE] {entry['content']}\n"
                
        # Add a special critiques section if available
        critiques_section = ""
        if critiques:
            critiques_section = "\nPrevious Critiques:\n" + "\n".join([f"- {c[:300]}..." for c in critiques])
                
        # Create the final prompt with history
        prompt = f"""
Task ID: {task.task_id}
Requesting Agent: {task.agent}
Task Content: {task.content}

Discussion History:
{history_text}
{critiques_section}

Your task is to provide a final conclusion based on all the discussion above.
Synthesize the key insights and provide a clear, actionable recommendation.
"""
        
        # Get system prompt template for conclusion
        system_message = self.prompts.conclusion
        
        # Initialize variables for response tracking
        conclusion_content = ""
        confidence = 0.8  # Default confidence
        
        # Get the WebSocket instance from the base agent
        ws = getattr(self, "websocket", None)
        
        if self.stream_enabled and ws:
            # Use the standardized streaming method that follows the Manus Killswitch Standard
            logger.info(f"Using standardized streaming response for conclusion on task {task.task_id}")
            
            conclusion_content = await self._stream_llm(prompt, ws, task.task_id, system_message)
        else:
            # Fall back to standard API response if streaming isn't available
            messages = [{"role": "user", "content": prompt}]
            conclusion_content = await self.call_anthropic_api(messages, system_message)
            
            if not conclusion_content:
                # Fallback if API call fails
                conclusion_content = f"[Conclusion by {self.agent_name}] I was unable to reach a conclusion due to technical difficulties. Please try again."
        
        # Try to extract confidence score if present
        try:
            if "confidence: " in conclusion_content.lower():
                parts = conclusion_content.lower().split("confidence: ")
                confidence_str = parts[1].strip()
                confidence = float(confidence_str.split()[0])
                confidence = max(0.0, min(1.0, confidence))  # Clamp to valid range
        except:
            logger.debug(f"Couldn't extract confidence score from conclusion, using default.")
            # Keep default confidence

        logger.info(f"Conclusion generated for {task.task_id}: {conclusion_content[:100]}...")

        # Add this conclusion to the task history
        self.task_histories[task.task_id].append({
            "role": "assistant",
            "content": conclusion_content,
            "event": TaskEvent.CONCLUDE.value
        })

        # Send final conclusion back to the orchestrator (Grok)
        result = TaskResultFactory.create_task_result(
            task_id=task.task_id,
            agent=self.agent_name,
            content=conclusion_content,
            target_agent=settings.GROK_AGENT_NAME,
            event=TaskEvent.CONCLUDE,  # Indicates this IS the conclusion
            outcome=TaskOutcome.SUCCESS,
            confidence=confidence
        )
        await self.publish_to_agent(settings.GROK_AGENT_NAME, result)
        
        # For non-streaming mode, also send the complete result to frontend
        if not self.stream_enabled:
            await self.publish_to_frontend(result)
        else:
            # For streaming, send a "stream complete" message
            await self.publish_update(
                task.task_id, 
                TaskEvent.INFO, 
                f"Conclusion complete.", 
                settings.GROK_AGENT_NAME,
                metadata={"stream_complete": True, "confidence": confidence}
            )

    async def handle_chat_message(self, message: Message):
        """Handles chat messages directed at Claude using the Anthropic API."""
        logger.info(f"{self.agent_name} received CHAT from {message.agent}: {message.content[:50]}...")
        
        # Prepare a simple message for the API
        messages = [
            {
                "role": "user",
                "content": f"Message from {message.agent}: {message.content}"
            }
        ]
        
        # Use the chat prompt template with agent name substitution
        system_prompt = self.prompts.chat.format(agent_name=message.agent)
        
        # Initialize response tracking
        response_content = ""
        
        if self.stream_enabled and message.task_id:
            # Use streaming for chat if task_id is available
            stream = await self.call_anthropic_api(
                messages=messages, 
                system_prompt=system_prompt,
                stream=True,
                stream_handler=self.stream_handler
            )
            
            if stream:
                # Collect the full response
                full_response = ""
                async for chunk in stream:
                    if chunk is None:  # Error in stream
                        break
                    full_response += chunk
                
                response_content = full_response
            else:
                # Fallback if streaming fails
                response_content = f"{self.agent_name} received your message but encountered an issue generating a response."
        else:
            # Use standard API response
            response_content = await self.call_anthropic_api(messages, system_prompt)
            
            if not response_content:
                # Fallback if API call fails
                response_content = f"{self.agent_name} received your message but encountered an issue generating a response."
        
        # Send final response
        reply = MessageFactory.create_message(
            task_id=message.task_id,
            agent=self.agent_name,
            content=response_content,
            target_agent=message.agent  # Reply to sender
        )
        await self.publish_to_agent(message.agent, reply)
        
        # For non-streaming mode or chat without task_id, send the complete reply
        if not self.stream_enabled or not message.task_id:
            await self.publish_to_frontend(reply)

    async def handle_tool_response(self, tool_result: TaskResult):
        """Claude might need tool results if critique/arbitration involves external data."""
        logger.info(f"{self.agent_name} received TOOL_RESPONSE (TaskID: {tool_result.task_id}): {tool_result.content[:50]}...")
        
        # Add tool result to task history
        if tool_result.task_id not in self.task_histories:
            self.task_histories[tool_result.task_id] = []
            
        self.task_histories[tool_result.task_id].append({
            "role": "user",
            "content": f"Tool Response: {tool_result.content}",
            "event": "TOOL_RESPONSE"
        })
        
        # Let the orchestrator know we've received the tool result
        await self.publish_update(
            tool_result.task_id, 
            TaskEvent.INFO, 
            f"Incorporated tool result into analysis: {tool_result.content[:30]}...", 
            settings.GROK_AGENT_NAME
        )

    # --- Methods for Abstract Base Class ---
    async def get_notes(self) -> Dict[str, Any]:
        """Return agent status information."""
        active_tasks = list(self.task_histories.keys())
        active_streams = list(self.active_streams.keys())
        return {
            "agent": self.agent_name,
            "status": "Active" if active_tasks else "Idle",
            "role": "Arbitration/Reconciliation",
            "model": self.model,
            "active_tasks": len(active_tasks),
            "active_streams": len(active_streams),
            "streaming_enabled": self.stream_enabled
        }

    async def process_response(self, response: Any, originating_agent: str):
        """Process a response from another agent."""
        logger.debug(f"{self.agent_name} received response from {originating_agent}")
        # Try parsing as standard message/task and route
        if isinstance(response, Task) or isinstance(response, TaskResult):
            await self.handle_modify_task(response)
        elif isinstance(response, Message):
            await self.handle_chat_message(response)
        else:
            logger.warning(f"Received non-standard response type {type(response)} from {originating_agent}")
    
    async def stop(self):
        """Clean up before stopping the agent."""
        # Cancel any active streams
        self.active_streams.clear()
        
        # Close HTTP client
        if hasattr(self, 'http_client'):
            await self.http_client.aclose()
            logger.info(f"{self.agent_name} stopping - cleaned up HTTP client")
        
        # Call parent class stop
        await super().stop()


# --- Agent Entry Point ---
async def main():
    agent = ClaudeAgent()
    await agent.start()
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        logger.info("ClaudeAgent main task cancelled.")
    finally:
        await agent.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("ClaudeAgent stopped by user.")