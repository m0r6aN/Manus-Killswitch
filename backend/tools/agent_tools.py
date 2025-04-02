# backend/tools/agent_tools.py
# Merged ToolExecutionMixin + Python-specific methods.

import asyncio
import json
import uuid
import httpx
from typing import Dict, Any, Optional, List

from backend.core.config import settings, logger
from backend.models.models import TaskEvent, TaskOutcome

class ToolExecutionMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pending_tool_executions = {}
        self.tool_api_url = settings.TOOLCORE_API_URL
        self.python_execution_stats = {"total": 0, "success": 0, "failed": 0, "times": []}
        logger.info(f"{self.agent_name} initialized ToolExecutionMixin")

    async def request_tool_execution(self, tool_name: str, tool_input: Dict[str, Any], task_context: Optional[Any] = None, synchronous: bool = False, timeout: int = 30) -> str:
        task_id = task_context.get("task_id") if task_context else f"task_{uuid.uuid4().hex[:10]}"
        endpoint = f"{self.tool_api_url}/execute{'/sync' if synchronous else ''}"
        payload = {
            "tool_name": tool_name,
            "tool_input": tool_input,
            "task_id": task_id,
            "agent_id": self.agent_name,
            "timeout": timeout,
            "callback_channel": self.channel_name
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(endpoint, json=payload, timeout=timeout + 10 if synchronous else 10)
                result = response.json()
                
                if response.status_code != 200:
                    await self.publish_update(task_id, TaskEvent.FAIL, f"Tool {tool_name} failed: {result.get('message', 'API error')}", "orchestrator", TaskOutcome.FAILURE)
                    return None
                
                if synchronous:
                    status = result.get("status", "error")
                    await self.publish_update(task_id, TaskEvent.TOOL_COMPLETE if status == "success" else TaskEvent.FAIL, f"Tool {tool_name}: {status}", "orchestrator", TaskOutcome.SUCCESS if status == "success" else TaskOutcome.FAILURE)
                    return result
                
                execution_id = result["execution_id"]
                self.pending_tool_executions[execution_id] = {"tool_name": tool_name, "task_id": task_id, "start_time": asyncio.get_event_loop().time()}
                await self.publish_update(task_id, TaskEvent.INFO, f"Tool {tool_name} execution started (ID: {execution_id})", "orchestrator")
                return execution_id
        except Exception as e:
            await self.publish_update(task_id, TaskEvent.FAIL, f"Tool {tool_name} error: {str(e)}", "orchestrator", TaskOutcome.FAILURE)
            return None

    async def handle_tool_response(self, tool_result_data: Dict[str, Any]):
        execution_id = tool_result_data.get("execution_id")
        if execution_id not in self.pending_tool_executions:
            logger.warning(f"{self.agent_name} Unknown execution_id: {execution_id}")
            return
        
        exec_info = self.pending_tool_executions.pop(execution_id)
        tool_name = exec_info["tool_name"]
        task_id = exec_info["task_id"]
        status = tool_result_data.get("status")
        result = tool_result_data.get("result")
        error = tool_result_data.get("error")
        
        if tool_name == "python_sandbox":
            self.python_execution_stats["total"] += 1
            self.python_execution_stats["times"].append(asyncio.get_event_loop().time() - exec_info["start_time"])
            if len(self.python_execution_stats["times"]) > 100:
                self.python_execution_stats["times"] = self.python_execution_stats["times"][-100:]
            if status == "success":
                self.python_execution_stats["success"] += 1
            else:
                self.python_execution_stats["failed"] += 1
        
        logger.info(f"{self.agent_name} Tool {tool_name} (ID: {execution_id}) completed: {status}")
        if status == "success":
            await self._process_successful_tool_result(tool_name, result, execution_id, task_id)
        else:
            await self._process_failed_tool_result(tool_name, error, execution_id, task_id)

    async def _process_successful_tool_result(self, tool_name: str, result: Any, execution_id: str, task_id: str):
        content = f"Tool {tool_name} succeeded: {json.dumps(result, indent=2)}"
        print(f"[{self.agent_name}] SUCCESS - {tool_name}: {result}")
        await self.publish_update(task_id, TaskEvent.TOOL_COMPLETE, content, "orchestrator", TaskOutcome.SUCCESS)

    async def _process_failed_tool_result(self, tool_name: str, error: str, execution_id: str, task_id: str):
        content = f"Tool {tool_name} failed: {error}"
        print(f"[{self.agent_name}] FAILURE - {tool_name}: {error}")
        await self.publish_update(task_id, TaskEvent.FAIL, content, "orchestrator", TaskOutcome.FAILURE)

    # Convenience Methods
    async def execute_python_code(self, code: str, task_id: str, dependencies: List[str] = [], timeout: int = 30, allow_file_access: bool = True) -> str:
        return await self.request_tool_execution("python_sandbox", {"code": code, "dependencies": dependencies, "timeout": timeout, "allow_file_access": allow_file_access}, {"task_id": task_id})

    async def search_web(self, query: str, task_id: str) -> str:
        return await self.request_tool_execution("web_search", {"query": query}, {"task_id": task_id})

    async def scrape_webpage(self, url: str, task_id: str) -> str:
        return await self.request_tool_execution("web_scrape", {"url": url}, {"task_id": task_id})

    async def execute_data_analysis(self, code: str, task_id: str, include_visualization: bool = True) -> str:
        deps = ["pandas", "numpy", "scipy"]
        if include_visualization:
            deps.extend(["matplotlib", "seaborn", "plotly"])
        return await self.request_tool_execution("python_sandbox", {"code": code, "dependencies": deps, "timeout": 60, "memory_limit": 1024, "allow_file_access": True}, {"task_id": task_id})

class ToolCapableAgent:
    def __init__(self, agent_class):
        self.enhanced_class = type(f"Tool{agent_class.__name__}", (ToolExecutionMixin, agent_class), {})
    def __call__(self, *args, **kwargs):
        return self.enhanced_class(*args, **kwargs)