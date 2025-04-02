import pytest
import asyncio
from fastapi.testclient import TestClient
from backend.main import app  # Adjust import based on your app file
from backend.core.redis_client import get_redis_pool
import redis.asyncio as redis
from backend.agents.base_agent import BaseAgent

@pytest.fixture
async def client():
    return TestClient(app)

@pytest.fixture
async def redis_client():
    return await get_redis_pool()

@pytest.fixture
async def agent(redis_client):
    agent = BaseAgent("test_agent", redis_client)
    await agent.start()
    yield agent
    await agent.stop()

@pytest.mark.asyncio
async def test_web_search(client, agent, redis_client):
    # Request
    task_id = "test_web_search"
    execution_id = await agent.request_tool_execution("web_search", {"query": "AI news"}, {"task_id": task_id})
    assert execution_id is not None
    
    # Wait for result (simulate polling)
    await asyncio.sleep(2)
    
    # Check agent's processed result
    assert execution_id not in agent.pending_tool_executions  # Should be popped
    # Add more assertions based on frontend logs or agent's internal state

@pytest.mark.asyncio
async def test_python_sandbox(client, agent, redis_client):
    # Request
    task_id = "test_python"
    code = "print('Hello from sandbox!')"
    execution_id = await agent.execute_python_code(code, task_id)
    assert execution_id is not None
    
    # Wait for sandbox result
    await asyncio.sleep(5)  # Adjust based on sandbox speed
    
    # Check result
    assert execution_id not in agent.pending_tool_executions
    # Add assertions for stdout in agent's logs or frontend

@pytest.mark.asyncio
async def test_file_rw_failure(client, agent, redis_client):
    # Request with bad path
    task_id = "test_file_rw_fail"
    execution_id = await agent.request_tool_execution("file_rw", {"mode": "read", "path": "../forbidden.txt"}, {"task_id": task_id})
    assert execution_id is not None
    
    # Wait for failure
    await asyncio.sleep(2)
    
    # Check failure handled
    assert execution_id not in agent.pending_tool_executions

@pytest.mark.asyncio
async def test_tool_list(client):
    response = client.get("/tools/list")
    assert response.status_code == 200
    tools = response.json()["tools"]
    assert "web_search" in tools
    assert "python_sandbox" in tools