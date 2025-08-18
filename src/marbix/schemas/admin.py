from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from marbix.schemas.user import SubscriptionStatusEnum


class AdminStatsResponse(BaseModel):
    total_users: int
    total_strategies: int
    successful_strategies: int
    failed_strategies: int
    processing_strategies: int
    # Subscription stats
    free_users: int
    pending_pro_users: int
    pro_users: int

class UserSubscriptionManagement(BaseModel):
    """Schema for admin to manage user subscriptions"""
    user_id: str
    subscription_status: SubscriptionStatusEnum
    admin_note: Optional[str] = None

class SubscriptionManagementResponse(BaseModel):
    """Response for subscription management operations"""
    success: bool
    message: str
    user_id: str
    old_status: SubscriptionStatusEnum
    new_status: SubscriptionStatusEnum
    updated_at: datetime
    updated_by: str