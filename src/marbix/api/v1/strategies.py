from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from marbix.core.deps import get_current_user, get_db
from marbix.models.user import User
from marbix.schemas.strategy import StrategyListItem, StrategyItem
from marbix.models.make_request import MakeRequest
from typing import List

router = APIRouter()

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
                marketing_budget=request_data.get("marketing_budget"),
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
    return StrategyDetail(
        request_id=strategy.request_id,
        business_type=data.get("business_type", ""),
        business_goal=data.get("business_goal", ""),
        location=data.get("location", ""),
        marketing_budget=data.get("marketing_budget"),
        status=strategy.status,
        created_at=strategy.created_at,
        completed_at=strategy.completed_at,
        result=strategy.result or "",
        sources=strategy.sources or ""
    )