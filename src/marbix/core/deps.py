from typing import Generator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt
from jwt import PyJWTError
from marbix.db.session import SessionLocal
from marbix.core.config import settings
from marbix.crud.user import get_user_by_id
from marbix.schemas.user import UserOut
from marbix.models.user import User, SubscriptionStatus
from marbix.models.role import UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
oauth2_scheme_admin = OAuth2PasswordBearer(tokenUrl="/admin/login")


def get_db() -> Generator[Session, None, None]:
    """
    Provide a transactional database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> UserOut:
    """
    Decode JWT token and fetch the current user from the database.
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}
    )

    try:
        payload = jwt.decode(
            token,
            settings.AUTH_SECRET,
            algorithms=["HS256"]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_error
    except PyJWTError:
        raise credentials_error

    user = get_user_by_id(db, user_id)
    if user is None:
        raise credentials_error

    return user


async def get_current_admin(token: str = Depends(oauth2_scheme_admin), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, settings.AUTH_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub")
        role = payload.get("role")

        if not user_id or role != UserRole.ADMIN.value:
            raise HTTPException(status_code=403, detail="Not authorized")

        admin = db.query(User).filter(User.id == user_id, User.role == UserRole.ADMIN).first()
        if not admin:
            raise HTTPException(status_code=404, detail="Admin not found")

        return admin

    except PyJWTError:
        raise HTTPException(status_code=403, detail="Invalid token")


async def get_current_pro_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to ensure the current user has PRO subscription.
    Use this for endpoints that require PRO access.
    """
    if current_user.subscription_status != SubscriptionStatus.PRO:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PRO subscription required to access this feature"
        )
    return current_user


def require_subscription(required_status: SubscriptionStatus):
    """
    Factory function to create subscription requirement dependencies.
    
    Usage:
    @router.get("/pro-feature")
    def pro_feature(user: User = Depends(require_subscription(SubscriptionStatus.PRO))):
        pass
    """
    async def subscription_dependency(
        current_user: User = Depends(get_current_user)
    ) -> User:
        if current_user.subscription_status != required_status:
            status_name = required_status.value.upper()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{status_name} subscription required to access this feature"
            )
        return current_user
    
    return subscription_dependency


async def get_user_subscription_info(
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Dependency to get detailed subscription information for the current user.
    Returns a dictionary with subscription details.
    """
    return {
        "user_id": current_user.id,
        "subscription_status": current_user.subscription_status.value,
        "is_pro": current_user.subscription_status == SubscriptionStatus.PRO,
        "is_free": current_user.subscription_status == SubscriptionStatus.FREE,
        "is_pending": current_user.subscription_status == SubscriptionStatus.PENDING_PRO,
        "subscription_updated_at": current_user.subscription_updated_at,
        "subscription_granted_by": current_user.subscription_granted_by
    }