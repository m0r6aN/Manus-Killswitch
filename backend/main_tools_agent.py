# Entry point for Tools agent API
# This file mainly imports the FastAPI app from the tools_agent package
# so uvicorn can run it: uvicorn backend.main_tools_agent:app
from backend.agents.tools_agent.api import app
from backend.core.config import logger

# You can add any module-level setup here if needed,
# but FastAPI startup events in api.py are generally preferred.

logger.info("ToolCore API application instance loaded.")

# Example: Directly run init_db if needed outside of FastAPI startup
# Useful for CLI-based DB initialization
# import asyncio
# from backend.agents.tools_agent.db.database import init_db, close_db
# async def setup_db():
#     await init_db()
#     await close_db()
# if __name__ == "__main__":
#     # This block won't run when using uvicorn, but useful for direct execution
#     logger.info("Running DB setup directly...")
#     asyncio.run(setup_db())
#     logger.info("DB setup complete.")