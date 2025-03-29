# Entry point for WebSocket server
import asyncio
from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from backend.server.websocket_server import redis_listener, handle_websocket_connection
from backend.server.connection_manager import manager  # Import your connection manager
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
    
    try:
        # Initialize Redis pool
        redis_pool = await get_redis_pool()
        logger.info("Redis pool initialized successfully")
        
        # Start the Redis listener task
        redis_listener_task = asyncio.create_task(redis_listener(redis_pool))
        logger.info("Redis listener task started.")
    except Exception as e:
        logger.error(f"Error during WebSocket Server startup: {e}")
        # Still continue to serve even if Redis fails, as it might recover
    
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
    
    # Cleanup any remaining connections
    client_count = manager.get_active_connections_count()
    if client_count > 0:
        logger.info(f"Closing {client_count} remaining WebSocket connections")
        # Your ConnectionManager may not have a close_all method - implement if needed
    
    # Note: We decided earlier not to close the global redis pool here
    # await close_redis_pool()
    logger.info("WebSocket Server shutdown complete.")
# --- END LIFESPAN FUNCTION ---

# Log middleware to debug WebSocket connection issues
async def log_requests(request: Request, call_next):
    if request.url.path.startswith("/ws"):
        logger.info(f"WebSocket request: {request.method} {request.url.path}")
        logger.info(f"Headers: {request.headers}")
        
        # Log origin for CORS debugging
        if "origin" in request.headers:
            logger.info(f"Origin: {request.headers['origin']}")
    
    response = await call_next(request)
    
    if request.url.path.startswith("/ws"):
        logger.info(f"WebSocket response status: {response.status_code}")
    
    return response

# --- FastAPI INSTANTIATION ---
app = FastAPI(
    title="Manus WebSocket Server",
    description="Middleware for real-time communication between frontend and AI agents.",
    version="1.0.0",
    lifespan=lifespan # Pass the lifespan manager
)

# Add CORS middleware with permissive settings for WebSocket connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # More permissive for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add logging middleware for debugging
app.middleware("http")(log_requests)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for frontend connections."""
    # Log basic info about the connection
    client_host = websocket.client.host if websocket.client else "unknown"
    logger.info(f"New WebSocket connection from {client_host}")
    
    # Pass to the handler function
    await handle_websocket_connection(websocket)

# Add an additional endpoint that matches the client's expectation
@app.websocket("/ws/tasks")
async def tasks_websocket_endpoint(websocket: WebSocket):
    """Alternative WebSocket endpoint for backward compatibility."""
    logger.info("Client connected via /ws/tasks endpoint")
    await handle_websocket_connection(websocket)

@app.get("/")
async def read_root():
    return {
        "message": "Manus WebSocket Server is running",
        "redis_listener": "active" if redis_listener_task and not redis_listener_task.done() else "inactive",
        "connections": manager.get_active_connections_count()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    redis_healthy = False
    try:
        # Get a fresh Redis connection
        redis = await get_redis_pool()
        await redis.ping()
        redis_healthy = True
    except Exception as e:
        logger.error(f"Health check - Redis error: {e}")
    
    # Check Redis listener task
    listener_active = redis_listener_task and not redis_listener_task.done()
    
    return {
        "status": "healthy" if redis_healthy and listener_active else "unhealthy",
        "redis": "connected" if redis_healthy else "disconnected",
        "redis_listener": "active" if listener_active else "inactive",
        "connections": manager.get_active_connections_count()
    }

# If running directly using uvicorn main_websocket:app
# The startup/shutdown events handle initialization.