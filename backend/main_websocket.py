# Entry point for WebSocket server
import asyncio
from fastapi import FastAPI, WebSocket
# ADD THIS IMPORT
from contextlib import asynccontextmanager

from backend.server.websocket_server import redis_listener, handle_websocket_connection
from backend.core.redis_client import get_redis_pool, close_redis_pool
from backend.core.config import logger, settings

# Keep redis_listener_task as a module-level variable to access in lifespan phases
redis_listener_task = None

# --- DEFINE LIFESPAN FUNCTION ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_listener_task
    # --- Startup Logic ---
    logger.info("Starting WebSocket Server (lifespan)...")
    # Initialize Redis pool
    redis_pool = await get_redis_pool()
    # Start the Redis listener task
    redis_listener_task = asyncio.create_task(redis_listener(redis_pool))
    logger.info("Redis listener task started.")
    logger.info("WebSocket Server startup complete.")

    yield # Application runs here

    # --- Shutdown Logic ---
    logger.info("Shutting down WebSocket Server (lifespan)...")
    if redis_listener_task:
        logger.info("Cancelling Redis listener task...")
        redis_listener_task.cancel()
        try:
            await redis_listener_task
        except asyncio.CancelledError:
            logger.info("Redis listener task successfully cancelled.")
        except Exception as e:
            logger.error(f"Error during Redis listener task shutdown: {e}")
    # Note: We decided earlier not to close the global redis pool here
    # await close_redis_pool()
    logger.info("WebSocket Server shutdown complete.")
# --- END LIFESPAN FUNCTION ---


# --- FastAPI INSTANTIATION ---
app = FastAPI(
    title="Manus WebSocket Server",
    description="Middleware for real-time communication between frontend and AI agents.",
    version="1.0.0",
    lifespan=lifespan # Pass the lifespan manager
)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for frontend connections."""
    await handle_websocket_connection(websocket)

@app.get("/")
async def read_root():
    return {"message": "Manus WebSocket Server is running"}

# If running directly using uvicorn main_websocket:app
# The startup/shutdown events handle initialization.