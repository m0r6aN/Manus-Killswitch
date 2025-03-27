# Entry point for Claude agent
import asyncio
from backend.agents.claude_agent import ClaudeAgent
from backend.core.config import logger
#from backend.core.redis_client import close_redis_pool

async def main():
    agent = ClaudeAgent()
    await agent.start()
    try:
        # Keep the agent running indefinitely
        logger.debug("Awaiting asyncio future..")
        await asyncio.Future() # This will wait forever unless cancelled
    except asyncio.CancelledError:
        logger.info("ClaudeAgent main task cancelled.")
    finally:
        await agent.stop()
        # await close_redis_pool() # Close pool if this is the only process

if __name__ == "__main__":
    try:
        logger.info("Starting Claude Agent...")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Claude Agent stopped by user.")
    except Exception as e:
         logger.exception(f"Claude Agent encountered critical error: {e}")
    finally:
        logger.info("Claude Agent shutdown.")