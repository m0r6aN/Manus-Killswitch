import asyncio
from backend.agents.coordinator_agent import CoordinatorAgent
from backend.core.config import logger
from backend.core.redis_client import close_redis_pool

async def main():
    agent = CoordinatorAgent()
    await agent.start()
    try:
        # Keep the agent running indefinitely
        await asyncio.Future() # This will wait forever unless cancelled
    except asyncio.CancelledError:
        logger.info(f"{agent.agent_name} main task cancelled.")
    finally:
        await agent.stop()
        # await close_redis_pool() # Consider if needed

if __name__ == "__main__":
    try:
        logger.info("Starting Coordinator Agent...")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Coordinator Agent stopped by user.")
    except Exception as e:
         logger.exception(f"Coordinator Agent encountered critical error: {e}")
    finally:
        logger.info("Coordinator Agent shutdown.")