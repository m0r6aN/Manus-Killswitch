# Manus-Killswitch Tool Integration

## Overview

This package integrates various tools with the Manus-Killswitch architecture, including web search, web scraping, Python code execution, and data oracles. It provides a unified interface for agents to access these tools through a secure sandbox environment.

## Features

- **Sandboxed Python Execution**: Execute Python code safely in Docker containers
- **Unified Tool Interface**: Common interface for all tools
- **Agent Integration**: Easy-to-use mixins for agent integration
- **Async Support**: All tools support asynchronous operation
- **Redis Integration**: Tool execution results published to Redis
- **Mocked APIs**: Placeholders for real API integrations coming soon

## Key Components

1. **EnhancedToolExecutor** - Core service for tool execution
2. **Tool Routes** - FastAPI endpoints for accessing tools
3. **Agent Integration** - Mixin for agent capability enhancement

## Available Tools

- **`python_exec`** - Execute Python code in a sandbox
- **`web_search`** - Search the web (mocked)
- **`web_scrape`** - Scrape a webpage (mocked)
- **`file_rw`** - Read/write files
- **`local_file_retriever`** - Retrieve and parse code files
- **`weather`** - Get weather info (mocked)
- **`news`** - Get news articles (mocked)
- **`stock`** - Get stock information (mocked)
- **`crypto`** - Get cryptocurrency info (mocked)
- **`image_analyzer`** - Analyze image content (mocked)

## Installation

1. Copy the provided files to your Manus-Killswitch installation
2. Update your `requirements.txt` with the required dependencies
3. Register the tool routes in your FastAPI app
4. Decorate your agents with `ToolCapableAgent`

## Getting Started

```python
# Create a tool-capable agent
from backend.agents.agent_tool_integration import ToolCapableAgent
from backend.agents.base_agent import BaseAgent

@ToolCapableAgent
class MyAgent(BaseAgent):
    # Your agent implementation
    pass

# Use the agent to execute Python code
result = await agent.execute_python_code(
    code="print('Hello, world!')",
    task_id="task_123"
)

# Or search the web
result = await agent.search_web(
    query="Latest AI news"
)
```

## Testing

Run the provided test script to verify the installation:

```bash
python test_tool_integration.py
```

## Extending

To add a new tool:

1. Add the tool implementation to `enhanced_executor.py`
2. Register the tool in the `tools` dictionary
3. Add a convenience method to `ToolExecutionAgent` if desired

## Next Steps

- Replace mocked implementations with real APIs
- Add authentication and rate limiting
- Implement additional tools
- Add caching for tool results

## Requirements

- Python 3.8+
- Docker (for sandboxed execution)
- Redis
- FastAPI
- httpx
- aiofiles

## License

Same as the main Manus-Killswitch project