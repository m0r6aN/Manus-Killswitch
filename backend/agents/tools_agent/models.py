# SQLAlchemy models for ToolCore
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Index
from sqlalchemy.sql import func
from sqlalchemy.dialects.sqlite import JSON # Or use Text if JSON not supported well
from backend.agents.tools_agent.db.database import Base
import json as py_json

class Tool(Base):
    __tablename__ = "tools"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    # Store JSON schema as a string, validate on API level
    parameters = Column(Text, nullable=True) # Store JSON Schema as string
    # Path relative to the TOOLS_DIR defined in config
    path = Column(String, nullable=True) # Path for script/module types
    # Entrypoint: function name for 'function' type, filename for 'script' type
    entrypoint = Column(String, nullable=True)
    type = Column(String, nullable=False) # 'script', 'function', 'module'
    version = Column(String, nullable=True, default="1.0.0")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    # Store tags as JSON array string or comma-separated string
    tags = Column(Text, nullable=True) # e.g., '["data", "analysis"]' or "data,analysis"
    active = Column(Boolean, default=True)

    # Add indexes for commonly queried fields
    __table_args__ = (
        Index("ix_tools_type", "type"),
        Index("ix_tools_active", "active"),
        # Index("ix_tools_tags", "tags"), # Indexing text blobs like tags can be tricky/inefficient depending on DB
    )

    def __repr__(self):
        return f"<Tool(id={self.id}, name='{self.name}', type='{self.type}', active={self.active})>"

    @property
    def parameter_schema(self) -> dict | None:
        """Parses the parameters JSON string into a dict."""
        if self.parameters:
            try:
                return py_json.loads(self.parameters)
            except py_json.JSONDecodeError:
                return None
        return None

    @property
    def tag_list(self) -> list[str]:
        """Parses the tags string into a list."""
        if not self.tags:
            return []
        try:
            # Try parsing as JSON first
            tags = py_json.loads(self.tags)
            if isinstance(tags, list):
                return [str(tag).strip() for tag in tags if str(tag).strip()]
        except py_json.JSONDecodeError:
            # Fallback to comma-separated
            return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
        return [] # Should not happen if JSON loads but isn't a list, but good practice