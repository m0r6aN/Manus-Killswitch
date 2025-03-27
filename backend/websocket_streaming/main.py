# backend/websocket-streaming/websocket-server.py

from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json
from redis.asyncio import Redis
import asyncio
from loguru import logger
import sys
from contextlib import asynccontextmanager

from backend.models.models import MessageIntent, TaskEvent, TaskOutcome
from backend.task_engine import task_manager

# Remove default logger and set up both console and file logging
logger.remove()
logger.add(sys.stdout, level="INFO", format="{time} - {level} - {message}")
logger.add("/app/logs/websocket-server.log", level="INFO", format="{time} - {level} - {message}", rotation="1 MB")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code
    logger.info("WebSocket Server starting up...")
    try:
        await redis_client.ping()
        logger.info("Successfully connected to Redis")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
    
    yield  # This is where the app runs
    
    # Shutdown code
    logger.info("WebSocket Server shutting down...")

# Initialize Redis client
redis_client = Redis(host="redis", port=6379, decode_responses=True)

# Create FastAPI app with lifespan
app = FastAPI(lifespan=lifespan)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Allow frontend origin
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

async def check_agent_ready(agent_name: str):
    """Check if an agent is ready by checking both capitalized and lowercase heartbeats"""
    # Try both uppercase and lowercase versions of the heartbeat key
    variants = [
        f"{agent_name}_heartbeat",                # Original
        f"{agent_name.lower()}_heartbeat",        # Lowercase
        f"{agent_name.capitalize()}_heartbeat"    # Capitalized
    ]
    
    for variant in variants:
        heartbeat = await redis_client.get(variant)
        if heartbeat == "alive":
            logger.info(f"Agent {agent_name} ready - found at key: {variant}")
            return True
    
    # Debug output to help diagnose issues
    heartbeat_keys = await redis_client.keys("*_heartbeat")
    logger.warning(f"Agent {agent_name} not ready - checked variants: {variants}")
    logger.warning(f"Available heartbeat keys: {heartbeat_keys}")
    return False

async def all_agents_ready():
    """Check if all required agents are ready to accept connections"""
    # Required agent names - these match the logical names used in the system
    required_agents = ["Grok", "Claude", "GPT"]
    
    all_ready = True
    missing_agents = []
    
    for agent in required_agents:
        if not await check_agent_ready(agent):
            all_ready = False
            missing_agents.append(agent)
    
    if all_ready:
        logger.info("All agents ready!")
    else:
        logger.warning(f"Agents not ready: {missing_agents}")
        
        # Debug output - list all heartbeat keys in Redis
        heartbeat_keys = await redis_client.keys("*_heartbeat")
        logger.info(f"All heartbeat keys in Redis: {heartbeat_keys}")
        
    return all_ready

async def wait_for_agents(timeout: int = 30):
    start_time = asyncio.get_event_loop().time()
    while not await all_agents_ready():
        if asyncio.get_event_loop().time() - start_time > timeout:
            logger.error("Timeout waiting for agents to be ready")
            return False
        await asyncio.sleep(1)
    return True

@app.websocket("/ws/tasks")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Client connected to /ws/tasks")
    
    # Log client information if available
    client = websocket.client
    logger.info(f"Client info: {client}")
    
    async with redis_client.pubsub() as pubsub:
        await pubsub.subscribe("responses_channel")
        logger.info("Subscribed to Redis responses_channel")
        
        # Wait for agents to be ready before starting message processing
        if not await wait_for_agents():
            logger.error("Agents not ready - closing connection")
            await websocket.send_json({"error": "Agents not ready, please try again later"})
            await websocket.close()
            return
        
        try:
            await asyncio.gather(
                listen_to_redis(pubsub, websocket),
                receive_from_ws(websocket)
            )
        except Exception as e:
            logger.error(f"Error in websocket handler: {e}")
            await websocket.close()

@app.get("/health")
async def health_check():
    try:
        await redis_client.ping()
        return {"status": "healthy", "redis": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "redis": "disconnected"}
          
async def receive_from_ws(websocket: WebSocket):
    """Handle incoming messages from the client"""
    logger.info("Started receive_from_ws function")
    while True:
        try:
            # Receive message from websocket
            message = await websocket.receive_json()
            
            # Process based on message type
            if message.get("type") == "start_task":
                await handle_start_task(message, websocket)
            elif message.get("type") == "check_status":
                await handle_check_status(message, websocket)
            elif message.get("type") == "complete_task":
                await handle_complete_task(message, websocket)
        except WebSocketDisconnect:
            logger.info("Client disconnected")
            break
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await websocket.send_json({"error": str(e)})
            
    async def handle_start_task(message, websocket):
        """Handle a request to start a new task"""
        try:
            content = message.get("content", "")
            agent = message.get("agent", "Commander")
            target_agent = message.get("target_agent", "Grok")  # Default to Grok if not specified
            
            # Determine if there's any deadline pressure
            deadline = message.get("deadline")
            deadline_pressure = 0.8 if deadline and deadline == "urgent" else 0.5
            
            # Create and submit the task
            task, diagnostics = await task_manager.create_and_submit_task(
                content=content,
                agent=agent,
                target_agent=target_agent,
                intent=MessageIntent.START_TASK,
                event=TaskEvent.PLAN,
                confidence=0.9,
                deadline_pressure=deadline_pressure
            )
            
            # Send confirmation to client
            await websocket.send_json({
                "type": "task_created",
                "task_id": task.task_id,
                "effort": task.reasoning_effort.value,
                "diagnostics": diagnostics
            })
            
            logger.info(f"Created task {task.task_id} with effort {task.reasoning_effort.value}")        
        except Exception as e:
            logger.error(f"Error creating task: {e}")
            await websocket.send_json({"error": f"Failed to create task: {str(e)}"})

async def handle_check_status(message, websocket):
    """Handle a request to check task status"""
    task_id = message.get("task_id")
    if task_id in task_manager.active_tasks:
        task_data = task_manager.active_tasks[task_id]
        
        # Calculate elapsed time
        elapsed_time = datetime.now().timestamp() - task_data["start_time"]
        
        await websocket.send_json({
            "type": "task_status",
            "task_id": task_id,
            "status": "in_progress",
            "elapsed_time": elapsed_time,
            "interactions": len(task_data["agent_interactions"])
        })
    else:
        # Check if it's in history
        for task in task_manager.task_history:
            if task["task"]["task_id"] == task_id:
                await websocket.send_json({
                    "type": "task_status",
                    "task_id": task_id,
                    "status": "completed",
                    "outcome": task.get("outcome", "unknown"),
                    "duration": task.get("duration", 0)
                })
                return
                
        # Not found
        await websocket.send_json({
            "type": "task_status",
            "task_id": task_id,
            "status": "not_found"
        })

    async def handle_complete_task(message, websocket):
        """Handle a request to complete a task"""
        task_id = message.get("task_id")
        outcome_str = message.get("outcome", "completed")
        content = message.get("content", "Task completed")
        
        # Map string to enum
        outcome_map = {
            "completed": TaskOutcome.COMPLETED,
            "merged": TaskOutcome.MERGED,
            "escalated": TaskOutcome.ESCALATED
        }
        outcome = outcome_map.get(outcome_str, TaskOutcome.COMPLETED)
        
        # Get contributing agents
        contributing_agents = message.get("contributing_agents", [])
        
        # Complete the task
        result = await task_manager.complete_task(
            task_id=task_id,
            outcome=outcome,
            result_content=content,
            contributing_agents=contributing_agents
        )
        
        if result:
            await websocket.send_json({
                "type": "task_completed",
                "task_id": task_id,
                "outcome": outcome.value,
                "task_result": result.model_dump()
            })
        else:
            await websocket.send_json({
                "type": "error",
                "message": f"Failed to complete task {task_id}, task not found"
            })

            
async def listen_to_redis(pubsub, websocket: WebSocket):
    logger.info("Started listen_to_redis function")
    try:
        async for message in pubsub.listen():
            logger.info(f"Redis message received: {message}")
            if message["type"] == "message":
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                    
                try:
                    data = json.loads(data)
                    # Only forward to frontend if not from frontend
                    if data.get("source") != "frontend":
                        logger.info(f"Sending to WS: {data}")
                        await websocket.send_json(data)
                    else:
                        logger.info(f"Skipping frontend echo: {data}")
                except json.JSONDecodeError:
                    logger.warning(f"Received non-JSON data from Redis: {data}")
    except Exception as e:
        logger.error(f"Redis listener error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Uvicorn server...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")