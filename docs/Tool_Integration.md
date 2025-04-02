# Tool Integration Guide for Manus Killswitch

## Overview
This guide walks you through integrating tools into the Manus Killswitch architecture. We’ve consolidated everything into a unified `backend/tools/` powerhouse—agents wield tool capabilities via a slick mixin, while the ToolCore API serves up RESTful endpoints backed by local tools and a Python sandbox (Docker). Results flow through Redis, keeping the system tight and responsive.

## Architecture
The new setup revolves around three core components in `backend/tools/`:
1. **ToolCore API (`api_integration.py`)**: FastAPI endpoints for tool execution—handles local tools (`web_search`, `file_rw`) and proxies to the Python sandbox, with built-in polling for sandbox results.  
2. **Agent Tool Mixin (`agent_tools.py`)**: A `ToolExecutionMixin` that plugs into `BaseAgent`, giving agents seamless access to tools via HTTP requests and Redis responses.  
3. **Redis Listener (Optional, `tool_core.py`)**: A lightweight Redis listener for future tool request queuing—currently optional, expandable as needed.

### Flow
- **Request**: Agent -> `ToolExecutionMixin.request_tool_execution` -> POST to `/execute/`  
- **Execution**: `api_integration.py` -> Local tool or `ToolCoreService` -> Sandbox API -> Polling  
- **Response**: `ToolCoreService` -> Redis (`TOOL_COMPLETE`) -> `BaseAgent._listen_for_messages` -> `handle_tool_response`  

## Files
- **`backend/tools/api_integration.py`**: ToolCore API—routes, local tools, sandbox proxy with polling.  
- **`backend/tools/agent_tools.py`**: Agent mixin—tool requests, response handling, Python wrappers.  
- **`backend/tools/tool_core.py`**: Optional Redis listener for tool requests.  
- **`backend/agents/base_agent.py`**: Updated with `ToolExecutionMixin` integration.  

### Deleted Files
Old files torched in the refactor:
- `routes/python_routes.py`
- `routes/tool_routes.py`
- `agents/tools_agent/agent_tool_integration.py`
- `agents/tools_agent/task_tool_integration.py`
- `agents/tools_agent/agent_python_tools.py`

## Installation
1. **Place Files**:  
   - Drop `api_integration.py`, `agent_tools.py`, `tool_core.py` into `backend/tools/`.  
   - Patch `base_agent.py` in `backend/agents/` (see below).  

2. **Dependencies**: Add to `requirements.txt`:  
   ```
   aiofiles>=0.8.0
   httpx>=0.24.0
   redis>=5.0.0  # For redis.asyncio
   ```

3. **Register Routes**: In your main FastAPI app (e.g., `backend/main.py`):  
   ```python
   from fastapi import FastAPI
   from backend.tools.api_integration import register_execute_routes

   app = FastAPI(title="Manus Killswitch API")
   register_execute_routes(app)
   ```

## Usage

### 1. Using Tools from Agents
Patch `BaseAgent` with the mixin:
```python
from backend.tools.agent_tools import ToolExecutionMixin
import redis.asyncio as redis

class BaseAgent(ToolExecutionMixin):
    def __init__(self, agent_name: str, redis_client: redis.Redis):
        super().__init__(agent_name=agent_name, redis_client=redis_client)
        self.channel_name = f"{agent_name}_channel"
        # Rest of BaseAgent init
```

Then use it in your agent:
```python
from backend.agents.base_agent import BaseAgent

class GPTAgent(BaseAgent):
    pass

# Usage
agent = GPTAgent("gpt_agent", redis_client)
await agent.start()

# Generic tool execution
execution_id = await agent.request_tool_execution(
    tool_name="web_search",
    tool_input={"query": "AI news"},
    task_context={"task_id": "web_task_123"}
)

# Python sandbox
execution_id = await agent.execute_python_code(
    code="print('Hello, cosmos!')",
    task_id="py_task_123"
)

# Web search convenience
execution_id = await agent.search_web("Latest AI breakthroughs", "search_task_123")
```

### 2. Direct API Access
Hit the ToolCore API directly:
```python
import httpx

async def execute_tool():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/execute/",  # Adjust port as needed
            json={
                "tool_name": "python_sandbox",
                "parameters": {"code": "print('Direct hit!')"},
                "task_id": "direct_task_123",
                "callback_channel": "test_agent_channel"
            }
        )
        return response.json()
```

### 3. Python Code Execution
Use the sandbox endpoint:
```python
async def run_python():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/execute/",
            json={
                "tool_name": "python_sandbox",
                "parameters": {
                    "code": "import numpy as np; print(np.array([1, 2, 3]))",
                    "dependencies": ["numpy"],
                    "timeout": 30,
                    "allow_file_access": True
                },
                "task_id": "numpy_task_123"
            }
        )
        return response.json()
```

## Available Tools
| Tool Name           | Description                  | Input Parameters                       |
|---------------------|------------------------------|----------------------------------------|
| `python_sandbox`    | Execute Python in Docker     | `code`, `dependencies`, `timeout`, `allow_file_access` |
| `web_search`        | Search the web (mocked)      | `query`                                |
| `web_scrape`        | Scrape a page (mocked)       | `url`                                  |
| `file_rw`           | Read/write files             | `mode` ("read"/"write"), `path`, `content` (write) |
| `local_file_retriever` | Parse code files          | `path`                                 |

- **Note**: `web_search`, `web_scrape` are mocked—real APIs coming soon!

## Testing the Integration
1. **Start the Server**: Run `uvicorn backend.main:app --reload`.  
2. **Test Script**:  
   ```python
   # test_tools.py
   import asyncio
   import httpx

   async def test_python_sandbox():
       async with httpx.AsyncClient() as client:
           response = await client.post(
               "http://localhost:8000/execute/",
               json={
                   "tool_name": "python_sandbox",
                   "parameters": {"code": "print('Cosmos conquered!')"},
                   "task_id": "test_py"
               }
           )
           print(f"Python result: {response.json()}")

   async def test_web_search():
       async with httpx.AsyncClient() as client:
           response = await client.post(
               "http://localhost:8000/execute/quick/web_search",
               json={"query": "AI news"}
           )
           print(f"Web search result: {response.json()}")

   async def main():
       await test_python_sandbox()
       await test_web_search()

   if __name__ == "__main__":
       asyncio.run(main())
   ```

## Integration with Redis
- **Channel**: Results hit the agent’s channel (e.g., `gpt_agent_channel`) as `TOOL_COMPLETE`:  
  ```json
  {
      "type": "TOOL_COMPLETE",
      "data": {
          "execution_id": "task_123",
          "status": "success",
          "result": {"stdout": "Hello, cosmos!", "stderr": "", "execution_time": 0.5},
          "error": null
      }
  }
  ```
- **Agents**: `BaseAgent._listen_for_messages` catches these, routes to `ToolExecutionMixin.handle_tool_response`.

## Troubleshooting
- **Tool Not Found**: Check `tool_name` against `/tools/list`.  
- **Sandbox Error**: Ensure Docker sandbox is running (`SANDBOX_API_URL`).  
- **Redis Issues**: Verify Redis is up and `REDIS_URL` is set.  
- **Timeout**: Bump `timeout` in tool input for slow ops.

## Next Steps
1. **Real APIs**: Swap mocks for `web_search`, `web_scrape` (e.g., SerpAPI, BeautifulSoup).  
2. **Security**: Add auth and rate limits to `/execute/`.  
3. **Caching**: Store results in Redis for quick retrieval.  
4. **Optimization**: Replace polling with sandbox Redis callbacks if latency spikes.

---

