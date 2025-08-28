from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional
from enum import Enum

class SubscriptionStatusEnum(str, Enum):
    FREE = "free"
    PENDING_PRO = "pending-pro"
    PRO = "pro"

class UserOut(BaseModel):
    id: str
    email: str
    name: str
    number: Optional[str] = None
    created_at: datetime
    subscription_status: SubscriptionStatusEnum
    subscription_updated_at: Optional[datetime] = None
    subscription_granted_by: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class UserOutComment(BaseModel):
    id: str
    email: str
    name: str
    admin_comment: str

class UserSubscriptionUpdate(BaseModel):
    """Schema for updating user subscription status"""
    subscription_status: SubscriptionStatusEnum

class SubscriptionStatusResponse(BaseModel):
    """Response for subscription status operations"""
    success: bool
    message: str
    subscription_status: SubscriptionStatusEnum
