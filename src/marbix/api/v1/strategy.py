from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from marbix.schemas.strategy import StrategyRequest, StrategyResponse
from marbix.services.hook_sender import push_to_webhook
from marbix.core.deps import get_current_user, get_db

router = APIRouter()
 
@router.post("/strategy", response_model=StrategyResponse, status_code=status.HTTP_202_ACCEPTED)
async def strategy_endpoint(
    payload: StrategyRequest,
    db: Session = Depends(get_db),
):
    await push_to_webhook(payload.dict())
    return StrategyResponse(status="accepted")
