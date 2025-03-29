import os
import asyncio
import random
import json
from typing import Any, Dict, Union

from backend.agents.base_agent import BaseAgent
from backend.core.config import settings, logger
from backend.models.models import ReasoningEffort, Task, Message, TaskResult, MessageIntent, TaskEvent, TaskOutcome
from backend.factories.factories import MessageFactory, TaskResultFactory, TaskFactory, estimate_reasoning_effort

import openai

class GPTAgent(BaseAgent):
    """
    GPT-4o Agent: Backend Operations & Response Refinement.
    Generates initial proposals, refines based on feedback, interacts with ToolCore (Placeholder Logic).
    """

    def __init__(self):
        agent_name = os.environ.get("AGENT_NAME")
        llm_model = os.environ.get("LLM_MODEL")
        api_key = os.environ.get("AGENT_API_KEY")
        api_url = os.environ.get("API_URL")
        #api_version = os.environ.get("API_VERSION")
        
        super().__init__(agent_name=agent_name, llm_model=llm_model, api_url=api_url, api_key=api_key)
        openai.api_key = settings.GPT_API_KEY  # or self.api_key
        self.agent_prompts = {
            "GPT": "You are the backend operations agent, responsible for initial proposals and refinements.",
            "Claude": "You are the philosophical reasoning agent, focused on ethical dilemmas.",
            "Grok": "You are a creative and strategic agent who loves unconventional solutions."
        }
        
    def select_model(effort: ReasoningEffort) -> str:
        if effort == ReasoningEffort.LOW:
            return "gpt-3.5-turbo"
        elif effort == ReasoningEffort.MEDIUM:
            return "gpt-4"
        elif effort == ReasoningEffort.HIGH:
            return "gpt-4o"  # or your most capable fine-tuned model

    async def handle_start_task(self, task: Task, ws):
        """Handles the initial task assignment to generate a proposal."""
        logger.info(f"{self.agent_name} received START_TASK (ID: {task.task_id}): {task.content[:50]}...")
        await self.publish_update(task.task_id, TaskEvent.PLAN, "Planning initial proposal...", settings.GROK_AGENT_NAME)
        
        prompt = f"Generate an initial proposal for the following task:\n\n{task.content}"
        proposal_content = await self._stream_llm(prompt, ws, task.task_id)

        # Placeholder proposal generation
        await asyncio.sleep(random.uniform(1, 4)) # Simulate processing
        # Check if task involves a tool (simple keyword check)
        if "tool" in task.content.lower() or "execute" in task.content.lower() or "run script" in task.content.lower():
             # Placeholder: Decide to use a tool
             tool_name = "example_tool" # Hardcoded for now
             tool_params = {"input_arg": task.content[:30]} # Dummy params
             logger.info(f"Task requires a tool. Requesting execution of '{tool_name}'.")
             await self.request_tool_execution(task.task_id, tool_name, tool_params, settings.GROK_AGENT_NAME)
             # State should now be AWAITING_TOOL, response will come via handle_tool_response
             return # Don't generate proposal yet

        # If no tool needed immediately
        proposal_options = [
            f"Initial Proposal: Based on '{task.content[:30]}...', the recommended approach is Method A.",
            f"Proposal Draft: We should analyze factors X, Y, and Z. Initial thoughts point towards Solution B.",
            f"Plan: 1. Gather data. 2. Analyze trends. 3. Formulate strategy. Starting with data gathering.",
        ]
        proposal_content = f"[Proposal by {self.agent_name}] {random.choice(proposal_options)}"
        confidence = random.uniform(0.7, 0.95)

        logger.info(f"Initial proposal generated for {task.task_id}: {proposal_content[:100]}...")

        # Send proposal back to orchestrator (Grok)
        result = TaskResultFactory.create_task_result(
            task_id=task.task_id,
            agent=self.agent_name,
            content=proposal_content,
            target_agent=settings.GROK_AGENT_NAME,
            event=TaskEvent.EXECUTE, # Indicate proposal/execution is done for now
            outcome=TaskOutcome.SUCCESS, # Proposal generation was successful
            confidence=confidence
        )
        await self.publish_to_agent(settings.GROK_AGENT_NAME, result)
        await self.publish_to_frontend(result)

    async def _call_llm(self, prompt: str, system_message: str) -> str:
        system_message = self.agent_prompts.get(self.agent_name, "You are a helpful assistant.")
        try:
            response = await openai.ChatCompletion.acreate(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1024,
                stream=True
            )
            return response.choices[0].message["content"]
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return "[LLM Error] Failed to generate response."
        
    async def _stream_llm(self, prompt: str, ws, task_id: str, system_message: str):
        system_message = self.agent_prompts.get(self.agent_name, "You are a helpful assistant.")
        try:
            stream = await openai.ChatCompletion.acreate(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                stream=True,
            )

            content = ""
            async for chunk in stream:
                delta = chunk.choices[0].delta.get("content", "")
                content += delta
                if delta.strip():
                    # Real-time stream to frontend
                    stream_msg = {
                        "event": "stream_update",
                        "data": {
                            "agent": self.agent_name,
                            "task_id": task_id,
                            "delta": delta
                        }
                    }
                    await ws.send(json.dumps(stream_msg))

            return content

        except Exception as e:
            self.logger.error(f"Streaming LLM failed: {e}")
            return "[LLM Streaming Error]"

    async def handle_modify_task(self, task_update: Union[Task, TaskResult]):
        """Handles requests for refinement based on critique."""
        logger.info(f"{self.agent_name} received update from {task_update.agent} (Event: {task_update.event.value}): {task_update.content[:50]}...")

        if task_update.target_agent == self.agent_name and task_update.event == TaskEvent.REFINE:
            await self.perform_refinement(task_update)
        else:
            logger.debug(f"{self.agent_name} ignored update not targeted as a refinement request.")


    async def perform_refinement(self, task_update: Union[Task, TaskResult], ws):
        """Placeholder: Refine the proposal based on critique."""
        logger.info(f"{self.agent_name} performing REFINEMENT for task {task_update.task_id} based on critique: {task_update.content[:50]}...")
        await self.publish_update(task_update.task_id, TaskEvent.REFINE, "Refining proposal based on feedback...", settings.GROK_AGENT_NAME)

        prompt = f"The previous proposal received the following critique:\n\n'{task_update.content}'\n\nPlease refine the proposal to address this feedback."
        refined_content = await self._stream_llm(prompt, ws, task_update.task_id)

        # Placeholder refinement logic
        await asyncio.sleep(random.uniform(1, 3))
        refinement_options = [
            f"Refined Proposal: Addressing critique '{task_update.content[:30]}...'. Added details to section X.",
            f"Updated Plan: Incorporated feedback. Alternative approach Y considered and integrated.",
            f"Revision 1: Strengthened reasoning as requested. Evidence added.",
        ]
        # Simulate maybe formatting as JSON
        if random.random() > 0.7:
             refined_data = {
                 "status": "refined",
                 "based_on_critique": task_update.content[:50] + "...",
                 "changes": random.choice(["Added details", "Strengthened reasoning", "Revised approach"]),
                 "confidence_score": round(random.uniform(0.8, 1.0), 2)
             }
             refined_content = json.dumps(refined_data, indent=2)
             logger.info("Formatted refined response as JSON.")
        else:
             refined_content = f"[Refinement by {self.agent_name}] {random.choice(refinement_options)}"

        confidence = random.uniform(0.8, 1.0) # Confidence after refinement

        logger.info(f"Refinement generated for {task_update.task_id}: {refined_content[:100]}...")

        # Send refined proposal back to orchestrator (Grok)
        result = TaskResultFactory.create_task_result(
            task_id=task_update.task_id,
            agent=self.agent_name,
            content=refined_content,
            target_agent=settings.GROK_AGENT_NAME,
            event=TaskEvent.REFINE, # Indicates this IS the refinement
            outcome=TaskOutcome.SUCCESS,
            confidence=confidence
        )
        await self.publish_to_agent(settings.GROK_AGENT_NAME, result)
        await self.publish_to_frontend(result)


    async def handle_chat_message(self, message: Message, ws):
        """Handles chat messages directed at GPT."""
        logger.info(f"{self.agent_name} received CHAT from {message.agent}: {message.content[:50]}...")
        # Simple echo or basic response
        #response_content = f"{self.agent_name} acknowledging chat: '{message.content[:30]}...'"
        
        prompt = f"User sent: '{message.content}'\n\nRespond in a helpful, conversational tone."
        response_content = await self._stream_llm(prompt, ws, message.task_id)
        
        reply = MessageFactory.create_message(
            task_id=message.task_id,
            agent=self.agent_name,
            content=response_content,
            target_agent=message.agent
        )
        await self.publish_to_agent(message.agent, reply)
        await self.publish_to_frontend(reply)


    async def handle_tool_response(self, tool_result: TaskResult, ws):
        """Handles results from ToolCore after requesting execution."""
        logger.info(f"{self.agent_name} received TOOL_RESPONSE (TaskID: {tool_result.task_id}) from {tool_result.agent}: {tool_result.content[:50]}...")

        if tool_result.outcome == TaskOutcome.SUCCESS:
            # Incorporate tool result into the task processing
            # Simulate using the tool result to generate the actual proposal/response
            await self.publish_update(tool_result.task_id, TaskEvent.EXECUTE, f"Processing result from tool: {tool_result.content[:30]}...", settings.GROK_AGENT_NAME)
            await asyncio.sleep(random.uniform(0.5, 2)) # Simulate processing tool result

            prompt = f"Given the tool output:\n\n'{tool_result.content}'\n\nPlease generate a revised proposal or action plan."
            final_content = await self._stream_llm(prompt, ws, tool_result.task_id)

            # Placeholder using tool result
            final_content = f"[Proposal by {self.agent_name} using Tool Result] Based on tool output '{tool_result.content[:30]}...', the proposal is now Z."
            confidence = random.uniform(0.85, 1.0)

            logger.info(f"Proposal generated using tool result for {tool_result.task_id}: {final_content[:100]}...")

            # Send final proposal back to orchestrator
            result = TaskResultFactory.create_task_result(
                task_id=tool_result.task_id,
                agent=self.agent_name,
                content=final_content,
                target_agent=settings.GROK_AGENT_NAME,
                event=TaskEvent.EXECUTE, # Back to execute state after tool use
                outcome=TaskOutcome.SUCCESS,
                confidence=confidence,
                contributing_agents=[self.agent_name, settings.TOOLS_AGENT_NAME] # Acknowledge tool contribution
            )
            await self.publish_to_agent(settings.GROK_AGENT_NAME, result)
            await self.publish_to_frontend(result)

        else:
            # Handle tool execution failure
            logger.error(f"Tool execution failed for task {tool_result.task_id}: {tool_result.content}")
            await self.publish_error(tool_result.task_id, f"Tool execution failed: {tool_result.content}", settings.GROK_AGENT_NAME)


    # --- Placeholder methods for Abstract Base Class ---
    async def get_notes(self) -> Dict[str, Any]:
         return {"agent": self.agent_name, "status": "Idle", "role": "Proposal/Refinement/Tool Use"}

    async def process_response(self, response: Any, originating_agent: str):
         logger.debug(f"{self.agent_name} received generic response from {originating_agent}")
         if isinstance(response, (Task, TaskResult, Message)):
             await self.handle_modify_task(response) # Assume it's a modification request
         else:
             logger.warning(f"Received non-standard response type {type(response)} from {originating_agent}")

# --- Agent Entry Point ---
async def main():
    agent = GPTAgent()
    await agent.start()
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        logger.info("GPTAgent main task cancelled.")
    finally:
        await agent.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("GPTAgent stopped by user.")