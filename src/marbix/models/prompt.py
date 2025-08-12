from sqlalchemy import Column, String, DateTime, Text, JSON, Boolean, Integer
from sqlalchemy.orm import relationship
from uuid import uuid4
from datetime import datetime
from marbix.db.base import Base

class Prompt(Base):
    __tablename__ = "prompts"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid4()))
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    content = Column(Text, nullable=False)
    
    # Metadata fields
    category = Column(String, nullable=True, index=True)
    tags = Column(JSON, nullable=True)  # Array of strings
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Versioning fields (for future enhancements)
    version = Column(Integer, default=1, nullable=False)
    parent_id = Column(String, nullable=True, index=True)  # For versioning
    
    # Usage tracking
    usage_count = Column(Integer, default=0, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    
    # Audit fields
    created_by = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<Prompt(id='{self.id}', name='{self.name}', version={self.version})>"
