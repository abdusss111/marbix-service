from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List

class PromptBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    content: str = Field(..., min_length=1)
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    is_active: bool = True

class PromptCreate(PromptBase):
    pass

class PromptUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None

class PromptResponse(PromptBase):
    id: str
    version: int
    usage_count: int
    last_used_at: Optional[datetime] = None
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class PromptListItem(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    is_active: bool
    version: int
    usage_count: int
    last_used_at: Optional[datetime] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class PromptUsage(BaseModel):
    prompt_id: str
    increment_usage: bool = True
