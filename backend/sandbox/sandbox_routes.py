# routes/sandbox_routes.py

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse
import httpx
import os
import logging
from typing import Dict, Any, Optional

from backend.models.models import Task, TaskEvent, MessageIntent, TaskOutcome, TaskResult
from backend.factories.factories import TaskResultFactory
from backend.core.config import settings

# Import the tool service
from task_tool_integration import ToolService

# Configure logger
logger = logging.getLogger("sandbox_routes")

# Create the router
router = APIRouter()

# Initialize the tool service
tool_service = ToolService(sandbox_api_url=settings.SANDBOX_API_URL)

# Routes
@router.post("/execute")
async def execute_code(request: Dict[str, Any]):
    """
    Execute Python code in the sandbox.
    This endpoint is called by the frontend.
    """
    try:
        # Extract parameters
        code = request.get("code", "")
        task_id = request.get("task_id", "")
        timeout = request.get("timeout", 30)
        dependencies = request.get("dependencies", [])
        allow_file_access = request.get("allow_file_access", True)
        execution_mode = request.get("execution_mode", "docker")
        requesting_agent = request.get("requesting_agent", "UI")
        
        # Execute the code
        result = await tool_service.execute_code(
            task_id=task_id,
            code=code,
            agent=requesting_agent,
            dependencies=dependencies,
            timeout=timeout,
            allow_file_access=allow_file_access
        )
        
        # Return the result
        return result
        
    except Exception as e:
        logger.error(f"Error executing code: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error executing code: {str(e)}"
        )

@router.get("/result/{execution_id}")
async def get_execution_result(execution_id: str):
    """
    Get the result of a code execution.
    This endpoint is called by the frontend.
    """
    try:
        # Get the result
        result = await tool_service.get_execution_result(execution_id)
        
        # If still processing, return 202 status
        if result.get("status") == "pending":
            return JSONResponse(
                status_code=202,
                content={"status": "pending", "message": "Execution still in progress"}
            )
        
        # Return the result
        return result
        
    except Exception as e:
        logger.error(f"Error getting execution result: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting execution result: {str(e)}"
        )

@router.get("/status/{execution_id}")
async def get_execution_status(execution_id: str):
    """
    Get the status of a code execution.
    This endpoint is called by the frontend.
    """
    try:
        # Use direct HTTP call to the sandbox API
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{settings.SANDBOX_API_URL}/status/{execution_id}")
            
            if response.status_code == 404:
                raise HTTPException(
                    status_code=404,
                    detail=f"Execution {execution_id} not found"
                )
                
            return response.json()
            
    except httpx.HTTPError as e:
        logger.error(f"HTTP error getting execution status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting execution status: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error getting execution status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting execution status: {str(e)}"
        )

@router.get("/stats")
async def get_stats():
    """
    Get sandbox execution statistics.
    This endpoint is called by the frontend.
    """
    try:
        # Use direct HTTP call to the sandbox API
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{settings.SANDBOX_API_URL}/stats")
            return response.json()
            
    except Exception as e:
        logger.error(f"Error getting sandbox stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting sandbox stats: {str(e)}"
        )

# Function to register routes with the main app
def register_sandbox_routes(app):
    app.include_router(router, prefix="/api/sandbox", tags=["sandbox"])