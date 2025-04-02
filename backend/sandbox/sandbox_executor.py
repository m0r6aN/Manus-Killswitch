# sandbox_executor.py

import os
import sys
import uuid
import json
import asyncio
import tempfile
import subprocess
import shutil
from pathlib import Path
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
import time
import docker
import re
import base64
from io import BytesIO

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, validator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sandbox_executor")

# Models for API
class ExecutionRequest(BaseModel):
    code: str
    task_id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:10]}")
    timeout: int = 30  # Default timeout in seconds
    memory_limit: int = 512  # Default memory limit in MB
    dependencies: List[str] = []
    allow_file_access: bool = False
    inputs: Dict[str, Any] = {}
    requesting_agent: Optional[str] = None
    execution_mode: str = "docker"  # 'docker' or 'subprocess' - docker is more secure
    entry_point: Optional[str] = None  # Optional specific file to run
    
    @validator('execution_mode')
    def validate_execution_mode(cls, v):
        if v not in ['docker', 'subprocess']:
            raise ValueError(f"execution_mode must be 'docker' or 'subprocess', got {v}")
        return v
    
    @validator('timeout')
    def validate_timeout(cls, v):
        if v < 1 or v > 300:  # 5 minutes max
            raise ValueError(f"timeout must be between 1 and 300 seconds, got {v}")
        return v
    
    @validator('memory_limit')
    def validate_memory_limit(cls, v):
        if v < 16 or v > 2048:  # 2GB max
            raise ValueError(f"memory_limit must be between 16 and 2048 MB, got {v}")
        return v
    
    @validator('dependencies')
    def validate_dependencies(cls, v):
        # Validate each dependency is a valid PyPI package name
        # Basic validation: alphanumeric characters, dashes, underscores, dots
        for dep in v:
            if not re.match(r'^[A-Za-z0-9_\-\.]+[A-Za-z0-9_\-\.]==?[A-Za-z0-9_\-\.]*$', dep) and \
               not re.match(r'^[A-Za-z0-9_\-\.]+$', dep):
                raise ValueError(f"Invalid dependency format: {dep}")
        return v

class ExecutionResult(BaseModel):
    task_id: str
    execution_id: str
    status: str  # 'success', 'error', 'timeout'
    stdout: str = ""
    stderr: str = ""
    error_message: Optional[str] = None
    execution_time: float
    output_files: Dict[str, str] = {}  # filename -> base64 content
    memory_usage: Optional[float] = None
    exit_code: Optional[int] = None

class ExecutionStatus(BaseModel):
    task_id: str
    execution_id: str
    status: str  # 'pending', 'running', 'completed', 'failed'
    start_time: Optional[float] = None
    end_time: Optional[float] = None

# Execution Manager
class SandboxExecutionManager:
    def __init__(self):
        self.active_executions: Dict[str, Dict[str, Any]] = {}
        self.completed_executions: Dict[str, ExecutionResult] = {}
        self.execution_history: List[Dict[str, Any]] = []
        
        # Initialize Docker client if available
        try:
            self.docker_client = docker.from_env()
            # Check if docker is running
            self.docker_client.ping()
            logger.info("Docker initialized successfully")
            self.docker_available = True
        except Exception as e:
            logger.warning(f"Docker initialization failed: {e}. Falling back to subprocess execution.")
            self.docker_available = False
    
    async def execute_code(self, request: ExecutionRequest) -> str:
        """
        Submit code for execution and return an execution ID.
        The actual execution happens asynchronously.
        """
        execution_id = f"exec_{uuid.uuid4().hex[:10]}"
        
        # Store in active executions
        self.active_executions[execution_id] = {
            "request": request.dict(),
            "status": "pending",
            "start_time": None,
            "end_time": None
        }
        
        # Start execution in the background
        asyncio.create_task(self._execute_code_task(execution_id, request))
        
        return execution_id
    
    async def _execute_code_task(self, execution_id: str, request: ExecutionRequest):
        """Background task to actually execute the code."""
        try:
            # Mark as running
            self.active_executions[execution_id]["status"] = "running"
            self.active_executions[execution_id]["start_time"] = time.time()
            
            # Choose execution method
            if request.execution_mode == 'docker' and self.docker_available:
                result = await self._execute_in_docker(execution_id, request)
            else:
                result = await self._execute_in_subprocess(execution_id, request)
            
            # Store result
            self.completed_executions[execution_id] = result
            
            # Update status
            self.active_executions[execution_id]["status"] = "completed"
            self.active_executions[execution_id]["end_time"] = time.time()
            
            # Add to history
            self.execution_history.append({
                "execution_id": execution_id,
                "task_id": request.task_id,
                "status": result.status,
                "execution_time": result.execution_time,
                "timestamp": time.time(),
                "agent": request.requesting_agent
            })
            
            # Limit history size
            if len(self.execution_history) > 1000:
                self.execution_history = self.execution_history[-1000:]
                
            # Cleanup completed executions after a while
            if len(self.completed_executions) > 100:
                oldest_keys = sorted(self.completed_executions.keys())[:50]
                for key in oldest_keys:
                    del self.completed_executions[key]
        
        except Exception as e:
            logger.error(f"Error in execution task: {e}")
            
            # Create an error result
            result = ExecutionResult(
                task_id=request.task_id,
                execution_id=execution_id,
                status="error",
                error_message=f"Internal execution error: {str(e)}",
                execution_time=time.time() - (self.active_executions[execution_id].get("start_time") or time.time()),
                stdout="",
                stderr=""
            )
            
            # Store result
            self.completed_executions[execution_id] = result
            
            # Update status
            self.active_executions[execution_id]["status"] = "failed"
            self.active_executions[execution_id]["end_time"] = time.time()
    
    async def _execute_in_docker(self, execution_id: str, request: ExecutionRequest) -> ExecutionResult:
        """Execute code in a Docker container for better isolation."""
        start_time = time.time()
        work_dir = Path(tempfile.mkdtemp(prefix=f"sandbox_{execution_id}_"))
        
        try:
            # Create files
            code_file = work_dir / "main.py"
            with open(code_file, 'w') as f:
                f.write(request.code)
            
            # If specific entry point is provided
            if request.entry_point:
                entry_file = work_dir / request.entry_point
                with open(entry_file, 'w') as f:
                    f.write(request.code)
            
            # Create requirements.txt if dependencies
            if request.dependencies:
                req_file = work_dir / "requirements.txt"
                with open(req_file, 'w') as f:
                    f.write("\n".join(request.dependencies))
            
            # Write inputs to file if provided
            if request.inputs:
                input_file = work_dir / "inputs.json"
                with open(input_file, 'w') as f:
                    json.dump(request.inputs, f)
            
            # Create Dockerfile
            dockerfile = work_dir / "Dockerfile"
            with open(dockerfile, 'w') as f:
                f.write(f"""
FROM python:3.10-slim

WORKDIR /app

# Copy code files
COPY . /app/

# Install dependencies if any
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

# Run the code
CMD ["python", "{request.entry_point or 'main.py'}"]
""")
            
            # Build and run container
            container_name = f"sandbox_{execution_id}"
            
            # Build
            image, logs = self.docker_client.images.build(
                path=str(work_dir),
                tag=container_name,
                rm=True
            )
            
            # Run with limits
            container = self.docker_client.containers.run(
                container_name,
                detach=True,
                mem_limit=f"{request.memory_limit}m",
                memswap_limit=f"{request.memory_limit}m",
                cpu_period=100000,  # Default period
                cpu_quota=50000,    # 0.5 CPU
                network_mode="none" if not request.allow_file_access else "bridge",
                read_only=not request.allow_file_access,
                auto_remove=True
            )
            
            try:
                # Wait for execution with timeout
                result = container.wait(timeout=request.timeout)
                exit_code = result.get('StatusCode', -1)
                
                # Get output
                stdout = container.logs(stdout=True, stderr=False).decode('utf-8', errors='replace')
                stderr = container.logs(stdout=False, stderr=True).decode('utf-8', errors='replace')
                
                # Check for output files in specific directory
                output_files = {}
                if request.allow_file_access:
                    try:
                        output_dir = Path(work_dir) / "output"
                        output_dir.mkdir(exist_ok=True)
                        
                        # Copy from container to output dir
                        container.get_archive("/app/output", output_dir)
                        
                        # Read and encode files
                        for file_path in output_dir.glob("**/*"):
                            if file_path.is_file():
                                with open(file_path, 'rb') as f:
                                    file_content = f.read()
                                    output_files[file_path.name] = base64.b64encode(file_content).decode('utf-8')
                    except Exception as e:
                        logger.warning(f"Error collecting output files: {e}")
                
                # Get memory usage stats
                memory_usage = None
                try:
                    stats = container.stats(stream=False)
                    memory_usage = stats.get('memory_stats', {}).get('usage', 0) / (1024 * 1024)  # Convert to MB
                except:
                    pass
                
                status = "success" if exit_code == 0 else "error"
                
                return ExecutionResult(
                    task_id=request.task_id,
                    execution_id=execution_id,
                    status=status,
                    stdout=stdout,
                    stderr=stderr,
                    error_message=None if exit_code == 0 else f"Process exited with code {exit_code}",
                    execution_time=time.time() - start_time,
                    output_files=output_files,
                    memory_usage=memory_usage,
                    exit_code=exit_code
                )
                
            except Exception as e:
                logger.error(f"Error running container: {e}")
                try:
                    container.kill()
                except:
                    pass
                    
                return ExecutionResult(
                    task_id=request.task_id,
                    execution_id=execution_id,
                    status="error",
                    error_message=f"Container execution error: {str(e)}",
                    execution_time=time.time() - start_time,
                    stdout="",
                    stderr=""
                )
                
        except Exception as e:
            logger.error(f"Docker execution error: {e}")
            return ExecutionResult(
                task_id=request.task_id,
                execution_id=execution_id,
                status="error",
                error_message=f"Docker execution error: {str(e)}",
                execution_time=time.time() - start_time,
                stdout="",
                stderr=""
            )
            
        finally:
            # Clean up
            try:
                # Remove image
                self.docker_client.images.remove(container_name, force=True)
            except:
                pass
                
            # Remove temp directory
            try:
                shutil.rmtree(work_dir)
            except:
                pass
    
    async def _execute_in_subprocess(self, execution_id: str, request: ExecutionRequest) -> ExecutionResult:
        """Execute code in a subprocess (less secure fallback)."""
        start_time = time.time()
        work_dir = Path(tempfile.mkdtemp(prefix=f"sandbox_{execution_id}_"))
        venv_dir = work_dir / "venv"
        
        try:
            # Create the Python file
            main_file = work_dir / "main.py"
            with open(main_file, 'w') as f:
                f.write(request.code)
            
            # If specific entry point is provided
            entry_file = main_file
            if request.entry_point:
                entry_file = work_dir / request.entry_point
                with open(entry_file, 'w') as f:
                    f.write(request.code)
            
            # Create virtual environment
            venv_process = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "venv", str(venv_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            venv_stdout, venv_stderr = await asyncio.wait_for(
                venv_process.communicate(), timeout=60
            )
            
            if venv_process.returncode != 0:
                return ExecutionResult(
                    task_id=request.task_id,
                    execution_id=execution_id,
                    status="error",
                    error_message=f"Failed to create virtual environment: {venv_stderr.decode('utf-8')}",
                    execution_time=time.time() - start_time,
                    stdout=venv_stdout.decode('utf-8'),
                    stderr=venv_stderr.decode('utf-8')
                )
            
            # Install dependencies if any
            if request.dependencies:
                # Construct pip command
                pip_path = venv_dir / "bin" / "pip" if os.name != 'nt' else venv_dir / "Scripts" / "pip.exe"
                pip_args = [str(pip_path), "install", "--no-cache-dir"] + request.dependencies
                
                pip_process = await asyncio.create_subprocess_exec(
                    *pip_args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(work_dir)
                )
                
                pip_stdout, pip_stderr = await asyncio.wait_for(
                    pip_process.communicate(), timeout=120
                )
                
                if pip_process.returncode != 0:
                    return ExecutionResult(
                        task_id=request.task_id,
                        execution_id=execution_id,
                        status="error",
                        error_message=f"Failed to install dependencies: {pip_stderr.decode('utf-8')}",
                        execution_time=time.time() - start_time,
                        stdout=pip_stdout.decode('utf-8'),
                        stderr=pip_stderr.decode('utf-8')
                    )
            
            # Write inputs to file if provided
            if request.inputs:
                input_file = work_dir / "inputs.json"
                with open(input_file, 'w') as f:
                    json.dump(request.inputs, f)
            
            # Create output directory if file access allowed
            if request.allow_file_access:
                output_dir = work_dir / "output"
                output_dir.mkdir(exist_ok=True)
            
            # Execute the Python script
            python_path = venv_dir / "bin" / "python" if os.name != 'nt' else venv_dir / "Scripts" / "python.exe"
            
            process = await asyncio.create_subprocess_exec(
                str(python_path), str(entry_file),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(work_dir)
            )
            
            try:
                # Wait for execution with timeout
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=request.timeout
                )
                
                stdout_str = stdout.decode('utf-8', errors='replace')
                stderr_str = stderr.decode('utf-8', errors='replace')
                exit_code = process.returncode
                
                # Collect output files if allowed
                output_files = {}
                if request.allow_file_access:
                    output_dir = work_dir / "output"
                    if output_dir.exists():
                        for file_path in output_dir.glob("**/*"):
                            if file_path.is_file():
                                with open(file_path, 'rb') as f:
                                    file_content = f.read()
                                    rel_path = str(file_path.relative_to(output_dir))
                                    output_files[rel_path] = base64.b64encode(file_content).decode('utf-8')
                
                status = "success" if exit_code == 0 else "error"
                error_message = None if exit_code == 0 else f"Process exited with code {exit_code}"
                
                return ExecutionResult(
                    task_id=request.task_id,
                    execution_id=execution_id,
                    status=status,
                    stdout=stdout_str,
                    stderr=stderr_str,
                    error_message=error_message,
                    execution_time=time.time() - start_time,
                    output_files=output_files,
                    exit_code=exit_code
                )
                
            except asyncio.TimeoutError:
                # Process exceeded timeout, kill it
                try:
                    process.kill()
                except Exception:
                    pass
                
                return ExecutionResult(
                    task_id=request.task_id,
                    execution_id=execution_id,
                    status="timeout",
                    error_message=f"Execution timed out after {request.timeout} seconds",
                    execution_time=time.time() - start_time,
                    stdout="",
                    stderr=""
                )
                
        except Exception as e:
            logger.error(f"Subprocess execution error: {e}")
            return ExecutionResult(
                task_id=request.task_id,
                execution_id=execution_id,
                status="error",
                error_message=f"Execution error: {str(e)}",
                execution_time=time.time() - start_time,
                stdout="",
                stderr=""
            )
            
        finally:
            # Clean up
            try:
                shutil.rmtree(work_dir)
            except:
                pass
    
    def get_execution_result(self, execution_id: str) -> Optional[ExecutionResult]:
        """Get the result of a completed execution."""
        return self.completed_executions.get(execution_id)
    
    def get_execution_status(self, execution_id: str) -> ExecutionStatus:
        """Get the status of an execution."""
        if execution_id in self.active_executions:
            execution = self.active_executions[execution_id]
            
            return ExecutionStatus(
                task_id=execution['request']['task_id'],
                execution_id=execution_id,
                status=execution['status'],
                start_time=execution['start_time'],
                end_time=execution['end_time']
            )
        
        # Check completed executions
        if execution_id in self.completed_executions:
            result = self.completed_executions[execution_id]
            
            return ExecutionStatus(
                task_id=result.task_id,
                execution_id=execution_id,
                status="completed" if result.status == "success" else "failed",
                start_time=None,
                end_time=None
            )
        
        # Not found
        raise KeyError(f"Execution {execution_id} not found")
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get statistics about executions."""
        active_count = len(self.active_executions)
        completed_count = len(self.completed_executions)
        history_count = len(self.execution_history)
        
        # Calculate success/failure/timeout counts
        status_counts = {"success": 0, "error": 0, "timeout": 0}
        for result in self.completed_executions.values():
            status_counts[result.status] = status_counts.get(result.status, 0) + 1
        
        # Calculate average execution time
        exec_times = [result.execution_time for result in self.completed_executions.values() 
                    if result.execution_time is not None]
        avg_exec_time = sum(exec_times) / len(exec_times) if exec_times else 0
        
        return {
            "active_executions": active_count,
            "completed_executions": completed_count,
            "execution_history": history_count,
            "status_counts": status_counts,
            "average_execution_time": avg_exec_time
        }

# Create FastAPI app
app = FastAPI(
    title="Python Code Execution Sandbox",
    description="Secure execution environment for Python code",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize dependencies
execution_manager = SandboxExecutionManager()
redis_integration = None

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global redis_integration
    
    # Initialize Redis integration if needed
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    if redis_url:
        redis_integration = RedisIntegration(redis_url)
        connected = await redis_integration.connect()
        
        if connected:
            # Start Redis listener in the background
            asyncio.create_task(redis_integration.start_listener())
    
    # Log startup information
    logger.info("Sandbox Executor API started")
    logger.info(f"Docker available: {execution_manager.docker_available}")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    # Close Redis connection if open
    if redis_integration and redis_integration.redis:
        await redis_integration.redis.close()
    
    logger.info("Sandbox Executor API shutdown")

# Routes
@app.post("/execute", response_model=Dict[str, str])
async def execute_code(request: ExecutionRequest):
    """Submit code for execution and return execution ID."""
    try:
        execution_id = await execution_manager.execute_code(request)
        return {"execution_id": execution_id, "task_id": request.task_id}
    except Exception as e:
        logger.error(f"Error executing code: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/result/{execution_id}", response_model=Optional[ExecutionResult])
async def get_execution_result(execution_id: str):
    """Get result of an execution by ID."""
    try:
        result = execution_manager.get_execution_result(execution_id)
        if result is None:
            status = execution_manager.get_execution_status(execution_id)
            return JSONResponse(
                status_code=202,  # Accepted but not ready
                content={"status": status.status, "message": "Execution still in progress"}
            )
        
        return result
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")
    except Exception as e:
        logger.error(f"Error getting execution result: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status/{execution_id}", response_model=ExecutionStatus)
async def get_execution_status(execution_id: str):
    """Get status of an execution by ID."""
    try:
        return execution_manager.get_execution_status(execution_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")
    except Exception as e:
        logger.error(f"Error getting execution status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats", response_model=Dict[str, Any])
async def get_stats():
    """Get execution statistics."""
    try:
        return execution_manager.get_execution_stats()
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload-execute")
async def upload_execute(
    code_file: UploadFile = File(...),
    task_id: str = Form(...),
    timeout: int = Form(30),
    memory_limit: int = Form(512),
    allow_file_access: bool = Form(False),
    requesting_agent: Optional[str] = Form(None),
    execution_mode: str = Form("docker"),
    dependencies: str = Form("")
):
    """Execute code from an uploaded file."""
    try:
        file_content = await code_file.read()
        code = file_content.decode('utf-8')
        
        # Parse dependencies
        deps_list = []
        if dependencies.strip():
            deps_list = [d.strip() for d in dependencies.split(',')]
        
        request = ExecutionRequest(
            code=code,
            task_id=task_id,
            timeout=timeout,
            memory_limit=memory_limit,
            dependencies=deps_list,
            allow_file_access=allow_file_access,
            requesting_agent=requesting_agent,
            execution_mode=execution_mode
        )
        
        execution_id = await execution_manager.execute_code(request)
        return {"execution_id": execution_id, "task_id": task_id}
    except Exception as e:
        logger.error(f"Error executing uploaded code: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# TaskManager Integration
class TaskIntegration:
    """Integration with the TaskManager system."""
    
    @staticmethod
    async def handle_execution_task(task_id: str, code: str, agent: str, 
                                  dependencies: List[str] = [], 
                                  timeout: int = 30) -> Dict[str, Any]:
        """
        Handle a code execution task from the task manager.
        Returns execution details that can be passed back to the task manager.
        """
        try:
            # Create execution request
            request = ExecutionRequest(
                code=code,
                task_id=task_id,
                timeout=timeout,
                memory_limit=512,  # Default value
                dependencies=dependencies,
                allow_file_access=True,  # Allow file access for task integration
                requesting_agent=agent,
                execution_mode="docker"  # Prefer Docker for security
            )
            
            # Submit for execution
            execution_id = await execution_manager.execute_code(request)
            
            # Wait for completion (up to timeout + margin)
            max_wait = timeout + 5
            wait_time = 0
            poll_interval = 0.5
            
            while wait_time < max_wait:
                await asyncio.sleep(poll_interval)
                wait_time += poll_interval
                
                try:
                    status = execution_manager.get_execution_status(execution_id)
                    if status.status in ["completed", "failed"]:
                        break
                except:
                    pass
            
            # Get result
            result = execution_manager.get_execution_result(execution_id)
            
            if result is None:
                return {
                    "status": "error",
                    "execution_id": execution_id,
                    "message": "Execution timed out or failed to complete",
                    "result": None
                }
            
            # Format result for task manager
            return {
                "status": "completed",
                "execution_id": execution_id,
                "task_id": task_id,
                "result": {
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "execution_time": result.execution_time,
                    "status": result.status,
                    "output_files": result.output_files
                }
            }
            
        except Exception as e:
            logger.error(f"Error in task integration: {e}")
            return {
                "status": "error",
                "message": str(e),
                "result": None
            }

# Redis integration for pub/sub if needed
class RedisIntegration:
    """Integration with Redis for pub/sub messaging."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis = None
        
    async def connect(self):
        """Connect to Redis."""
        try:
            from redis.asyncio import Redis
            self.redis = Redis.from_url(self.redis_url)
            await self.redis.ping()
            logger.info("Connected to Redis")
            return True
        except ImportError:
            logger.warning("Redis package not installed. Redis integration disabled.")
            return False
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}")
            return False
    
    async def publish_execution_result(self, execution_id: str, result: ExecutionResult, request: ExecutionRequest): # Add request object
        """Publish execution result notification to Redis."""
        if not self.redis: return
        try:
            await self.redis.publish(
                "sandbox:execution_results",
                json.dumps({
                    "execution_id": execution_id,
                    "task_id": result.task_id,
                    "status": result.status, # Can publish minimal status here
                    "requesting_agent": request.requesting_agent, # <<< ADD THIS FIELD
                    "timestamp": time.time()
                })
            )
        except Exception as e:
            logger.error(f"Error publishing to Redis: {e}")
    
    async def start_listener(self):
        """Start listening for execution requests on Redis."""
        if not self.redis:
            logger.warning("Redis not connected, can't start listener")
            return
            
        try:
            # Subscribe to execution requests channel
            pubsub = self.redis.pubsub()
            await pubsub.subscribe("sandbox:execution_requests")
            
            logger.info("Started Redis listener for execution requests")
            
            # Listen for messages
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        request_data = json.loads(message["data"])
                        logger.info(f"Received execution request: {request_data.get('task_id')}")
                        
                        # Convert to execution request
                        request = ExecutionRequest(**request_data)
                        
                        # Execute
                        execution_id = await execution_manager.execute_code(request)
                        
                        # Publish acknowledgment
                        await self.redis.publish(
                            "sandbox:execution_acknowledgments",
                            json.dumps({
                                "execution_id": execution_id,
                                "task_id": request.task_id,
                                "status": "submitted",
                                "timestamp": time.time()
                            })
                        )
                    except Exception as e:
                        logger.error(f"Error processing Redis message: {e}")
                        
        except Exception as e:
            logger.error(f"Redis listener error: {e}")
        finally:
            # Ensure we unsubscribe
            await pubsub.unsubscribe("sandbox:execution_requests")
            logger.info("Redis listener stopped")