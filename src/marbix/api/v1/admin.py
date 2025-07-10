from fastapi import FastAPI, APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from marbix.schemas.login AdminLoginRequest, AdminLoginResponse
from marbix.schemas.user import UserOut
from marbix.core.deps import get_db
from marbix.core.config import settings

router = APIRouter()

@router.post("/login")
async def authenticate_admin():

@router.get("/users")
async def get_all_users():

@router.get("/users/")