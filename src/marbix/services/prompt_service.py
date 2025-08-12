from sqlalchemy.orm import Session
from marbix.crud.prompt import (
    create_prompt, get_prompt_by_id, get_prompt_by_name,
    get_prompts, update_prompt, delete_prompt, increment_prompt_usage,
    get_prompts_by_category, get_active_prompts
)
from marbix.schemas.prompt import PromptCreate, PromptUpdate, PromptResponse, PromptListItem
from typing import List, Optional
from fastapi import HTTPException

class PromptService:
    """Service class for prompt management operations."""
    
    @staticmethod
    async def create_prompt(
        db: Session, 
        prompt_data: PromptCreate, 
        created_by: Optional[str] = None
    ) -> PromptResponse:
        """
        Create a new prompt.
        
        :param db: Database session
        :param prompt_data: Prompt creation data
        :param created_by: ID of the user creating the prompt
        :return: Created prompt response
        :raises: HTTPException if prompt with same name already exists
        """
        # Check if prompt with same name already exists
        existing_prompt = get_prompt_by_name(db, prompt_data.name)
        if existing_prompt:
            raise HTTPException(
                status_code=400, 
                detail=f"Prompt with name '{prompt_data.name}' already exists"
            )
        
        db_prompt = create_prompt(db, prompt_data, created_by)
        return PromptResponse.model_validate(db_prompt)
    
    @staticmethod
    async def get_prompt(
        db: Session, 
        prompt_id: str, 
        increment_usage: bool = False
    ) -> PromptResponse:
        """
        Get a prompt by ID.
        
        :param db: Database session
        :param prompt_id: Prompt ID
        :param increment_usage: Whether to increment usage count
        :return: Prompt response
        :raises: HTTPException if prompt not found
        """
        db_prompt = get_prompt_by_id(db, prompt_id)
        if not db_prompt:
            raise HTTPException(status_code=404, detail="Prompt not found")
        
        if increment_usage:
            increment_prompt_usage(db, prompt_id)
        
        return PromptResponse.model_validate(db_prompt)
    
    @staticmethod
    async def get_prompts(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None
    ) -> List[PromptListItem]:
        """
        Get list of prompts with filtering and pagination.
        
        :param db: Database session
        :param skip: Number of records to skip
        :param limit: Maximum number of records to return
        :param category: Filter by category
        :param is_active: Filter by active status
        :param search: Search in name, description, and content
        :return: List of prompt list items
        """
        db_prompts = get_prompts(
            db, skip=skip, limit=limit, 
            category=category, is_active=is_active, search=search
        )
        return [PromptListItem.model_validate(prompt) for prompt in db_prompts]
    
    @staticmethod
    async def update_prompt(
        db: Session, 
        prompt_id: str, 
        prompt_data: PromptUpdate
    ) -> PromptResponse:
        """
        Update an existing prompt.
        
        :param db: Database session
        :param prompt_id: Prompt ID
        :param prompt_data: Updated prompt data
        :return: Updated prompt response
        :raises: HTTPException if prompt not found
        """
        # Check if prompt exists
        existing_prompt = get_prompt_by_id(db, prompt_id)
        if not existing_prompt:
            raise HTTPException(status_code=404, detail="Prompt not found")
        
        # If name is being updated, check for conflicts
        if prompt_data.name and prompt_data.name != existing_prompt.name:
            name_conflict = get_prompt_by_name(db, prompt_data.name)
            if name_conflict:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Prompt with name '{prompt_data.name}' already exists"
                )
        
        updated_prompt = update_prompt(db, prompt_id, prompt_data)
        if not updated_prompt:
            raise HTTPException(status_code=404, detail="Prompt not found")
        
        return PromptResponse.model_validate(updated_prompt)
    
    @staticmethod
    async def delete_prompt(db: Session, prompt_id: str) -> bool:
        """
        Delete a prompt.
        
        :param db: Database session
        :param prompt_id: Prompt ID
        :return: True if deleted successfully
        :raises: HTTPException if prompt not found
        """
        # Check if prompt exists
        existing_prompt = get_prompt_by_id(db, prompt_id)
        if not existing_prompt:
            raise HTTPException(status_code=404, detail="Prompt not found")
        
        success = delete_prompt(db, prompt_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete prompt")
        
        return True
    
    @staticmethod
    async def get_prompts_by_category(db: Session, category: str) -> List[PromptListItem]:
        """
        Get all prompts in a specific category.
        
        :param db: Database session
        :param category: Category name
        :return: List of prompt list items
        """
        db_prompts = get_prompts_by_category(db, category)
        return [PromptListItem.model_validate(prompt) for prompt in db_prompts]
    
    @staticmethod
    async def get_active_prompts(db: Session) -> List[PromptListItem]:
        """
        Get all active prompts.
        
        :param db: Database session
        :return: List of active prompt list items
        """
        db_prompts = get_active_prompts(db)
        return [PromptListItem.model_validate(prompt) for prompt in db_prompts]
    
    @staticmethod
    async def increment_usage(db: Session, prompt_id: str) -> PromptResponse:
        """
        Increment usage count for a prompt.
        
        :param db: Database session
        :param prompt_id: Prompt ID
        :return: Updated prompt response
        :raises: HTTPException if prompt not found
        """
        updated_prompt = increment_prompt_usage(db, prompt_id)
        if not updated_prompt:
            raise HTTPException(status_code=404, detail="Prompt not found")
        
        return PromptResponse.model_validate(updated_prompt)
