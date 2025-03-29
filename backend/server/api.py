import sys
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Optional
import asyncio
from loguru import logger
import numpy as np
from backend.agents.grok_agent import GrokAgent
from backend.config import settings
from backend.models.models import MessageIntent, TaskEvent
from contextlib import asynccontextmanager

# Configure Loguru
logger.remove()
logger.add(
    sys.stderr,
    level=settings.LOGURU_LEVEL,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

# Define lifespan handler
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    await agent.start()
    yield
    # Shutdown logic
    await agent.stop()

app = FastAPI(lifespan=lifespan)  # Pass lifespan handler to FastAPI
agent = GrokAgent()

@app.post("/tasks/create")
async def create_task(content: str, agent_name: str = "user", batch_id: Optional[str] = None, depends_on: Optional[str] = None):
    if depends_on:
        task, diagnostics, target = await agent.create_dependent_task(content, depends_on, agent_name)
    else:
        if batch_id:
            # Handle batching with similarity check
            task, diagnostics, target = await agent.hub.create_and_route_task(content, agent_name)
            similar_tasks = [t for t in agent.task_states.values() if t.get("batch_id") == batch_id]
            if similar_tasks:
                new_embedding = agent.hub.clustering_system.embedding_model.encode([content])[0]
                batch_embeddings = [
                    agent.hub.clustering_system.embedding_model.encode([t["content"]])[0]
                    for t in similar_tasks[:3]
                ]
                similarities = [
                    np.dot(new_embedding, batch_emb) / 
                    (np.linalg.norm(new_embedding) * np.linalg.norm(batch_emb))
                    for batch_emb in batch_embeddings
                ]
                avg_similarity = sum(similarities) / len(similarities)
                diagnostics["batch_similarity"] = avg_similarity
                if avg_similarity > 0.7:
                    batch_content = "\n".join([t["content"] for t in similar_tasks] + [content])
                    task.content = f"Batch {batch_id}: {batch_content}"
                    target = similar_tasks[0]["target_agent"]
                else:
                    task.metadata["batch_id"] = batch_id
        else:
            task, diagnostics, target = await agent.hub.create_and_route_task(content, agent_name)
    if task:
        return {"task_id": task.task_id, "target_agent": target, "diagnostics": diagnostics}
    return {"error": "Task creation failed"}, 400

@app.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    task_data = agent.hub.task_manager.active_tasks.get(task_id)
    if task_data:
        return {
            "task_id": task_id,
            "status": task_data["task"].event.value,
            "agent": task_data["task"].target_agent,
            "content": task_data["task"].content,
            "start_time": task_data["start_time"]
        }
    completed = next((t for t in agent.hub.task_manager.task_history if t["task"].task_id == task_id), None)
    if completed:
        return {
            "task_id": task_id,
            "status": "completed",
            "outcome": completed["outcome"],
            "duration": completed["duration"]
        }
    return {"error": "Task not found"}, 404

@app.get("/tasks/{task_id}/results")
async def get_task_results(task_id: str):
    completed = next((t for t in agent.hub.task_manager.task_history if t["task"].task_id == task_id), None)
    if completed and "result" in completed:
        return {
            "task_id": task_id,
            "result": completed["result"].content,
            "outcome": completed["outcome"],
            "contributing_agents": completed["result"].contributing_agents
        }
    return {"error": "No results available"}, 404

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    agent.ws = websocket
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        agent.ws = None

async def run_benchmark(task_count: int = 100):
    tasks = [f"Test task {i}: {np.random.choice(['analyze', 'create', 'compare'])} stuff" for i in range(task_count)]
    start = time.time()
    for content in tasks:
        await agent.hub.create_and_route_task(content, "benchmark")
    duration = time.time() - start
    throughput = task_count / duration
    logger.info(f"Benchmark: {throughput:.2f} tasks/sec")
    return throughput

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)