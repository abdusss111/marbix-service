from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from marbix.core.deps import get_current_user, get_db
from marbix.models.user import User
from marbix.schemas.prompt import (
    PromptCreate, PromptUpdate, PromptResponse, PromptListItem, PromptUsage
)
from marbix.services.prompt_service import PromptService
from typing import List, Optional

router = APIRouter()

@router.post("/", response_model=PromptResponse)
async def create_prompt(
    prompt_data: PromptCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new prompt.
    """
    return await PromptService.create_prompt(
        db, prompt_data, created_by=current_user.id
    )

@router.get("/", response_model=List[PromptListItem])
async def get_prompts(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    category: Optional[str] = Query(None, description="Filter by category"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search in name, description, and content"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of prompts with optional filtering and pagination.
    """
    return await PromptService.get_prompts(
        db, skip=skip, limit=limit, 
        category=category, is_active=is_active, search=search
    )

@router.get("/{prompt_id}", response_model=PromptResponse)
async def get_prompt(
    prompt_id: str,
    increment_usage: bool = Query(False, description="Whether to increment usage count"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a prompt by ID.
    """
    return await PromptService.get_prompt(
        db, prompt_id, increment_usage=increment_usage
    )

@router.put("/{prompt_id}", response_model=PromptResponse)
async def update_prompt(
    prompt_id: str,
    prompt_data: PromptUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update an existing prompt.
    """
    return await PromptService.update_prompt(db, prompt_id, prompt_data)

@router.delete("/{prompt_id}")
async def delete_prompt(
    prompt_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a prompt.
    """
    await PromptService.delete_prompt(db, prompt_id)
    return {"message": "Prompt deleted successfully"}

@router.get("/category/{category}", response_model=List[PromptListItem])
async def get_prompts_by_category(
    category: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all prompts in a specific category.
    """
    return await PromptService.get_prompts_by_category(db, category)

@router.get("/active", response_model=List[PromptListItem])
async def get_active_prompts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all active prompts.
    """
    return await PromptService.get_active_prompts(db)

@router.post("/{prompt_id}/usage", response_model=PromptResponse)
async def increment_prompt_usage(
    prompt_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Increment usage count for a prompt.
    """
    return await PromptService.increment_usage(db, prompt_id)

@router.get("/search", response_model=List[PromptListItem])
async def search_prompts(
    q: str = Query(..., description="Search query"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search prompts by query string.
    """
    return await PromptService.get_prompts(
        db, skip=skip, limit=limit, search=q
    )
