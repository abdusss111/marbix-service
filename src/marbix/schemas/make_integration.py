
# src/marbix/schemas/make_integration.py
from pydantic import BaseModel, field_validator
from typing import Optional, Union, Any
from datetime import datetime
import json

class MakeWebhookRequest(BaseModel):
    """Request model for Make webhook integration"""
    business_type: str
    business_goal: str
    location: str
    current_volume: str
    product_data: str
    target_audience_info: str
    competitors: Optional[str] = None
    actions: Optional[str] = None
    marketing_budget: Optional[str] = None

class MakeWebhookPayload(MakeWebhookRequest):
    """Payload sent to Make webhook"""
    callback_url: str
    request_id: str

class MakeCallbackResponse(BaseModel):
    """Response model from Make callback"""
    result: Union[str, dict, Any]  # Accept any type for now
    status: str = "completed"
    error: Optional[str] = None
    
    @field_validator('result', mode='before')
    def convert_result_to_string(cls, v):
        """Convert any result to string"""
        if isinstance(v, dict):
            # If it's a dict with 'text' field, extract it
            if 'text' in v:
                return v['text']
            # Otherwise convert whole dict to string
            return json.dumps(v, ensure_ascii=False)
        elif isinstance(v, str):
            return v
        else:
            return str(v)

class ProcessingStatus(BaseModel):
    """Status response for processing requests"""
    request_id: str
    status: str
    message: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class WebSocketMessage(BaseModel):
    """Message sent through WebSocket"""
    request_id: str
    status: str
    result: Optional[str] = None
    error: Optional[str] = None
    message: Optional[str] = None