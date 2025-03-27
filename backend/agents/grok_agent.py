import asyncio
from typing import Any, Dict, Union

from backend.agents.base_agent import BaseAgent
from backend.core.config import settings, logger
from backend.models.models import Task, Message, TaskResult, MessageIntent, TaskEvent, TaskOutcome
from backend.factories.factories import MessageFactory, TaskFactory

class GrokAgent(BaseAgent):
    """
    Grok Agent: Moderation & Orchestration.
    Routes tasks, manages simple debate states (placeholder), detects basic issues.
    """

    def __init__(self):
        super().__init__(agent_name=settings.GROK_AGENT_NAME, api_key=settings.GROK_API_KEY)
        # Simple state tracking per task_id
        self.task_states: Dict[str, Dict[str, Any]] = {}

    async def handle_start_task(self, task: Task):
        """Handles a new task request, usually from the user/frontend."""
        logger.info(f"{self.agent_name} received START_TASK (ID: {task.task_id}): {task.content[:50]}...")

        # Basic validation
        if not task.content:
             await self.publish_error(task.task_id, "Task content cannot be empty.", task.agent)
             return

        # Initialize state for this task
        self.task_states[task.task_id] = {
            "status": TaskEvent.PLAN,
            "original_requester": task.agent, # Usually 'user' or client_id
            "current_step": "initial_proposal",
            "round": 1,
            "history": [f"Task received from {task.agent}: {task.content}"]
        }

        # --- Orchestration Logic ---
        # Simplistic: Assign initial proposal to GPT-4o
        target_agent = settings.GPT_AGENT_NAME
        logger.info(f"Assigning initial task '{task.task_id}' to {target_agent}")

        # Create a new Task object specifically for the target agent
        agent_task = TaskFactory.create_task(
            agent=self.agent_name, # Grok is assigning the task
            content=task.content,
            target_agent=target_agent,
            task_id=task.task_id, # Keep the same task ID
            intent=MessageIntent.START_TASK,
            event=TaskEvent.PLAN # Instruct the agent to start planning/executing
        )
        await self.publish_to_agent(target_agent, agent_task)

        # Inform frontend that task is progressing
        await self.publish_update(
            task.task_id,
            TaskEvent.PLAN,
            f"Task assigned to {target_agent} for initial proposal.",
            self.task_states[task.task_id]["original_requester"] # Inform original requester
        )
        await self.publish_to_frontend(agent_task) # Also broadcast the assignment


    async def handle_modify_task(self, task_update: Union[Task, TaskResult]):
        """Handles results/updates from other agents, orchestrates next steps."""
        task_id = task_update.task_id
        sender = task_update.agent
        logger.info(f"{self.agent_name} received MODIFY_TASK/RESULT (ID: {task_id}) from {sender} (Event: {task_update.event.value})")

        if task_id not in self.task_states:
            logger.warning(f"Received update for unknown/completed task ID: {task_id}. Ignoring.")
            # Optionally inform sender?
            # await self.publish_system_message(f"Task ID {task_id} not found or already completed.", sender=sender)
            return

        # Update history
        self.task_states[task_id]["history"].append(f"Update from {sender} ({task_update.event.value}): {task_update.content[:100]}...")
        self.task_states[task_id]["status"] = task_update.event # Update status based on received event


        # --- Simple Debate/Workflow Logic ---
        current_step = self.task_states[task_id].get("current_step", "unknown")
        original_requester = self.task_states[task_id]["original_requester"]

        next_agent = None
        next_action_description = ""
        next_event = TaskEvent.INFO # Default next event

        if task_update.event == TaskEvent.FAIL or task_update.outcome == TaskOutcome.FAILURE:
             logger.error(f"Task {task_id} failed at step '{current_step}'. Reporting error.")
             await self.publish_error(task_id, f"Agent {sender} reported failure: {task_update.content}", original_requester)
             del self.task_states[task_id] # End task state
             return

        if task_update.event == TaskEvent.COMPLETE and task_update.outcome == TaskOutcome.SUCCESS:
            logger.success(f"Task {task_id} completed by {sender}. Final result: {task_update.content[:100]}...")
            # Forward final result to original requester and potentially broadcast
            final_result = TaskResultFactory.create_task_result(
                 task_id=task_id,
                 agent=sender, # Keep original sender as the reporting agent
                 content=task_update.content,
                 target_agent=original_requester,
                 event=TaskEvent.COMPLETE,
                 outcome=TaskOutcome.SUCCESS,
                 confidence=task_update.confidence,
                 contributing_agents=task_update.contributing_agents
            )
            await self.publish_to_agent(original_requester, final_result) # Specific target needed if not user
            await self.publish_to_frontend(final_result)
            del self.task_states[task_id] # End task state
            return

        # --- Placeholder Debate Round Logic ---
        # Round 1: GPT proposes -> Send to Claude for critique
        if sender == settings.GPT_AGENT_NAME and current_step == "initial_proposal":
            next_agent = settings.CLAUDE_AGENT_NAME
            next_action_description = "Requesting critique of initial proposal."
            self.task_states[task_id]["current_step"] = "critique"
            next_event = TaskEvent.CRITIQUE

        # Round 2: Claude critiques -> Send back to GPT for refinement
        elif sender == settings.CLAUDE_AGENT_NAME and current_step == "critique":
            next_agent = settings.GPT_AGENT_NAME
            next_action_description = "Requesting refinement based on critique."
            self.task_states[task_id]["current_step"] = "refine"
            next_event = TaskEvent.REFINE
            self.task_states[task_id]["round"] += 1

        # Round 3: GPT refines -> Send to Claude for final conclusion/arbitration
        elif sender == settings.GPT_AGENT_NAME and current_step == "refine":
            # Simple loop detection/limit
            if self.task_states[task_id]["round"] >= 3: # Limit rounds
                 logger.warning(f"Task {task_id} reached round limit. Forcing conclusion.")
                 next_agent = settings.CLAUDE_AGENT_NAME
                 next_action_description = "Maximum rounds reached. Requesting final conclusion."
                 self.task_states[task_id]["current_step"] = "conclude"
                 next_event = TaskEvent.CONCLUDE
            else:
                 next_agent = settings.CLAUDE_AGENT_NAME
                 next_action_description = "Requesting evaluation of refined proposal."
                 # Keep in critique step? Or move to a new 'evaluate_refinement' step?
                 self.task_states[task_id]["current_step"] = "critique" # Go back to critique
                 next_event = TaskEvent.CRITIQUE # Ask Claude to critique again

        # Round 4: Claude concludes -> Task finished
        elif sender == settings.CLAUDE_AGENT_NAME and current_step == "conclude":
             logger.info(f"Task {task_id}: Claude provided final conclusion. Completing task.")
             # Claude's conclusion message IS the final result here
             final_content = f"Final Conclusion by {sender}: {task_update.content}"
             await self.publish_completion(task_id, final_content, original_requester, task_update.confidence)
             del self.task_states[task_id]
             return # End processing

        # Handle tool results specifically - typically resume previous flow
        elif task_update.event == TaskEvent.TOOL_COMPLETE:
             logger.info(f"Task {task_id}: Received tool result from {sender}. Forwarding to originating agent.")
             # Find out who was waiting for the tool (needs better state tracking)
             # For now, assume the last active agent (e.g., GPT) needs it. This is brittle!
             # A better approach: store 'waiting_for_tool' state with the requesting agent name.
             originating_agent = settings.GPT_AGENT_NAME # HACK: Assume GPT requested it
             next_agent = originating_agent
             next_action_description = f"Forwarding tool result for {task_update.content[:50]}..."
             # Set the event to indicate the tool result is being provided
             next_event = TaskEvent.TOOL_COMPLETE # Or maybe just INFO/MODIFY_TASK

        else:
            logger.warning(f"Task {task_id}: Unhandled state transition from agent {sender} in step '{current_step}' with event '{task_update.event.value}'. No action taken.")
            # Maybe just broadcast the update to the frontend?
            await self.publish_to_frontend(task_update)
            return # Don't proceed if state is unhandled

        # --- Send next step instruction ---
        if next_agent:
            logger.info(f"Task {task_id}: {next_action_description} Sending to {next_agent}.")

            # Create message/task for the next agent, including context/history if needed
            next_task = TaskFactory.create_task(
                 agent=self.agent_name,
                 # Pass the previous agent's content as the new task content
                 content=f"Context: {next_action_description}\nPrevious Output from {sender}:\n---\n{task_update.content}\n---\nPlease perform your role.",
                 target_agent=next_agent,
                 task_id=task_id,
                 intent=MessageIntent.MODIFY_TASK, # It's modifying the ongoing task state
                 event=next_event # Instruct the agent on the expected action
            )
            await self.publish_to_agent(next_agent, next_task)
            await self.publish_to_frontend(next_task) # Inform frontend of the transition
        else:
             logger.debug(f"Task {task_id}: No next agent determined for update from {sender} in step {current_step}.")


    async def handle_chat_message(self, message: Message):
        """Handles general chat messages, potentially broadcasting or interpreting commands."""
        logger.info(f"{self.agent_name} received CHAT from {message.agent}: {message.content[:50]}...")

        # Simple broadcast to frontend for now
        # Add command parsing later if needed (e.g., "/status task_id")
        if message.agent != self.agent_name: # Avoid echoing own messages if subscribed broadly
            await self.publish_to_frontend(message)


    async def handle_check_status(self, message: BaseMessage):
         task_id = message.task_id
         requester = message.agent
         logger.info(f"{self.agent_name} received CHECK_STATUS for task {task_id} from {requester}")
         if task_id in self.task_states:
             state = self.task_states[task_id]
             status_msg = f"Task {task_id} status: {state.get('status', 'Unknown')}. Current step: {state.get('current_step', 'Unknown')}. Round: {state.get('round', 'N/A')}."
             await self.publish_update(task_id, TaskEvent.INFO, status_msg, requester)
         else:
             status_msg = f"Task {task_id} not found or already completed."
             await self.publish_update(task_id, TaskEvent.INFO, status_msg, requester)


    async def handle_tool_response(self, tool_result: TaskResult):
        """Grok might receive tool responses if it needs to coordinate based on them."""
        # This might be redundant if handle_modify_task covers TOOL_COMPLETE events
        logger.info(f"{self.agent_name} received TOOL_RESPONSE (TaskID: {tool_result.task_id}) from {tool_result.agent}.")
        # Potentially forward or process based on the current task state
        # For now, assuming handle_modify_task manages TOOL_COMPLETE events sufficiently.
        await self.handle_modify_task(tool_result) # Delegate to main logic

    # --- Placeholder methods for Abstract Base Class ---
    async def get_notes(self) -> Dict[str, Any]:
         # Return current state overview
         return {
              "agent": self.agent_name,
              "active_tasks": list(self.task_states.keys()),
              "task_details": self.task_states # Maybe truncate history
         }

    async def process_response(self, response: Any, originating_agent: str):
         # Generic response processing if needed, likely handled by handle_modify_task
         logger.debug(f"{self.agent_name} received generic response from {originating_agent}, delegating...")
         # Attempt to parse and route
         # This might be needed if agents send non-standard messages
         if isinstance(response, (Task, TaskResult, Message)):
             await self.handle_modify_task(response) # Try standard handler
         else:
             logger.warning(f"Received non-standard response type {type(response)} from {originating_agent}")

# --- Agent Entry Point ---
async def main():
    agent = GrokAgent()
    await agent.start()
    try:
        # Keep the agent running indefinitely
        while True:
            await asyncio.sleep(3600) # Sleep for an hour, or use asyncio.Event
    except asyncio.CancelledError:
        logger.info("GrokAgent main task cancelled.")
    finally:
        await agent.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("GrokAgent stopped by user.")