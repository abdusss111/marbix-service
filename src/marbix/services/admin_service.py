import os
import jwt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from passlib.context import CryptContext
from marbix.models.user import User
from marbix.models.make_request import MakeRequest
from marbix.models.role import UserRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
JWT_SECRET = os.getenv("AUTH_SECRET", "secret-key")


def authenticate_admin(email: str, password: str, db: Session) -> str:
    """
    Authenticates admin by email and password. Returns JWT if valid.
    """
    admin = db.query(User).filter(User.email == email, User.role == UserRole.ADMIN).first()
    
    print(pwd_context.verify(password, admin.password))
    print(password, admin.password)

    if not admin or not admin.password or not pwd_context.verify(password, admin.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    return generate_admin_jwt(admin)


def generate_admin_jwt(admin: User) -> str:
    """
    Generates JWT token for admin with role in payload.
    """
    payload = {
        "sub": admin.id,
        "email": admin.email,
        "role": admin.role.value
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def get_all_users(db: Session):
    """
    Returns list of users (excluding admins).
    """
    return db.query(User).order_by(desc(User.created_at)).all()


def get_user_by_id(user_id: str, db: Session):
    """
    Returns user by ID. Raises 404 if not found.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def get_user_strategies(user_id: str, db: Session):
    """
    Returns all strategies (make_requests) for the given user ID.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return db.query(MakeRequest).filter(MakeRequest.user_id == user_id).all()
