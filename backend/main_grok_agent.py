# Entry point for Grok agent
import asyncio

from backend.agents.grok_agent import GrokAgent
from backend.core.config import logger
from backend.core.redis_client import close_redis_pool

async def main():
    agent = GrokAgent()
    await agent.start()
    try:
        # Keep the agent running indefinitely
        await asyncio.Future() # This will wait forever unless cancelled
    except asyncio.CancelledError:
        logger.info("GrokAgent main task cancelled.")
    finally:
        await agent.stop()
        # await close_redis_pool()

if __name__ == "__main__":
    try:
        logger.info("Starting Grok Agent...")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Grok Agent stopped by user.")
    except Exception as e:
         logger.exception(f"Grok Agent encountered critical error: {e}")
    finally:
        logger.info("Grok Agent shutdown.")