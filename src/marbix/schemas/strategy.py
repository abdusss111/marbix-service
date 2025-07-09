# src/marbix/schemas/strategy.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class StrategyListItem(BaseModel):
    request_id: str
    business_type: str
    business_goal: str
    location: str
    marketing_budget: Optional[str]
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
    result: str
    
    class Config:
        from_attributes = True