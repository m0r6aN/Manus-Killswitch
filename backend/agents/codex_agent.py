import asyncio
import json
from typing import Any, Dict, Union, List
import re

from backend.agents.base_agent import BaseAgent
from backend.core.config import settings, logger
from backend.models.models import Task, Message, TaskResult, MessageIntent, TaskEvent, TaskOutcome
from backend.models.workflow_models import WorkflowGenerationRequest, WorkflowTask, WorkflowPlan # Import workflow models
from backend.factories.factories import TaskResultFactory, MessageFactory

# Define CODEX_API_KEY if needed, otherwise assume BaseAgent handles generic LLM keys/clients
CODEX_API_KEY = "YOUR_CODEX_LLM_API_KEY_HERE" # Replace or manage via config/env

class CodexAgent(BaseAgent):
    """
    Codex Agent: Specification understanding, code generation, and workflow planning.
    """

    def __init__(self):
        # Use a specific agent name from settings if defined, or default
        agent_name = getattr(settings, 'CODEX_AGENT_NAME', 'codex')
        api_key = getattr(settings, 'CODEX_API_KEY', CODEX_API_KEY) # Get API key from settings or default
        super().__init__(agent_name=agent_name, api_key=api_key)
        logger.info(f"CodexAgent initialized as '{self.agent_name}'.")

    async def handle_start_task(self, task: Task):
        """Codex can be tasked directly for code gen, docs, etc."""
        logger.info(f"{self.agent_name} received START_TASK (ID: {task.task_id}): {task.content[:50]}...")
        await self.publish_update(task.task_id, TaskEvent.PLAN, f"Acknowledged task. Planning...", task.agent)

        # Placeholder: Simulate processing based on content
        await asyncio.sleep(random.uniform(1, 3))
        response_content = await self._call_llm(f"Process this request related to code/docs/specs: {task.content}") # Placeholder LLM

        await self.publish_completion(task.task_id, f"Codex Response:\n{response_content}", task.agent)

    async def handle_generate_workflow(self, task: Task):
        """Handles requests to generate a workflow plan from natural language."""
        logger.info(f"{self.agent_name} received GENERATE_WORKFLOW task (ID: {task.task_id}) from {task.agent}")
        await self.publish_update(task.task_id, TaskEvent.PLAN, "Generating workflow plan...", task.agent)

        try:
            # 1. Parse the request payload from task content
            try:
                request_data = json.loads(task.content)
                workflow_request = WorkflowGenerationRequest(**request_data)
                logger.debug(f"Parsed workflow request prompt: {workflow_request.prompt[:100]}...")
            except (json.JSONDecodeError, TypeError, ValueError) as e:
                logger.error(f"Failed to parse workflow request JSON: {e}. Content: {task.content[:200]}")
                await self.publish_error(task.task_id, f"Invalid request format: {e}", task.agent)
                return

            # 2. Construct prompt for the LLM
            llm_prompt = self._build_workflow_llm_prompt(workflow_request.prompt)

            # 3. Call the LLM
            logger.debug("Calling LLM for workflow generation...")
            # Use target_model hint if provided, otherwise use default LLM for Codex
            llm_response_str = await self._call_llm(llm_prompt) # Add target_model param if _call_llm supports it
            logger.debug(f"LLM response received (first 200 chars): {llm_response_str[:200]}...")


            # 4. Parse and validate the LLM response (expecting JSON)
            try:
                # Clean potential markdown code fences ```json ... ```
                cleaned_response_str = self._extract_json_from_markdown(llm_response_str)

                # Parse the string into a list of dictionaries
                workflow_data = json.loads(cleaned_response_str)
                if not isinstance(workflow_data, list):
                     raise ValueError("LLM response is not a JSON list.")

                # Validate using Pydantic - this expects a list, so wrap it for WorkflowPlan
                # validated_plan = WorkflowPlan.model_validate({'__root__': workflow_data})
                # OR validate each task individually
                validated_tasks: List[WorkflowTask] = [WorkflowTask(**task_data) for task_data in workflow_data]
                logger.success(f"Successfully parsed and validated {len(validated_tasks)} workflow tasks from LLM response.")

                # Serialize the validated list back to JSON string for the TaskResult content
                result_content = json.dumps([task.model_dump() for task in validated_tasks], indent=4)

            except (json.JSONDecodeError, ValueError, TypeError) as e:
                logger.error(f"Failed to parse or validate LLM workflow response: {e}. Response: {llm_response_str[:500]}")
                await self.publish_error(task.task_id, f"Failed to process LLM response: {e}. See logs for details.", task.agent)
                # Optionally send the raw response back for debugging
                # await self.publish_update(task.task_id, TaskEvent.FAIL, f"LLM response processing failed. Raw:\n{llm_response_str}", task.agent)
                return

            # 5. Send the validated workflow plan back
            await self.publish_completion(
                task_id=task.task_id,
                final_content=result_content, # Send the validated, formatted JSON string
                target_agent=task.agent, # Send back to the requester (usually Grok)
                confidence=0.9 # Confidence in the generated plan (could be adjusted based on validation)
            )
            logger.info(f"Workflow plan sent successfully for task {task.task_id}.")

        except Exception as e:
             logger.exception(f"Unexpected error during workflow generation for task {task.task_id}: {e}")
             await self.publish_error(task.task_id, f"Unexpected error: {e}", task.agent)


    def _build_workflow_llm_prompt(self, user_prompt: str) -> str:
        """Constructs the detailed prompt for the LLM to generate the workflow JSON."""

        # Define the JSON structure expected using Pydantic schema descriptions (or manually)
        # This is crucial for instructing the LLM correctly.
        workflow_task_schema_desc = """
        [
            {
                "id": "string (unique task identifier, e.g., task-abc123)",
                "name": "string (human-readable name)",
                "description": "string (detailed description)",
                "types": ["string", ...] (e.g., "DATA_EXTRACTION", "DATA_PROCESSING", "CONTENT_CREATION", "SYSTEM_CONFIG", "TESTING", "EXECUTION", "REPORTING"),
                "required_capabilities": ["string", ...] (e.g., "database_access", "sql_knowledge", "copywriting", "email_system_knowledge"),
                "dependencies": [
                    {
                        "task_id": "string (ID of the prerequisite task)",
                        "dependency_type": "string ('completion' or 'data_availability')",
                        "is_blocking": boolean (true if execution must wait)
                    }, ...
                ],
                "execution_order": integer (starting from 1, indicates logical phase),
                "can_parallelize": boolean (true if task can run alongside others in the same execution_order),
                "estimated_complexity": float (optional, e.g., 1.0 to 5.0),
                "expected_duration": integer (optional, estimated seconds),
                "assignments": { "agent": null, "tools": [] } (Leave as null/empty list),
                "needs_review": boolean (optional, true if manual review needed),
                "parameters": { "key": "value", ... } (optional, specific inputs needed),
                "output_schema": { "key": "type", ... } (optional, describes expected output structure)
            },
            ...
        ]
        """

        prompt = f"""
        You are an expert system designer responsible for planning workflows.
        Based on the user's request, break down the process into a sequence of logical tasks.
        Output ONLY a valid JSON list adhering strictly to the following structure for each task:

        {workflow_task_schema_desc}

        Guidelines:
        - Decompose the request into granular, actionable steps.
        - Clearly define dependencies between tasks using the `dependencies` list and correct `task_id` references. Ensure `task_id` values are unique within the list you generate.
        - Determine the logical `execution_order` for each task. Tasks that can run concurrently should share the same `execution_order` and have `can_parallelize` set to true.
        - Identify relevant `types` and `required_capabilities` for each task.
        - Provide estimates for `estimated_complexity` (1-5 scale) and `expected_duration` (seconds) if possible, otherwise omit them or set to null.
        - Keep `assignments` fields (`agent`, `tools`) as null/empty; assignment happens later.
        - Ensure the output is a single, valid JSON list of task objects, without any surrounding text or explanations.

        User Request:
        "{user_prompt}"

        JSON Workflow Plan:
        """
        return prompt.strip()

    def _extract_json_from_markdown(self, text: str) -> str:
        """Extracts JSON content potentially wrapped in markdown code fences."""
        # Regex to find JSON within ```json ... ``` or just ``` ... ```
        match = re.search(r'```(json)?\s*([\s\S]*?)\s*```', text, re.IGNORECASE)
        if match:
            logger.debug("Extracted JSON from markdown code block.")
            return match.group(2).strip()
        else:
            # If no markdown block found, assume the whole string might be JSON (or partial JSON)
            # Try to find the start of a JSON list or object
            first_bracket = text.find('[')
            first_curly = text.find('{')

            if first_bracket == -1 and first_curly == -1:
                # No JSON structure indicators found
                return text # Return original text, parsing will likely fail

            start_index = -1
            if first_bracket != -1 and first_curly != -1:
                 start_index = min(first_bracket, first_curly)
            elif first_bracket != -1:
                 start_index = first_bracket
            else: # first_curly must be != -1
                 start_index = first_curly

            # Find the corresponding closing bracket/curly (this is imperfect)
            # A more robust parser might be needed for complex cases
            # For now, just take from the first bracket/curly onwards
            potential_json = text[start_index:]
            logger.debug("Attempting to parse text starting from first JSON indicator.")
            return potential_json.strip()


    # --- Override other handlers as needed ---

    async def handle_modify_task(self, task_update: Union[Task, TaskResult]):
        """Handles updates/feedback for ongoing Codex tasks."""
        logger.info(f"{self.agent_name} received MODIFY_TASK from {task_update.agent} (Event: {task_update.event.value})")
        # Placeholder: Could handle feedback on generated code, docs, or workflows
        await self.publish_update(task_update.task_id, TaskEvent.INFO, "Feedback received, processing...", task_update.agent)
        # ... implement refinement logic ...


    async def handle_chat_message(self, message: Message):
        logger.info(f"{self.agent_name} received CHAT from {message.agent}: {message.content[:50]}...")
        # Respond to general queries about capabilities, specs, etc.
        response_content = await self._call_llm(f"Answer this query related to software architecture/code/workflows: {message.content}")
        reply = MessageFactory.create_message(
            task_id=message.task_id,
            agent=self.agent_name,
            content=response_content,
            target_agent=message.agent
        )
        await self.publish_to_agent(message.agent, reply)
        await self.publish_to_frontend(reply)

    # --- Dispatch incoming messages ---
    async def handle_incoming_message(self, raw_data: str):
        """Overrides BaseAgent to include GENERATE_WORKFLOW intent."""
        try:
            # Basic intent check before full parsing
            data = json.loads(raw_data)
            intent_str = data.get("intent")

            if intent_str == MessageIntent.GENERATE_WORKFLOW.value:
                task = Task.deserialize(raw_data)
                await self.handle_generate_workflow(task)
            else:
                # Delegate to base class handler for other intents
                await super().handle_incoming_message(raw_data)

        except json.JSONDecodeError:
             logger.error(f"{self.agent_name} received invalid JSON: {raw_data[:100]}...")
        except Exception as e:
            logger.exception(f"Error routing incoming message in {self.agent_name}: {e}")
            try:
                task_id = json.loads(raw_data).get("task_id", "unknown")
                await self.publish_error(task_id, f"Error processing message: {e}")
            except Exception as report_e:
                 logger.error(f"Failed to report error for {self.agent_name}: {report_e}")


    # --- Placeholder methods for Abstract Base Class ---
    async def get_notes(self) -> Dict[str, Any]:
         return {"agent": self.agent_name, "status": "Idle", "role": "Code/Spec/Workflow Assistance"}

    async def process_response(self, response: Any, originating_agent: str):
         logger.debug(f"{self.agent_name} received generic response from {originating_agent}")
         # Delegate or handle based on context if needed

# --- Agent Entry Point (Similar to other agents) ---
import random # Add for placeholder sleep

async def main():
    agent = CodexAgent()
    await agent.start()
    try:
        await asyncio.Future() # Keep running
    except asyncio.CancelledError:
        logger.info(f"{agent.agent_name} main task cancelled.")
    finally:
        await agent.stop()

# Keep the if __name__ == "__main__": block as in other agent main files