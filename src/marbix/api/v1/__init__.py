from fastapi import APIRouter

# import individual routers
from .auth import router as auth_router
from .make import router as make_router
from .admin import router as admin_router
from .strategies import router as strategy_router
from .prompts import router as prompts_router
# create a unified router for /api/v1
api_router = APIRouter()

# mount sub‑routers under their own prefixes
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(make_router, prefix="/api", tags=["make"])
api_router.include_router(strategy_router, prefix="/api", tags=["strategies"])
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
api_router.include_router(prompts_router, prefix="/admin/prompts", tags=["prompts"])