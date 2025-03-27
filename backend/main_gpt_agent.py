# Entry point for GPT agent

import asyncio
from backend.agents.gpt_agent import GPTAgent
from backend.core.config import logger
from backend.core.redis_client import close_redis_pool

async def main():
    agent = GPTAgent()
    await agent.start()
    try:
        # Keep the agent running indefinitely
        await asyncio.Future() # This will wait forever unless cancelled
    except asyncio.CancelledError:
        logger.info("GPTAgent main task cancelled.")
    finally:
        await agent.stop()
        # await close_redis_pool()

if __name__ == "__main__":
    try:
        logger.info("Starting GPT Agent...")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("GPT Agent stopped by user.")
    except Exception as e:
         logger.exception(f"GPT Agent encountered critical error: {e}")
    finally:
        logger.info("GPT Agent shutdown.")