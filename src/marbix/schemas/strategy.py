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
    current_volume: Optional[str] = ""
    product_data: Optional[str] = ""
    target_audience_info: Optional[str] = ""
    competitors: Optional[str] = None
    actions: Optional[str] = None  # или List[str] = [] если это список
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
    result: str
    
    class Config:
        from_attributes = True