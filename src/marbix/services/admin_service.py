import os
import jwt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from passlib.context import CryptContext
from marbix.models.user import User, SubscriptionStatus
from marbix.models.make_request import MakeRequest
from marbix.models.role import UserRole
from marbix.schemas.user import SubscriptionStatusEnum
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy import func

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
JWT_SECRET = os.getenv("AUTH_SECRET", "secret-key")


def authenticate_admin(email: str, password: str, db: Session) -> str:
    """
    Authenticates admin by email and password. Returns JWT if valid.
    """
    admin = db.query(User).filter(User.email == email, User.role == UserRole.ADMIN).first()

    if not admin or not admin.password or not pwd_context.verify(password, admin.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    return generate_admin_jwt(admin)


def generate_admin_jwt(admin: User) -> str:
    """
    Generates JWT token for admin with role in payload.
    """
    payload = {
        "sub": admin.id,
        "email": admin.email,
        "role": admin.role.value
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def get_all_users(db: Session, subscription_status: Optional[SubscriptionStatusEnum] = None):
    """
    Returns list of users (excluding admins) with optional subscription status filter.
    """
    query = db.query(User).filter(User.role != UserRole.ADMIN)
    
    if subscription_status:
        # Convert SubscriptionStatusEnum to SubscriptionStatus for database query
        status_mapping = {
            SubscriptionStatusEnum.FREE: SubscriptionStatus.FREE,
            SubscriptionStatusEnum.PENDING_PRO: SubscriptionStatus.PENDING_PRO,
            SubscriptionStatusEnum.PRO: SubscriptionStatus.PRO
        }
        db_status = status_mapping[subscription_status]
        query = query.filter(User.subscription_status == db_status)
    
    return query.order_by(desc(User.created_at)).all()


def get_user_by_id(user_id: str, db: Session):
    """
    Returns user by ID. Raises 404 if not found.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def get_user_strategies(user_id: str, db: Session):
    """
    Returns all strategies (make_requests) for the given user ID.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return db.query(MakeRequest).filter(MakeRequest.user_id == user_id).all()


def get_admin_statistics(db: Session):
    """
    Returns admin dashboard statistics.
    """
    # Total users (excluding admins)
    total_users = db.query(func.count(User.id)).filter(User.role != UserRole.ADMIN).scalar()
    
    # Subscription statistics
    free_users = db.query(func.count(User.id)).filter(
        User.role != UserRole.ADMIN,
        User.subscription_status == SubscriptionStatus.FREE
    ).scalar()
    
    pending_pro_users = db.query(func.count(User.id)).filter(
        User.role != UserRole.ADMIN,
        User.subscription_status == SubscriptionStatus.PENDING_PRO
    ).scalar()
    
    pro_users = db.query(func.count(User.id)).filter(
        User.role != UserRole.ADMIN,
        User.subscription_status == SubscriptionStatus.PRO
    ).scalar()
    
    # Total strategies
    total_strategies = db.query(func.count(MakeRequest.request_id)).join(User, MakeRequest.user_id == User.id).filter(User.role != UserRole.ADMIN).scalar()
    
    # Successful strategies (completed)
    
    successful_strategies = (
    db.query(func.count(MakeRequest.request_id))
      .join(User, MakeRequest.user_id == User.id)
      .filter(
          MakeRequest.status == "completed",
          User.role       != UserRole.ADMIN
      )
      .scalar()
    )

    # Calculate crashed strategies (processing > 20 minutes)
    twenty_minutes_ago = datetime.utcnow() - timedelta(minutes=20)
    failed_strategies = (
    db.query(func.count(MakeRequest.request_id))
      .join(User, MakeRequest.user_id == User.id)
      .filter(
          MakeRequest.status       == "processing",
          MakeRequest.created_at   < twenty_minutes_ago,
          User.role                != UserRole.ADMIN
      )
      .scalar())
    
    # Currently processing (within 20 minutes)
    processing_strategies = db.query(func.count(MakeRequest.request_id)).filter(
        MakeRequest.status == "processing",
        MakeRequest.created_at >= twenty_minutes_ago
    ).scalar()
    
    return {
        "total_users": total_users,
        "total_strategies": total_strategies,
        "successful_strategies": successful_strategies,
        "failed_strategies": failed_strategies,
        "processing_strategies": processing_strategies,
        "free_users": free_users,
        "pending_pro_users": pending_pro_users,
        "pro_users": pro_users
    }


def get_users_by_subscription_status(db: Session, subscription_status: SubscriptionStatus):
    """
    Returns users filtered by specific subscription status.
    """
    return db.query(User).filter(
        User.role != UserRole.ADMIN,
        User.subscription_status == subscription_status
    ).order_by(desc(User.created_at)).all()