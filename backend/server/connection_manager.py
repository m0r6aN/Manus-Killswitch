# WebSocket connection manager

import asyncio
import json
from fastapi import WebSocket
from typing import Dict, List, Optional
from backend.config import settings
from backend.core.config import logger
import uuid

class ConnectionManager:
    """Manages active WebSocket connections."""
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {} # client_id -> WebSocket
        logger.info("ConnectionManager initialized.")

    async def connect(self, websocket: WebSocket) -> str:
        """Accepts a new WebSocket connection and assigns a unique client ID."""
        await websocket.accept()
        client_id = str(uuid.uuid4())
        self.active_connections[client_id] = websocket
        logger.info(f"New WebSocket connection accepted: {client_id}")
        # Send client_id back to client upon connection
        await self.send_personal_message({"type": "system", "payload": {"message": "Connected to server.", "client_id": client_id}}, client_id)
        return client_id

    def disconnect(self, client_id: str):
        """Removes a WebSocket connection."""
        if client_id in self.active_connections:
            # del self.active_connections[client_id] # Don't delete immediately, connection might still be closing
            logger.info(f"WebSocket connection disconnected: {client_id}")
            # Actual removal might happen implicitly when WebSocket closes or explicitly after confirming close
            if client_id in self.active_connections: # Check again in case already removed
                 del self.active_connections[client_id]
        else:
            logger.warning(f"Attempted to disconnect non-existent client_id: {client_id}")


    async def send_personal_message(self, message: dict, client_id: str):
        """Sends a JSON message to a specific client."""
        websocket = self.active_connections.get(client_id)
        if websocket:
            try:
                await websocket.send_json(message)
                logger.trace(f"Sent personal message to {client_id}: {str(message)[:100]}...")
            except Exception as e:
                logger.error(f"Error sending personal message to {client_id}: {e}. Removing connection.")
                self.disconnect(client_id) # Remove if sending fails
        else:
            logger.warning(f"Attempted to send message to non-existent client_id: {client_id}")


    async def broadcast(self, message: dict, exclude_client_id: Optional[str] = None):
        """Sends a JSON message to all connected clients, optionally excluding one."""
        disconnected_clients = []
        # Iterate over a copy of the keys to allow modification during iteration
        client_ids = list(self.active_connections.keys())
        logger.debug(f"Broadcasting message to {len(client_ids)} clients (excluding {exclude_client_id}).")

        for client_id in client_ids:
            if client_id == exclude_client_id:
                continue

            websocket = self.active_connections.get(client_id)
            if websocket:
                 try:
                     await websocket.send_json(message)
                     logger.trace(f"Broadcast message sent to {client_id}.")
                 except Exception as e:
                     logger.error(f"Error broadcasting message to {client_id}: {e}. Marking for removal.")
                     disconnected_clients.append(client_id)
            else:
                 # Should ideally not happen if client_ids is from active_connections keys
                 logger.warning(f"Client {client_id} not found during broadcast despite being in key list.")
                 disconnected_clients.append(client_id) # Mark for removal just in case


        # Remove disconnected clients after iteration
        for client_id in disconnected_clients:
            self.disconnect(client_id)
            
    async def frontend_redis_broadcaster(redis_client, manager):
        """
        Listens ONLY to the FRONTEND channel and broadcasts messages to WebSocket clients.
        (This is your adapted existing listener)
        """
        channel = settings.FRONTEND_CHANNEL # Standardize channel name
        pubsub = redis_client.pubsub()

        while True: # Keep trying to connect/subscribe
            try:
                await pubsub.connect()
                await pubsub.subscribe(channel)
                logger.info(f"Frontend Broadcaster subscribed to Redis channel: {channel}")

                while True: # Listen for messages
                    try:
                        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                        if not message:
                            await asyncio.sleep(0.01)
                            continue

                        if message["type"] == "message":
                            data = message["data"]
                            if isinstance(data, bytes):
                                data = data.decode("utf-8")

                            logger.debug(f"Frontend Broadcaster received: {data[:150]}...")

                            if manager.get_active_connections_count() == 0:
                                # logger.debug("No WebSocket clients, skipping broadcast") # Maybe too noisy
                                continue

                            try:
                                json_data = json.loads(data)
                                # Directly broadcast the received JSON data
                                # Assumes agents format messages correctly via publish_to_frontend
                                await manager.broadcast(json_data)

                            except json.JSONDecodeError:
                                logger.warning(f"Frontend Broadcaster received non-JSON data from {channel}: {data[:100]}...")
                            except Exception as e:
                                logger.error(f"Error broadcasting Redis message: {e}", exc_info=True)

                    except asyncio.CancelledError:
                        logger.info(f"Frontend Broadcaster task for {channel} cancelled.")
                        await pubsub.unsubscribe(channel)
                        return # Exit the outer loop as well
                    except Exception as e: # Catch Redis connection errors etc.
                        logger.error(f"Frontend Broadcaster error reading from {channel}: {e}", exc_info=True)
                        await pubsub.unsubscribe(channel) # Unsubscribe before retrying connect
                        break # Break inner loop, outer loop will retry subscribe
            except Exception as e:
                logger.error(f"Fatal error in Frontend Broadcaster setup for {channel}: {e}", exc_info=True)
            finally:
                if pubsub.is_connected():
                    await pubsub.close() # Clean up connection

            logger.info(f"Retrying Frontend Broadcaster subscription to {channel} in 5 seconds...")
            await asyncio.sleep(5)

    def get_active_connections_count(self) -> int:
        """Returns the number of active connections."""
        return len(self.active_connections)

# Global instance
manager = ConnectionManager()