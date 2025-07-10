from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from marbix.schemas.login import AdminLoginRequest, AdminLoginResponse
from marbix.core.deps import get_db, get_current_admin
from marbix.services import admin_service
from marbix.models.user import User
from marbix.schemas.strategy import StrategyListItem
from marbix.schemas.user import UserOut
from typing import List
from marbix.models.make_request import MakeRequest

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


@router.get("/users/{user_id}/strategies", response_model=List[StrategyListItem])
def get_user_strategies(user_id: str, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    strategies = db.query(MakeRequest).filter(
        MakeRequest.user_id == user_id,
        MakeRequest.status == "completed"
    ).order_by(MakeRequest.created_at.desc()).all()

    return [
        StrategyListItem(
            request_id=s.request_id,
            business_type=(s.request_data or {}).get("business_type", ""),
            business_goal=(s.request_data or {}).get("business_goal", ""),
            location=(s.request_data or {}).get("location", ""),
            marketing_budget=(s.request_data or {}).get("marketing_budget"),
            status=s.status,
            created_at=s.created_at,
            completed_at=s.completed_at,
            result=s.result or ""
        )
        for s in strategies
    ]
