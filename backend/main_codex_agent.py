import asyncio
from backend.agents.codex_agent import CodexAgent
from backend.core.config import logger
from backend.core.redis_client import close_redis_pool

async def main():
    agent = CodexAgent()
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
        logger.info("Starting Codex Agent...")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Codex Agent stopped by user.")
    except Exception as e:
         logger.exception(f"Codex Agent encountered critical error: {e}")
    finally:
        logger.info("Codex Agent shutdown.")