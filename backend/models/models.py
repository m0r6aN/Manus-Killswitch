import datetime as dt
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator

# --- Enums ---

class MessageIntent(str, Enum):
    CHAT = "chat"                     # General communication between agents or user->agent
    START_TASK = "start_task"         # Initiate a new task for an agent
    CHECK_STATUS = "check_status"     # Request status update on a task
    MODIFY_TASK = "modify_task"       # Modify or provide feedback on an ongoing task/result
    TOOL_REQUEST = "tool_request"     # Agent requests execution of a tool
    TOOL_RESPONSE = "tool_response"   # ToolCore responds with tool execution result
    HEARTBEAT = "heartbeat"           # Agent heartbeat signal (internal, might not be a full message)
    SYSTEM = "system"                 # System-level messages (e.g., agent status, errors)
    ORCHESTRATION = "orchestration"   # Messages related to managing agent interaction (e.g., Grok signals)
    GENERATE_WORKFLOW = "generate_workflow" 
    WORKFLOW_STEP = "workflow_step"   # <-- Maybe add for Grok assigning steps?

class TaskEvent(str, Enum):
    PLAN = "plan"                     # Agent is planning the task
    EXECUTE = "execute"               # Agent is executing the task (or sub-step)
    CRITIQUE = "critique"             # Agent is critiquing a response (Claude's role)
    REFINE = "refine"                 # Agent is refining based on critique/feedback (GPT-4o's role)
    CONCLUDE = "conclude"             # Agent is concluding the debate/task (Claude's role)
    COMPLETE = "complete"             # Task is successfully completed
    FAIL = "fail"                     # Task failed
    ESCALATE = "escalate"             # Task requires escalation or human intervention
    INFO = "info"                     # General informational update about the task
    AWAITING_TOOL = "awaiting_tool"   # Agent is waiting for a tool result
    TOOL_COMPLETE = "tool_complete"   # Tool execution finished

class TaskOutcome(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"

class ReasoningEffort(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    
def get_reasoning_strategy(effort: ReasoningEffort) -> str:
    """
    Maps reasoning effort to a cognitive strategy the agent should use.
    """
    if effort == ReasoningEffort.LOW:
        return "direct_answer"
    elif effort == ReasoningEffort.MEDIUM:
        return "chain-of-thought"
    elif effort == ReasoningEffort.HIGH:
        return "chain-of-draft"
    return "unknown"
    
class ReasoningStrategy(str, Enum):
    DIRECT = "direct_answer"
    COT = "chain-of-thought"
    COD = "chain-of-draft"
    
# --- Core Message/Task Models ---

class BaseMessage(BaseModel):
    type: str = Field(..., description="Message type identifier")
    timestamp: dt.datetime = Field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc),
        description="UTC timestamp"
    )
    
    model_config = {
        "json_encoders": {dt.datetime: lambda v: v.isoformat()}
    }

    def serialize(self) -> str:
        # Pydantic v2 uses model_dump_json
        return self.model_dump_json()

    @classmethod
    def deserialize(cls, data: str) -> 'BaseMessage':
        # Pydantic v2 uses model_validate_json
        return cls.model_validate_json(data)

class Message(BaseMessage):
    """Model for general chat or informational messages."""
    content: str
    intent: MessageIntent = MessageIntent.CHAT
    target_agent: Optional[str] = None # Optional: Direct message to specific agent

class Task(BaseMessage):
    """Model representing a task assigned to an agent."""
    content: str # Description of the task
    target_agent: str # The agent assigned to the task
    intent: MessageIntent = MessageIntent.START_TASK
    event: TaskEvent = TaskEvent.PLAN # Current state/event of the task
    confidence: Optional[float] = Field(default=0.9, ge=0.0, le=1.0) # Agent's confidence in its current step/plan
    reasoning_effort: Optional[ReasoningEffort] = None # Estimated effort
    reasoning_strategy: Optional[ReasoningStrategy] = Field(None, description="Agent thinking strategy, e.g., chain-of-thought")
    metadata: Optional[Dict[str, Any]] = None # Additional context

    # Re-validate effort on creation based on content/event/intent
    @model_validator(mode='before')
    @classmethod
    def set_reasoning_effort(cls, values):
        from backend.factories.factories import estimate_reasoning_effort # Avoid circular import
        content = values.get('content')
        event = values.get('event')
        intent = values.get('intent')
        if content and not values.get('reasoning_effort'): # Only estimate if not provided
             values['reasoning_effort'] = estimate_reasoning_effort(content, event.value if event else None, intent.value if intent else None)
        return values
    
class SystemStatusMessage(BaseMessage):
    system_ready: bool = Field(..., description="Whether the system is ready")
    agent_status: Dict[str, str] = Field(..., description="Status of each agent")
    
    # Set the type field automatically
    type: str = "system_status_update"


class TaskResult(Task):
    """Model representing the result or update of a task."""
    outcome: TaskOutcome
    contributing_agents: List[str] = Field(default_factory=list)

    # Ensure intent is appropriate for a result/update
    @field_validator('intent')
    @classmethod
    def check_intent(cls, v):
        # Allow MODIFY_TASK for feedback/updates, TOOL_RESPONSE for tool results
        allowed_intents = {MessageIntent.MODIFY_TASK, MessageIntent.TOOL_RESPONSE, MessageIntent.SYSTEM}
        if v not in allowed_intents:
            # Forcing it to MODIFY_TASK if it's clearly a result/update
            return MessageIntent.MODIFY_TASK
            # raise ValueError(f"TaskResult intent must be one of {allowed_intents}")
        return v

    # Ensure event reflects a state of completion or update
    @field_validator('event')
    @classmethod
    def check_event(cls, v):
        # Events like COMPLETE, FAIL, INFO, REFINE, CONCLUDE, TOOL_COMPLETE are suitable
        disallowed_events = {TaskEvent.PLAN, TaskEvent.EXECUTE, TaskEvent.CRITIQUE} # Starting events
        if v in disallowed_events:
             # Force to INFO if an unsuitable starting event is used for a result
             return TaskEvent.INFO
            # raise ValueError(f"TaskResult event cannot be one of {disallowed_events}")
        return v


# --- ToolCore Models (Used by ToolCore API, might overlap/refine later) ---

# Defined in backend.agents.tools_agent.schemas
# Example reference:
# from backend.agents.tools_agent.schemas import ToolCreate, ToolRead, ToolExecutionRequest

# --- WebSocket Message Model ---

class WebSocketMessage(BaseModel):
    """Model for messages exchanged via WebSocket between Frontend and WS Server."""
    type: str # e.g., 'chat_message', 'start_task', 'agent_update', 'system_info', 'error'
    payload: Dict[str, Any] # Contains the actual data, could be a serialized Message, Task, etc.
    client_id: Optional[str] = None # Optional: Identifier for the frontend client connection
    timestamp: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))

    def serialize(self) -> str:
        return self.model_dump_json()

    @classmethod
    def deserialize(cls, data: str) -> 'WebSocketMessage':
        return cls.model_validate_json(data)

