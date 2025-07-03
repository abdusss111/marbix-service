from typing import Optional, Any
from pydantic import BaseModel

class StrategyRequest(BaseModel):
    business_type:        str
    business_goal:        str
    location:             str
    current_volume:       str
    product_data:         str
    target_audience_info: str
    competitors:          Optional[str] = None
    actions:              Optional[str] = None
    marketing_budget:     Optional[str] = None

class StrategyResponse(BaseModel):
    status: str
    detail: Optional[Any] = None
