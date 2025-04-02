# CRUD operations for tools
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import or_, and_
import json

from . import models, schemas
from backend.core.config import logger

async def get_tool_by_id(db: AsyncSession, tool_id: int) -> models.Tool | None:
    """Fetches a tool by its primary key."""
    result = await db.execute(select(models.Tool).filter(models.Tool.id == tool_id))
    return result.scalars().first()

async def get_tool_by_name(db: AsyncSession, name: str) -> models.Tool | None:
    """Fetches a tool by its unique name."""
    result = await db.execute(select(models.Tool).filter(models.Tool.name == name))
    return result.scalars().first()

async def get_tools(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    q: str | None = None,
    tags: str | None = None, # Comma-separated tags for query param
    tool_type: str | None = None,
    active_only: bool = True
) -> list[models.Tool]:
    """Fetches a list of tools with filtering and pagination."""
    query = select(models.Tool)

    filters = []
    if active_only:
        filters.append(models.Tool.active == True)
    if tool_type:
        filters.append(models.Tool.type == tool_type)

    # Search query (name or description)
    if q:
        filters.append(
            or_(
                models.Tool.name.ilike(f"%{q}%"),
                models.Tool.description.ilike(f"%{q}%")
            )
        )

    # Tags filtering (basic substring matching for simplicity)
    # More robust: Use JSON functions if DB supports, or normalize tags on save/query
    if tags:
        tag_list = [t.strip() for t in tags.split(',') if t.strip()]
        if tag_list:
            tag_filters = []
            for tag in tag_list:
                 # Check if tag exists in comma-separated list OR as element in JSON array string
                 tag_filters.append(models.Tool.tags.ilike(f"%{tag}%"))
            filters.append(or_(*tag_filters)) # Match any of the provided tags

    if filters:
        query = query.filter(and_(*filters))

    query = query.offset(skip).limit(limit).order_by(models.Tool.name)
    result = await db.execute(query)
    return result.scalars().all()


async def create_tool(db: AsyncSession, tool: schemas.ToolCreate) -> models.Tool:
    """Creates a new tool entry in the database."""
    # Check if name already exists
    existing_tool = await get_tool_by_name(db, tool.name)
    if existing_tool:
        logger.warning(f"Attempted to create tool with existing name: {tool.name}")
        # Raise exception or return existing? Let's raise for clarity in API.
        raise ValueError(f"Tool with name '{tool.name}' already exists.")

    db_tool = models.Tool(**tool.model_dump())
    db.add(db_tool)
    # await db.commit() # Commit is handled by the get_db dependency context manager
    await db.flush() # Ensure the object gets an ID if needed immediately
    await db.refresh(db_tool) # Refresh to get DB defaults like created_at
    logger.info(f"Created tool: {db_tool.name} (ID: {db_tool.id})")
    return db_tool

async def update_tool(db: AsyncSession, tool_id: int, tool_update: schemas.ToolUpdate) -> models.Tool | None:
    """Updates an existing tool."""
    db_tool = await get_tool_by_id(db, tool_id)
    if not db_tool:
        return None

    update_data = tool_update.model_dump(exclude_unset=True) # Get only provided fields

    # Check for name conflict if name is being updated
    if "name" in update_data and update_data["name"] != db_tool.name:
        existing_tool = await get_tool_by_name(db, update_data["name"])
        if existing_tool:
            logger.warning(f"Attempted to update tool ID {tool_id} with existing name: {update_data['name']}")
            raise ValueError(f"Tool name '{update_data['name']}' is already in use.")

    for key, value in update_data.items():
        setattr(db_tool, key, value)

    # Mark for update, commit/flush handled by dependency
    db.add(db_tool)
    await db.flush()
    await db.refresh(db_tool)
    logger.info(f"Updated tool: {db_tool.name} (ID: {db_tool.id})")
    return db_tool

async def delete_tool(db: AsyncSession, tool_id: int) -> models.Tool | None:
    """Deletes a tool from the database."""
    db_tool = await get_tool_by_id(db, tool_id)
    if not db_tool:
        return None

    await db.delete(db_tool)
    # await db.commit() # Handled by dependency
    await db.flush()
    logger.info(f"Deleted tool: {db_tool.name} (ID: {db_tool.id})")
    return db_tool # Return the deleted object info

async def set_tool_activity(db: AsyncSession, tool_id: int, active: bool) -> models.Tool | None:
    """Sets the active status of a tool."""
    db_tool = await get_tool_by_id(db, tool_id)
    if not db_tool:
        return None

    if db_tool.active != active:
        db_tool.active = active
        db.add(db_tool)
        await db.flush()
        await db.refresh(db_tool)
        logger.info(f"Set tool {db_tool.name} (ID: {db_tool.id}) active status to: {active}")

    return db_tool