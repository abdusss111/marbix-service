from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from marbix.schemas.login import AdminLoginRequest, AdminLoginResponse
from marbix.core.deps import get_db, get_current_admin
from marbix.services import admin_service
from marbix.models.user import User, SubscriptionStatus
from marbix.schemas.strategy import StrategyItem
from marbix.schemas.user import UserOut, SubscriptionStatusEnum
from typing import List, Optional
from marbix.models.make_request import MakeRequest
from marbix.schemas.admin import AdminStatsResponse, UserSubscriptionManagement, SubscriptionManagementResponse
from datetime import datetime
router = APIRouter()


@router.post("/login", response_model=AdminLoginResponse)
def login_admin(data: AdminLoginRequest, db: Session = Depends(get_db)):
    token = admin_service.authenticate_admin(data.email, data.password, db)
    return {"access_token": token}


@router.get("/users", response_model=List[UserOut])
def get_all_users(
    subscription_status: Optional[SubscriptionStatusEnum] = Query(None, description="Filter users by subscription status"),
    admin: User = Depends(get_current_admin), 
    db: Session = Depends(get_db)
):
    return admin_service.get_all_users(db, subscription_status)


@router.get("/users/{user_id}", response_model=UserOut)
def get_user_by_id(user_id: str, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return admin_service.get_user_by_id(user_id, db)


@router.get("/users/{user_id}/strategies", response_model=List[StrategyItem])
def get_user_strategies(user_id: str, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    strategies = db.query(MakeRequest).filter(MakeRequest.user_id == user_id).order_by(MakeRequest.created_at.desc()).all()
    return [
        StrategyItem(
            request_id=s.request_id,
            business_type=(s.request_data or {}).get("business_type", ""),
            business_goal=(s.request_data or {}).get("business_goal", ""),
            location=(s.request_data or {}).get("location", ""),
            promotion_budget=(s.request_data or {}).get("promotion_budget"),
            team_budget=(s.request_data or {}).get("team_budget"),
            current_volume=(s.request_data or {}).get("current_volume", ""),
            product_data=(s.request_data or {}).get("product_data", ""),
            target_audience_info=(s.request_data or {}).get("target_audience_info", ""),
            competitors=(s.request_data or {}).get("competitors"),
            actions=(s.request_data or {}).get("actions"),
            status=s.status,
            created_at=s.created_at,
            completed_at=s.completed_at,
            result=s.result or "",
            sources=s.sources or None
        )
        for s in strategies
    ]


@router.get("/statistics", response_model=AdminStatsResponse)
def get_admin_statistics(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """
    Returns admin dashboard statistics including user count, strategy counts by status.
    """
    return admin_service.get_admin_statistics(db)


@router.get("/users/pending-subscriptions", response_model=List[UserOut])
def get_pending_subscriptions(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """
    Get all users with pending PRO subscription requests.
    """
    return admin_service.get_users_by_subscription_status(db, SubscriptionStatus.PENDING_PRO)


@router.post("/users/{user_id}/subscription", response_model=SubscriptionManagementResponse)
def update_user_subscription(
    user_id: str,
    subscription_data: UserSubscriptionManagement,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Update a user's subscription status.
    Only admins can grant or revoke subscriptions.
    """
    # Get the target user
    target_user = admin_service.get_user_by_id(user_id, db)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Store old status for response
    old_status_mapping = {
        SubscriptionStatus.FREE: SubscriptionStatusEnum.FREE,
        SubscriptionStatus.PENDING_PRO: SubscriptionStatusEnum.PENDING_PRO,
        SubscriptionStatus.PRO: SubscriptionStatusEnum.PRO
    }
    old_status = old_status_mapping[target_user.subscription_status]
    
    # Convert SubscriptionStatusEnum to SubscriptionStatus
    status_mapping = {
        SubscriptionStatusEnum.FREE: SubscriptionStatus.FREE,
        SubscriptionStatusEnum.PENDING_PRO: SubscriptionStatus.PENDING_PRO,
        SubscriptionStatusEnum.PRO: SubscriptionStatus.PRO
    }
    
    new_subscription_status = status_mapping[subscription_data.subscription_status]
    
    # Update the subscription
    target_user.subscription_status = new_subscription_status
    target_user.subscription_updated_at = datetime.utcnow()
    target_user.subscription_granted_by = admin.id
    
    db.commit()
    db.refresh(target_user)
    
    return SubscriptionManagementResponse(
        success=True,
        message=f"User subscription updated from {old_status.value} to {subscription_data.subscription_status.value}",
        user_id=user_id,
        old_status=old_status,
        new_status=subscription_data.subscription_status,
        updated_at=target_user.subscription_updated_at,
        updated_by=admin.id
    )


@router.delete("/users/{user_id}/subscription")
def revoke_user_subscription(
    user_id: str,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Revoke a user's PRO subscription (set back to FREE).
    """
    target_user = admin_service.get_user_by_id(user_id, db)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if target_user.subscription_status == SubscriptionStatus.FREE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has FREE subscription"
        )
    
    old_status_mapping = {
        SubscriptionStatus.FREE: SubscriptionStatusEnum.FREE,
        SubscriptionStatus.PENDING_PRO: SubscriptionStatusEnum.PENDING_PRO,
        SubscriptionStatus.PRO: SubscriptionStatusEnum.PRO
    }
    old_status = old_status_mapping[target_user.subscription_status]
    
    # Revoke subscription
    target_user.subscription_status = SubscriptionStatus.FREE
    target_user.subscription_updated_at = datetime.utcnow()
    target_user.subscription_granted_by = admin.id
    
    db.commit()
    db.refresh(target_user)
    
    return SubscriptionManagementResponse(
        success=True,
        message=f"User subscription revoked from {old_status.value} to FREE",
        user_id=user_id,
        old_status=old_status,
        new_status=SubscriptionStatusEnum.FREE,
        updated_at=target_user.subscription_updated_at,
        updated_by=admin.id
    )