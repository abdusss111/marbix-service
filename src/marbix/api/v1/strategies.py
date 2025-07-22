from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from marbix.core.deps import get_current_user, get_db
from marbix.models.user import User
from marbix.schemas.strategy import StrategyListItem
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