# Task, Message, Result factories + Reasoning Effort

import datetime as dt
from typing import List, Optional
from enum import Enum
import uuid

from backend.models.models import (
    Message,
    Task,
    TaskResult,
    MessageIntent,
    TaskEvent,
    TaskOutcome,
    ReasoningEffort,
)
from backend.core.config import logger

# --- Reasoning Effort Estimation ---

def estimate_reasoning_effort(content: str, event: Optional[str] = None, intent: Optional[str] = None) -> ReasoningEffort:
    """
    Automatically determines computational effort required for tasks based on content and context.
    """
    if not isinstance(content, str):
        logger.warning(f"Invalid content type for reasoning effort estimation: {type(content)}. Defaulting to LOW.")
        return ReasoningEffort.LOW

    keywords = {"analyze", "evaluate", "optimize", "debate", "compare", "hypothesize", "refactor", "critique", "reconcile", "arbitrate", "generate", "summarize"}
    word_count = len(content.split())
    content_lower = content.lower()
    has_keywords = any(kw in content_lower for kw in keywords)

    # Base effort on length and keywords
    if word_count <= 10 and not has_keywords:
        effort = ReasoningEffort.LOW
    elif word_count > 50 or has_keywords: # Increased threshold for high
        effort = ReasoningEffort.HIGH
    elif word_count > 15: # Medium range
        effort = ReasoningEffort.MEDIUM
    else:
        effort = ReasoningEffort.LOW # Default short non-keyword to low

    # Adjust based on context (event/intent)
    high_effort_events = {TaskEvent.REFINE.value, TaskEvent.ESCALATE.value, TaskEvent.CRITIQUE.value, TaskEvent.CONCLUDE.value}
    high_effort_intents = {MessageIntent.MODIFY_TASK.value, MessageIntent.START_TASK.value} # Starting a task often needs more effort

    if event and event in high_effort_events:
        # logger.debug(f"Effort overridden to HIGH due to event: {event}")
        effort = ReasoningEffort.HIGH
    elif intent and intent in high_effort_intents and effort != ReasoningEffort.HIGH:
         # Bump medium to high, keep low as low unless keywords/length triggered high
         if effort == ReasoningEffort.MEDIUM:
             # logger.debug(f"Effort promoted to HIGH due to intent: {intent}")
             effort = ReasoningEffort.HIGH
         elif effort == ReasoningEffort.LOW and (word_count > 15 or has_keywords): # If it was borderline low but has some indicators
              effort = ReasoningEffort.MEDIUM
              # logger.debug(f"Effort promoted to MEDIUM due to intent: {intent} and content indicators")


    logger.trace(f"Estimated effort: {effort.value} for content (first 50 chars): '{content[:50]}...' (Event: {event}, Intent: {intent})")
    return effort

# --- Object Factories ---

class TaskFactory:
    """Creates Task objects with automated reasoning effort assessment."""
    @staticmethod
    def create_task(
        agent: str,
        content: str,
        target_agent: str,
        task_id: Optional[str] = None,
        intent: MessageIntent = MessageIntent.START_TASK,
        event: TaskEvent = TaskEvent.PLAN,
        confidence: Optional[float] = 0.9,
        timestamp: Optional[dt.datetime] = None
    ) -> Task:
        """
        Creates a Task object, automatically estimating reasoning effort.
        """
        if task_id is None:
            task_id = str(uuid.uuid4())

        # Estimate effort using the dedicated function
        reasoning_effort = estimate_reasoning_effort(content, event.value, intent.value)

        logger.debug(f"Creating Task (ID: {task_id}): Target={target_agent}, Intent={intent.value}, Event={event.value}, Effort={reasoning_effort.value}")

        return Task(
            task_id=task_id,
            agent=agent, # Originating agent/user
            content=content,
            intent=intent,
            target_agent=target_agent,
            event=event,
            confidence=confidence,
            timestamp=timestamp or dt.datetime.now(dt.timezone.utc),
            reasoning_effort=reasoning_effort
        )

class MessageFactory:
    """Generates Message objects for agent communication."""
    @staticmethod
    def create_message(
        task_id: str,
        agent: str,
        content: str,
        intent: MessageIntent = MessageIntent.CHAT,
        target_agent: Optional[str] = None,
        timestamp: Optional[dt.datetime] = None
    ) -> Message:
        """
        Creates a standard Message object.
        """
        logger.debug(f"Creating Message (TaskID: {task_id}): Agent={agent}, Intent={intent.value}, Target={target_agent}")
        return Message(
            task_id=task_id,
            agent=agent,
            content=content,
            intent=intent,
            target_agent=target_agent,
            timestamp=timestamp or dt.datetime.now(dt.timezone.utc)
        )

class TaskResultFactory:
    """Produces TaskResult objects to encapsulate task outcomes."""
    @staticmethod
    def create_task_result(
        task_id: str,
        agent: str, # The agent reporting the result
        content: str, # Description of the result or update
        target_agent: str, # Who should receive this result (e.g., orchestrator, original requester)
        event: TaskEvent, # The event associated with this result (e.g., COMPLETE, REFINE, INFO)
        outcome: TaskOutcome, # Success/failure status
        contributing_agents: Optional[List[str]] = None,
        confidence: Optional[float] = 0.9,
        reasoning_effort: Optional[ReasoningEffort] = None, # Can be passed if known, otherwise estimated
        timestamp: Optional[dt.datetime] = None
    ) -> TaskResult:
        """
        Creates a TaskResult object. Estimates reasoning effort if not provided.
        """
        if reasoning_effort is None:
            # Estimate effort based on the *result* content and context
            reasoning_effort = estimate_reasoning_effort(content, event.value, MessageIntent.MODIFY_TASK.value) # Assume modify intent for results

        logger.debug(f"Creating TaskResult (TaskID: {task_id}): Agent={agent}, Event={event.value}, Outcome={outcome.value}, Effort={reasoning_effort.value}")

        return TaskResult(
            task_id=task_id,
            agent=agent,
            content=content,
            # Intent is tricky for results, MODIFY_TASK seems most appropriate for updates/feedback
            intent=MessageIntent.MODIFY_TASK,
            target_agent=target_agent,
            event=event,
            outcome=outcome,
            contributing_agents=contributing_agents or [agent], # Default to self if not specified
            confidence=confidence,
            reasoning_effort=reasoning_effort,
            timestamp=timestamp or dt.datetime.now(dt.timezone.utc)
        )

# Example Usage (for testing purposes)
if __name__ == "__main__":
    logger.info("Testing Factories...")

    # Test Reasoning Effort
    print("-" * 20)
    logger.info("Reasoning Effort Tests:")
    test_cases = [
        ("Simple chat", None, MessageIntent.CHAT.value),
        ("Analyze the results and compare", TaskEvent.PLAN.value, MessageIntent.START_TASK.value),
        ("Just a quick update.", TaskEvent.INFO.value, MessageIntent.MODIFY_TASK.value),
        ("Refine the proposal based on feedback.", TaskEvent.REFINE.value, MessageIntent.MODIFY_TASK.value),
        ("Summarize this very long document that requires careful reading and extraction of key points to ensure accuracy.", TaskEvent.EXECUTE.value, MessageIntent.START_TASK.value),
        (12345, None, None) # Invalid content test
    ]
    for content, event, intent in test_cases:
        effort = estimate_reasoning_effort(content, event, intent)
        logger.info(f"Content: '{str(content)[:30]}...' -> Effort: {effort.value}")

    print("-" * 20)
    logger.info("Factory Creation Tests:")
    # Test TaskFactory
    task = TaskFactory.create_task(
        agent="user",
        content="Please analyze the latest market trends for AI hardware.",
        target_agent="grok"
    )
    logger.info(f"Created Task: {task.model_dump_json(indent=2)}")

    # Test MessageFactory
    msg = MessageFactory.create_message(
        task_id=task.task_id,
        agent="grok",
        content="Acknowledged. Starting analysis.",
        target_agent="user"
    )
    logger.info(f"Created Message: {msg.model_dump_json(indent=2)}")

    # Test TaskResultFactory
    result = TaskResultFactory.create_task_result(
        task_id=task.task_id,
        agent="gpt",
        content="Analysis complete. Key trend is the rise of edge TPU devices. Confidence: 0.85",
        target_agent="claude", # Send to Claude for arbitration maybe
        event=TaskEvent.COMPLETE,
        outcome=TaskOutcome.SUCCESS,
        confidence=0.85,
        contributing_agents=["gpt", "tools-agent"]
    )
    logger.info(f"Created TaskResult: {result.model_dump_json(indent=2)}")
    logger.info("Factory tests complete.")