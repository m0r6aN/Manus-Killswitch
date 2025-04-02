# Pydantic schemas for ToolCore API

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any, Literal
import json
import datetime as dt

# --- Tool Schemas ---

class ToolBase(BaseModel):
    name: str = Field(..., min_length=1, description="Unique name of the tool.")
    description: Optional[str] = Field(None, description="Detailed description of what the tool does.")
    parameters: Optional[str] = Field(None, description="JSON schema string defining input parameters.")
    path: Optional[str] = Field(None, description="Path to the script/module file relative to the tools directory.")
    entrypoint: Optional[str] = Field(None, description="Function name or script filename.")
    type: Literal['script', 'function', 'module'] = Field(..., description="Type of the tool.")
    version: str = Field("1.0.0", description="Version of the tool.")
    tags: Optional[str] = Field(None, description="JSON array string or comma-separated list of tags.")
    active: bool = Field(True, description="Whether the tool is active and usable.")

    @field_validator('parameters')
    @classmethod
    def validate_parameters_json(cls, v):
        if v is None:
            return v
        try:
            json.loads(v)
        except json.JSONDecodeError:
            raise ValueError("Parameters must be a valid JSON string or null.")
        return v

    @field_validator('tags')
    @classmethod
    def validate_tags_format(cls, v):
        if v is None:
            return v
        # Allow either comma-separated or JSON array string
        try:
            parsed = json.loads(v)
            if not isinstance(parsed, list):
                raise ValueError("If tags is JSON, it must be an array.")
        except json.JSONDecodeError:
            # If not JSON, assume comma-separated (no strict validation here)
            pass
        return v

    @model_validator(mode='after')
    def check_path_and_entrypoint(self) -> 'ToolBase':
        if self.type == 'script':
            if not self.path:
                 raise ValueError("Path is required for script type tools.")
            # Entrypoint for script usually implies the script file itself, often redundant with path
            if not self.entrypoint:
                 self.entrypoint = self.path # Default entrypoint to path for scripts
        # Add checks for 'function' and 'module' if needed
        # elif self.type == 'function':
        #     if not self.entrypoint:
        #         raise ValueError("Entrypoint (function name) is required for function type tools.")
        #     # Path might store the module containing the function
        #     if not self.path:
        #          raise ValueError("Path (module file) is required for function type tools.")
        return self


class ToolCreate(ToolBase):
    pass # Inherits all fields and validation

class ToolUpdate(ToolBase):
    # Make all fields optional for PUT requests
    name: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    parameters: Optional[str] = None
    path: Optional[str] = None
    entrypoint: Optional[str] = None
    type: Optional[Literal['script', 'function', 'module']] = None
    version: Optional[str] = None
    tags: Optional[str] = None
    active: Optional[bool] = None

    # Need to re-run validation if type/path change
    @model_validator(mode='after')
    def check_path_and_entrypoint_on_update(self) -> 'ToolUpdate':
         # Only perform check if type or path is being updated
         if self.type or self.path:
             temp_type = self.type or 'script' # Assume script if type not provided but path is
             temp_path = self.path
             if temp_type == 'script' and not temp_path:
                 # This validation is tricky on update, as the existing value might suffice.
                 # Maybe skip strict validation here or fetch existing record first in PUT route.
                 pass # Relaxing for update, assuming existing value is okay if not provided
         return self

class ToolRead(ToolBase):
    id: int
    created_at: dt.datetime
    updated_at: Optional[dt.datetime] = None

    class Config:
        from_attributes = True # Pydantic v2 replacement for orm_mode


# --- Execution Schemas ---

class ToolExecutionRequest(BaseModel):
    tool_name: str = Field(..., description="Name of the tool to execute.")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Input parameters for the tool.")
    dry_run: bool = Field(False, description="If true, validate inputs but do not execute.")
    requesting_agent: Optional[str] = Field(None, description="Name of the agent requesting execution.")
    task_id: Optional[str] = Field(None, description="Associated task ID, for context and tracking.")


class ToolExecutionResponse(BaseModel):
    status: Literal["acknowledged", "completed", "failed", "validation_error", "not_found"]
    message: str
    result: Optional[Any] = Field(None, description="Output from the tool execution, if successful and synchronous.")
    error: Optional[str] = Field(None, description="Error message if execution failed.")
    validation_errors: Optional[Dict[str, Any]] = Field(None, description="Details of parameter validation errors.")
    execution_id: Optional[str] = Field(None, description="Unique ID for tracking asynchronous execution.")