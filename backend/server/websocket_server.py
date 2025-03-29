# backend/server/websocket_server.py
import asyncio
import json
import time
import uuid
from typing import Dict, Optional, Any, List
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.core.config import logger, settings
from backend.core.redis_client import get_redis_pool
from backend.factories.factories import TaskFactory
from backend.server.connection_manager import manager
from backend.models.models import (
    Task, TaskEvent, MessageIntent, TaskOutcome, 
    ReasoningEffort, Message, TaskResult, WebSocketMessage
)


# Track active WebSocket connections
active_connections: Dict[str, WebSocket] = {}
agent_status: Dict[str, str] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code
    logger.info("🚀 WebSocket Server starting up...")
    try:
        redis_client = await get_redis_pool()
        await redis_client.ping()
        logger.info("✅ Successfully connected to Redis")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Redis: {e}")
    
    # Initialize agent heartbeat monitoring
    asyncio.create_task(monitor_agent_heartbeats())
    
    # Start the Redis listener
    asyncio.create_task(redis_listener(await get_redis_pool()))
    
    yield  # This is where the app runs
    
    # Shutdown code
    logger.info("🛑 WebSocket Server shutting down...")

# Create FastAPI app with lifespan
app = FastAPI(
    title="AI Council WebSocket Server",
    description="WebSocket server for AI agent communication and task management",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def check_agent_ready(agent_name: str) -> bool:
    """
    Check if an agent is ready by checking both capitalized and lowercase heartbeats.
    Returns True if agent is ready, False otherwise.
    """
    redis_client = await get_redis_pool()
    
    # Try various formats of the heartbeat key for robustness
    variants = [
        f"{agent_name}_heartbeat",                # Original
        f"{agent_name.lower()}_heartbeat",        # Lowercase
        f"{agent_name.capitalize()}_heartbeat"    # Capitalized
    ]
    
    for variant in variants:
        heartbeat = await redis_client.get(variant)
        heartbeat_str = heartbeat.decode("utf-8") if isinstance(heartbeat, bytes) else heartbeat
        if heartbeat_str == "alive":
            logger.info(f"Agent {agent_name} ready - found at key: {variant}")
            agent_status[agent_name] = "ready"
            return True
    
    # Debug output to help diagnose issues
    heartbeat_keys = await redis_client.keys("*_heartbeat")
    logger.warning(f"Agent {agent_name} not ready - checked variants: {variants}")
    logger.warning(f"Available heartbeat keys: {heartbeat_keys}")
    agent_status[agent_name] = "offline"
    return False

async def monitor_agent_heartbeats():
    """Continuously monitor agent heartbeats and update status"""
    while True:
        try:
            # Check all required agents
            for agent in settings.REQUIRED_AGENTS:
                await check_agent_ready(agent)
                
            # Broadcast status update to all connected clients
            if active_connections:
                status_data = await check_agent_status()
                status_message = {
                    "type": "system_status_update",
                    "payload": status_data
                }
                await manager.broadcast(status_message)
                
            # Wait before checking again
            await asyncio.sleep(10)
            
        except Exception as e:
            logger.error(f"Error in heartbeat monitoring: {e}")
            await asyncio.sleep(30)  # Longer delay on error

async def check_agent_status():
    """Check the status of AI agents and return their status."""
    try:
        redis_client = await get_redis_pool()
        heartbeat_keys = await redis_client.keys("*_heartbeat")
        
        # Parse agent names from heartbeat keys
        agent_statuses = {}
        for key in heartbeat_keys:
            agent_name = key.decode("utf-8").replace("_heartbeat", "") if isinstance(key, bytes) else key.replace("_heartbeat", "")
            status = await redis_client.get(key)
            status_str = status.decode("utf-8") if isinstance(status, bytes) else status
            agent_statuses[agent_name] = "online" if status_str == "alive" else "offline"
        
        return {
            "agent_status": agent_statuses,
            "system_ready": len(agent_statuses) > 0 and all(status == "online" for status in agent_statuses.values()),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error checking agent status: {e}")
        return {
            "agent_status": {},
            "system_ready": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

async def all_agents_ready() -> bool:
    """Check if all required agents are ready to accept connections"""
    all_ready = True
    missing_agents = []
    
    for agent in settings.REQUIRED_AGENTS:
        if not await check_agent_ready(agent):
            all_ready = False
            missing_agents.append(agent)
    
    if all_ready:
        logger.info("✅ All agents ready!")
    else:
        logger.warning(f"⚠️ Agents not ready: {missing_agents}")
        
        # Debug output - list all heartbeat keys in Redis
        redis_client = await get_redis_pool()
        heartbeat_keys = await redis_client.keys("*_heartbeat")
        logger.info(f"All heartbeat keys in Redis: {heartbeat_keys}")
        
    return all_ready

async def wait_for_agents(timeout: int = 30) -> bool:
    """
    Wait for all agents to be ready with a timeout.
    Returns True if all agents ready, False if timeout exceeded.
    """
    start_time = asyncio.get_event_loop().time()
    while not await all_agents_ready():
        if asyncio.get_event_loop().time() - start_time > timeout:
            logger.error("⏱️ Timeout waiting for agents to be ready")
            return False
        await asyncio.sleep(1)
    return True

async def redis_listener(redis_client):
    """Listen for messages from Redis and broadcast them to WebSocket clients."""
    channel = "responses_channel"
    
    async with redis_client.pubsub() as pubsub:
        await pubsub.subscribe(channel)
        logger.info(f"Redis listener subscribed to channel: {channel}")
        
        try:
            while True:
                try:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    
                    if not message:
                        await asyncio.sleep(0.01)
                        continue
                        
                    if message["type"] == "message":
                        data = message["data"]
                        if isinstance(data, bytes):
                            data = data.decode("utf-8")
                        
                        logger.debug(f"Redis message received: {data[:100]}...")
                        
                        # Check if any clients are connected before processing
                        active_connections_count = manager.get_active_connections_count()
                        if active_connections_count == 0:
                            logger.debug("No WebSocket clients connected, skipping broadcast")
                            continue
                            
                        try:
                            json_data = json.loads(data)
                            
                            # Skip messages from frontend to prevent echoing
                            if json_data.get("source") == "frontend":
                                logger.debug("Skipping frontend echo")
                                continue
                                
                            # Get message type, defaulting to "message" if not specified
                            message_type = json_data.get("type", "message")
                            
                            # For system_status_update messages
                            if message_type == "system_status_update":
                                formatted_message = {
                                    "type": "system_status_update",
                                    "payload": json_data
                                }
                                await manager.broadcast(formatted_message)
                                
                            # If message already has the right structure, broadcast directly
                            elif "type" in json_data and "payload" in json_data:
                                await manager.broadcast(json_data)
                                
                            # Otherwise, format as a standard message
                            else:
                                formatted_message = {
                                    "type": message_type,
                                    "payload": json_data
                                }
                                await manager.broadcast(formatted_message)
                                
                        except json.JSONDecodeError:
                            logger.warning(f"Received non-JSON data from Redis: {data[:100]}...")
                        except Exception as e:
                            logger.error(f"Error processing Redis message: {str(e)}")
                            
                except asyncio.CancelledError:
                    logger.info("Redis listener task cancelled")
                    break
                except Exception as e:
                    logger.exception(f"Unexpected error in Redis listener: {e}")
                    await asyncio.sleep(1)  # Prevent tight loop on persistent errors
        finally:
            logger.info(f"Unsubscribing from Redis channel: {channel}")
            if pubsub:
                await pubsub.unsubscribe(channel)
                await pubsub.close()

async def process_task_creation(message: dict) -> dict:
    """
    Process a task creation request using the enhanced TaskFactory.
    Returns the task data with reasoning effort information.
    """
    try:
        # Extract task information from message
        content = message.get("content", "")
        agent = message.get("agent", "user")
        target_agent = message.get("target_agent", settings.DEFAULT_AGENT)
        event_str = message.get("event", "plan")
        intent_str = message.get("intent", "start_task")
        confidence = message.get("confidence", 0.9)
        
        # Generate task_id if not provided
        task_id = message.get("task_id", f"task_{uuid.uuid4().hex[:10]}")
        
        # Parse event and intent
        try:
            event = TaskEvent(event_str)
        except ValueError:
            event = TaskEvent.PLAN
            logger.warning(f"Invalid event '{event_str}', defaulting to PLAN")
            
        try:
            intent = MessageIntent(intent_str)
        except ValueError:
            intent = MessageIntent.START_TASK
            logger.warning(f"Invalid intent '{intent_str}', defaulting to START_TASK")
        
        # Get deadline pressure if present
        deadline_pressure = message.get("deadline_pressure", None)
        
        # Create task with TaskFactory
        task, diagnostics = TaskFactory.create_task(
            task_id=task_id,
            agent=agent,
            content=content,
            target_agent=target_agent,
            intent=intent,
            event=event,
            confidence=confidence,
            deadline_pressure=deadline_pressure
        )
        
        # Log the task creation with effort level
        logger.info(f"Created task {task_id} with {task.reasoning_effort.value.upper()} effort, targeting {target_agent}")
        
        # Return task data and diagnostics
        task_data = task.model_dump()
        return {
            "task": task_data,
            "diagnostics": diagnostics,
            "task_id": task_id,
            "reasoning_effort": task.reasoning_effort.value,
            "reasoning_strategy": task.reasoning_strategy.value,
        }
        
    except Exception as e:
        logger.error(f"Error creating task: {str(e)}")
        return {
            "error": f"Task creation failed: {str(e)}",
            "task_id": message.get("task_id", "unknown")
        }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for client connections"""
    # Accept the connection using your connection manager
    client_id = await manager.connect(websocket)
    logger.info(f"WebSocket connection accepted for client {client_id}")
    
    # Send a more detailed welcome message
    welcome_message = {
        "type": "connection_established",
        "payload": {
            "client_id": client_id,
            "message": "Connected to WebSocket server",
            "timestamp": datetime.now().isoformat()
        }
    }
    await manager.send_personal_message(welcome_message, client_id)
    
    # Check for agent availability and send status
    status_data = await check_agent_status()
    status_message = {
        "type": "system_status_update",
        "payload": status_data
    }
    await manager.send_personal_message(status_message, client_id)
    
    # Wait for agents to be ready
    system_ready = await wait_for_agents(timeout=5)  # Short timeout for initial check
    if not system_ready:
        logger.warning(f"Starting session for client {client_id} with agents not ready")
        not_ready_message = {
            "type": "warning",
            "payload": {
                "message": "Some agents are not ready. You may experience limited functionality.",
                "timestamp": datetime.now().isoformat()
            }
        }
        await manager.send_personal_message(not_ready_message, client_id)
    
    try:
        # Main message receiving loop
        while True:
            # Wait for messages from the client
            data = await websocket.receive_text()
            logger.info(f"Received message from client {client_id}: {data[:100]}...")
            
            try:
                # Parse the message
                message = json.loads(data)
                
                # Add client ID if not present
                if "client_id" not in message:
                    message["client_id"] = client_id
                
                # Add source identifier if not present
                if "source" not in message:
                    message["source"] = "frontend"
                
                # Process "start_task" message type with our TaskFactory
                if message.get("type") == "start_task":
                    task_result = await process_task_creation(message)
                    
                    # Send the task creation response
                    task_response = {
                        "type": "task_created",
                        "payload": task_result
                    }
                    await manager.send_personal_message(task_response, client_id)
                    
                    # If task was created successfully, publish to Redis
                    if "error" not in task_result:
                        # Add task to Redis for agents to pick up
                        redis_client = await get_redis_pool()
                        await redis_client.publish("responses_channel", json.dumps({
                            "type": "task",
                            "source": "task_factory",
                            "task": task_result["task"]
                        }))
                        logger.info(f"Published task {task_result['task_id']} to Redis")
                
                # Forward other messages to Redis
                else:
                    redis_client = await get_redis_pool()
                    await redis_client.publish("responses_channel", json.dumps(message))
                    logger.info(f"Published message from client {client_id} to Redis")
                
                # Send acknowledgment
                ack_message = {
                    "type": "ack",
                    "payload": {
                        "received": True,
                        "message_id": message.get("id", None),
                        "timestamp": datetime.now().isoformat()
                    }
                }
                await manager.send_personal_message(ack_message, client_id)
                
            except json.JSONDecodeError:
                logger.warning(f"Received invalid JSON from client {client_id}")
                error_message = {
                    "type": "error",
                    "payload": {
                        "message": "Invalid JSON format",
                        "received": data[:100] + "..." if len(data) > 100 else data
                    }
                }
                await manager.send_personal_message(error_message, client_id)
            except Exception as e:
                logger.error(f"Error processing message from client {client_id}: {e}")
                try:
                    error_message = {
                        "type": "error",
                        "payload": {
                            "message": "Error processing message",
                            "error": str(e)
                        }
                    }
                    await manager.send_personal_message(error_message, client_id)
                except:
                    pass  # If we can't send the error, client might be disconnected
                
    except WebSocketDisconnect:
        logger.info(f"Client {client_id} disconnected")
    except Exception as e:
        logger.exception(f"Unexpected error with client {client_id}: {e}")
    finally:
        # Disconnect using your connection manager
        manager.disconnect(client_id)
        logger.info(f"Client {client_id} connection closed.")

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    try:
        redis_client = await get_redis_pool()
        redis_ping = await redis_client.ping()
        agent_statuses = await check_agent_status()
        
        return {
            "status": "healthy",
            "redis_connected": redis_ping,
            "active_connections": manager.get_active_connections_count(),
            "agent_status": agent_statuses,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }