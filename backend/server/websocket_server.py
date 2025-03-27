# FastAPI WebSocket server logic

import asyncio
import json
import redis.asyncio as redis
from fastapi import WebSocket, WebSocketDisconnect

from backend.core.config import settings, logger, get_agent_channel, get_agent_heartbeat_key
from backend.core.redis_client import get_redis_pool, publish_message, get_key
from backend.models.models import WebSocketMessage, Message, Task, TaskResult, MessageIntent, TaskEvent, TaskOutcome # Import necessary models
from backend.factories.factories import TaskFactory # To create tasks from user input
from .connection_manager import manager

async def redis_listener(redis_client: redis.Redis):
    """Listens to Redis broadcast channel and sends messages to WebSocket clients."""
    pubsub = redis_client.pubsub()
    channel = settings.FRONTEND_CHANNEL
    await pubsub.subscribe(channel)
    logger.info(f"WebSocket Server subscribed to Redis channel '{channel}' for frontend broadcasts.")

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0) # Use timeout to allow checking loop condition
            if message and message.get("type") == "message":
                raw_data = message["data"]
                logger.debug(f"WS Server received from Redis '{channel}': {raw_data[:100]}...")
                try:
                    # Attempt to parse as a known agent message type (Message, Task, TaskResult)
                    # We need to wrap it in the WebSocketMessage format for the frontend
                    parsed_data = None
                    parsed_type = "unknown_update" # Default type

                    # Try parsing as different types - This is inefficient.
                    # Agents should ideally publish in a consistent format or include type info.
                    # Assuming agents publish serialized Message, Task, or TaskResult directly.
                    try:
                         parsed_data = TaskResult.deserialize(raw_data).model_dump()
                         parsed_type = "task_result"
                    except Exception:
                         try:
                             parsed_data = Task.deserialize(raw_data).model_dump()
                             parsed_type = "task_update" # A task object can represent an update
                         except Exception:
                             try:
                                 parsed_data = Message.deserialize(raw_data).model_dump()
                                 # Determine type based on intent
                                 intent = parsed_data.get("intent")
                                 if intent == MessageIntent.CHAT.value:
                                      parsed_type = "chat_message"
                                 elif intent == MessageIntent.SYSTEM.value:
                                      parsed_type = "system_info"
                                 else:
                                      parsed_type = "agent_message" # Generic
                             except Exception as parse_err:
                                 logger.error(f"Failed to parse Redis message into known agent model: {parse_err}. Raw: {raw_data[:100]}...")
                                 # Send raw data or an error message
                                 parsed_data = {"error": "Failed to parse message", "raw": raw_data}
                                 parsed_type = "error"

                    if parsed_data:
                        ws_message = WebSocketMessage(type=parsed_type, payload=parsed_data)
                        await manager.broadcast(ws_message.model_dump())

                except Exception as e:
                    logger.exception(f"Error processing message from Redis '{channel}': {e}")
            # Add a small sleep to prevent high CPU usage if timeout=0
            await asyncio.sleep(0.01)
    except asyncio.CancelledError:
        logger.info("Redis listener task cancelled.")
    except redis.exceptions.ConnectionError:
         logger.error("Redis connection lost in listener. Task exiting.")
         # Consider adding reconnection logic or letting docker restart the service
    except Exception as e:
         logger.exception(f"Unexpected error in Redis listener: {e}")
    finally:
        logger.info(f"Unsubscribing WS Server from Redis channel '{channel}'.")
        if pubsub:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

async def handle_websocket_connection(websocket: WebSocket):
    """Handles incoming WebSocket connections and messages."""
    client_id = await manager.connect(websocket)
    redis_client = await get_redis_pool()

    try:
        while True:
            raw_data = await websocket.receive_text()
            logger.debug(f"WS Server received from Client {client_id}: {raw_data[:100]}...")
            try:
                ws_message = WebSocketMessage.deserialize(raw_data)
                ws_message.client_id = client_id # Inject client_id for context

                # Process message based on type
                if ws_message.type == "chat_message" or ws_message.type == "start_task":
                    # Route user message/task to Grok (Orchestrator)
                    payload = ws_message.payload
                    content = payload.get("content")
                    task_id = payload.get("task_id") # Frontend might send existing task_id for related messages

                    if not content:
                         await manager.send_personal_message(
                             WebSocketMessage(type="error", payload={"message": "Content cannot be empty."}).model_dump(),
                             client_id
                         )
                         continue

                    # Use TaskFactory to create a Task object
                    # Agent is 'user' or client_id, target is Grok
                    task = TaskFactory.create_task(
                         agent=client_id, # Use client_id as the user identifier
                         content=content,
                         target_agent=settings.GROK_AGENT_NAME,
                         task_id=task_id, # Pass existing task_id if available
                         intent=MessageIntent.START_TASK if ws_message.type == "start_task" else MessageIntent.CHAT
                    )

                    # Publish the Task to Grok's channel
                    grok_channel = get_agent_channel(settings.GROK_AGENT_NAME)
                    await publish_message(redis_client, grok_channel, task.serialize())
                    logger.info(f"Forwarded message from {client_id} to {settings.GROK_AGENT_NAME} via channel {grok_channel}")

                    # Echo back to user's frontend for immediate display? Optional.
                    # echo_payload = task.model_dump()
                    # await manager.send_personal_message(
                    #      WebSocketMessage(type="my_message", payload=echo_payload).model_dump(),
                    #      client_id
                    # )

                elif ws_message.type == "get_agent_status":
                     # Placeholder: Check agent heartbeats
                     agents_to_check = [settings.GROK_AGENT_NAME, settings.CLAUDE_AGENT_NAME, settings.GPT_AGENT_NAME, settings.TOOLS_AGENT_NAME]
                     status_payload = {}
                     for agent_name in agents_to_check:
                         heartbeat_key = get_agent_heartbeat_key(agent_name)
                         status = await get_key(redis_client, heartbeat_key)
                         status_payload[agent_name] = "alive" if status == "alive" else "offline"

                     await manager.send_personal_message(
                         WebSocketMessage(type="agent_status", payload=status_payload).model_dump(),
                         client_id
                     )

                else:
                    logger.warning(f"Received unhandled WebSocket message type from {client_id}: {ws_message.type}")
                    await manager.send_personal_message(
                         WebSocketMessage(type="error", payload={"message": f"Unknown message type: {ws_message.type}"}).model_dump(),
                         client_id
                     )

            except json.JSONDecodeError:
                logger.error(f"Received invalid JSON from client {client_id}: {raw_data[:100]}...")
                await manager.send_personal_message(
                    WebSocketMessage(type="error", payload={"message": "Invalid JSON format."}).model_dump(),
                    client_id
                )
            except Exception as e: # Catch Pydantic validation errors etc.
                logger.error(f"Error processing message from client {client_id}: {e}")
                await manager.send_personal_message(
                    WebSocketMessage(type="error", payload={"message": f"Error processing message: {e}"}).model_dump(),
                    client_id
                )

    except WebSocketDisconnect:
        logger.info(f"Client {client_id} disconnected.")
        manager.disconnect(client_id)
    except Exception as e:
        logger.exception(f"Unexpected error in WebSocket handler for client {client_id}: {e}")
        manager.disconnect(client_id) # Ensure disconnect on error