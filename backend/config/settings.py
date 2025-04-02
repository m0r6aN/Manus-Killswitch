import os
from pydantic_settings import BaseSettings
from loguru import logger
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
        REDIS_HOST = os.getenv("REDIS_HOST", "redis"),
        REDIS_PORT = int(os.getenv("REDIS_PORT", 6379)),
        REDIS_CHANNEL_MOD = os.getenv("REDIS_CHANNEL_MOD", "moderation_channel"),
        REDIS_CHANNEL_RES = os.getenv("REDIS_CHANNEL_RES", "responses_channel"),
        REDIS_CHANNEL_ARB = os.getenv("REDIS_CHANNEL_ARB", "arbitration_channel"),
        WS_URI = os.getenv("WS_URI", "ws://websocket-server:8000/ws/tasks"),  # Updated
        HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", 10)),
        HEARTBEAT_EXPIRY = int(os.getenv("HEARTBEAT_EXPIRY", 15)),
        API_URL = os.getenv("API_URL", "https://api.xai.com/v1/messages"),
        MODEL = os.getenv("MODEL", "grok-3"),
        CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", 0.25)),
        CONSENSUS_THRESHOLD = float(os.getenv("CONSENSUS_THRESHOLD", 0.15)),
        MIN_DEBATE_ROUNDS = int(os.getenv("MIN_DEBATE_ROUNDS", 2)),
        MAX_DEBATE_ROUNDS = int(os.getenv("MAX_DEBATE_ROUNDS", 4)),
        CACHING_ENABLED = os.getenv("CACHING_ENABLED", "true").lower() =="true",
        CACHE_TTL = int(os.getenv("CACHE_TTL", 300)),
        TOPIC_EXTRACTION_ENABLED = os.getenv("TOPIC_EXTRACTION_ENABLED", "true").lower() =="true",
        ENABLE_DEADLOCK_DETECTION = os.getenv("ENABLE_DEADLOCK_DETECTION", "true").lower() =="true",
        DEBATE_TIMEOUT = int(os.getenv("DEBATE_TIMEOUT", 30)),
        MAX_HISTORY_SIZE = int(os.getenv("MAX_HISTORY_SIZE", 10))
        FRONTEND_CHANNEL = os.getenv("FRONTEND_CHANNEL")