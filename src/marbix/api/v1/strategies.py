from fastapi import APIRouter, HTTPException, Depends, Body
from sqlalchemy.orm import Session
from marbix.core.deps import get_current_user, get_db
from marbix.models.user import User, SubscriptionStatus
from marbix.schemas.strategy import StrategyListItem, StrategyItem
from marbix.schemas.enhanced_strategy import (
    EnhancementRequest, 
    EnhancementResponse, 
    EnhancedStrategyResponse
)
from marbix.models.make_request import MakeRequest
from marbix.services.enhancement_service import enhancement_service
from marbix.core.config import settings
from arq import create_pool
from typing import List, Optional
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/strategies", response_model=List[StrategyListItem])
async def get_user_strategies(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 20
):
    """Get list of user's completed strategies"""
    try:
        # Получаем только завершенные стратегии пользователя
        strategies = db.query(MakeRequest).filter(
            MakeRequest.user_id == current_user.id,
            MakeRequest.status == "completed"
        ).order_by(
            MakeRequest.created_at.desc()
        ).offset(skip).limit(limit).all()
        
        # Формируем ответ с нужными полями
        result = []
        for strategy in strategies:
            # Извлекаем данные из request_data JSON
            request_data = strategy.request_data or {}
            
            item = StrategyListItem(
                request_id=strategy.request_id,
                business_type=request_data.get("business_type", ""),
                business_goal=request_data.get("business_goal", ""),
                location=request_data.get("location", ""),
                promotion_budget=request_data.get("promotion_budget"),
                team_budget=request_data.get("team_budget"),
                status=strategy.status,
                created_at=strategy.created_at,
                completed_at=strategy.completed_at
            )
            result.append(item)
        
        return result
        
    except Exception as e:
        print(f"Error getting user strategies: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve strategies")

@router.get("/strategies/{strategy_id}", response_model=StrategyItem)
async def get_strategy_by_id(
    strategy_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a single completed strategy by its ID (includes the `result`)."""
    strategy = (
        db.query(MakeRequest)
          .filter(
              MakeRequest.request_id == strategy_id,
              MakeRequest.user_id == current_user.id,
              MakeRequest.status == "completed"
          )
          .first()
    )
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    data = strategy.request_data or {}
    
    # Sources are already stored as JSON array in database
    sources_array = strategy.sources or []
    
    return StrategyItem(
        request_id=strategy.request_id,
        business_type=data.get("business_type", ""),
        business_goal=data.get("business_goal", ""),
        location=data.get("location", ""),
        promotion_budget=data.get("promotion_budget"),
        team_budget=data.get("team_budget"),
        status=strategy.status,
        created_at=strategy.created_at,
        completed_at=strategy.completed_at,
        result=strategy.result or "",
        sources=sources_array
    )

@router.post("/strategies/{strategy_id}/enhance", response_model=EnhancementResponse)
async def enhance_strategy(
    strategy_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Optional[EnhancementRequest] = Body(default=None)
):
    """
    Enhance a strategy with 9 detailed sections using AI generation.
    
    Flow:
    1. Validate original strategy exists and is completed
    2. Create enhancement record
    3. Queue enhancement worker job 
    4. Return enhancement ID for tracking
    """
    try:
        logger.info(f"Enhancement request for strategy {strategy_id} by user {current_user.id}")
        
        # 1. PRO PLAN VALIDATION - Only pro users can enhance strategies
        if current_user.subscription_status != SubscriptionStatus.PRO:
            logger.warning(
                f"User {current_user.id} ({current_user.subscription_status.value}) "
                f"attempted to enhance strategy. Pro plan required."
            )
            raise HTTPException(
                status_code=403, 
                detail="Strategy enhancement requires a Pro subscription. Upgrade your plan to access this feature."
            )
        
        # 2. Validate original strategy (using request_id field)
        original_strategy = db.query(MakeRequest).filter(
            MakeRequest.request_id == strategy_id,
            MakeRequest.user_id == current_user.id
        ).first()
        
        if not original_strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")
        
        if original_strategy.status != "completed":
            raise HTTPException(
                status_code=400, 
                detail=f"Strategy must be completed before enhancement (current status: {original_strategy.status})"
            )
        
        if not original_strategy.result:
            raise HTTPException(status_code=400, detail="Strategy has no content to enhance")
        
        # 2. Create enhancement record (using request_id for foreign key)
        enhancement = enhancement_service.create_enhancement_record(
            original_strategy_id=original_strategy.request_id,  # Use request_id
            user_id=current_user.id,
            db=db
        )
        
        # 3. Queue enhancement worker job
        try:
            from arq.connections import RedisSettings
            redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
            redis_pool = await create_pool(redis_settings)
            await redis_pool.enqueue_job(
                "enhance_strategy_workflow",
                enhancement_id=enhancement.id,
                strategy_id=original_strategy.request_id,  # Use request_id
                user_id=current_user.id
            )
            await redis_pool.close()
            logger.info(f"Enhancement job queued for {enhancement.id}")
            
        except Exception as queue_error:
            logger.error(f"Failed to queue enhancement job: {queue_error}")
            # Update enhancement status to error
            from marbix.models.enhanced_strategy import EnhancementStatus
            enhancement_service.update_enhancement_status(
                enhancement.id, 
                EnhancementStatus.ERROR, 
                db, 
                error=f"Failed to queue job: {str(queue_error)}"
            )
            raise HTTPException(status_code=500, detail="Failed to start enhancement process")
        
        # 4. Return enhancement response
        return EnhancementResponse(
            enhancement_id=enhancement.id,
            original_strategy_id=strategy_id,  # Return external request_id
            status=enhancement.status,
            message="Strategy enhancement started. This will take a few minutes to complete.",
            created_at=enhancement.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Enhancement request failed for strategy {strategy_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/strategies/{strategy_id}/enhanced", response_model=EnhancedStrategyResponse)
async def get_latest_enhanced_strategy(
    strategy_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the latest enhanced strategy for a given strategy ID"""
    # Get the latest enhancement for this strategy
    enhancement = enhancement_service.get_latest_enhancement_by_strategy_id(strategy_id, current_user.id, db)
    
    if not enhancement:
        raise HTTPException(status_code=404, detail="No enhancement found for this strategy")
    
    return EnhancedStrategyResponse.from_orm(enhancement)


@router.get("/strategy-limits")
async def get_strategy_limits(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's current strategy count and plan limits"""
    try:
        # Count completed strategies
        completed_count = db.query(MakeRequest).filter(
            MakeRequest.user_id == current_user.id,
            MakeRequest.status == "completed"
        ).count()
        
        # Get user's plan and limits
        user_plan = current_user.subscription_status
        max_strategies = 10 if user_plan == SubscriptionStatus.PRO else 1
        
        return {
            "user_id": current_user.id,
            "subscription_plan": user_plan.value,
            "current_strategies": completed_count,
            "max_strategies": max_strategies,
            "remaining_strategies": max(0, max_strategies - completed_count),
            "can_create_more": completed_count < max_strategies,
            "can_enhance": user_plan == SubscriptionStatus.PRO
        }
        
    except Exception as e:
        logger.error(f"Error getting strategy limits for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve strategy limits")


@router.get("/strategies/{strategy_id}/enhancement/{enhancement_id}", response_model=EnhancedStrategyResponse)
async def get_enhanced_strategy(
    strategy_id: str,
    enhancement_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get enhanced strategy by enhancement ID"""
    enhancement = enhancement_service.get_enhancement_by_id(enhancement_id, db)
    
    if not enhancement:
        raise HTTPException(status_code=404, detail="Enhancement not found")
    
    if enhancement.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Validate strategy_id matches (compare with original strategy's request_id)
    original_strategy = enhancement_service.get_strategy_by_id(enhancement.original_strategy_id, db)
    if not original_strategy or original_strategy.request_id != strategy_id:
        raise HTTPException(status_code=400, detail="Enhancement does not belong to this strategy")
    
    return EnhancedStrategyResponse.from_orm(enhancement)