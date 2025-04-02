# --- START OF FILE codex_agent.py ---

import asyncio
import json
import os
from typing import Any, Dict, Union, List, Optional # Added Optional
import re
import random
from datetime import datetime

# Import Google Generative AI library
import google.generativeai as genai
from google.generativeai.types import GenerationConfig, SafetySettingDict, HarmCategory, HarmBlockThreshold

from backend.agents.base_agent import BaseAgent
from backend.core.config import settings, logger
# Import ReasoningEffort and ReasoningStrategy from models
from backend.factories.factories import MessageFactory
from backend.models.models import (
    Task, Message, TaskResult, MessageIntent, TaskEvent, TaskOutcome,
    ReasoningEffort, ReasoningStrategy # Added imports
)
from backend.models.workflow_models import WorkflowGenerationRequest, WorkflowTask, WorkflowPlan
# Factories are used by BaseAgent's publish methods, direct import maybe not needed here
# from backend.factories.factories import TaskResultFactory, MessageFactory # Keep if used directly elsewhere

# --- Gemini Configuration ---
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY_HERE" # Replace or manage via config/env
DEFAULT_SAFETY_SETTINGS: List[SafetySettingDict] = [
    {"category": HarmCategory.HARM_CATEGORY_HARASSMENT, "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE},
    {"category": HarmCategory.HARM_CATEGORY_HATE_SPEECH, "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE},
    {"category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE},
    {"category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE},
]
DEFAULT_GENERATION_CONFIG = GenerationConfig(
    # temperature=0.7,
    # max_output_tokens=4096 # Example adjustment
)
# --- End Gemini Configuration ---


class CodexAgent(BaseAgent):
    """
    Codex Agent: Specification understanding, code generation, workflow planning, powered by Gemini.
    Utilizes reasoning effort and strategy hints.
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

        if not self.api_key:
            logger.warning(f"Gemini API key for {self.agent_name} is not configured. LLM calls will fail.")
            self.model = None
        else:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(
                    model_name=getattr(settings, 'CODEX_GEMINI_MODEL', 'gemini-1.5-flash'),
                    safety_settings=DEFAULT_SAFETY_SETTINGS,
                    generation_config=DEFAULT_GENERATION_CONFIG
                )
                logger.info(f"CodexAgent initialized as '{self.agent_name}' using Gemini model '{self.model.model_name}'.")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini model for {self.agent_name}: {e}")
                self.model = None

    def _apply_reasoning_strategy_to_prompt(self, prompt: str, strategy: Optional[ReasoningStrategy]) -> str:
        """Adds instructions to the prompt based on the reasoning strategy."""
        if strategy == ReasoningStrategy.COT:
            # Prepend instruction to think step-by-step
            logger.debug("Applying Chain-of-Thought strategy instruction.")
            return f"Think step-by-step before providing your final answer.\n\nUser: {prompt}"
        elif strategy == ReasoningStrategy.COD:
            # Prepend instruction for more detailed drafting (simple version)
            # NOTE: True Chain-of-Draft requires multiple rounds (draft, critique, refine),
            # which isn't handled by this single modification. This is just a hint.
            logger.debug("Applying Chain-of-Draft strategy instruction (prompt hint).")
            return f"Generate a detailed draft, considering potential issues and alternatives, before providing the final output.\n\nUser: {prompt}"
        # If strategy is LOW or None, use the original prompt directly
        logger.debug(f"Applying Direct Answer strategy (or no strategy specified).")
        return prompt # Return original prompt for DIRECT or None


    async def _call_llm(self, prompt: str, system_message: Optional[str] = None, strategy: Optional[ReasoningStrategy] = None) -> str:
        """
        Calls the Gemini API (non-streaming), potentially modifying the prompt based on strategy.
        """
        if not self.model:
            logger.error(f"{self.agent_name}: Gemini model not available.")
            return "[LLM Error: Model not configured]"

        try:
            # Apply strategy modifications to the user prompt part
            modified_prompt = self._apply_reasoning_strategy_to_prompt(prompt, strategy)

            # Combine system message (if any) with the potentially modified user prompt
            full_prompt = f"{system_message}\n\n{modified_prompt}" if system_message else modified_prompt

            logger.debug(f"Calling Gemini (non-streaming) for {self.agent_name}. Strategy: {strategy}. Prompt length: {len(full_prompt)}")

            response = await self.model.generate_content_async(
                 full_prompt,
                 safety_settings=DEFAULT_SAFETY_SETTINGS,
                 generation_config=DEFAULT_GENERATION_CONFIG
                 )

            # ... (rest of the error checking and response handling remains the same) ...
            if not response.candidates:
                 block_reason = response.prompt_feedback.block_reason if response.prompt_feedback else "Unknown"
                 safety_ratings = response.prompt_feedback.safety_ratings if response.prompt_feedback else []
                 logger.warning(f"Gemini response blocked. Reason: {block_reason}. Ratings: {safety_ratings}")
                 return f"[LLM Safety Block: {block_reason}]"
            try:
                result_text = response.text
                logger.debug(f"Gemini response received (first 100 chars): {result_text[:100]}")
                return result_text
            except ValueError as ve:
                 logger.warning(f"Gemini response.text access error: {ve}. Checking parts...")
                 if response.parts:
                     return "".join(part.text for part in response.parts)
                 else:
                     logger.error(f"Gemini response blocked or empty, no text or parts found.")
                     return "[LLM Error: Blocked or empty response]"

        except Exception as e:
            logger.exception(f"Error calling Gemini API for {self.agent_name}: {e}")
            return f"[LLM Error: {e}]"

    async def _stream_llm(self, prompt: str, ws, task_id: str, system_message: Optional[str] = None, strategy: Optional[ReasoningStrategy] = None):
        """
        Streams a response from the Gemini API, potentially modifying the prompt based on strategy.
        Pushes deltas to the frontend WebSocket.
        """
        agent_name = self.agent_name
        full_text = ""

        if not self.model:
            logger.error(f"{agent_name}: Gemini model not available for streaming.")
            # Send error via WebSocket
            # ... (error sending code remains the same) ...
            await ws.send(json.dumps({
                "event": "error",
                "data": { "agent": agent_name, "task_id": task_id, "message": "LLM model not configured." }
            }))
            return "[Streaming Error: Model not configured]"

        try:
            # Apply strategy modifications to the user prompt part
            modified_prompt = self._apply_reasoning_strategy_to_prompt(prompt, strategy)

            # Combine system message (if any) with the potentially modified user prompt
            full_prompt = f"{system_message}\n\n{modified_prompt}" if system_message else modified_prompt

            logger.debug(f"Streaming Gemini response for task {task_id}. Strategy: {strategy}. Prompt length: {len(full_prompt)}")

            # Use stream=True for the streaming call
            stream = await self.model.generate_content_async(
                full_prompt,
                stream=True,
                safety_settings=DEFAULT_SAFETY_SETTINGS,
                generation_config=DEFAULT_GENERATION_CONFIG
            )

            async for chunk in stream:
                # ... (rest of the streaming logic: safety check, delta extraction, ws.send remains the same) ...
                if not chunk.candidates:
                    block_reason = chunk.prompt_feedback.block_reason if chunk.prompt_feedback else "Unknown"
                    logger.warning(f"Gemini stream chunk blocked for task {task_id}. Reason: {block_reason}")
                    continue
                try:
                    delta = chunk.text
                    if delta:
                        full_text += delta
                        if delta.strip():
                            await ws.send(json.dumps({
                                "event": "stream_update",
                                "data": { "agent": agent_name, "task_id": task_id, "delta": delta }
                            }))
                except ValueError as ve:
                     logger.warning(f"Gemini stream chunk access error for task {task_id}: {ve}. Skipping chunk.")
                     continue
                except Exception as chunk_e:
                    logger.error(f"Error processing Gemini stream chunk for task {task_id}: {chunk_e}")
                    continue

            logger.debug(f"Gemini stream finished for task {task_id}. Full text length: {len(full_text)}")
            # Optional: Send final result event
            await ws.send(json.dumps({
                "event": "final_result",
                "data": { "agent": agent_name, "task_id": task_id, "content": full_text }
            }))
            return full_text

        except Exception as e:
            logger.exception(f"{agent_name} streaming failed for task {task_id}: {e}")
            # Send error message via WebSocket
            # ... (error sending code remains the same) ...
            try:
                await ws.send(json.dumps({
                    "event": "error",
                    "data": { "agent": agent_name, "task_id": task_id, "message": f"Streaming failed: {e}" }
                }))
            except Exception as ws_e:
                logger.error(f"Failed to send streaming error to WebSocket for task {task_id}: {ws_e}")
            return "[Streaming Error]"


    async def handle_start_task(self, task: Task):
        """Codex processes START_TASK using task's reasoning strategy."""
        logger.info(f"{self.agent_name} received START_TASK (ID: {task.task_id}, Strategy: {task.reasoning_strategy}, Effort: {task.reasoning_effort}): {task.content[:50]}...")
        # Use the publish_update from BaseAgent which uses factories
        await self.publish_update(task.task_id, TaskEvent.PLAN, f"Acknowledged task. Processing request with strategy '{task.reasoning_strategy.value if task.reasoning_strategy else 'default'}'.", task.agent)

        # Use the non-streaming Gemini call here, passing the strategy
        system_msg = "You are an expert software engineer and technical writer. Respond directly to the user's request for code, documentation, or specifications."
        # Pass the strategy from the task to the LLM call
        response_content = await self._call_llm(
            prompt=task.content,
            system_message=system_msg,
            strategy=task.reasoning_strategy # Pass the strategy here
        )

        # Use publish_completion/error from BaseAgent which use factories
        if "[LLM Error:" in response_content or "[LLM Safety Block:" in response_content:
             await self.publish_error(task.task_id, f"Failed to get LLM response: {response_content}", task.agent)
        else:
             # Confidence might be adjusted based on perceived difficulty or strategy outcome later
             await self.publish_completion(task.task_id, f"Codex Response:\n{response_content}", task.agent, confidence=task.confidence) # Pass confidence from original task maybe

    async def handle_generate_workflow(self, task: Task):
        """Handles GENERATE_WORKFLOW using task's reasoning strategy."""
        logger.info(f"{self.agent_name} received GENERATE_WORKFLOW task (ID: {task.task_id}, Strategy: {task.reasoning_strategy}, Effort: {task.reasoning_effort}) from {task.agent}")
        await self.publish_update(task.task_id, TaskEvent.PLAN, f"Generating workflow plan with strategy '{task.reasoning_strategy.value if task.reasoning_strategy else 'default'}'.", task.agent)

        try:
            # 1. Parse request (remains the same)
            try:
                request_data = json.loads(task.content)
                workflow_request = WorkflowGenerationRequest(**request_data)
                logger.debug(f"Parsed workflow request prompt: {workflow_request.prompt[:100]}...")
            except (json.JSONDecodeError, TypeError, ValueError) as e:
                logger.error(f"Failed to parse workflow request JSON: {e}. Content: {task.content[:200]}")
                await self.publish_error(task.task_id, f"Invalid request format: {e}", task.agent)
                return

            # 2. Construct LLM prompt (remains the same, includes system instructions)
            llm_prompt = self._build_workflow_llm_prompt(workflow_request.prompt)

            # 3. Call the LLM (non-streaming), passing the strategy
            logger.debug("Calling Gemini for workflow generation...")
            # Pass the strategy from the task. No separate system message needed as prompt is self-contained.
            llm_response_str = await self._call_llm(
                prompt=llm_prompt,
                strategy=task.reasoning_strategy # Pass the strategy here
                )
            logger.debug(f"LLM response received (first 200 chars): {llm_response_str[:200]}...")

            # Check for LLM errors (remains the same)
            if "[LLM Error:" in llm_response_str or "[LLM Safety Block:" in llm_response_str:
                logger.error(f"LLM call failed during workflow generation: {llm_response_str}")
                await self.publish_error(task.task_id, f"LLM failed: {llm_response_str}", task.agent)
                return

            # 4. Parse and validate (remains the same)
            try:
                cleaned_response_str = self._extract_json_from_markdown(llm_response_str)
                workflow_data = json.loads(cleaned_response_str)
                if not isinstance(workflow_data, list):
                     if isinstance(workflow_data, dict) and len(workflow_data) == 1:
                         key = list(workflow_data.keys())[0]
                         if isinstance(workflow_data[key], list):
                             logger.warning("LLM returned JSON object wrapping the list, extracting list.")
                             workflow_data = workflow_data[key]
                         else:
                             raise ValueError(f"LLM response is a JSON object, but does not contain a list under the top key ('{key}').")
                     else:
                         raise ValueError("LLM response is not a JSON list.")

                validated_tasks: List[WorkflowTask] = [WorkflowTask(**task_data) for task_data in workflow_data]
                logger.success(f"Successfully parsed and validated {len(validated_tasks)} workflow tasks from LLM response.")
                result_content = json.dumps([task.model_dump(mode='json') for task in validated_tasks], indent=4)

            except (json.JSONDecodeError, ValueError, TypeError) as e:
                logger.error(f"Failed to parse or validate LLM workflow response: {e}. Response: {llm_response_str[:500]}")
                await self.publish_error(task.task_id, f"Failed to process LLM response: {e}. Raw response logged.", task.agent)
                await self.publish_update(task.task_id, TaskEvent.INFO, f"LLM response processing failed. Raw:\n{llm_response_str}", task.agent)
                return

            # 5. Send the validated workflow plan back using publish_completion
            await self.publish_completion(
                task_id=task.task_id,
                final_content=result_content,
                target_agent=task.agent,
                # Confidence might be adjusted based on strategy success / validation strictness
                confidence=0.85 # Keep default or adjust
            )
            logger.info(f"Workflow plan sent successfully for task {task.task_id}.")

        except Exception as e:
             logger.exception(f"Unexpected error during workflow generation for task {task.task_id}: {e}")
             await self.publish_error(task.task_id, f"Unexpected error: {e}", task.agent)


    # _build_workflow_llm_prompt method remains the same
    def _build_workflow_llm_prompt(self, user_prompt: str) -> str:
        # ... (implementation unchanged) ...
        workflow_task_schema_desc = WorkflowTask.model_json_schema(mode='serialization')
        schema_str = json.dumps(workflow_task_schema_desc, indent=2)
        prompt = f"""
        You are an expert system designer responsible for planning workflows based on user requests.
        Your task is to break down the user's request into a sequence of logical, granular, and actionable tasks.
        Output ONLY a valid JSON list representing the workflow plan. Each object in the list must strictly adhere to the following JSON Schema:

        ```json
        {{
            "description": "A JSON Schema for a list of workflow tasks",
            "type": "array",
            "items": {schema_str}
        }}""" # Start the JSON array for the LLM

            # We add the opening bracket to strongly hint the desired output format.
            # The LLM should only complete the list contents and the closing bracket.
        return prompt.strip()
    
# _extract_json_from_markdown method remains the same
def _extract_json_from_markdown(self, text: str) -> str:
    # ... (implementation unchanged) ...
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text, re.IGNORECASE)
    if match:
        extracted = match.group(1).strip()
        logger.debug("Extracted JSON from markdown code block.")
        if extracted.startswith('[') and extracted.endswith(']'): return extracted
        if extracted.startswith('{') and extracted.endswith('}'): return extracted
        logger.warning("Content inside markdown block doesn't look like complete JSON, attempting secondary extraction.")
        text = extracted

    first_bracket = text.find('[')
    first_curly = text.find('{')
    last_bracket = text.rfind(']')
    last_curly = text.rfind('}')
    start_index = -1
    end_index = -1
    if first_bracket != -1 and first_curly != -1: start_index = min(first_bracket, first_curly)
    elif first_bracket != -1: start_index = first_bracket
    elif first_curly != -1: start_index = first_curly
    if last_bracket != -1 and last_curly != -1:
        if start_index == first_bracket and last_bracket > start_index: end_index = last_bracket
        elif start_index == first_curly and last_curly > start_index: end_index = last_curly
        else: end_index = max(last_bracket, last_curly)
    elif last_bracket != -1 and last_bracket > start_index: end_index = last_bracket
    elif last_curly != -1 and last_curly > start_index: end_index = last_curly
    if start_index != -1 and end_index != -1:
        potential_json = text[start_index : end_index + 1]
        logger.debug(f"Attempting extraction from index {start_index} to {end_index}.")
        if (potential_json.startswith('[') and potential_json.endswith(']')) or \
           (potential_json.startswith('{') and potential_json.endswith('}')):
             return potential_json.strip()
        else:
            logger.warning("Extracted text boundaries don't form valid JSON structure.")
            return text.strip()
    else:
        logger.debug("No clear JSON start/end indicators found in text.")
        return text.strip()


# --- Override other handlers as needed ---

async def handle_modify_task(self, task_update: Union[Task, TaskResult]):
    """Handles updates/feedback for ongoing Codex tasks."""
    # TODO: Potentially use reasoning strategy from the feedback if provided
    strategy = getattr(task_update, 'reasoning_strategy', None)
    logger.info(f"{self.agent_name} received MODIFY_TASK from {task_update.agent} (Event: {task_update.event.value}, Strategy: {strategy})")
    await self.publish_update(task_update.task_id, TaskEvent.INFO, "Feedback received. Processing modification...", task_update.agent)
    # ... implement refinement logic, potentially calling _call_llm with the feedback content and strategy ...
    # Example:
    # feedback_content = task_update.content
    # response = await self._call_llm(f"Refine the previous output based on this feedback: {feedback_content}", strategy=strategy)
    # await self.publish_update(task_update.task_id, TaskEvent.REFINE, response, task_update.agent)


async def handle_chat_message(self, message: Message):
    """Handles direct chat messages (reasoning effort/strategy less critical here)."""
    # Note: Chat messages don't typically carry reasoning effort/strategy.
    # If they did via metadata, we could pass it to _call_llm.
    logger.info(f"{self.agent_name} received CHAT from {message.agent}: {message.content[:50]}...")
    system_msg = "You are the Codex AI Agent, specializing in software design, code, specifications, and workflow planning. Answer the user's query concisely and helpfully."
    # Using default strategy (None) for chat
    response_content = await self._call_llm(message.content, system_message=system_msg)

    if "[LLM Error:" in response_content or "[LLM Safety Block:" in response_content:
        reply_content = f"Sorry, I encountered an issue processing your request: {response_content}"
    else:
         reply_content = response_content

    # Use MessageFactory via BaseAgent's publish methods if possible, or directly
    reply = Message( # Using Message model directly for clarity here
        task_id=message.task_id or f"chat_{message.message_id}",
        agent=self.agent_name,
        content=reply_content,
        intent=MessageIntent.CHAT, # Explicitly setting intent
        target_agent=message.agent,
        timestamp=datetime.datetime.now(datetime.timezone.utc) # Ensure timestamp
    )
    await self.publish_to_agent(message.agent, reply)
    await self.publish_to_frontend(reply)
    logger.info(f"{self.agent_name} sent chat reply to {message.agent}.")


# --- Dispatch incoming messages ---
async def handle_incoming_message(self, raw_data: str):
    # The Task model validation (`model_validator`) in models.py already calls
    # estimate_reasoning_effort if 'reasoning_effort' isn't present when deserializing.
    # So, when a Task arrives here, it should already have effort/strategy populated.
    try:
        data = json.loads(raw_data)
        intent_str = data.get("intent")
        message_type = data.get("type")

        if intent_str == MessageIntent.GENERATE_WORKFLOW.value and message_type == Task.__name__:
            task = Task.model_validate_json(raw_data)
            await self.handle_generate_workflow(task)
        else:
            await super().handle_incoming_message(raw_data)

    except json.JSONDecodeError:
         logger.error(f"{self.agent_name} received invalid JSON: {raw_data[:200]}...")
    except Exception as e:
        logger.exception(f"Error routing incoming message in {self.agent_name}: {e}")
        try:
             task_id_match = re.search(r'"task_id"\s*:\s*"([^"]+)"', raw_data)
             task_id = task_id_match.group(1) if task_id_match else "unknown"
             await self.publish_error(task_id, f"Internal error processing message: {e}")
        except Exception as report_e:
             logger.error(f"Failed to report error for {self.agent_name}: {report_e}")


# --- Placeholder methods for Abstract Base Class ---
async def get_notes(self) -> Dict[str, Any]:
     status = "Idle"
     if not self.model: status = "Error - Model Not Initialized"
     return {"agent": self.agent_name, "status": status, "role": "Code/Spec/Workflow Assistance (Gemini)", "model": getattr(self.model, 'model_name', 'N/A')}

async def process_response(self, response: Any, originating_agent: str):
     logger.debug(f"{self.agent_name} received generic response from {originating_agent}. Data: {str(response)[:100]}")
                
    