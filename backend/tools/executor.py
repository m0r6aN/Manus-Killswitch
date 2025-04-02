# enhanced_executor.py

import os
import json
import httpx
import asyncio
import logging
import uuid
import aiofiles
from typing import Dict, Any, List, Optional, Tuple, Union

from fastapi import HTTPException
from pydantic import BaseModel, Field

# Import your existing modules as needed
from backend.core.config import settings
from backend.core.redis_client import get_redis_pool
from backend.models.models import TaskEvent, TaskOutcome

# Configure logging
logger = logging.getLogger("enhanced_executor")

class ToolExecutionRequest(BaseModel):
    """Request model for tool execution."""
    tool_name: str
    tool_input: Dict[str, Any]
    task_id: str
    agent_id: Optional[str] = None
    timeout: Optional[int] = 30

class ToolExecutionResult(BaseModel):
    """Result model for tool execution."""
    execution_id: str
    task_id: str
    tool_name: str
    status: str  # "success", "error", "timeout"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None

class ToolExecutor:
    """
    Enhanced Tool Executor that combines all tool implementations and adds sandboxed Python execution.
    This is the integration point for all tools in the system.
    """
    
    def __init__(self, sandbox_api_url: Optional[str] = None):
        """Initialize the enhanced tool executor."""
        self.sandbox_api_url = sandbox_api_url or os.environ.get("SANDBOX_API_URL", "http://localhost:8001")
        self.tools = {
            "web_search": self.web_search,
            "web_scrape": self.web_scrape,
            "file_rw": self.file_rw,
            "local_file_retriever": self.local_file_retriever,
            "python_exec": self.python_exec,
            # Add more tools as they become available
            "weather": self.weather,
            "news": self.news,
            "stock": self.stock,
            "crypto": self.crypto,
            "image_analyzer": self.image_analyzer
        }
        
        logger.info(f"EnhancedToolExecutor initialized with {len(self.tools)} tools")
    
    async def execute_tool(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        """
        Execute a tool based on the provided request.
        This is the main entry point for tool execution.
        """
        execution_id = f"tool_{uuid.uuid4().hex[:10]}"
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Check if tool exists
            if request.tool_name not in self.tools:
                logger.warning(f"Tool {request.tool_name} not found")
                return ToolExecutionResult(
                    execution_id=execution_id,
                    task_id=request.task_id,
                    tool_name=request.tool_name,
                    status="error",
                    error=f"Tool {request.tool_name} not found"
                )
            
            # Execute the tool with a timeout
            try:
                logger.info(f"Executing tool {request.tool_name} for task {request.task_id}")
                result = await asyncio.wait_for(
                    self.tools[request.tool_name](request.tool_input),
                    timeout=request.timeout
                )
                
                # Calculate execution time
                execution_time = asyncio.get_event_loop().time() - start_time
                
                # Check if result has a status field
                status = result.get("status", "success")
                
                if status == "error":
                    return ToolExecutionResult(
                        execution_id=execution_id,
                        task_id=request.task_id,
                        tool_name=request.tool_name,
                        status="error",
                        error=result.get("error", "Unknown error"),
                        execution_time=execution_time
                    )
                
                return ToolExecutionResult(
                    execution_id=execution_id,
                    task_id=request.task_id,
                    tool_name=request.tool_name,
                    status="success",
                    result=result,
                    execution_time=execution_time
                )
                
            except asyncio.TimeoutError:
                logger.warning(f"Tool {request.tool_name} timed out after {request.timeout}s")
                return ToolExecutionResult(
                    execution_id=execution_id,
                    task_id=request.task_id,
                    tool_name=request.tool_name,
                    status="timeout",
                    error=f"Tool execution timed out after {request.timeout} seconds",
                    execution_time=request.timeout
                )
                
        except Exception as e:
            logger.error(f"Error executing tool {request.tool_name}: {e}")
            return ToolExecutionResult(
                execution_id=execution_id,
                task_id=request.task_id,
                tool_name=request.tool_name,
                status="error",
                error=f"Tool execution failed: {str(e)}",
                execution_time=asyncio.get_event_loop().time() - start_time
            )
    
    async def publish_result(self, result: ToolExecutionResult):
        """Publish tool execution result to Redis."""
        try:
            redis_client = await get_redis_pool()
            await redis_client.publish(
                "tools:execution_results",
                json.dumps(result.dict())
            )
            logger.info(f"Published result for tool {result.tool_name} to Redis")
        except Exception as e:
            logger.error(f"Error publishing tool result to Redis: {e}")
    
    # Tool implementations
    
    async def web_search(self, tool_input: dict) -> dict:
        """
        Searches the web (mocked for now, real API later).
        """
        query = tool_input.get("query", "")
        if not query:
            return {"status": "error", "error": "No query provided"}
        
        # Mocked search (replace with real API like SerpAPI/Google later)
        mock_results = [
            {"title": f"Result 1 for {query}", "url": "http://mocked.com/1"},
            {"title": f"Result 2 for {query}", "url": "http://mocked.com/2"}
        ]
        return {
            "status": "success",
            "query": query,
            "results": mock_results
        }
    
    async def web_scrape(self, tool_input: dict) -> dict:
        """
        Scrapes a URL (mocked, real scraping with httpx/BeautifulSoup soon).
        """
        url = tool_input.get("url", "")
        if not url:
            return {"status": "error", "error": "No URL provided"}
        
        # Mocked scrape (replace with httpx/BS4 later)
        mock_content = f"Mocked content scraped from {url}"
        return {
            "status": "success",
            "url": url,
            "content": mock_content
        }
    
    async def file_rw(self, tool_input: dict) -> dict:
        """
        Reads/writes files locally.
        """
        mode = tool_input.get("mode", "read")  # "read" or "write"
        path = tool_input.get("path", "")
        content = tool_input.get("content", "") if mode == "write" else None
        
        if not path:
            return {"status": "error", "error": "No file path provided"}
        
        try:
            if mode == "read":
                async with aiofiles.open(path, "r") as f:
                    file_content = await f.read()
                return {
                    "status": "success",
                    "mode": "read",
                    "path": path,
                    "content": file_content
                }
            elif mode == "write":
                if not content:
                    return {"status": "error", "error": "No content provided for write"}
                async with aiofiles.open(path, "w") as f:
                    await f.write(content)
                return {
                    "status": "success",
                    "mode": "write",
                    "path": path,
                    "content": content
                }
            else:
                return {"status": "error", "error": f"Invalid mode: {mode}"}
        except FileNotFoundError:
            return {"status": "error", "error": f"File not found: {path}"}
        except Exception as e:
            return {"status": "error", "error": f"File operation failed: {str(e)}"}
    
    async def local_file_retriever(self, tool_input: dict) -> dict:
        """
        Retrieves and parses local code files (Python focus).
        """
        path = tool_input.get("path", "")
        if not path:
            return {"status": "error", "error": "No file path provided"}
        
        try:
            async with aiofiles.open(path, "r") as f:
                content = await f.read()
            
            # Import ast only when needed to avoid global import
            import ast
            
            # Parse Python code with AST
            if path.endswith(".py"):
                tree = ast.parse(content)
                functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
                imports = [node.names[0].name for node in ast.walk(tree) if isinstance(node, ast.Import)]
                parsed = {"functions": functions, "imports": imports}
            else:
                parsed = {}  # Non-Python files get raw content only
            
            return {
                "status": "success",
                "path": path,
                "content": content,
                "parsed": parsed
            }
        except FileNotFoundError:
            return {"status": "error", "error": f"File not found: {path}"}
        except SyntaxError:
            return {"status": "error", "error": f"Syntax error in {path}"}
        except Exception as e:
            return {"status": "error", "error": f"Failed to process file: {str(e)}"}
    
    async def python_exec(self, tool_input: dict) -> dict:
        """
        Executes Python code in the sandbox via the sandbox API.
        This is significantly more secure than using RestrictedPython directly
        since it leverages the Docker container sandbox we've built.
        """
        code = tool_input.get("code", "")
        task_id = tool_input.get("task_id", f"task_{uuid.uuid4().hex[:10]}")
        timeout = tool_input.get("timeout", 30)
        dependencies = tool_input.get("dependencies", [])
        allow_file_access = tool_input.get("allow_file_access", False)
        
        if not code:
            return {"status": "error", "error": "No code provided"}
        
        try:
            # Use the sandbox API to execute the code
            logger.info(f"Sending Python code to sandbox for execution (task_id: {task_id})")
            
            # Prepare execution request
            execution_request = {
                "code": code,
                "task_id": task_id,
                "timeout": timeout,
                "dependencies": dependencies,
                "allow_file_access": allow_file_access,
                "requesting_agent": "tool_executor",
                "execution_mode": "docker"  # Always use Docker for security
            }
            
            # Call the sandbox API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.sandbox_api_url}/execute",
                    json=execution_request,
                    timeout=timeout + 10  # Add buffer time for API call
                )
                
                if response.status_code != 200:
                    logger.error(f"Sandbox API error: {response.status_code} - {response.text}")
                    return {
                        "status": "error",
                        "error": f"Sandbox API error: {response.status_code}"
                    }
                
                # Get execution ID
                execution_data = response.json()
                execution_id = execution_data.get("execution_id")
                
                if not execution_id:
                    return {
                        "status": "error",
                        "error": "No execution ID returned from sandbox"
                    }
                
                logger.info(f"Python execution submitted to sandbox (ID: {execution_id})")
                
                # Poll for result with timeout
                max_wait = timeout + 5  # Give a bit of extra time
                wait_time = 0
                poll_interval = 0.5
                
                while wait_time < max_wait:
                    await asyncio.sleep(poll_interval)
                    wait_time += poll_interval
                    
                    # Get execution result
                    result_response = await client.get(
                        f"{self.sandbox_api_url}/result/{execution_id}",
                        timeout=10
                    )
                    
                    # If still processing, continue polling
                    if result_response.status_code == 202:
                        continue
                    
                    # Otherwise, return the result
                    if result_response.status_code == 200:
                        execution_result = result_response.json()
                        
                        # Format the result
                        return {
                            "status": execution_result.get("status", "error"),
                            "code": code,
                            "execution_id": execution_id,
                            "stdout": execution_result.get("stdout", ""),
                            "stderr": execution_result.get("stderr", ""),
                            "execution_time": execution_result.get("execution_time", 0),
                            "output_files": execution_result.get("output_files", {}),
                            "exit_code": execution_result.get("exit_code", None)
                        }
                    else:
                        return {
                            "status": "error",
                            "error": f"Failed to get execution result: {result_response.status_code}"
                        }
                
                # If we get here, polling timed out
                return {
                    "status": "timeout",
                    "error": f"Timed out waiting for execution result after {max_wait}s",
                    "execution_id": execution_id
                }
                
        except httpx.HTTPError as e:
            logger.error(f"HTTP error executing Python code: {e}")
            return {
                "status": "error",
                "error": f"HTTP error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Error executing Python code: {e}")
            return {
                "status": "error",
                "error": f"Execution failed: {str(e)}"
            }