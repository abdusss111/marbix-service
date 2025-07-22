# src/marbix/schemas/make_integration.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class MakeWebhookRequest(BaseModel):
    """Request model for Make webhook integration"""
    business_type: str
    business_goal: str
    location: str
    current_volume: str
    product_data: str
    target_audience_info: str
    user_number: str
    competitors: Optional[str] = None
    actions: Optional[str] = None
    marketing_budget: Optional[str] = None

class MakeWebhookPayload(MakeWebhookRequest):
    """Payload sent to Make webhook"""
    callback_url: str
    request_id: str

class MakeCallbackResponse(BaseModel):
    """Response model from Make callback"""
    result: str
    status: str = "completed"
    source: str
    error: Optional[str] = None

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