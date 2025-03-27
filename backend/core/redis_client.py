 # Redis connection utility
import redis.asyncio as redis
from .config import settings, logger

_redis_pool = None

async def get_redis_pool() -> redis.Redis:
    """Initializes and returns the Redis connection pool."""
    global _redis_pool
    if _redis_pool is None:
        try:
            logger.info(f"Connecting to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}")
            # decode_responses=True automatically decodes keys/values from bytes to strings
            _redis_pool = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=0,
                decode_responses=True,
                health_check_interval=30 # Check connection health periodically
            )
            # Test connection
            await _redis_pool.ping()
            logger.success("Successfully connected to Redis and pinged.")
        except redis.exceptions.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred during Redis connection: {e}")
            raise
    return _redis_pool

async def close_redis_pool():
    """Closes the Redis connection pool."""
    global _redis_pool
    if _redis_pool:
        logger.info("Closing Redis connection pool...")
        await _redis_pool.close()
        _redis_pool = None
        logger.info("Redis connection pool closed.")

async def publish_message(redis_client: redis.Redis, channel: str, message: str):
    """Publishes a message to a Redis channel."""
    try:
        await redis_client.publish(channel, message)
        logger.debug(f"Published to {channel}: {message[:100]}...") # Log truncated message
    except Exception as e:
        logger.error(f"Error publishing message to {channel}: {e}")

async def set_key_with_ttl(redis_client: redis.Redis, key: str, value: str, ttl: int):
    """Sets a key in Redis with a Time-To-Live (TTL)."""
    try:
        await redis_client.setex(key, ttl, value)
        logger.trace(f"Set key '{key}' with TTL {ttl}s")
    except Exception as e:
        logger.error(f"Error setting key '{key}' with TTL: {e}")

async def get_key(redis_client: redis.Redis, key: str) -> str | None:
    """Gets a key value from Redis."""
    try:
        return await redis_client.get(key)
    except Exception as e:
        logger.error(f"Error getting key '{key}': {e}")
        return None