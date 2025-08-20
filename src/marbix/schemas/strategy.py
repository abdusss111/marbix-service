# src/marbix/schemas/strategy.py
from pydantic import BaseModel, field_validator
from typing import Optional, List, Union
from datetime import datetime

class StrategyListItem(BaseModel):
    request_id: str
    business_type: str
    business_goal: str
    location: str
    promotion_budget: Optional[str] = None
    team_budget: Optional[str] = None
    current_volume: Optional[str] = ""
    product_data: Optional[str] = ""
    target_audience_info: Optional[str] = ""
    competitors: Optional[str] = None
    actions: Optional[str] = None  # или List[str] = [] если это список
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class StrategyItem(BaseModel):
    request_id: str
    business_type: str
    business_goal: str
    location: str
    promotion_budget: Optional[str] = None
    team_budget: Optional[str] = None
    current_volume: Optional[str] = ""
    product_data: Optional[str] = ""
    target_audience_info: Optional[str] = ""
    competitors: Optional[str] = None
    actions: Optional[str] = None  # или List[str] = [] если это список
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
    result: str
    sources: Optional[List[str]]  # Array of source URLs
    
    class Config:
        from_attributes = True


class SourcesCallbackRequest(BaseModel):
    sources: Union[List[str], str] = []

    @field_validator('sources', mode='before')
    @classmethod
    def parse_sources(cls, v):
        """Handle both string and array inputs from Make.com"""
        if isinstance(v, str):
            if v.startswith('[') and v.endswith(']'):
                v = v[1:-1]
                sources = [url.strip() for url in v.split(', ') if url.strip()]
                return sources
            else:
                return [v.strip()] if v.strip() else []
        elif isinstance(v, list):
            return v
        else:
            return []