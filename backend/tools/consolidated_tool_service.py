# backend/tools/consolidated_tool_service.py
# FastAPI HTTP API + Redis Listener + Tool Execution + Sandbox Polling

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import httpx
import redis.asyncio as redis
from fastapi import (BackgroundTasks, Depends, FastAPI, File, Form,
                     HTTPException, Request, UploadFile)
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker # Import async_sessionmaker

from backend.core.config import logger, settings
from backend.core.redis_client import get_redis_pool, publish_message

# Assume these tool modules exist and expose an async function 'run'
from backend.tools import file_rw, local_file_retriever, web_scrape, web_search

# Assume these exist and are correctly defined
from . import crud, schemas
# Assuming database setup provides get_db dependency AND the session maker
from .db.database import SessionLocal, get_db # IMPORTANT: Need access to the Session Maker

# --- Constants ---
LOCAL_TOOLS = {
    "web_search": web_search.run,
    "web_scrape": web_scrape.run,
    "file_rw": file_rw.run,
    "local_file_retriever": local_file_retriever.run,
}
PYTHON_SANDBOX_TOOL_NAME = "python_sandbox"
TOOL_REQUEST_CHANNEL = settings.get("TOOL_REQUEST_REDIS_CHANNEL", "tool_requests") # Configurable channel

# --- ToolCore Service (Handles Sandbox Interaction & Polling) ---
class ToolCoreService:
    # ... (Keep the ToolCoreService class exactly as defined in the previous refactoring) ...
    # Methods: __init__, set_clients, start_polling, stop_polling,
    #          execute_python_sandbox, _poll_active_executions, _handle_result, _publish_result
    def __init__(self):
        self.http_client: Optional[httpx.AsyncClient] = None
        self.redis_client: Optional[redis.Redis] = None
        self.active_executions: Dict[str, Dict[str, Any]] = {}
        self.execution_results: Dict[str, Dict[str, Any]] = {}
        self._polling_task: Optional[asyncio.Task] = None
        self._stop_polling = asyncio.Event()

    def set_clients(self, http_client: httpx.AsyncClient, redis_client: redis.Redis):
        self.http_client = http_client
        self.redis_client = redis_client
        logger.info("ToolCoreService clients initialized.")

    async def start_polling(self):
        if not self._polling_task or self._polling_task.done():
            if not self.http_client or not self.redis_client:
                logger.error("Cannot start polling: HTTP or Redis client not set.")
                return
            self._stop_polling.clear()
            self._polling_task = asyncio.create_task(self._poll_active_executions())
            logger.info(f"Started sandbox result polling task. Interval: {settings.get('SANDBOX_POLL_INTERVAL', 1.0)}s")

    async def stop_polling(self):
        if self._polling_task and not self._polling_task.done():
            logger.info("Stopping sandbox result polling task...")
            self._stop_polling.set()
            try:
                await asyncio.wait_for(self._polling_task, timeout=5.0)
                logger.info("Stopped sandbox result polling task.")
            except asyncio.TimeoutError:
                logger.warning("Polling task did not stop gracefully within timeout.")
                self._polling_task.cancel()
            except Exception as e:
                logger.error(f"Error stopping polling task: {e}")
            finally:
                self._polling_task = None

    async def execute_python_sandbox(self, task_id: str, parameters: Dict[str, Any], requesting_agent: str) -> Dict[str, Any]:
        if not self.http_client:
            return {"status": "error", "message": "HTTP client not available", "task_id": task_id}

        code = parameters.get("code", "")
        if not code:
            return {"status": "error", "message": "No code provided", "task_id": task_id}

        payload = {
            "task_id": task_id,
            "code": code,
            "timeout": parameters.get("timeout", 30),
            "memory_limit": parameters.get("memory_limit", 512),
            "dependencies": parameters.get("dependencies", []),
            "allow_file_access": parameters.get("allow_file_access", True),
            "requesting_agent": requesting_agent,
            "execution_mode": "docker"
        }

        try:
            logger.debug(f"Sending execution request to sandbox: {payload.get('task_id')}")
            response = await self.http_client.post(f"{settings.SANDBOX_API_URL}/execute", json=payload)
            response.raise_for_status()

            result = response.json()
            execution_id = result.get("execution_id")
            if not execution_id:
                 logger.error(f"Sandbox response missing 'execution_id': {result}")
                 return {"status": "error", "message": "Sandbox response missing 'execution_id'", "task_id": task_id}

            self.active_executions[execution_id] = {
                "task_id": task_id,
                "agent": requesting_agent,
                "start_time": asyncio.get_event_loop().time(),
            }
            logger.info(f"Submitted task {task_id} to sandbox. Execution ID: {execution_id}")
            return {"status": "submitted", "execution_id": execution_id, "task_id": task_id}

        except httpx.RequestError as e:
            logger.error(f"HTTP error calling sandbox /execute for task {task_id}: {e}", exc_info=True)
            return {"status": "error", "message": f"HTTP error calling sandbox: {e}", "task_id": task_id}
        except Exception as e:
            logger.error(f"Unexpected error submitting to sandbox for task {task_id}: {e}", exc_info=True)
            return {"status": "error", "message": str(e), "task_id": task_id}

    async def _poll_active_executions(self):
        while not self._stop_polling.is_set():
            await asyncio.sleep(settings.get("SANDBOX_POLL_INTERVAL", 1.0))
            current_exec_ids = list(self.active_executions.keys())
            if not current_exec_ids: continue

            # logger.debug(f"Polling for results of {len(current_exec_ids)} executions...")
            for exec_id in current_exec_ids:
                if exec_id not in self.active_executions: continue # Check if removed concurrently

                try:
                    poll_url = f"{settings.SANDBOX_API_URL}/result/{exec_id}"
                    response = await self.http_client.get(poll_url)

                    if response.status_code == 202: continue # Still processing
                    elif response.status_code == 200:
                        result = response.json()
                        logger.info(f"Received result for sandbox exec {exec_id}: Status {result.get('status')}")
                        await self._handle_result(exec_id, result)
                    elif response.status_code == 404:
                        logger.warning(f"Sandbox returned 404 for execution {exec_id}. Assuming lost/expired.")
                        await self._handle_result(exec_id, {"status": "error", "error_message": "Execution result not found (404)."})
                    else:
                        logger.error(f"Polling error for {exec_id}: Status {response.status_code}, Response: {response.text}")
                        await self._handle_result(exec_id, {"status": "error", "error_message": f"Polling failed with status {response.status_code}"})

                except httpx.RequestError as e: logger.error(f"HTTP error polling for {exec_id}: {e}")
                except Exception as e: logger.error(f"Unexpected error polling for {exec_id}: {e}", exc_info=True)
            # logger.debug("Polling cycle complete.")


    async def _handle_result(self, execution_id: str, result_data: Dict[str, Any]):
        """Processes the received result, publishes it, and cleans up."""
        exec_info = self.active_executions.pop(execution_id, None)
        if not exec_info:
            logger.warning(f"Received result for unknown or already handled execution {execution_id}")
            return

        task_id = exec_info.get("task_id", execution_id)
        agent = exec_info.get("agent", "unknown_agent")
        self.execution_results[execution_id] = result_data # Optional cache
        await self._publish_result(task_id, agent, execution_id, result_data)

    async def _publish_result(self, task_id: str, agent: str, execution_id: str, result: Dict[str, Any]):
        """Publishes the final tool result to the appropriate Redis channel."""
        if not self.redis_client:
            logger.error(f"Cannot publish result for task {task_id}: Redis client not available.")
            return

        final_status = result.get("status", "error")
        payload = {
            "type": "TOOL_COMPLETE",
            "data": {
                "execution_id": task_id,
                "sandbox_execution_id": execution_id if task_id != execution_id else None, # Only if different
                "status": final_status,
                "result": result if final_status == "success" else None,
                "error": result.get("error_message") or result.get("stderr") if final_status != "success" else None
            }
        }
        # Filter out None values in data for cleaner message
        payload["data"] = {k: v for k, v in payload["data"].items() if v is not None}

        channel = f"{agent}_channel"
        try:
            await publish_message(self.redis_client, channel, json.dumps(payload))
            logger.info(f"Published result for task {task_id} (Exec ID: {execution_id}) to channel {channel}")
        except Exception as e:
            logger.error(f"Failed to publish result for task {task_id} to {channel}: {e}", exc_info=True)

# --- Core Background Execution Task ---
async def execute_tool_task(
    tool_name: str,
    parameters: Dict[str, Any],
    task_id: str,
    requesting_agent: str,
    callback_channel: str,
    # Pass dependencies explicitly
    db_session_factory: async_sessionmaker[AsyncSession], # Pass factory instead of session
    redis_client: redis.Redis,
    tool_service: ToolCoreService,
):
    """
    Background task to execute a tool (local, sandbox, or DB).
    Manages its own DB session and publishes result to Redis.
    """
    result_payload_data = {
        "execution_id": task_id,
        "status": "error",
        "result": None,
        "error": "Tool execution failed unexpectedly."
    }
    is_sandbox = False
    db: Optional[AsyncSession] = None # Initialize db session var

    try:
        # --- Create DB Session for this task ---
        async with db_session_factory() as db: # Create session using the factory
            logger.info(f"Executing task {task_id} for tool '{tool_name}' requested by {requesting_agent}")

            if tool_name == PYTHON_SANDBOX_TOOL_NAME:
                is_sandbox = True
                submit_result = await tool_service.execute_python_sandbox(task_id, parameters, requesting_agent)
                if submit_result["status"] == "submitted":
                    logger.info(f"Sandbox task {task_id} submitted successfully. Polling will handle result.")
                    return # Polling loop publishes final result
                else:
                    result_payload_data["status"] = "error"
                    result_payload_data["error"] = submit_result.get("message", "Sandbox submission failed")

            elif tool_name in LOCAL_TOOLS:
                tool_callable = LOCAL_TOOLS[tool_name]
                logger.info(f"Executing local tool '{tool_name}' for task {task_id}")
                tool_result = await tool_callable(parameters)
                result_payload_data["status"] = tool_result.get("status", "error")
                result_payload_data["result"] = tool_result.get("result") if result_payload_data["status"] == "success" else None
                result_payload_data["error"] = tool_result.get("error") if result_payload_data["status"] != "success" else None
                logger.info(f"Local tool '{tool_name}' task {task_id} completed with status: {result_payload_data['status']}")

            else:
                # Try fetching tool from DB
                logger.debug(f"Looking up DB tool '{tool_name}' for task {task_id}")
                db_tool = await crud.get_tool_by_name(db, tool_name)
                if db_tool:
                    logger.warning(f"DB tool execution for '{tool_name}' (task {task_id}) is not implemented.")
                    result_payload_data["status"] = "error"
                    result_payload_data["error"] = f"Tool '{tool_name}' found in DB, but execution is not implemented."
                    # raise NotImplementedError(...) # Or handle as error message
                else:
                    logger.error(f"Tool '{tool_name}' not found locally or in DB for task {task_id}")
                    result_payload_data["status"] = "error"
                    result_payload_data["error"] = f"Tool '{tool_name}' not found."

            # Publish result for non-sandbox tools or if sandbox submission failed
            if not is_sandbox or result_payload_data["status"] == "error":
                payload = {"type": "TOOL_COMPLETE", "data": result_payload_data}
                await publish_message(redis_client, callback_channel, json.dumps(payload))
                logger.info(f"Published immediate result for task {task_id} to channel {callback_channel}")

    except Exception as e:
        logger.error(f"Core error during execution of tool '{tool_name}' task {task_id}: {e}", exc_info=True)
        result_payload_data["status"] = "error"
        result_payload_data["error"] = f"Internal error during tool execution: {str(e)}"
        # Attempt to publish error result if unexpected exception occurred
        payload = {"type": "TOOL_COMPLETE", "data": result_payload_data}
        try:
            await publish_message(redis_client, callback_channel, json.dumps(payload))
            logger.warning(f"Published error result for task {task_id} after exception to {callback_channel}")
        except Exception as pub_e:
            logger.critical(f"FAILED TO PUBLISH error result for task {task_id} to {callback_channel}: {pub_e}", exc_info=True)
    # No finally block needed for db session closure due to `async with`

# --- Redis Listener Task ---
async def redis_listener_task(
    redis_client: redis.Redis,
    tool_service: ToolCoreService,
    db_session_factory: async_sessionmaker[AsyncSession],
    stop_event: asyncio.Event
):
    """Listens to Redis Pub/Sub channel for tool requests and spawns execution tasks."""
    pubsub = None
    while not stop_event.is_set():
        try:
            if pubsub is None:
                pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
                await pubsub.subscribe(TOOL_REQUEST_CHANNEL)
                logger.info(f"Subscribed to Redis channel: {TOOL_REQUEST_CHANNEL}")

            # Listen with a timeout to allow checking the stop_event periodically
            message = await asyncio.wait_for(pubsub.get_message(), timeout=1.0)
            if message is None:
                continue # Timeout occurred, check stop_event

            logger.debug(f"Received raw message on {TOOL_REQUEST_CHANNEL}")
            try:
                data = json.loads(message["data"])
                tool_name = data.get("tool_name") or data.get("tool") # Allow both keys
                parameters = data.get("parameters", {})
                task_id = data.get("task_id", f"task_{uuid.uuid4().hex[:10]}")
                requesting_agent = data.get("requesting_agent", "unknown_agent")
                callback_channel = data.get("callback_channel") or f"{requesting_agent}_channel"

                if not tool_name:
                    logger.error(f"Received invalid tool request on Redis (missing tool_name): {data}")
                    continue

                logger.info(f"Received tool request via Redis: Tool='{tool_name}', TaskID='{task_id}', Agent='{requesting_agent}'")

                # Spawn the execution task without awaiting it here
                # Pass the DB session factory, not a session
                asyncio.create_task(execute_tool_task(
                    tool_name=tool_name,
                    parameters=parameters,
                    task_id=task_id,
                    requesting_agent=requesting_agent,
                    callback_channel=callback_channel,
                    db_session_factory=db_session_factory, # Pass factory
                    redis_client=redis_client, # Pass shared client
                    tool_service=tool_service  # Pass shared service
                ))

            except json.JSONDecodeError:
                logger.error(f"Failed to decode JSON from Redis message on {TOOL_REQUEST_CHANNEL}: {message['data']}")
            except Exception as e:
                logger.error(f"Error processing Redis tool request: {e}", exc_info=True)

        except asyncio.TimeoutError:
            continue # No message received, loop again to check stop_event
        except redis.RedisError as e:
            logger.error(f"Redis connection error in listener: {e}. Attempting to reconnect...", exc_info=True)
            if pubsub:
                await pubsub.unsubscribe(TOOL_REQUEST_CHANNEL)
                await pubsub.close() # Close the pubsub connection properly
                pubsub = None # Reset pubsub to trigger re-subscription
            await asyncio.sleep(5) # Wait before retrying connection
        except Exception as e:
            logger.error(f"Unexpected error in Redis listener loop: {e}", exc_info=True)
            await asyncio.sleep(5) # Avoid tight loop on unexpected errors

    # Cleanup on stop
    if pubsub:
        try:
            await pubsub.unsubscribe(TOOL_REQUEST_CHANNEL)
            await pubsub.close()
            logger.info(f"Unsubscribed from Redis channel: {TOOL_REQUEST_CHANNEL}")
        except Exception as e:
            logger.error(f"Error during Redis listener cleanup: {e}")


# --- FastAPI Application Setup & Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Application startup...")
    stop_listener_event = asyncio.Event()

    # Create shared resources
    http_client = httpx.AsyncClient(timeout=settings.get("HTTP_CLIENT_TIMEOUT", 60.0))
    redis_client = await get_redis_pool() # Assume returns a connected client/pool instance
    tool_service = ToolCoreService()
    tool_service.set_clients(http_client, redis_client)

    # Get DB session factory (replace SessionLocal with your actual factory)
    # Ensure SessionLocal is the async_sessionmaker instance
    db_session_factory: async_sessionmaker[AsyncSession] = SessionLocal

    # Store shared resources in app state
    app.state.tool_service = tool_service
    app.state.http_client = http_client
    app.state.redis_client = redis_client
    app.state.db_session_factory = db_session_factory # Store factory
    app.state._stop_listener_event = stop_listener_event # Store event for potential external stop trigger

    # Start background tasks
    await tool_service.start_polling()
    listener = asyncio.create_task(redis_listener_task(
        redis_client=redis_client,
        tool_service=tool_service,
        db_session_factory=db_session_factory,
        stop_event=stop_listener_event
    ))
    app.state._listener_task = listener # Store task handle
    logger.info("Tool service polling and Redis listener started.")

    yield # Application runs here

    # Shutdown
    logger.info("Application shutdown sequence initiated...")
    # 1. Stop accepting new requests via Redis
    logger.info("Stopping Redis listener...")
    stop_listener_event.set()
    try:
        await asyncio.wait_for(listener, timeout=5.0)
        logger.info("Redis listener task stopped.")
    except asyncio.TimeoutError:
        logger.warning("Redis listener task did not stop gracefully within timeout.")
        listener.cancel()
    except Exception as e:
         logger.error(f"Error stopping listener task: {e}")

    # 2. Stop polling for sandbox results
    await tool_service.stop_polling() # Handles its own logging

    # 3. Close external connections
    logger.info("Closing HTTP client...")
    await http_client.aclose()
    logger.info("Closing Redis client/pool...")
    if hasattr(redis_client, 'aclose'): await redis_client.aclose()
    elif hasattr(redis_client, 'close'): await redis_client.close() # Compatibility
    logger.info("Resources closed. Shutdown complete.")


# Create FastAPI app with consolidated lifespan management
app = FastAPI(
    title="Consolidated Tool Service",
    description="Handles tool execution via HTTP API and Redis messages.",
    lifespan=lifespan
)

# --- Dependency Functions ---
async def get_tool_service(request: Request) -> ToolCoreService:
    return request.app.state.tool_service

# get_db remains the same (provided by your db.database module)
# get_redis_pool remains the same (provided by your redis_client module)

# --- FastAPI Route Definitions ---

@app.post("/execute/", response_model=schemas.ToolExecutionResponse, status_code=202)
async def execute_tool_endpoint(
    request_data: schemas.ToolExecutionRequest,
    background_tasks: BackgroundTasks,
    # db: AsyncSession = Depends(get_db), # Don't need db session here directly
    redis_client: redis.Redis = Depends(get_redis_pool), # Still useful for direct publish if needed
    tool_service: ToolCoreService = Depends(get_tool_service),
    request: Request # Access request to get app state
):
    """ Accepts HTTP tool execution request, runs via BackgroundTasks. """
    tool_name = request_data.tool_name
    parameters = request_data.parameters
    task_id = request_data.task_id or f"task_{uuid.uuid4().hex[:10]}"
    requesting_agent = request_data.requesting_agent or "unknown_agent"
    callback_channel = request_data.callback_channel or f"{requesting_agent}_channel"

    # Get DB session factory from app state
    db_session_factory: async_sessionmaker[AsyncSession] = request.app.state.db_session_factory

    # Use FastAPI's BackgroundTasks for HTTP requests
    background_tasks.add_task(
        execute_tool_task, # Use the same core task function
        tool_name=tool_name,
        parameters=parameters,
        task_id=task_id,
        requesting_agent=requesting_agent,
        callback_channel=callback_channel,
        db_session_factory=db_session_factory, # Pass factory
        redis_client=redis_client, # Pass redis client from dependency
        tool_service=tool_service # Pass shared service
    )

    logger.info(f"Acknowledged HTTP request for tool '{tool_name}', task_id: {task_id}")
    return schemas.ToolExecutionResponse(
        status="acknowledged",
        message=f"Tool '{tool_name}' execution acknowledged via HTTP.",
        execution_id=task_id
    )

@app.post("/execute/quick/{tool_name}")
async def execute_tool_quick(
    tool_name: str,
    parameters: Dict[str, Any], # Use request body
    db: AsyncSession = Depends(get_db) # Need DB for sync check
):
    """ Executes a *local* tool synchronously. """
    if tool_name in LOCAL_TOOLS:
        tool_callable = LOCAL_TOOLS[tool_name]
        try:
            logger.info(f"Executing quick local tool '{tool_name}'")
            result = await tool_callable(parameters)
            return result # Return raw result
        except Exception as e:
            logger.error(f"Error during quick execution of tool '{tool_name}': {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error executing tool: {str(e)}")
    elif tool_name == PYTHON_SANDBOX_TOOL_NAME:
         raise HTTPException(status_code=400, detail="Quick execution not supported for python_sandbox. Use /execute/ endpoint.")
    else:
        db_tool = await crud.get_tool_by_name(db, tool_name)
        if db_tool:
            raise HTTPException(status_code=501, detail="Quick execution not implemented for DB tools.")
        else:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found or not supported for quick execution.")


@app.get("/tools/list")
async def list_tools(db: AsyncSession = Depends(get_db)):
    """ Lists available tools (local, sandbox, DB). """
    try:
        db_tools_list = await crud.get_all_tools(db)
        db_tool_names = [t.name for t in db_tools_list]
    except Exception as e:
        logger.error(f"Failed to retrieve tools from database: {e}", exc_info=True)
        db_tool_names = ["<error retrieving db tools>"]

    all_tools = list(LOCAL_TOOLS.keys()) + [PYTHON_SANDBOX_TOOL_NAME] + db_tool_names
    unique_tools = sorted(list(set(all_tools)))
    return {"status": "success", "tools": unique_tools}


@app.post("/execute/upload-execute", response_model=schemas.ToolExecutionResponse, status_code=202)
async def upload_and_execute_sandbox(
    background_tasks: BackgroundTasks, # Use BG tasks for HTTP uploads
    request: Request, # Access app state
    code_file: UploadFile = File(...),
    task_id: Optional[str] = Form(None),
    timeout: int = Form(30),
    memory_limit: int = Form(512),
    dependencies: Optional[List[str]] = Form(None), # Use List for potential multiple values
    requesting_agent: Optional[str] = Form(None),
    # db: AsyncSession = Depends(get_db), # Not needed directly here
    redis_client: redis.Redis = Depends(get_redis_pool), # Need for task
    tool_service: ToolCoreService = Depends(get_tool_service) # Need for task
):
    """ Uploads a Python script and executes it in the sandbox via BackgroundTasks. """
    try:
        file_content_bytes = await code_file.read()
        file_content = file_content_bytes.decode('utf-8')
    except Exception as e:
         logger.error(f"Failed to read uploaded file '{code_file.filename}': {e}")
         raise HTTPException(status_code=400, detail=f"Error reading uploaded file: {e}")
    finally:
        await code_file.close()

    final_task_id = task_id or f"task_{uuid.uuid4().hex[:10]}"
    final_agent = requesting_agent or "unknown_agent"
    callback_channel = f"{final_agent}_channel"
    db_session_factory: async_sessionmaker[AsyncSession] = request.app.state.db_session_factory

    parameters = {
        "code": file_content,
        "timeout": timeout,
        "memory_limit": memory_limit,
        "dependencies": dependencies or [],
        "allow_file_access": True
    }

    background_tasks.add_task(
        execute_tool_task,
        tool_name=PYTHON_SANDBOX_TOOL_NAME,
        parameters=parameters,
        task_id=final_task_id,
        requesting_agent=final_agent,
        callback_channel=callback_channel,
        db_session_factory=db_session_factory, # Pass factory
        redis_client=redis_client,
        tool_service=tool_service
    )

    logger.info(f"Acknowledged request for uploaded code execution via HTTP, task_id: {final_task_id}")
    return schemas.ToolExecutionResponse(
        status="acknowledged",
        message="Python code execution acknowledged via HTTP.",
        execution_id=final_task_id
    )


# --- Main execution (for running directly with uvicorn) ---
# Example: uvicorn backend.tools.consolidated_tool_service:app --reload
# if __name__ == "__main__":
#     import uvicorn
#     # Make sure settings are loaded appropriately if running this way
#     uvicorn.run(app, host="0.0.0.0", port=8000)