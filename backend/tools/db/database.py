# DB setup and session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.core.config import settings, logger
import os
import asyncio

DATABASE_URL = settings.DATABASE_URL

# Ensure the directory for the SQLite database exists
if DATABASE_URL.startswith("sqlite"):
    db_path = DATABASE_URL.split("///")[1]
    db_dir = os.path.dirname(db_path)
    if not os.path.exists(db_dir):
        logger.info(f"Database directory not found. Creating: {db_dir}")
        os.makedirs(db_dir, exist_ok=True)
    logger.info(f"Using SQLite database at: {db_path}")


# Create async engine
engine = create_async_engine(DATABASE_URL, echo=False) # Set echo=True for SQL logging

# Create async session maker
# expire_on_commit=False is recommended for FastAPI background tasks or when objects
# need to be accessed after the session is closed.
AsyncSessionFactory = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False, # Explicit commit/rollback needed
    autoflush=False,  # Explicit flush needed if required before commit
)

# Base class for declarative models
Base = declarative_base()

from typing import AsyncGenerator

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency function that yields an AsyncSession."""
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            logger.error(f"Database transaction failed: {e}")
            await session.rollback()
            raise
        finally:
             # Closing the session is handled by the context manager `async with`
             pass


async def init_db():
    """Initializes the database by creating tables defined in models."""
    async with engine.begin() as conn:
        logger.info("Initializing database...")
        # Drop and recreate tables (Use with caution, especially in production!)
        # await conn.run_sync(Base.metadata.drop_all)
        # logger.info("Existing tables dropped.")
        try:
            await conn.run_sync(Base.metadata.create_all)
            logger.success("Database tables created successfully (if they didn't exist).")
        except Exception as e:
             logger.error(f"Error creating database tables: {e}")
             raise

async def close_db():
    """Closes the database engine connection."""
    logger.info("Closing database engine connection...")
    await engine.dispose()
    logger.info("Database engine connection closed.")


# Example of running init_db directly (e.g., for setup scripts)
# if __name__ == "__main__":
#     async def setup():
#         await init_db()
#         await close_db()
#     asyncio.run(setup())