from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from marbix.schemas.login import AdminLoginRequest, AdminLoginResponse
from marbix.core.deps import get_db, get_current_admin
from marbix.services import admin_service
from marbix.models.user import User
from marbix.schemas.strategy import StrategyItem
from marbix.schemas.user import UserOut
from typing import List
from marbix.models.make_request import MakeRequest
from marbix.schemas.admin import AdminStatsResponse
router = APIRouter()


@router.post("/login", response_model=AdminLoginResponse)
def login_admin(data: AdminLoginRequest, db: Session = Depends(get_db)):
    token = admin_service.authenticate_admin(data.email, data.password, db)
    return {"access_token": token}


@router.get("/users", response_model=List[UserOut])
def get_all_users(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return admin_service.get_all_users(db)


@router.get("/users/{user_id}", response_model=UserOut)
def get_user_by_id(user_id: str, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return admin_service.get_user_by_id(user_id, db)


@router.get("/users/{user_id}/strategies", response_model=List[StrategyItem])
def get_user_strategies(user_id: str, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    strategies = db.query(MakeRequest).filter(MakeRequest.user_id == user_id).order_by(MakeRequest.created_at.desc()).all()
    return [
        StrategyListItem(
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
            result=s.result or ""
        )
        for s in strategies
    ]


@router.get("/statistics", response_model=AdminStatsResponse)
def get_admin_statistics(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """
    Returns admin dashboard statistics including user count, strategy counts by status.
    """
    return admin_service.get_admin_statistics(db)