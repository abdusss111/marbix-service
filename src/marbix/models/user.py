from sqlalchemy import Column, String, ForeignKey, DateTime, Text, JSON
from sqlalchemy.orm import relationship
from uuid import uuid4
from datetime import datetime
from marbix.db.base import Base

from sqlalchemy import Enum as SqlEnum
from marbix.models.role import UserRole
from enum import Enum

class SubscriptionStatus(Enum):
    FREE = "free"
    PENDING_PRO = "pending-pro"
    PRO = "pro"

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String)
    number = Column(String, nullable=True)
    password = Column(String, nullable=True)
    role = Column(SqlEnum(UserRole), default=UserRole.USER, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    
    # Subscription fields
    subscription_status = Column(SqlEnum(SubscriptionStatus), default=SubscriptionStatus.FREE, nullable=False)
    subscription_updated_at = Column(DateTime, nullable=True)
    subscription_granted_by = Column(String, nullable=True)  # Admin ID who granted the subscription

    admin_comment = Column(String, nullable=True)