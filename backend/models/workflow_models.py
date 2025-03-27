from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Literal, Union
import uuid

class WorkflowDependency(BaseModel):
    task_id: str = Field(..., description="ID of the task this task depends on.")
    dependency_type: Literal['completion', 'data_availability'] = Field('completion', description="Type of dependency.")
    is_blocking: bool = Field(True, description="Does this dependency block execution until met?")

class WorkflowTaskAssignment(BaseModel):
    agent: Optional[str] = Field(None, description="Suggested agent to perform the task.")
    tools: List[str] = Field(default_factory=list, description="Suggested tools required for the task.")

class WorkflowTask(BaseModel):
    # Let's generate ID dynamically if not provided by LLM
    id: str = Field(default_factory=lambda: f"task-{uuid.uuid4().hex[:8]}", description="Unique identifier for the task within the workflow.")
    name: str = Field(..., description="Human-readable name of the task.")
    description: str = Field(..., description="Detailed description of what the task entails.")
    types: List[str] = Field(default_factory=list, description="Categorical types of the task (e.g., DATA_EXTRACTION, CONTENT_CREATION).")
    required_capabilities: List[str] = Field(default_factory=list, description="Specific capabilities needed (e.g., database_access, copywriting).")
    dependencies: List[WorkflowDependency] = Field(default_factory=list, description="List of tasks this task depends on.")
    execution_order: int = Field(..., ge=1, description="Logical execution order or phase number.")
    can_parallelize: bool = Field(False, description="Whether this task can run in parallel with others of the same execution order.")
    estimated_complexity: Optional[float] = Field(None, ge=0, description="Estimated complexity score (e.g., 1-5).")
    expected_duration: Optional[int] = Field(None, ge=0, description="Estimated duration in seconds.")
    assignments: WorkflowTaskAssignment = Field(default_factory=WorkflowTaskAssignment, description="Suggested agent and tool assignments.")
    needs_review: Optional[bool] = Field(None, description="Flag if this task step requires manual review.")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Specific input parameters needed for this task.")
    output_schema: Optional[Dict[str, Any]] = Field(None, description="Expected output data structure/schema from this task.")

    @validator('id', pre=True, always=True)
    def set_id_if_none(cls, v):
        return v or f"task-{uuid.uuid4().hex[:8]}"

class WorkflowPlan(BaseModel):
    # The root model is simply a list of tasks
    __root__: List[WorkflowTask]

    # Allow iteration directly over the list
    def __iter__(self):
        return iter(self.__root__)

    def __getitem__(self, item):
        return self.__root__[item]

    def __len__(self):
        return len(self.__root__)

# Input model for the workflow generation request
class WorkflowGenerationRequest(BaseModel):
    prompt: str
    target_model: Optional[str] = None
    # Could add context, existing tools, agent capabilities etc. later