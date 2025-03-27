# Settings (Redis host, ports etc.)import os
from typing import List
from pydantic_settings import BaseSettings
from loguru import logger
import sys
from pathlib import Path

# Determine base directory dynamically - assumes config.py is in core folder
BASE_DIR = Path(__file__).resolve().parent.parent.parent # This should point to manus-killswitch directory

class Settings(BaseSettings):
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    WEBSOCKET_PORT: int = 8000
    TOOLCORE_PORT: int = 8001
    HEARTBEAT_INTERVAL: int = 5  # Seconds
    HEARTBEAT_TTL: int = 15      # Seconds (should be > interval)

    # Agent specific settings (can be overridden by env vars in docker-compose)
    GROK_AGENT_NAME: str = "grok"
    CLAUDE_AGENT_NAME: str = "claude"
    GPT_AGENT_NAME: str = "gpt"
    TOOLS_AGENT_NAME: str = "tools-agent" # Name mainly for logging/reference
    CODEX_AGENT_NAME: str = "codex"
    COORDINATOR_AGENT_NAME: str = "coordinator"

    # For use by the Coordinator agent
    REQUIRED_AGENTS_FOR_READY: List[str] = [
        GROK_AGENT_NAME,
        CLAUDE_AGENT_NAME,
        GPT_AGENT_NAME,
        TOOLS_AGENT_NAME, # Monitor ToolCore API via its healthcheck/heartbeat? Needs ToolCore to *send* a heartbeat.
        CODEX_AGENT_NAME,
    ]
    
    # Readiness check settings for Coordinator
    AGENT_READY_TIMEOUT: int = 60 # Seconds
    AGENT_CHECK_INTERVAL: int = 3  # Seconds

    FRONTEND_CHANNEL: str = "frontend_broadcast"
    SYSTEM_CHANNEL: str = "system_control" # For system-wide messages

    # ToolCore Specific
    DATABASE_URL: str = f"sqlite+aiosqlite:///{BASE_DIR / 'backend/agents/tools_agent/db/toolstore.db'}" # Default local path
    TOOLS_DIR: str = str(BASE_DIR / "backend/agents/tools_agent/tools") # Default local path

    # Logging
    LOGURU_LEVEL: str = "INFO"

    # API Keys (placeholders - load securely in production)
    GROK_API_KEY: str = "YOUR_GROK_API_KEY_HERE"
    CLAUDE_API_KEY: str = "YOUR_CLAUDE_API_KEY_HERE"
    GPT_API_KEY: str = "YOUR_GPT_API_KEY_HERE"
    CODEX_API_KEY: str = "YOUR_CODEX_LLM_API_KEY_HERE"

    TOOLS_API_URL: str = "http://localhost:8001" # Default for local testing

    class Config:
        # If you have a .env file, uncomment the line below
        # env_file = ".env"
        env_file_encoding = 'utf-8'
        extra = 'ignore' # Ignore extra fields from environment


settings = Settings()

# Configure Loguru
logger.remove() # Remove default handler
logger.add(
    sys.stderr,
    level=settings.LOGURU_LEVEL,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

# Add file logger (optional)
# logger.add("logs/file_{time}.log", level="INFO", rotation="1 day")

logger.info("Settings loaded successfully.")
logger.debug(f"Redis Host: {settings.REDIS_HOST}, Port: {settings.REDIS_PORT}")
logger.debug(f"ToolCore DB URL: {settings.DATABASE_URL}")
logger.debug(f"Tools Dir: {settings.TOOLS_DIR}")
logger.debug(f"Tools API URL: {settings.TOOLS_API_URL}")

def get_agent_channel(agent_name: str) -> str:
    """Returns the dedicated Redis channel name for an agent."""
    return f"{agent_name}_channel"

def get_agent_heartbeat_key(agent_name: str) -> str:
    """Returns the Redis key for an agent's heartbeat."""
    return f"{agent_name}_heartbeat"