from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from marbix.core.deps import get_db, get_current_user
from marbix.models.user import User, SubscriptionStatus
from marbix.schemas.user import SubscriptionStatusResponse, SubscriptionStatusEnum

router = APIRouter()


@router.post("/request-pro", response_model=SubscriptionStatusResponse)
def request_pro_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Endpoint for users to request PRO subscription.
    Changes their status to 'pending-pro' for admin review.
    """
    # Check if user is already PRO
    if current_user.subscription_status == SubscriptionStatus.PRO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have PRO subscription"
        )
    
    # Check if user already has a pending request
    if current_user.subscription_status == SubscriptionStatus.PENDING_PRO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have a pending PRO subscription request"
        )
    
    # Update user subscription status to pending
    current_user.subscription_status = SubscriptionStatus.PENDING_PRO
    current_user.subscription_updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(current_user)
    
    return SubscriptionStatusResponse(
        success=True,
        message="PRO subscription request submitted successfully. Please wait for admin approval.",
        subscription_status=SubscriptionStatusEnum.PENDING_PRO
    )


@router.get("/status", response_model=SubscriptionStatusResponse)
def get_subscription_status(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user's subscription status.
    """
    # Convert SubscriptionStatus enum to SubscriptionStatusEnum for response
    status_mapping = {
        SubscriptionStatus.FREE: SubscriptionStatusEnum.FREE,
        SubscriptionStatus.PENDING_PRO: SubscriptionStatusEnum.PENDING_PRO,
        SubscriptionStatus.PRO: SubscriptionStatusEnum.PRO
    }

    print(current_user.subscription_status)
    return SubscriptionStatusResponse(
        success=True,
        message="Subscription status retrieved successfully",
        subscription_status=status_mapping[current_user.subscription_status]
    )
