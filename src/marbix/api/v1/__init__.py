from fastapi import APIRouter

# import individual routers
from .auth import router as auth_router
from .make import router as make_router
# create a unified router for /api/v1
api_router = APIRouter()

# mount sub‑routers under their own prefixes
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(make_router, prefix="/api", tags=["strategy"])
