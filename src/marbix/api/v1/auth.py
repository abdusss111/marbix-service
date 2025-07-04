from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from marbix.schemas.login import LoginRequest, LoginResponse
from marbix.schemas.user import UserOut
from marbix.core.deps import get_db
from marbix.services.google_auth_service import authenticate_with_google_token
from marbix.core.config import settings

router = APIRouter()

@router.post("/login", response_model=LoginResponse)
async def login(
    req: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    1. Exchange Google code for token, validate and fetch user info
    2. Find or create user in DB
    3. Generate and return our JWT with expiry and user info
    """
    try:
        user, jwt_token = await authenticate_with_google_token(req.code, db)
    except HTTPException as e:
        raise e
    # Calculate expiry in seconds
    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    return LoginResponse(
        access_token=jwt_token,
        token_type="bearer",
        expires_in=expires_in,
        user=UserOut.from_orm(user)
    )
    
