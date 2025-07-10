from typing import Generator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt
from marbix.db.session import SessionLocal
from marbix.core.config import settings
from marbix.crud.user import get_user_by_id
from marbix.schemas.user import UserOut
from marbix.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
oauth2_scheme_admin = OAuth2PasswordBearer(tokenUrl="/admin/login")
JWT_SECRET = os.getenv("AUTH_SECRET")


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
    except jwt.PyJWTError:
        raise credentials_error

    user = get_user_by_id(db, user_id)
    if user is None:
        raise credentials_error

    return user


async def get_current_admin(token: str = Depends(oauth2_scheme_admin), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub")
        role = payload.get("role")

        if not user_id or role != UserRole.ADMIN.value:
            raise HTTPException(status_code=403, detail="Not authorized")

        admin = db.query(User).filter(User.id == user_id, User.role == UserRole.ADMIN).first()
        if not admin:
            raise HTTPException(status_code=404, detail="Admin not found")

        return admin

    except jwt.PyJWTError::
        raise HTTPException(status_code=403, detail="Invalid token")