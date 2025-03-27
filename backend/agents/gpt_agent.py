import asyncio
import random
import json
from typing import Any, Dict, Union

from backend.agents.base_agent import BaseAgent
from backend.core.config import settings, logger
from backend.models.models import Task, Message, TaskResult, MessageIntent, TaskEvent, TaskOutcome
from backend.factories.factories import TaskResultFactory

class GPTAgent(BaseAgent):
    """
    GPT-4o Agent: Backend Operations & Response Refinement.
    Generates initial proposals, refines based on feedback, interacts with ToolCore (Placeholder Logic).
    """

    def __init__(self):
        super().__init__(agent_name=settings.GPT_AGENT_NAME, api_key=settings.GPT_API_KEY)

    async def handle_start_task(self, task: Task):
        """Handles the initial task assignment to generate a proposal."""
        logger.info(f"{self.agent_name} received START_TASK (ID: {task.task_id}): {task.content[:50]}...")
        await self.publish_update(task.task_id, TaskEvent.PLAN, "Planning initial proposal...", settings.GROK_AGENT_NAME)

        # Simulate LLM call for initial proposal
        # prompt = f"Generate an initial proposal for the following task: {task.content}"
        # proposal_content = await self._call_llm(prompt)

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


    async def handle_modify_task(self, task_update: Union[Task, TaskResult]):
        """Handles requests for refinement based on critique."""
        logger.info(f"{self.agent_name} received update from {task_update.agent} (Event: {task_update.event.value}): {task_update.content[:50]}...")

        if task_update.target_agent == self.agent_name and task_update.event == TaskEvent.REFINE:
            await self.perform_refinement(task_update)
        else:
            logger.debug(f"{self.agent_name} ignored update not targeted as a refinement request.")


    async def perform_refinement(self, task_update: Union[Task, TaskResult]):
        """Placeholder: Refine the proposal based on critique."""
        logger.info(f"{self.agent_name} performing REFINEMENT for task {task_update.task_id} based on critique: {task_update.content[:50]}...")
        await self.publish_update(task_update.task_id, TaskEvent.REFINE, "Refining proposal based on feedback...", settings.GROK_AGENT_NAME)

        # Simulate LLM call for refinement
        # Needs access to original proposal + critique
        # prompt = f"Refine the proposal based on the following critique:\nCritique: {task_update.content}\n\nOriginal context/proposal (needs state management):\n[...]"
        # refined_content = await self._call_llm(prompt)

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


    async def handle_chat_message(self, message: Message):
        """Handles chat messages directed at GPT."""
        logger.info(f"{self.agent_name} received CHAT from {message.agent}: {message.content[:50]}...")
        # Simple echo or basic response
        response_content = f"{self.agent_name} acknowledging chat: '{message.content[:30]}...'"
        reply = MessageFactory.create_message(
            task_id=message.task_id,
            agent=self.agent_name,
            content=response_content,
            target_agent=message.agent
        )
        await self.publish_to_agent(message.agent, reply)
        await self.publish_to_frontend(reply)


    async def handle_tool_response(self, tool_result: TaskResult):
        """Handles results from ToolCore after requesting execution."""
        logger.info(f"{self.agent_name} received TOOL_RESPONSE (TaskID: {tool_result.task_id}) from {tool_result.agent}: {tool_result.content[:50]}...")

        if tool_result.outcome == TaskOutcome.SUCCESS:
            # Incorporate tool result into the task processing
            # Simulate using the tool result to generate the actual proposal/response
            await self.publish_update(tool_result.task_id, TaskEvent.EXECUTE, f"Processing result from tool: {tool_result.content[:30]}...", settings.GROK_AGENT_NAME)
            await asyncio.sleep(random.uniform(0.5, 2)) # Simulate processing tool result

            # prompt = f"Generate a proposal based on the task context and the following tool result:\nTool Result: {tool_result.content}\n\nTask Context: [...]"
            # final_content = await self._call_llm(prompt)

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