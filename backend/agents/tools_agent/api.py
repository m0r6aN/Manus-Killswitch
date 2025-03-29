import json
from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Any, List, Optional, Union
from sqlalchemy.ext.asyncio import AsyncSession

from . import crud, models, schemas, executor
from .db.database import get_db, init_db, close_db
from backend.core.config import logger, settings
# Import models from the main models package if needed for communication
from backend.models.models import TaskResult, MessageIntent, TaskEvent, TaskOutcome
from backend.factories.factories import TaskResultFactory
# Import redis client for potential async result reporting
from backend.core.redis_client import get_redis_pool, publish_message
import redis.asyncio as redis
import uuid

# --- DEFINE LIFESPAN FUNCTION ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup Logic ---
    logger.info("Starting ToolCore API (lifespan) with hot reload...")
    await init_db() # Initialize the database and create tables
    # We don't necessarily need to get/store the redis pool on app.state here,
    # as routes get it via Depends(get_redis_pool).
    # If needed elsewhere during startup/shutdown, you could add:
    # app.state.redis_pool = await get_redis_pool()
    logger.info("ToolCore API startup complete.")

    yield # Application runs here

    # --- Shutdown Logic ---
    logger.info("Shutting down ToolCore API (lifespan)...")
    # Optional: Explicitly close DB engine connections if needed
    # await close_db()
    # Optional: Close global redis pool if this were the only app using it
    # await close_redis_pool()
    logger.info("ToolCore API shutdown complete.")
# --- END LIFESPAN FUNCTION ---


# --- FastAPI INSTANTIATION ---
app = FastAPI(
    title="Manus ToolCore API",
    description="API for managing and executing tools within the Manus Killswitch Framework.",
    version="1.0.0",
    lifespan=lifespan # Pass the lifespan manager
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # More permissive for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Health Check Endpoint ---
@app.get("/health", tags=["Health"])
async def health_check():
    """Basic health check endpoint."""
    # Could add checks for DB and Redis connectivity here
    return {"status": "ok"}

# --- Tool Management Endpoints ---
@app.post("/tools/", response_model=schemas.ToolRead, status_code=201, tags=["Tool Management"])
async def create_tool_endpoint(
    tool: schemas.ToolCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new tool in the ToolCore registry.
    """
    try:
        return await crud.create_tool(db=db, tool=tool)
    except ValueError as e:
        logger.warning(f"Failed to create tool: {e}")
        raise HTTPException(status_code=409, detail=str(e)) # 409 Conflict for duplicate name
    except Exception as e:
        logger.exception(f"Unexpected error creating tool: {e}")
        raise HTTPException(status_code=500, detail="Internal server error creating tool.")


@app.get("/tools/", response_model=List[schemas.ToolRead], tags=["Tool Management"])
async def read_tools_endpoint(
    skip: int = 0,
    limit: int = 100,
    q: Optional[str] = Query(None, description="Search query for tool name or description"),
    tags: Optional[str] = Query(None, description="Comma-separated list of tags to filter by"),
    type: Optional[str] = Query(None, description="Filter by tool type (script, function, module)"),
    active_only: bool = Query(True, description="Return only active tools"),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve a list of registered tools, with optional filtering and pagination.
    """
    tools = await crud.get_tools(db=db, skip=skip, limit=limit, q=q, tags=tags, tool_type=type, active_only=active_only)
    return tools


@app.get("/tools/{tool_id_or_name}", response_model=schemas.ToolRead, tags=["Tool Management"])
async def read_tool_endpoint(
    tool_id_or_name: Union[int, str],
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve a specific tool by its ID or unique name.
    """
    db_tool = None
    if isinstance(tool_id_or_name, int):
        db_tool = await crud.get_tool_by_id(db=db, tool_id=tool_id_or_name)
    else:
        db_tool = await crud.get_tool_by_name(db=db, name=tool_id_or_name)

    if db_tool is None:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_id_or_name}' not found")
    return db_tool


@app.put("/tools/{tool_id}", response_model=schemas.ToolRead, tags=["Tool Management"])
async def update_tool_endpoint(
    tool_id: int,
    tool_update: schemas.ToolUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update an existing tool by its ID. Only provided fields will be updated.
    """
    try:
        db_tool = await crud.update_tool(db=db, tool_id=tool_id, tool_update=tool_update)
        if db_tool is None:
            raise HTTPException(status_code=404, detail=f"Tool with ID {tool_id} not found")
        return db_tool
    except ValueError as e: # Handle name conflict from crud.update_tool
        logger.warning(f"Failed to update tool ID {tool_id}: {e}")
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error updating tool ID {tool_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error updating tool.")


@app.delete("/tools/{tool_id}", response_model=schemas.ToolRead, tags=["Tool Management"])
async def delete_tool_endpoint(
    tool_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a tool by its ID.
    """
    db_tool = await crud.delete_tool(db=db, tool_id=tool_id)
    if db_tool is None:
        raise HTTPException(status_code=404, detail=f"Tool with ID {tool_id} not found")
    # The object returned by crud.delete_tool still holds the data before deletion
    return db_tool

# --- Tool Execution Endpoint ---

async def report_execution_result(
    redis_client: redis.Redis,
    task_id: str,
    requesting_agent: str,
    tool_name: str,
    success: bool,
    result: Optional[Any] = None,
    error: Optional[str] = None
):
    """Helper to send execution results back via Redis."""
    if not task_id or not requesting_agent:
        logger.warning("Cannot report tool result: Missing task_id or requesting_agent.")
        return

    target_channel = f"{requesting_agent}_channel" # Send directly to agent's channel
    logger.debug(f"Reporting tool '{tool_name}' result for task {task_id} to channel {target_channel}")

    if success:
        outcome = TaskOutcome.SUCCESS
        event = TaskEvent.TOOL_COMPLETE
        content = json.dumps(result) if result is not None else "Tool executed successfully (no content)."
        confidence = 1.0
    else:
        outcome = TaskOutcome.FAILURE
        event = TaskEvent.FAIL # Use FAIL event for tool failures
        content = f"Tool '{tool_name}' execution failed: {error or 'Unknown error'}"
        confidence = 0.0

    task_result_msg = TaskResultFactory.create_task_result(
        task_id=task_id,
        agent=settings.TOOLS_AGENT_NAME, # Result is from ToolCore
        content=content,
        target_agent=requesting_agent, # Target the agent who requested it
        event=event,
        outcome=outcome,
        confidence=confidence
    )

    await publish_message(redis_client, target_channel, task_result_msg.serialize())
    # Optionally also publish to frontend?
    # await publish_message(redis_client, settings.FRONTEND_CHANNEL, task_result_msg.serialize())

async def execute_tool_background(
    db: AsyncSession,
    redis_client: redis.Redis,
    tool: models.Tool,
    parameters: dict,
    task_id: str,
    requesting_agent: str
):
    """Background task to execute the tool and report result via Redis."""
    logger.info(f"[BG Task] Executing tool '{tool.name}' for task {task_id}")
    success, result, error, _ = await executor.execute_tool(tool, parameters, dry_run=False)
    logger.info(f"[BG Task] Execution of '{tool.name}' completed. Success: {success}")

    await report_execution_result(
        redis_client=redis_client,
        task_id=task_id,
        requesting_agent=requesting_agent,
        tool_name=tool.name,
        success=success,
        result=result,
        error=error
    )
    # Explicitly close the session used by the background task if get_db isn't used
    # If get_db *is* used via Depends, FastAPI handles it. But here we might need manual handling.
    # However, `get_db` uses AsyncSessionFactory which should manage sessions correctly.
    # Let's assume session management is okay for now. If issues arise, revisit this.
    # await db.close() # Potentially needed depending on session scope

@app.post("/execute/", response_model=schemas.ToolExecutionResponse, tags=["Tool Execution"])
async def execute_tool_endpoint(
    request: schemas.ToolExecutionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_pool) # Get redis pool via dependency
):
    """
    Execute a specified tool with given parameters.
    Supports dry runs and asynchronous execution with results reported via Redis.
    """
    tool_name = request.tool_name
    parameters = request.parameters
    dry_run = request.dry_run
    task_id = request.task_id or str(uuid.uuid4()) # Generate ID if not provided
    requesting_agent = request.requesting_agent or "unknown_agent"

    logger.info(f"Received execution request for tool '{tool_name}' (TaskID: {task_id}, Agent: {requesting_agent}, DryRun: {dry_run})")

    # 1. Find the tool
    db_tool = await crud.get_tool_by_name(db, tool_name)
    if not db_tool:
        logger.warning(f"Execution request failed: Tool '{tool_name}' not found.")
        return schemas.ToolExecutionResponse(
            status="not_found",
            message=f"Tool '{tool_name}' not found."
        )
    if not db_tool.active:
         logger.warning(f"Execution request failed: Tool '{tool_name}' is inactive.")
         return schemas.ToolExecutionResponse(
             status="failed",
             message=f"Tool '{tool_name}' is currently inactive."
         )

    # 2. Validate parameters (also done inside execute_tool, but good for early exit)
    schema = db_tool.parameter_schema
    is_valid, validation_errors = executor.validate_parameters(schema, parameters)
    if not is_valid:
        logger.warning(f"Parameter validation failed for tool '{tool_name}' execution request.")
        return schemas.ToolExecutionResponse(
            status="validation_error",
            message="Parameter validation failed.",
            validation_errors=validation_errors
        )

    # 3. Handle Dry Run
    if dry_run:
        logger.info(f"Dry run validation successful for tool '{tool_name}'.")
        return schemas.ToolExecutionResponse(
            status="completed", # Indicate validation success
            message="Dry run successful: Parameters are valid.",
            result={"dry_run_status": "valid"}
        )

    # 4. Execute Asynchronously in Background
    logger.info(f"Adding execution of tool '{tool_name}' (TaskID: {task_id}) to background tasks.")
    background_tasks.add_task(
        execute_tool_background,
        db, # Pass session - potentially problematic if session closes early. Revisit if needed.
        redis_client,
        db_tool,
        parameters,
        task_id,
        requesting_agent
    )

    # Return acknowledgement immediately
    return schemas.ToolExecutionResponse(
        status="acknowledged",
        message=f"Tool '{tool_name}' execution request acknowledged. Result will be sent asynchronously via Redis.",
        execution_id=task_id # Use task_id as execution_id for tracking
    )